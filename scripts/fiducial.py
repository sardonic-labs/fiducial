#!/usr/bin/env python3
"""fiducial.py - stdlib-only helpers for AI-driven KiCad hardware design."""

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EXIT_OK = 0
EXIT_VIOLATIONS = 1
EXIT_ENV = 2


# ---------------------------------------------------------------- s-expressions

def parse_sexp(text):
    tokens = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
        elif c == "(":
            tokens.append("(")
            i += 1
        elif c == ")":
            tokens.append(")")
            i += 1
        elif c == '"':
            j = i + 1
            buf = []
            while j < n:
                if text[j] == "\\" and j + 1 < n:
                    buf.append(text[j + 1])
                    j += 2
                elif text[j] == '"':
                    break
                else:
                    buf.append(text[j])
                    j += 1
            tokens.append(("str", "".join(buf)))
            i = j + 1
        else:
            j = i
            while j < n and text[j] not in ' \t\r\n()"':
                j += 1
            tokens.append(text[i:j])
            i = j
    pos = 0

    def walk():
        nonlocal pos
        assert tokens[pos] == "(", f"expected ( at token {pos}"
        pos += 1
        items = []
        while tokens[pos] != ")":
            t = tokens[pos]
            if isinstance(t, tuple):
                items.append(t[1])
                pos += 1
            elif t == "(":
                items.append(walk())
            else:
                items.append(t)
                pos += 1
        pos += 1
        return items

    try:
        return walk()
    except (IndexError, AssertionError) as e:
        raise ValueError(f"malformed S-expression: {e}")


def load_sexp(path):
    return parse_sexp(Path(path).read_text(encoding="utf-8"))


def sexp_get(node, key):
    """First direct child list whose head == key."""
    for item in node:
        if isinstance(item, list) and item and item[0] == key:
            return item
    return None


def sexp_find_all(node, key):
    out = []
    stack = [node]
    while stack:
        cur = stack.pop()
        for item in cur:
            if isinstance(item, list):
                if item and item[0] == key:
                    out.append(item)
                stack.append(item)
    return out


# ---------------------------------------------------------------- kicad-cli

def kicad_cli(args, timeout=180):
    exe = shutil.which("kicad-cli")
    if not exe:
        print("ERROR: kicad-cli not found on PATH. Run `doctor`.", file=sys.stderr)
        sys.exit(EXIT_ENV)
    proc = subprocess.run([exe] + args, capture_output=True, text=True,
                          timeout=timeout, encoding="utf-8", errors="replace")
    return proc


# ---------------------------------------------------------------- reports

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


# ---------------------------------------------------------------- commands

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


# ---------------------------------------------------------------- netlist

def _netlist_path(project):
    return Path(str(project).rsplit(".", 1)[0] + "-netlist.sexpr")


def _export_netlist(project):
    """Export the netlist for project. Returns (path, exit_code)."""
    out = _netlist_path(project)
    proc = kicad_cli(["sch", "export", "netlist", str(project),
                      "-o", str(out), "--format", "kicadsexpr"])
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        return out, EXIT_ENV
    return out, EXIT_OK


def cmd_netlist(args):
    out, rc = _export_netlist(args.project)
    if rc != EXIT_OK:
        return rc
    print(out)
    return EXIT_OK


def _cache_is_stale(netlist, project):
    """True if the cached netlist is absent or older than the schematic."""
    if not netlist.exists():
        return True
    if not Path(project).exists():
        return False
    return netlist.stat().st_mtime < Path(project).stat().st_mtime


def _load_nets(project, refresh=False):
    """Load (nets, values, footprints, freshly_exported) for a project.

    Reuses the cached netlist only while it is newer than the schematic;
    regenerates automatically when the schematic changed, and always when
    refresh is set (--refresh).
    """
    project = Path(project)
    netlist = _netlist_path(project)
    fresh = False
    if refresh or _cache_is_stale(netlist, project):
        out, rc = _export_netlist(project)
        if rc != EXIT_OK:
            sys.exit(rc)
        fresh = True
    root = load_sexp(netlist)
    nets_node = sexp_get(root, "nets") or sexp_get(root[0], "nets")
    comps_node = sexp_get(root, "components") or sexp_get(root[0], "components")
    values, footprints = {}, {}
    for comp in sexp_find_all(comps_node or [], "comp"):
        ref = _first_str(sexp_get(comp, "ref"))
        val = sexp_get(comp, "value")
        fp = sexp_get(comp, "footprint")
        values[ref] = _first_str(val) if val else ""
        footprints[ref] = _first_str(fp) if fp else ""
    nets = {}
    for net in sexp_find_all(nets_node or [], "net"):
        name = _first_str(sexp_get(net, "name"))
        nodes = {}
        for nd in sexp_find_all(net, "node"):
            ref = _first_str(sexp_get(nd, "ref"))
            pin = _first_str(sexp_get(nd, "pin"))
            nodes[(ref, pin)] = name
        nets[name] = nodes
    return nets, values, footprints, fresh


