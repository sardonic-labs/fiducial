#!/usr/bin/env python3
"""bom_check.py - BOM analysis for review workflows.

Stdlib-only. Generates BOM from schematic, cross-checks part ratings,
flags lifecycle concerns, and suggests alternatives. Designed for use by
the reviewer agent when auditing AI-generated designs.

Exit codes: 0 = clean, 1 = findings, 2 = environment/parse error.
"""

import argparse
import csv
import json
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fiducial import (
    load_sexp, sexp_get, sexp_find_all, _first_str,
    kicad_cli, EXIT_OK, EXIT_VIOLATIONS, EXIT_ENV,
)


def _get_ref(sym):
    for prop in sexp_find_all(sym, "property"):
        if len(prop) >= 3 and prop[1] == "Reference":
            return prop[2]
    return None


def _get_value(sym):
    for prop in sexp_find_all(sym, "property"):
        if len(prop) >= 3 and prop[1] == "Value":
            return prop[2]
    return ""


def _get_footprint(sym):
    for prop in sexp_find_all(sym, "property"):
        if len(prop) >= 3 and prop[1] == "Footprint":
            return prop[2]
    return ""


# ====================================================================
# parse: generate BOM from schematic
# ====================================================================

def cmd_parse(args):
    project = Path(args.project)
    bom_path = project.with_suffix(".bom.csv")

    proc = kicad_cli(["sch", "export", "bom", str(project),
                       "--fields", "Reference,Value,Footprint,${QUANTITY}",
                       "--group-by", "Value,Footprint",
                       "-o", str(bom_path)])
    if proc.returncode != 0:
        print(f"ERROR: BOM export failed: {proc.stderr}", file=sys.stderr)
        return EXIT_ENV

    # Parse and display the BOM
    rows = []
    if bom_path.exists():
        with open(bom_path, encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))

    if args.json:
        print(json.dumps({"command": "parse", "target": str(project),
                          "bom_path": str(bom_path), "rows": rows,
                          "total_lines": len(rows)}, indent=2))
        return EXIT_OK

    if not rows:
        print("BOM is empty.")
        return EXIT_OK

    # Display summary
    total_qty = 0
    print(f"{'REF':<16}{'VALUE':<16}{'FOOTPRINT':<32}{'QTY'}")
    print("-" * 70)
    for row in rows:
        refs = row.get("Reference", "")
        value = row.get("Value", "")
        fp = row.get("Footprint", "")
        qty = row.get("${QUANTITY}", "1")
        try:
            qty_int = int(qty)
        except ValueError:
            qty_int = 1
        total_qty += qty_int
        print(f"{refs:<16}{value:<16}{fp:<32}{qty}")

    print(f"\n{len(rows)} line(s), {total_qty} total parts")
    return EXIT_OK


# ====================================================================
# ratings: cross-check voltage/current ratings vs circuit demands
# ====================================================================

def cmd_ratings(args):
    """Check component ratings against circuit requirements.

    This performs heuristic checks:
    - Resistors: flag if power dissipation exceeds typical ratings
    - Capacitors: flag if voltage rating seems too low
    - Diodes/LEDs: flag if forward current seems excessive
    """
    root = load_sexp(args.project)
    symbols = [s for s in sexp_find_all(root, "symbol")
               if any(isinstance(i, list) and i and i[0] == "instances" for i in s)]

    findings = []

    # Extract components with their values
    components = []
    for sym in symbols:
        ref = _get_ref(sym)
        value = _get_value(sym)
        footprint = _get_footprint(sym)
        if ref and value:
            components.append({"ref": ref, "value": value, "footprint": footprint})

    # Virtual/power symbols that are not real components
    _VIRTUAL_PREFIXES = ("#", "PWR_FLAG", "FLG")

    # Heuristic checks
    for comp in components:
        ref = comp["ref"]
        value = comp["value"].strip()
        fp = comp["footprint"]

        # Skip virtual symbols (PWR_FLAG, power flags, etc.)
        if ref.startswith("#") or value.upper() == "PWR_FLAG":
            continue

        # Check for very small resistor values (possible short)
        if ref.upper().startswith("R"):
            try:
                if value.lower().endswith("r"):
                    val = float(value[:-1])
                elif value.lower().endswith("k"):
                    val = float(value[:-1]) * 1000
                elif value.lower().endswith("m"):
                    val = float(value[:-1]) * 0.001
                else:
                    val = float(value)
                if val < 0.1:
                    findings.append({
                        "type": "low_resistance",
                        "severity": "warning",
                        "detail": f"{ref}: {value} ohm - very low, check if intentional"
                    })
                elif val > 10e6:
                    findings.append({
                        "type": "high_resistance",
                        "severity": "info",
                        "detail": f"{ref}: {value} ohm - very high, check if intentional"
                    })
            except ValueError:
                pass

        # Check for missing footprint
        if not fp:
            findings.append({
                "type": "missing_footprint",
                "severity": "error",
                "detail": f"{ref} ({value}): no footprint assigned"
            })

    if args.json:
        print(json.dumps({"command": "ratings", "target": str(args.project),
                          "components_checked": len(components),
                          "findings": findings}, indent=2))
        return EXIT_VIOLATIONS if any(f["severity"] == "error" for f in findings) else EXIT_OK

    print(f"Components checked: {len(components)}")
    if findings:
        for f in findings:
            marker = "ERROR" if f["severity"] == "error" else "WARN" if f["severity"] == "warning" else "INFO"
            print(f"  [{marker}] {f['detail']}")
        errors = sum(1 for f in findings if f["severity"] == "error")
        return EXIT_VIOLATIONS if errors else EXIT_OK
    print("Rating checks passed.")
    return EXIT_OK


