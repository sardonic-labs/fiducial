#!/usr/bin/env python3
"""fiducial.py - stdlib-only helpers for AI-driven KiCad hardware design."""

import argparse
import csv
import json
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


def _run_report(kind, path, extra=()):
    report = Path(tempfile.gettempdir()) / f"fiducial-{kind}.json"
    prefix = ["sch"] if kind == "erc" else ["pcb"]
    proc = kicad_cli(prefix + [kind, str(path), "--format", "json",
                               "--output", str(report), *extra])
    if not report.exists():
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        print(f"ERROR: no {kind.upper()} report produced", file=sys.stderr)
        return EXIT_ENV
    data = json.loads(report.read_text(encoding="utf-8"))
    viol = data.get(kind, {})
    by_sev = {}
    for v in viol:
        sev = v.get("severity", "unknown").replace("severity_", "")
        by_sev.setdefault(sev, []).append(v)
    errors, warns = by_sev.get("error", []), by_sev.get("warning", [])
    print(f"{kind.upper()} on {path}: {len(errors)} errors, {len(warns)} warnings")
    for sev in ("error", "warning"):
        for v in by_sev.get(sev, []):
            where = ""
            for item in v.get("items", []):
                desc = item.get("description", "")
                if desc:
                    where = f" [{desc}]"
                    break
            print(f"  {sev.upper()}: {v.get('type', '?')} @ {v.get('pos', '?')}{where}")
            print(f"    {v.get('description', '')}")
    for sev, items in sorted(by_sev.items()):
        if sev not in ("error", "warning"):
            print(f"  {sev}: {len(items)}")
    if errors:
        return EXIT_VIOLATIONS
    return EXIT_OK


def cmd_erc(args):
    return _run_report("erc", args.project)


def cmd_drc(args):
    extra = ["--schematic-parity"] if args.parity else []
    return _run_report("drc", args.board, extra)


def cmd_netlist(args):
    out = Path(str(args.project).rsplit(".", 1)[0] + "-netlist.sexpr")
    proc = kicad_cli(["sch", "export", "netlist", str(args.project),
                      "-o", str(out), "--format", "kicadsexpr"])
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        return EXIT_ENV
    print(out)
    return EXIT_OK


def _load_nets(project):
    netlist = Path(str(project).rsplit(".", 1)[0] + "-netlist.sexpr")
    fresh = False
    if not netlist.exists():
        r = cmd_netlist(type("A", (), {"project": project})())
        if r != EXIT_OK:
            sys.exit(r)
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
    nets, _, _, fresh = _load_nets(args.project)
    print(f"# {'(regenerated)' if fresh else '(cached)'} "
          f"{len(nets)} nets; use --refresh to force re-export")
    for name in sorted(nets, key=str.lower):
        pins = ", ".join(f"{r}.{p}" for (r, p) in sorted(nets[name]))
        print(f"{name:<24} {pins}")
    return EXIT_OK


def cmd_pins(args):
    nets, values, footprints, _ = _load_nets(args.project)
    ref = args.ref
    pin2net = {}
    for name, nodes in nets.items():
        for (r, p), net in nodes.items():
            if r == ref:
                pin2net[p] = net
    if not pin2net:
        print(f"No connected pins found for '{ref}'. Check the reference.")
        return EXIT_VIOLATIONS
    print(f"{ref}  value={values.get(ref, '?')}  footprint={footprints.get(ref, '?')}")
    for pin in sorted(pin2net, key=_pin_sort):
        print(f"  pin {pin:<6} -> {pin2net[pin]}")
    return EXIT_OK


def _pin_sort(p):
    digits = "".join(c for c in str(p) if c.isdigit())
    return (int(digits) if digits else 10**9, str(p))


def cmd_check_intent(args):
    nets, _, _, _ = _load_nets(args.project)
    bad = 0
    with open(args.csv, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    required = {"ref", "pin", "expected_net"}
    if rows and not required.issubset(rows[0]):
        print(f"CSV must have columns {sorted(required)}")
        return EXIT_ENV
    print(f"{'ref':<8}{'pin':<7}{'expected':<18}{'actual':<18}result")
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
        mark = " " if status == "ok" else "*"
        print(f"{mark}{ref:<7}{pin:<7}{want:<18}{str(actual):<18}{status}")
    total = len(rows)
    print(f"\n{total - bad}/{total} connections verified")
    return EXIT_VIOLATIONS if bad else EXIT_OK


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
    if problems:
        for p in problems:
            print(f"LINT: {p}")
        print(f"\n{len(problems)} lint problem(s)")
        return EXIT_VIOLATIONS
    print(f"Lint clean ({len(refs)} symbols)")
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
    p.set_defaults(func=cmd_erc)

    p = sub.add_parser("drc", help="run DRC on a board")
    p.add_argument("board")
    p.add_argument("--parity", action="store_true", help="check schematic parity")
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
    p.set_defaults(func=cmd_check_intent)

    p = sub.add_parser("lint", help="structural schematic checks")
    p.add_argument("project")
    p.set_defaults(func=cmd_lint)

    p = sub.add_parser("render", help="export SVG renders")
    p.add_argument("projects", nargs="+")
    p.add_argument("--outdir", default="render")
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("bom", help="export BOM CSV")
    p.add_argument("project")
    p.set_defaults(func=cmd_bom)

    args = ap.parse_args(argv)

    if getattr(args, "refresh", False):
        nl = Path(str(args.project).rsplit(".", 1)[0] + "-netlist.sexpr")
        if nl.exists():
            nl.unlink()

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