def _first_str(node):
    """Value of a (key "value" ...) node - skips the key itself."""
    if node is None:
        return ""
    for x in node[1:]:
        if isinstance(x, str):
            return x
    return ""


def cmd_nets(args):
    nets, _, _, fresh = _load_nets(args.project, refresh=args.refresh)
    print(f"# {'(regenerated)' if fresh else '(cached)'} "
          f"{len(nets)} nets; use --refresh to force re-export")
    for name in sorted(nets, key=str.lower):
        pins = ", ".join(f"{r}.{p}" for (r, p) in sorted(nets[name]))
        print(f"{name:<24} {pins}")
    return EXIT_OK


def cmd_pins(args):
    nets, values, footprints, _ = _load_nets(args.project, refresh=args.refresh)
    ref = args.ref
    pin2net = {}
    for name, nodes in nets.items():
        for (r, p), net in nodes.items():
            if r == ref:
                pin2net[p] = net
    if not pin2net:
        print(f"ERROR: no connected pins found for '{ref}'. Check the reference.",
              file=sys.stderr)
        return EXIT_ENV
    print(f"{ref}  value={values.get(ref, '?')}  footprint={footprints.get(ref, '?')}")
    for pin in sorted(pin2net, key=_pin_sort):
        print(f"  pin {pin:<6} -> {pin2net[pin]}")
    return EXIT_OK


def _pin_sort(p):
    digits = "".join(c for c in str(p) if c.isdigit())
    return (int(digits) if digits else 10**9, str(p))