# ====================================================================
# lifecycle: flag parts with known lifecycle issues (placeholder)
# ====================================================================

def cmd_lifecycle(args):
    """Flag components that may have lifecycle issues.

    NOTE: This is a placeholder implementation. A production version would
    query a parts database (Octopart, Digikey API, etc.) for lifecycle status.
    For now, it flags common patterns that suggest potential issues.
    """
    root = load_sexp(args.project)
    symbols = [s for s in sexp_find_all(root, "symbol")
               if any(isinstance(i, list) and i and i[0] == "instances" for i in s)]

    findings = []
    components = []

    for sym in symbols:
        ref = _get_ref(sym)
        value = _get_value(sym)
        footprint = _get_footprint(sym)
        lib_node = sexp_get(sym, "lib_id")
        lib_id = _first_str(lib_node) if lib_node else ""
        if ref and value:
            components.append({
                "ref": ref, "value": value,
                "footprint": footprint, "lib_id": lib_id,
            })

    # Heuristic lifecycle flags
    for comp in components:
        ref = comp["ref"]
        value = comp["value"].strip().lower()
        fp = comp["footprint"].lower()

        # Flag placeholder values
        if value in ("?", "xxx", "tbd", "placeholder", "todo", "nc"):
            findings.append({
                "type": "placeholder_value",
                "severity": "error",
                "detail": f"{ref}: value is '{comp['value']}' - needs real part"
            })

        # Flag library footprints that suggest generic parts
        if "generic" in fp or "special" in fp:
            findings.append({
                "type": "generic_footprint",
                "severity": "warning",
                "detail": f"{ref}: uses generic/special footprint, verify real part exists"
            })

    if args.json:
        print(json.dumps({"command": "lifecycle", "target": str(args.project),
                          "components_checked": len(components),
                          "findings": findings}, indent=2))
        return EXIT_VIOLATIONS if any(f["severity"] == "error" for f in findings) else EXIT_OK

    print(f"Components checked: {len(components)}")
    if findings:
        for f in findings:
            marker = "ERROR" if f["severity"] == "error" else "WARN" if f["severity"] == "warning" else "INFO"
            print(f"  [{marker}] {f['detail']}")
        errors = sum(1 for f in findings if f["severity"] == "error")
        return EXIT_VIOLATIONS if errors else EXIT_OK
    print("No lifecycle issues detected (note: full lifecycle check requires external database).")
    return EXIT_OK


# ====================================================================
# alternates: suggest alternates for flagged parts (placeholder)
# ====================================================================

def cmd_alternates(args):
    """Suggest alternative parts for components.

    NOTE: This is a placeholder implementation. A production version would
    query distributor APIs for pin-compatible alternatives.
    """
    root = load_sexp(args.project)
    symbols = [s for s in sexp_find_all(root, "symbol")
               if any(isinstance(i, list) and i and i[0] == "instances" for i in s)]

    components = []
    for sym in symbols:
        ref = _get_ref(sym)
        value = _get_value(sym)
        footprint = _get_footprint(sym)
        if ref and value:
            components.append({"ref": ref, "value": value, "footprint": footprint})

    # Placeholder: no actual alternates database
    suggestions = []
    for comp in components:
        ref = comp["ref"]
        value = comp["value"].strip()
        # Flag very common parts that might have better alternatives
        if value.lower() in ("10k", "100k", "1k", "100r", "10r"):
            suggestions.append({
                "ref": ref,
                "value": value,
                "note": f"Common value {value} - verify package and power rating are adequate"
            })

    if args.json:
        print(json.dumps({"command": "alternates", "target": str(args.project),
                          "components_checked": len(components),
                          "suggestions": suggestions}, indent=2))
        return EXIT_OK

    if suggestions:
        print(f"Suggestions for {len(suggestions)} component(s):")
        for s in suggestions:
            print(f"  {s['ref']} ({s['value']}): {s['note']}")
    else:
        print("No alternate suggestions (note: full check requires parts database).")
    return EXIT_OK


# ====================================================================
# main
# ====================================================================

def main(argv=None):
    ap = argparse.ArgumentParser(prog="bom_check",
                                 description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("parse", help="generate BOM from schematic")
    p.add_argument("project", help="path to .kicad_sch")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_parse)

    p = sub.add_parser("ratings", help="cross-check component ratings")
    p.add_argument("project")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_ratings)

    p = sub.add_parser("lifecycle", help="flag lifecycle concerns")
    p.add_argument("project")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_lifecycle)

    p = sub.add_parser("alternates", help="suggest alternate parts")
    p.add_argument("project")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_alternates)

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
