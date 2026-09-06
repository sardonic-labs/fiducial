#!/usr/bin/env python3
"""seed_faults.py - seeded-fault benchmark generator for fiducial.

Generates 8 broken schematic variants from tests/fixtures/healthy.kicad_sch,
each with a matching intent.csv, a pre-exported netlist cache
(<board>-netlist.sexpr), and an expected.json describing which tool
catches the fault.

Stdlib-only, deterministic (no --seed needed: mutations are fixed).
Offline: the netlist cache is written NEWER than the .sch so
`lint` / `check-intent` reuse it without calling kicad-cli.

Usage:
    python scripts/seed_faults.py            # write fixtures
    python scripts/seed_faults.py --list     # list fault classes
    python scripts/seed_faults.py --check    # regenerate + verify expectations

Fault classes (schematic-only v1):
    label-typo, floating-pin, wrong-net, missing-part,
    duplicate-ref, off-grid, power-short, nc-violation
"""

import csv
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"
BASE_SCH = FIX / "healthy.kicad_sch"
OUTDIR = FIX / "faults"

# Canonical connectivity for the healthy board (mirrors
# tests/test_offline.py NETLIST_HEALTHY).
BASE_NETS = {
    "/A": [("R1", "1"), ("U1", "2")],
    "/B": [("R1", "2"), ("U1", "3")],
    "/VCC": [("U1", "1"), ("C1", "1")],
    "/GND": [("U1", "4"), ("C1", "2")],
}
BASE_COMPS = [("R1", "10k", "R_0603"), ("C1", "100n", "C_0603"),
              ("U1", "TestMCU", "QFN")]

INTENT_ROWS = [("R1", "1", "/A"), ("R1", "2", "/B"),
               ("U1", "1", "/VCC"), ("C1", "2", "/GND")]

FAULTS = ["label-typo", "floating-pin", "wrong-net", "missing-part",
          "duplicate-ref", "off-grid", "power-short", "nc-violation"]

# (lint_exit, intent_exit, lint_match, intent_match) per fault.
EXPECTED = {
    "label-typo": (1, 1, "appears only once", "WRONG"),
    "floating-pin": (1, 1, "single connection", "WRONG"),
    "wrong-net": (1, 1, "single connection", "WRONG"),
    "missing-part": (1, 1, "single connection", "MISSING"),
    "duplicate-ref": (1, 0, "duplicate reference", "connections verified"),
    "off-grid": (1, 0, "off-grid", "connections verified"),
    "power-short": (1, 1, "appears only once", "WRONG"),
    "nc-violation": (1, 1, "appears only once", "WRONG"),
}


def netlist_sexpr(nets, comps):
    lines = ['(export (version "E")', "\t(components"]
    for ref, val, fp in comps:
        lines.append(f'\t\t(comp (ref "{ref}") (value "{val}") '
                     f'(footprint "{fp}"))')
    lines.append("\t)")
    lines.append("\t(nets")
    for code, (name, nodes) in enumerate(nets.items(), start=1):
        lines.append(f'\t\t(net (code "{code}") (name "{name}")')
        for r, p in nodes:
            lines.append(f'\t\t\t(node (ref "{r}") (pin "{p}"))')
        lines.append("\t\t)")
    lines.append("\t)")
    lines.append(")")
    return "\n".join(lines) + "\n"


def mutate(name, sch_text, nets, comps):
    """Return (sch_text, nets, comps, intent_rows) for fault *name*."""
    intent = list(INTENT_ROWS)
    nets = {k: list(v) for k, v in nets.items()}
    comps = list(comps)
    if name == "label-typo":
        # one /A label becomes /AX: R1.1 splits onto its own net
        sch_text = sch_text.replace('(label "/A" (at 12.7 12.7 0))',
                                    '(label "/AX" (at 12.7 12.7 0))', 1)
        nets["/AX"] = [("R1", "1")]
        nets["/A"] = [("U1", "2")]
    elif name == "floating-pin":
        # C1.2 lifted from /GND; one /GND label removed
        sch_text = sch_text.replace('(label "/GND" (at 12.7 26.67 0))\n', '', 1)
        nets["/GND"] = [("U1", "4")]
        nets["unconnected-(C1-pad2)"] = [("C1", "2")]
    elif name == "wrong-net":
        # R1.2 bridged onto /A instead of /B (ERC-clean, intent WRONG)
        nets["/A"] = [("R1", "1"), ("U1", "2"), ("R1", "2")]
        nets["/B"] = [("U1", "3")]
    elif name == "missing-part":
        # handled in build_all (symbol-block removal); nothing here
        pass
    elif name == "duplicate-ref":
        sch_text = sch_text.replace('(property "Reference" "C1"',
                                    '(property "Reference" "R1"', 1)
    elif name == "off-grid":
        sch_text = sch_text.replace("(at 50.8 50.8 0)",
                                    "(at 50.9 50.8 0)", 1)
    elif name == "power-short":
        # /VCC merged into /GND
        sch_text = sch_text.replace('(label "/VCC"', '(label "/GND"', 1)
        nodes = nets.pop("/VCC")
        nets["/GND"] = nets["/GND"] + nodes
    elif name == "nc-violation":
        # R1.2 left floating though intent requires /B
        sch_text = sch_text.replace('(label "/B" (at 12.7 15.24 0))\n', '', 1)
        nets["/B"] = [("U1", "3")]
        nets["unconnected-(R1-pad2)"] = [("R1", "2")]
    return sch_text, nets, comps, intent


