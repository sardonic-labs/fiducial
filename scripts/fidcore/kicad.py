"""kicad-cli wrapper, JSON report handling, and ERC/DRC commands."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from fidcore.const import EXIT_ENV, EXIT_OK, EXIT_VIOLATIONS


def kicad_cli(args, timeout=180):
    exe = shutil.which("kicad-cli")
    if not exe:
        print("ERROR: kicad-cli not found on PATH. Run `doctor`.", file=sys.stderr)
        sys.exit(EXIT_ENV)
    proc = subprocess.run([exe] + args, capture_output=True, text=True,
                          timeout=timeout, encoding="utf-8", errors="replace")
    return proc


def _summarize_report(kind, target, extra=()):
    """Run kicad-cli <kind>, parse its JSON report from a unique temp file.

    Returns (summary, exit_code). summary is None on environment error.
    A unique tempfile guarantees a failure to produce a report can never
    fall back to parsing a stale report from a previous run.
    """
    fd, tmpname = tempfile.mkstemp(prefix=f"fiducial-{kind}-", suffix=".json")
    os.close(fd)
    report = Path(tmpname)
    report.unlink()
    prefix = ["sch"] if kind == "erc" else ["pcb"]
    try:
        proc = kicad_cli(prefix + [kind, str(target), "--format", "json",
                                   "--output", str(report), *extra])
        if not report.exists():
            print(proc.stdout)
            print(proc.stderr, file=sys.stderr)
            print(f"ERROR: no {kind.upper()} report produced", file=sys.stderr)
            return None, EXIT_ENV
        data = json.loads(report.read_text(encoding="utf-8"))
    finally:
        report.unlink(missing_ok=True)
    errors, warnings, other = [], [], {}
    for v in data.get(kind, []):
        sev = v.get("severity", "unknown").replace("severity_", "")
        if sev == "error":
            errors.append(v)
        elif sev == "warning":
            warnings.append(v)
        else:
            other.setdefault(sev, []).append(v)
    summary = {
        "tool": kind.upper(),
        "target": str(target),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "other_counts": {sev: len(items) for sev, items in sorted(other.items())},
    }
    return summary, (EXIT_VIOLATIONS if errors else EXIT_OK)


def _print_report_human(summary):
    print(f"{summary['tool']} on {summary['target']}: "
          f"{summary['error_count']} errors, {summary['warning_count']} warnings")
    for sev_name, key in (("ERROR", "errors"), ("WARNING", "warnings")):
        for v in summary[key]:
            where = ""
            for item in v.get("items", []):
                desc = item.get("description", "")
                if desc:
                    where = f" [{desc}]"
                    break
            print(f"  {sev_name}: {v.get('type', '?')} @ {v.get('pos', '?')}{where}")
            print(f"    {v.get('description', '')}")
    for sev, n in sorted(summary["other_counts"].items()):
        print(f"  {sev}: {n}")


def cmd_doctor(_args):
    ok = True
    exe = shutil.which("kicad-cli")
    if not exe:
        print("FAIL: kicad-cli not found on PATH")
        print("  Install KiCad 8+ or add e.g. C:\\Program Files\\KiCad\\9.0\\bin to PATH")
        return EXIT_ENV
    print(f"OK: {exe}")
    proc = subprocess.run([exe, "version"], capture_output=True, text=True)
    ver = (proc.stdout or proc.stderr).strip()
    print(f"OK: version {ver}")
    major = ver.split(".")[0].lstrip("v")
    if not major.isdigit() or int(major) < 7:
        print(f"WARN: KiCad {ver} is old; JSON reports need 7+")
        ok = False
    py = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(f"OK: python {py} ({sys.executable})")
    return EXIT_OK if ok else EXIT_ENV


def cmd_erc(args):
    summary, rc = _summarize_report("erc", args.project)
    if summary is None:
        return rc
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        _print_report_human(summary)
    return rc


def cmd_drc(args):
    extra = ["--schematic-parity"] if args.parity else []
    # Zone refill rewrites the board file, so it only happens on explicit
    # --save-board. A verification command must not mutate its input.
    if args.save_board:
        extra += ["--refill-zones", "--save-board"]
    summary, rc = _summarize_report("drc", args.board, extra)
    if summary is None:
        return rc
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        _print_report_human(summary)
    return rc
