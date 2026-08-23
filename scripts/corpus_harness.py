#!/usr/bin/env python3
"""Foreign-corpus harness: run fiducial against pinned third-party KiCad projects.

Purpose: prove fiducial behaves sanely on designs it was never written against.
This harness tests ROBUSTNESS, not correctness of the foreign boards:

  - ERC/DRC findings on foreign boards are EXPECTED and are not failures.
  - Crashes, tracebacks, hangs (timeout), or netlist-export failures ARE
    failures -- they mean fiducial cannot handle a real-world design.

Manifest format (corpus/MANIFEST.csv): name,git_url,pin,subdir
  pin   = a commit SHA; HEAD is resolved to this at clone time.
  subdir= only schematics under this path are scanned (optional).

Usage:
  python scripts/corpus_harness.py                 # full run, writes report
  python scripts/corpus_harness.py --only ZSWatch  # one entry
  python scripts/corpus_harness.py --dry-run       # list what would run

Exit codes follow the fiducial contract:
  0 all corpus entries processed without tool crashes
  1 at least one crash/timeout/tool-error (see report)
  2 environment error (bad manifest, git missing)
"""

import argparse
import csv
import datetime
import os
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIDUCIAL = os.path.join(REPO_ROOT, "scripts", "fiducial.py")
MANIFEST = os.path.join(REPO_ROOT, "corpus", "MANIFEST.csv")

# Commands run per schematic. lint is pure-python and cheap; erc/netlist
# exercise kicad-cli. bom/render omitted: slower, low extra signal.
COMMANDS = ["lint", "erc", "netlist"]
TIMEOUT_SECONDS = 180


def sh(args, cwd=None, timeout=None):
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def load_manifest(path):
    entries = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = (row.get("name") or "").strip()
            url = (row.get("git_url") or "").strip()
            pin = (row.get("pin") or "").strip()
            if not (name and url and pin):
                raise ValueError("manifest rows need name, git_url, pin: %r" % row)
            entries.append(
                {
                    "name": name,
                    "url": url,
                    "pin": pin,
                    "subdir": (row.get("subdir") or "").strip().strip("/"),
                }
            )
    if not entries:
        raise ValueError("manifest is empty")
    return entries


def clone(url, pin, dest):
    r = sh(["git", "clone", "--quiet", "--filter=blob:none", url, dest], timeout=600)
    if r.returncode != 0:
        return False, "clone failed: %s" % r.stderr.strip()[-300:]
    r = sh(["git", "-C", dest, "checkout", "--quiet", pin], timeout=120)
    if r.returncode != 0:
        return False, "checkout %s failed: %s" % (pin, r.stderr.strip()[-300:])
    return True, ""


def find_schematics(root, subdir):
    base = os.path.join(root, subdir) if subdir else root
    found = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in (".git",)]
        for fn in filenames:
            if fn.endswith(".kicad_sch"):
                found.append(os.path.join(dirpath, fn))
    return sorted(found)


def run_tool(cmd_args, timeout=TIMEOUT_SECONDS):
    """Run one fiducial command. Returns (crashed, detail)."""
    try:
        r = sh([sys.executable, FIDUCIAL] + cmd_args, timeout=timeout)
    except subprocess.TimeoutExpired:
        return True, "TIMEOUT after %ss" % timeout
    out = (r.stdout or "") + (r.stderr or "")
    crashed = False
    detail = ""
    # Findings are fine; crashes and hard errors are not. ERC exit code 1
    # means findings, which is acceptable on foreign hardware.
    if "Traceback" in out:
        crashed = True
        detail = "traceback"
    elif cmd_args[0] != "erc" and r.returncode == 2:
        crashed = True
        detail = "exit 2 (environment/config): %s" % out.strip()[-200:]
    elif r.returncode not in (0, 1):
        crashed = True
        detail = "exit %d: %s" % (r.returncode, out.strip()[-200:])
    return crashed, detail


def effective_commands():
    """Drop kicad-cli-dependent commands when kicad-cli is unavailable,
    so the harness stays usable on machines without KiCad installed."""
    if shutil.which("kicad-cli"):
        return list(COMMANDS)
    print("note: kicad-cli not found; running lint-only (robustness coverage reduced)")
    return ["lint"]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", help="process a single manifest entry by name")
    ap.add_argument("--dry-run", action="store_true", help="list, do not execute")
    args = ap.parse_args()

    try:
        entries = load_manifest(MANIFEST)
    except (OSError, ValueError) as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    if args.only:
        entries = [e for e in entries if e["name"] == args.only]
        if not entries:
            print("error: no manifest entry named %r" % args.only, file=sys.stderr)
            return 2

    work = tempfile.mkdtemp(prefix="fiducial-corpus-")
    cmds = effective_commands()
    results = []
    status = 0
    try:
        for entry in entries:
            name = entry["name"]
            dest = os.path.join(work, name)
            print("== %s (%s @ %s)" % (name, entry["url"], entry["pin"][:12]))
            ok, err = clone(entry["url"], entry["pin"], dest)
            if not ok:
                print("   CLONE FAIL: %s" % err)
                results.append((name, "-", "clone-fail", err))
                status = 1
                continue
            schs = find_schematics(dest, entry["subdir"])
            print("   %d schematic(s)" % len(schs))
            if not schs:
                results.append((name, "-", "no-schematics", "nothing discovered"))
                status = 1
                continue
            for sch in schs:
                rel = os.path.relpath(sch, dest)
                entry_crash = False
                details = []
                for cmd in cmds:
                    crashed, detail = run_tool([cmd, sch])
                    if crashed:
                        entry_crash = True
                        details.append("%s: %s" % (cmd, detail))
                verdict = "CRASH" if entry_crash else "ok"
                detail = "; ".join(details)
                print("   %-6s %s %s" % (verdict, rel, ("-- " + detail) if detail else ""))
                results.append((name, rel, verdict, detail))
                if entry_crash:
                    status = 1
    finally:
        write_report(results)
        if os.environ.get("CORPUS_KEEP"):
            print("kept clones in %s" % work)
        else:
            shutil.rmtree(work, ignore_errors=True)
    return status


def write_report(results):
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    lines = [
        "# Foreign corpus report",
        "",
        "Generated %s. Verdicts measure fiducial robustness only:" % now,
        "foreign-board findings are expected; crashes/timeouts are bugs.",
        "",
        "| project | schematic | verdict | detail |",
        "|---|---|---|---|",
    ]
    crashes = 0
    for name, rel, verdict, detail in results:
        if verdict in ("CRASH", "clone-fail", "no-schematics"):
            crashes += 1
        lines.append("| %s | `%s` | %s | %s |" % (name, rel, verdict, detail.replace("|", "\\|")))
    total = len(results)
    lines.insert(4, "")
    lines.insert(4, "**%d/%d clean**" % (total - crashes, total))
    out = os.path.join(REPO_ROOT, "corpus", "CORPUS_REPORT.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\nreport: %s" % out)


if __name__ == "__main__":
    sys.exit(main())