def _remove_symbol(sch_text, ref):
    """Remove the (symbol ...) block whose Reference is *ref* (depth-aware)."""
    idx = 0
    while True:
        start = sch_text.find("(symbol", idx)
        if start < 0:
            raise ValueError(f"symbol {ref} not found")
        depth = 0
        i = start
        while i < len(sch_text):
            if sch_text[i] == "(":
                depth += 1
            elif sch_text[i] == ")":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        block = sch_text[start:i + 1]
        if f'"Reference" "{ref}"' in block:
            return sch_text[:start] + sch_text[i + 1:]
        idx = i + 1


def build_all(outdir=OUTDIR):
    base_sch = BASE_SCH.read_text(encoding="utf-8")
    outdir.mkdir(parents=True, exist_ok=True)
    for name in FAULTS:
        d = outdir / name
        d.mkdir(exist_ok=True)
        sch, nets, comps, intent = mutate(name, base_sch,
                                          BASE_NETS, BASE_COMPS)
        if name == "missing-part":
            sch = _remove_symbol(base_sch, "C1")
            nets = {k: [(r, p) for (r, p) in v if r != "C1"]
                    for k, v in BASE_NETS.items()}
            nets = {k: v for k, v in nets.items() if v}
            comps = [c for c in BASE_COMPS if c[0] != "C1"]
            intent = list(INTENT_ROWS)
        board = d / "board.kicad_sch"
        board.write_text(sch, encoding="utf-8")
        with open(d / "intent.csv", "w", newline="",
                  encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["ref", "pin", "expected_net"])
            w.writerows(intent)
        (d / "board-netlist.sexpr").write_text(
            netlist_sexpr(nets, comps), encoding="utf-8")
        le, ie, lm, im = EXPECTED[name]
        (d / "expected.json").write_text(json.dumps({
            "fault": name,
            "lint_exit": le, "intent_exit": ie,
            "lint_match": lm, "intent_match": im,
        }, indent=2), encoding="utf-8")
        # netlist cache must be NEWER than the sch so fiducial reuses it
        # instead of invoking kicad-cli.
        sch_mtime = board.stat().st_mtime
        nl = d / "board-netlist.sexpr"
        os.utime(nl, (sch_mtime + 10, sch_mtime + 10))
    print(f"wrote {len(FAULTS)} faults to {outdir}")


def main(argv):
    if "--list" in argv:
        print("\n".join(FAULTS))
        return 0
    build_all()
    if "--check" in argv:
        import subprocess
        fid = ROOT / "scripts" / "fiducial.py"
        fails = 0
        for name in FAULTS:
            d = OUTDIR / name
            exp = json.loads((d / "expected.json").read_text())
            for cmd, key in (("lint", "lint_match"),
                             ("check-intent", "intent_match")):
                args = [sys.executable, str(fid), cmd, str(d / "board.kicad_sch")]
                if cmd == "check-intent":
                    args.append(str(d / "intent.csv"))
                p = subprocess.run(args, capture_output=True, text=True,
                                   encoding="utf-8")
                want_exit = exp["lint_exit"] if cmd == "lint" else exp["intent_exit"]
                ok = (p.returncode == want_exit
                      and exp[key] in (p.stdout + p.stderr))
                print(f"{'PASS' if ok else 'FAIL'} {name}/{cmd} "
                      f"(exit={p.returncode}, want={want_exit})")
                if not ok:
                    fails += 1
                    print((p.stdout + p.stderr)[:800])
        return 1 if fails else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