def cmd_check_intent(args):
    nets, _, _, _ = _load_nets(args.project, refresh=args.refresh)
    bad = 0
    with open(args.csv, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    required = {"ref", "pin", "expected_net"}
    if rows and not required.issubset(rows[0]):
        print(f"CSV must have columns {sorted(required)}")
        return EXIT_ENV
    results = []
    for row in rows:
        ref, pin, want = row["ref"].strip(), row["pin"].strip(), row["expected_net"].strip()
        actual = None
        for name, nodes in nets.items():
            if (ref, pin) in nodes:
                actual = name
                break
        if actual is None:
            status = "MISSING"
            bad += 1
        elif actual == want:
            status = "ok"
        else:
            status = "WRONG"
            bad += 1
        results.append({"ref": ref, "pin": pin, "expected": want,
                        "actual": actual, "status": status})
    orphans = _orphan_nets(nets) if args.orphans else []
    bad += len(orphans)
    total = len(rows)
    verified = total - sum(1 for r in results if r["status"] != "ok")
    if args.json:
        print(json.dumps({
            "command": "check-intent",
            "target": str(args.project),
            "results": results,
            "orphans": [{"net": n, "ref": r, "pin": p} for n, r, p in orphans],
            "verified": verified,
            "total": total,
        }, indent=2))
        return EXIT_VIOLATIONS if bad else EXIT_OK
    print(f"{'ref':<8}{'pin':<7}{'expected':<18}{'actual':<18}result")
    for res in results:
        mark = " " if res["status"] == "ok" else "*"
        print(f"{mark}{res['ref']:<7}{res['pin']:<7}{res['expected']:<18}"
              f"{str(res['actual']):<18}{res['status']}")
    if args.orphans:
        for name, ref, pin in orphans:
            print(f"{name:<24} {ref}.{pin}  ORPHAN (single-pin net)")
            bad += 1
        print(f"\n{len(orphans)} orphan net(s)")
    print(f"\n{verified}/{total} connections verified")
    return EXIT_VIOLATIONS if bad else EXIT_OK


def _orphan_nets(nets):
    """Nets with exactly one connected pin that are not explicit no-connects."""
    out = []
    for name, nodes in sorted(nets.items()):
        if len(nodes) == 1 and not name.startswith("unconnected"):
            ((ref, pin), _) = list(nodes.items())[0]
            out.append((name, ref, pin))
    return out


def _label_net(val, nets):
    """Net a sheet label merges into, or None."""
    for cand in ("/" + val, val):
        if cand in nets:
            return cand
    return None


def cmd_lint(args):
    root = load_sexp(args.project)
    problems = []
    refs = {}
    symbols = [s for s in sexp_find_all(root, "symbol")
               if any(isinstance(i, list) and i and i[0] == "instances" for i in s)]
    lib_syms = sexp_get(root, "lib_symbols")
    defined = {s[1] for s in sexp_find_all(lib_syms, "symbol")} if lib_syms else set()
    for sym in symbols:
        uuid = ""
        u = sexp_get(sym, "uuid")
        if u:
            uuid = _first_str(u)
        reference = None
        for prop in sexp_find_all(sym, "property"):
            if len(prop) >= 3 and prop[1] == "Reference":
                reference = prop[2]
        if not reference:
            problems.append(f"symbol without Reference property (uuid={uuid})")
            continue
        if reference in refs:
            problems.append(f"duplicate reference: {reference}")
        refs[reference] = sym
        inst = sexp_get(sym, "instances")
        if not inst:
            problems.append(f"{reference}: missing instances block")
        lib_node = sexp_get(sym, "lib_id")
        lib_id = _first_str(lib_node) if lib_node else "?"
        if defined and lib_id not in defined:
            problems.append(f"{reference}: uses '{lib_id}' but it is not in lib_symbols")
    seen_uuids = {}
    for u in sexp_find_all(root, "uuid"):
        uid = _first_str(u)
        if uid in seen_uuids:
            problems.append(f"duplicate uuid: {uid}")
        seen_uuids[uid] = True
    label_counts = {}
    for kind in ("label", "global_label", "hierarchical_label"):
        for lab in sexp_find_all(root, kind):
            val = _first_str(lab)
            if val:
                label_counts[(kind, val)] = label_counts.get((kind, val), 0) + 1
    nets = None
    connectivity_skipped = False
    try:
        nets, _, _, _ = _load_nets(args.project)
    except SystemExit:
        connectivity_skipped = True
        if not args.json:
            print("LINT: skipped connectivity checks (netlist export failed)")
    if nets is not None:
        for (kind, val), count in sorted(label_counts.items(), key=lambda kv: str(kv[0])):
            net = _label_net(val, nets)
            merged = net is not None and len(nets[net]) > 1
            if count == 1 and not merged:
                problems.append(f"{kind} '{val}' appears only once and does not "
                                f"join any multi-pin net - likely a typo")
        for name, ref, pin in _orphan_nets(nets):
            problems.append(f"net '{name}' has a single connection "
                            f"({ref}.{pin}) - dangling?")
    if args.json:
        doc = {"command": "lint", "target": str(args.project), "problems": problems}
        if connectivity_skipped:
            doc["note"] = "connectivity checks skipped (netlist export failed)"
        print(json.dumps(doc, indent=2))
        return EXIT_VIOLATIONS if problems else EXIT_OK
    if problems:
        for p in problems:
            print(f"LINT: {p}")
        print(f"\n{len(problems)} lint problem(s)")
        return EXIT_VIOLATIONS
    print(f"Lint clean ({len(refs)} symbols)")
    return EXIT_OK


def cmd_check_rules(args):
    nets, _, _, _ = _load_nets(args.project, refresh=args.refresh)
    with open(args.rules, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        required = {"rule", "net", "params"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            print(f"ERROR: rules CSV must have columns {sorted(required)}",
                  file=sys.stderr)
            return EXIT_ENV
        rules = [(row["rule"].strip(), row["net"].strip(), row["params"].strip())
                 for row in reader if row["rule"].strip()]
    violations = []
    for rule, net, params in rules:
        nodes = nets.get(net, {})
        if rule == "min-contacts":
            try:
                minimum = int(params)
            except ValueError:
                print(f"ERROR: min-contacts params must be an integer, "
                      f"got '{params}' (net {net})", file=sys.stderr)
                return EXIT_ENV
            if len(nodes) < minimum:
                violations.append({
                    "rule": rule, "net": net,
                    "detail": f"{len(nodes)} connection(s), need >= {minimum}",
                })
        elif rule == "net-exclusive":
            allowed = set(params.replace(",", " ").split())
            if not nodes:
                violations.append({"rule": rule, "net": net,
                                   "detail": "net not found in netlist"})
                continue
            for (ref, pin) in sorted(nodes):
                if ref not in allowed:
                    violations.append({
                        "rule": rule, "net": net,
                        "detail": f"{ref}.{pin} connected but only "
                                  f"{sorted(allowed)} allowed",
                    })
        else:
            print(f"ERROR: unknown rule type '{rule}' (net {net})", file=sys.stderr)
            return EXIT_ENV
    if args.json:
        print(json.dumps({
            "command": "check-rules",
            "target": str(args.project),
            "checked": len(rules),
            "violations": violations,
        }, indent=2))
        return EXIT_VIOLATIONS if violations else EXIT_OK
    for v in violations:
        print(f"RULE FAIL: [{v['rule']}] {v['net']}: {v['detail']}")
    if violations:
        print(f"\n{len(violations)} rule violation(s)")
        return EXIT_VIOLATIONS
    print(f"All {len(rules)} rule(s) pass")
    return EXIT_OK


def cmd_render(args):
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    rc = EXIT_OK
    for path in args.projects:
        stem = Path(path).stem
        if str(path).lower().endswith(".kicad_pcb"):
            target = str(outdir / (stem + ".svg"))
            sub = kicad_cli(["pcb", "export", "svg", str(path), "-o", target,
                             "--layers", "F.Cu,B.Cu,F.Mask,B.Mask,"
                                          "F.Silkscreen,B.Silkscreen,Edge.Cuts"])
        else:
            # sch export svg writes one file per sheet into the -o directory
            target = str(outdir / (stem + "-sch"))
            sub = kicad_cli(["sch", "export", "svg", str(path), "-o", target])
        if sub.returncode != 0:
            print(sub.stderr.strip() or sub.stdout.strip(), file=sys.stderr)
            print(f"ERROR: could not render {path}", file=sys.stderr)
            rc = EXIT_ENV
        else:
            print(f"rendered {path} -> {target}")
    return rc


def cmd_bom(args):
    out = Path(str(args.project).rsplit(".", 1)[0] + "-bom.csv")
    proc = kicad_cli(["sch", "export", "bom", str(args.project),
                      "--fields", "Reference,Value,Footprint,${QUANTITY}",
                      "--group-by", "Value,Footprint",
                      "-o", str(out)])
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        return EXIT_ENV
    print(out)
    return EXIT_OK


# ---------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(prog="fiducial", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor").set_defaults(func=cmd_doctor)

    p = sub.add_parser("erc", help="run ERC on a schematic")
    p.add_argument("project")
    p.add_argument("--json", action="store_true",
                   help="machine-readable JSON output")
    p.set_defaults(func=cmd_erc)

    p = sub.add_parser("drc", help="run DRC on a board")
    p.add_argument("board")
    p.add_argument("--parity", action="store_true", help="check schematic parity")
    p.add_argument("--save-board", dest="save_board", action="store_true",
                   help="refill zones and rewrite the board file (default: off)")
    p.add_argument("--json", action="store_true",
                   help="machine-readable JSON output")
    p.set_defaults(func=cmd_drc)

    p = sub.add_parser("netlist", help="export netlist")
    p.add_argument("project")
    p.set_defaults(func=cmd_netlist)

    p = sub.add_parser("nets", help="dump all nets")
    p.add_argument("project")
    p.add_argument("--refresh", action="store_true", help="force netlist re-export")
    p.set_defaults(func=cmd_nets)

    p = sub.add_parser("pins", help="dump one symbol's pins")
    p.add_argument("project")
    p.add_argument("ref")
    p.add_argument("--refresh", action="store_true")
    p.set_defaults(func=cmd_pins)

    p = sub.add_parser("check-intent", help="verify intent.csv against netlist")
    p.add_argument("project")
    p.add_argument("csv")
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--orphans", action="store_true",
                   help="also flag single-pin nets as violations")
    p.add_argument("--json", action="store_true",
                   help="machine-readable JSON output")
    p.set_defaults(func=cmd_check_intent)

    p = sub.add_parser("lint", help="structural schematic checks")
    p.add_argument("project")
    p.add_argument("--json", action="store_true",
                   help="machine-readable JSON output")
    p.set_defaults(func=cmd_lint)

    p = sub.add_parser("check-rules", help="verify house-style rules from a CSV")
    p.add_argument("project")
    p.add_argument("rules", help="rules CSV (see docs/rules.md)")
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--json", action="store_true",
                   help="machine-readable JSON output")
    p.set_defaults(func=cmd_check_rules)

    p = sub.add_parser("render", help="export SVG renders")
    p.add_argument("projects", nargs="+")
    p.add_argument("--outdir", default="render")
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("bom", help="export BOM CSV")
    p.add_argument("project")
    p.set_defaults(func=cmd_bom)

    args = ap.parse_args(argv)

    try:
        return args.func(args)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return EXIT_ENV
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return EXIT_ENV


if __name__ == "__main__":
    sys.exit(main())
