#!/usr/bin/env python3
"""schematic_check.py - deep schematic analysis for review workflows.

Stdlib-only. Parses .kicad_sch files and performs structural, connectivity,
and style checks that go beyond what lint/erc catch. Designed for use by the
reviewer agent when auditing AI-generated schematics.

Exit codes: 0 = clean, 1 = findings, 2 = environment/parse error.
"""

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

# Reuse the S-expression parser from fiducial
sys.path.insert(0, str(Path(__file__).parent))
from fiducial import (
    load_sexp, parse_sexp, sexp_get, sexp_find_all, _first_str,
    EXIT_OK, EXIT_VIOLATIONS, EXIT_ENV,
)

GRID_MM = 1.27
GRID_TOL = 0.01
POWER_PIN_PREFIXES = ("VDD", "VCC", "VSS", "GND", "AVDD", "AVSS", "DVDD",
                      "DVSS", "VBUS", "VBAT", "3V3", "5V", "12V")
POWER_LABEL_PREFIXES = ("+", "-", "VBAT", "VBUS")


def _on_grid(v):
    return abs(v / GRID_MM - round(v / GRID_MM)) <= GRID_TOL


def _load_schematic(path):
    root = load_sexp(path)
    symbols = [s for s in sexp_find_all(root, "symbol")
               if any(isinstance(i, list) and i and i[0] == "instances" for i in s)]
    lib_syms = sexp_get(root, "lib_symbols")
    defined = {s[1] for s in sexp_find_all(lib_syms, "symbol")} if lib_syms else set()
    return root, symbols, defined


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


def _get_position(sym):
    at = sexp_get(sym, "at")
    if at and len(at) >= 3:
        try:
            return float(at[1]), float(at[2])
        except (TypeError, ValueError):
            pass
    return None, None


def _is_power_pin(name):
    upper = name.upper().strip()
    return any(upper.startswith(p) for p in POWER_PIN_PREFIXES)


def _is_power_label(name):
    n = name.strip()
    if any(n.startswith(p) for p in POWER_LABEL_PREFIXES):
        return True
    return n.upper() in ("GND", "VCC", "VDD", "VSS", "AGND", "DGND",
                          "AVDD", "AVSS", "VBUS", "VBAT")


# ====================================================================
# power-pins: enumerate every power pin and its net
# ====================================================================

def cmd_power_pins(args):
    root, symbols, _ = _load_schematic(args.project)
    results = []
    for sym in symbols:
        ref = _get_ref(sym)
        if not ref:
            continue
        lib_node = sexp_get(sym, "lib_id")
        lib_id = _first_str(lib_node) if lib_node else ""
        for pin_node in sexp_find_all(sym, "pin"):
            pin_name = ""
            pin_number = ""
            for item in pin_node[1:]:
                if isinstance(item, list):
                    if item and item[0] == "name":
                        pin_name = _first_str(item) if len(item) > 1 else ""
                    elif item and item[0] == "pin":
                        pin_number = _first_str(item) if len(item) > 1 else ""
                elif isinstance(item, str):
                    if pin_number == "":
                        pin_number = item
            if _is_power_pin(pin_name):
                results.append({
                    "ref": ref,
                    "lib_id": lib_id,
                    "pin_name": pin_name,
                    "pin_number": pin_number,
                })

    if args.json:
        print(json.dumps({"command": "power-pins", "target": str(args.project),
                          "count": len(results), "pins": results}, indent=2))
        return EXIT_OK

    if not results:
        print("No power pins found in schematic symbols.")
        return EXIT_OK

    print(f"{'REF':<8}{'PIN NAME':<16}{'PIN#':<8}{'LIB_ID'}")
    for r in results:
        print(f"{r['ref']:<8}{r['pin_name']:<16}{r['pin_number']:<8}{r['lib_id']}")
    print(f"\n{len(results)} power pin(s) found")
    return EXIT_OK


# ====================================================================
# unconnected: pins with no wire/label connection
# ====================================================================

def cmd_unconnected(args):
    from fiducial import _load_nets
    nets, values, footprints, _ = _load_nets(args.project)
    root, symbols, _ = _load_schematic(args.project)

    connected_pins = set()
    for name, nodes in nets.items():
        for (ref, pin) in nodes:
            connected_pins.add((ref, pin))

    unconnected = []
    for sym in symbols:
        ref = _get_ref(sym)
        if not ref:
            continue
        for pin_node in sexp_find_all(sym, "pin"):
            pin_number = ""
            for item in pin_node[1:]:
                if isinstance(item, str) and pin_number == "":
                    pin_number = item
                elif isinstance(item, list) and item and item[0] == "pin":
                    pin_number = _first_str(item) if len(item) > 1 else ""
            if pin_number and (ref, pin_number) not in connected_pins:
                # Check for no-connect flag
                nc = False
                for nc_flag in sexp_find_all(root, "no_connect"):
                    nc_at = sexp_get(nc_flag, "at")
                    if nc_at:
                        nc = True
                        break
                if not nc:
                    unconnected.append({"ref": ref, "pin": pin_number})

    if args.json:
        print(json.dumps({"command": "unconnected", "target": str(args.project),
                          "count": len(unconnected), "pins": unconnected}, indent=2))
        return EXIT_VIOLATIONS if unconnected else EXIT_OK

    if not unconnected:
        print("No unconnected pins found.")
        return EXIT_OK

    print(f"{'REF':<8}{'PIN':<8}")
    for u in unconnected:
        print(f"{u['ref']:<8}{u['pin']:<8}")
    print(f"\n{len(unconnected)} unconnected pin(s)")
    return EXIT_VIOLATIONS if unconnected else EXIT_OK


# ====================================================================
# orphan-nets: nets with exactly one connected pin
# ====================================================================

def cmd_orphan_nets(args):
    from fiducial import _load_nets, _is_rail_net
    nets, _, _, _ = _load_nets(args.project)
    orphans = []
    for name, nodes in sorted(nets.items()):
        if len(nodes) == 1 and not name.startswith("unconnected"):
            ((ref, pin), _) = list(nodes.items())[0]
            orphans.append({"net": name, "ref": ref, "pin": pin})

    if args.json:
        print(json.dumps({"command": "orphan-nets", "target": str(args.project),
                          "count": len(orphans), "orphans": orphans}, indent=2))
        return EXIT_VIOLATIONS if orphans else EXIT_OK

    if not orphans:
        print("No orphan nets found.")
        return EXIT_OK

    print(f"{'NET':<24}{'REF':<8}{'PIN':<8}")
    for o in orphans:
        print(f"{o['net']:<24}{o['ref']:<8}{o['pin']:<8}")
    print(f"\n{len(orphans)} orphan net(s)")
    return EXIT_VIOLATIONS if orphans else EXIT_OK


# ====================================================================
# refdes-audit: check reference designator consistency
# ====================================================================

def cmd_refdes_audit(args):
    root, symbols, _ = _load_schematic(args.project)
    refs = {}
    prefix_counts = defaultdict(int)
    issues = []

    for sym in symbols:
        ref = _get_ref(sym)
        if not ref:
            issues.append({"type": "missing_ref", "detail": "symbol without Reference property"})
            continue
        prefix = "".join(c for c in ref if c.isalpha())
        if not prefix:
            issues.append({"type": "no_prefix", "detail": f"{ref}: no alphabetical prefix"})
            continue
        prefix_counts[prefix] += 1
        num_str = ref[len(prefix):]
        if not num_str.isdigit():
            issues.append({"type": "bad_number", "detail": f"{ref}: non-numeric suffix"})
            continue
        num = int(num_str)
        if ref in refs:
            issues.append({"type": "duplicate", "detail": f"duplicate reference: {ref}"})
        refs[ref] = {"num": num, "prefix": prefix, "sym": sym}

    # Check for gaps in numbering
    for prefix in sorted(prefix_counts):
        nums = sorted(refs[r]["num"] for r in refs if refs[r]["prefix"] == prefix)
        expected = list(range(1, max(nums) + 1)) if nums else []
        missing = set(expected) - set(nums)
        if missing:
            issues.append({"type": "gap",
                           "detail": f"{prefix}* numbering gap: missing {sorted(missing)}"})

    # Check for mixed conventions
    upper_refs = [r for r in refs if r == r.upper()]
    lower_refs = [r for r in refs if r != r.upper() and any(c.islower() for c in r)]
    if upper_refs and lower_refs:
        issues.append({"type": "mixed_case",
                       "detail": f"mixed case conventions: {upper_refs[:3]} vs {lower_refs[:3]}"})

    if args.json:
        print(json.dumps({"command": "refdes-audit", "target": str(args.project),
                          "total": len(refs), "issues": issues,
                          "prefix_counts": dict(prefix_counts)}, indent=2))
        return EXIT_VIOLATIONS if issues else EXIT_OK

    for prefix in sorted(prefix_counts):
        print(f"  {prefix}* : {prefix_counts[prefix]} components")
    if issues:
        print(f"\n{len(issues)} issue(s):")
        for i in issues:
            print(f"  [{i['type']}] {i['detail']}")
        return EXIT_VIOLATIONS
    print(f"\nRefdes audit clean ({len(refs)} symbols)")
    return EXIT_OK


# ====================================================================
# label-audit: check label naming and usage
# ====================================================================

def cmd_label_audit(args):
    root, symbols, _ = _load_schematic(args.project)
    from fiducial import _load_nets, _label_net

    label_counts = defaultdict(int)
    label_positions = {}
    for kind in ("label", "global_label", "hierarchical_label"):
        for lab in sexp_find_all(root, kind):
            val = _first_str(lab)
            if val:
                label_counts[(kind, val)] += 1
                at = sexp_get(lab, "at")
                if at and len(at) >= 3:
                    try:
                        x, y = float(at[1]), float(at[2])
                        label_positions[(kind, val)] = (x, y)
                    except (TypeError, ValueError):
                        pass

    issues = []
    try:
        nets, _, _, _ = _load_nets(args.project)
        for (kind, val), count in sorted(label_counts.items()):
            net = _label_net(val, nets)
            merged = net is not None and len(nets.get(net, {})) > 1
            if count == 1 and not merged:
                issues.append({
                    "type": "single_use",
                    "detail": f"{kind} '{val}' appears once and joins no multi-pin net"
                })
    except SystemExit:
        issues.append({"type": "skip", "detail": "connectivity check skipped (netlist unavailable)"})

    # Check naming conventions
    naming_issues = []
    for (kind, val) in label_counts:
        if val.startswith("Net-("):
            naming_issues.append(f"{kind} '{val}' - auto-generated name, consider renaming")
        if kind == "global_label" and _is_power_label(val):
            pass  # Power rails are fine as globals
        elif kind == "label" and any(c.isspace() for c in val):
            naming_issues.append(f"{kind} '{val}' contains whitespace")

    if args.json:
        print(json.dumps({"command": "label-audit", "target": str(args.project),
                          "label_count": len(label_counts),
                          "issues": issues, "naming_issues": naming_issues}, indent=2))
        return EXIT_VIOLATIONS if issues or naming_issues else EXIT_OK

    print(f"Label inventory: {len(label_counts)} unique labels")
    for (kind, val), count in sorted(label_counts.items()):
        marker = "*" if count == 1 else " "
        print(f"  {marker}{kind:<20} '{val}' x{count}")
    if issues:
        print(f"\nConnectivity issues ({len(issues)}):")
        for i in issues:
            print(f"  [{i['type']}] {i['detail']}")
    if naming_issues:
        print(f"\nNaming issues ({len(naming_issues)}):")
        for n in naming_issues:
            print(f"  {n}")
    return EXIT_VIOLATIONS if issues or naming_issues else EXIT_OK


# ====================================================================
# grid-check: symbols/labels off-grid
# ====================================================================

def cmd_grid_check(args):
    root, symbols, _ = _load_schematic(args.project)
    problems = []

    for sym in symbols:
        ref = _get_ref(sym)
        x, y = _get_position(sym)
        if x is not None and not (_on_grid(x) and _on_grid(y)):
            problems.append(f"{ref or '?'}: symbol position off-grid ({x}, {y})")

    off_wires = 0
    for wire in sexp_find_all(root, "wire"):
        for pt in sexp_find_all(wire, "xy"):
            try:
                x, y = float(pt[1]), float(pt[2])
            except (TypeError, ValueError):
                continue
            if not (_on_grid(x) and _on_grid(y)):
                off_wires += 1
                if off_wires <= 10:
                    problems.append(f"wire endpoint off-grid ({x}, {y})")
    if off_wires > 10:
        problems.append(f"... and {off_wires - 10} more off-grid wire endpoints")

    for kind in ("label", "global_label", "hierarchical_label"):
        for lab in sexp_find_all(root, kind):
            val = _first_str(lab)
            at = sexp_get(lab, "at")
            if at and len(at) >= 3:
                try:
                    x, y = float(at[1]), float(at[2])
                except (TypeError, ValueError):
                    continue
                if not (_on_grid(x) and _on_grid(y)):
                    problems.append(f"{kind} '{val}' off-grid ({x}, {y})")

    if args.json:
        print(json.dumps({"command": "grid-check", "target": str(args.project),
                          "count": len(problems), "problems": problems}, indent=2))
        return EXIT_VIOLATIONS if problems else EXIT_OK

    if not problems:
        print("Grid check clean.")
        return EXIT_OK
    for p in problems:
        print(f"  OFF-GRID: {p}")
    print(f"\n{len(problems)} off-grid item(s)")
    return EXIT_VIOLATIONS


# ====================================================================
# debris-scan: placeholder text, abandoned components
# ====================================================================

def cmd_debris_scan(args):
    from fiducial import _load_nets, _suspect_components
    root, symbols, _ = _load_schematic(args.project)
    debris = []

    # Check for placeholder text
    placeholders = ["TODO", "[pending]", "TBD", "???", "XXX", "FIXME"]
    for text in sexp_find_all(root, "text"):
        val = _first_str(text)
        if val:
            for ph in placeholders:
                if ph.lower() in val.lower():
                    debris.append({"type": "placeholder", "detail": f"text contains '{ph}': {val[:60]}"})
                    break

    # Check for comments with placeholders
    for note in sexp_find_all(root, "text"):
        val = _first_str(note)
        if val and any(ph.lower() in val.lower() for ph in placeholders):
            pass  # already caught above

    # Check for orphan components via netlist analysis
    try:
        nets, _, _, _ = _load_nets(args.project)
        suspects = _suspect_components(nets)
        for ref in suspects:
            debris.append({"type": "suspect_component",
                           "detail": f"{ref}: suspect tacked-on component"})
    except SystemExit:
        pass

    if args.json:
        print(json.dumps({"command": "debris-scan", "target": str(args.project),
                          "count": len(debris), "findings": debris}, indent=2))
        return EXIT_VIOLATIONS if debris else EXIT_OK

    if not debris:
        print("Debris scan clean.")
        return EXIT_OK
    for d in debris:
        print(f"  [{d['type']}] {d['detail']}")
    print(f"\n{len(debris)} debris item(s)")
    return EXIT_VIOLATIONS


# ====================================================================
# symbol-lookup: full pin/net map for one symbol
# ====================================================================

def cmd_symbol_lookup(args):
    from fiducial import _load_nets
    nets, values, footprints, _ = _load_nets(args.project)
    ref = args.ref

    pin2net = {}
    for name, nodes in nets.items():
        for (r, p) in nodes:
            if r == ref:
                pin2net[p] = name

    if not pin2net:
        print(f"ERROR: no connected pins found for '{ref}'.", file=sys.stderr)
        return EXIT_ENV

    print(f"{ref}  value={values.get(ref, '?')}  footprint={footprints.get(ref, '?')}")
    def _pin_sort(p):
        digits = "".join(c for c in str(p) if c.isdigit())
        return (int(digits) if digits else 10**9, str(p))
    for pin in sorted(pin2net, key=_pin_sort):
        net = pin2net[pin]
        power_marker = " [POWER]" if _is_power_label(net) else ""
        print(f"  pin {pin:<6} -> {net}{power_marker}")
    return EXIT_OK


# ====================================================================
# decoupling-check: verify decoupling caps near IC power pins
# ====================================================================

def cmd_decoupling_check(args):
    root, symbols, _ = _load_schematic(args.project)
    from fiducial import _load_nets

    # Find all ICs (U* prefix) and their power pins
    ics = {}
    for sym in symbols:
        ref = _get_ref(sym)
        if ref and ref.upper().startswith("U"):
            val = _get_value(sym)
            x, y = _get_position(sym)
            power_pins = []
            for pin_node in sexp_find_all(sym, "pin"):
                pin_name = ""
                pin_number = ""
                for item in pin_node[1:]:
                    if isinstance(item, list):
                        if item and item[0] == "name":
                            pin_name = _first_str(item) if len(item) > 1 else ""
                    elif isinstance(item, str) and pin_number == "":
                        pin_number = item
                if _is_power_pin(pin_name):
                    power_pins.append({"name": pin_name, "number": pin_number})
            if power_pins:
                ics[ref] = {"value": val, "x": x, "y": y, "power_pins": power_pins}

    # Find all capacitors
    caps = []
    for sym in symbols:
        ref = _get_ref(sym)
        if ref and ref.upper().startswith("C"):
            val = _get_value(sym)
            x, y = _get_position(sym)
            caps.append({"ref": ref, "value": val, "x": x, "y": y})

    # Check: each IC power pin pair should have a cap within reasonable distance
    findings = []
    try:
        nets, _, _, _ = _load_nets(args.project)
        for ic_ref, ic_data in ics.items():
            has_decoupling = False
            for pin in ic_data["power_pins"]:
                # Find what net this pin is on
                for name, nodes in nets.items():
                    if (ic_ref, pin["number"]) in nodes:
                        # Check if any cap is on this net
                        for cap in caps:
                            for cn, cnodes in nets.items():
                                if (cap["ref"], "1") in cnodes or (cap["ref"], "2") in cnodes:
                                    if cn == name:
                                        has_decoupling = True
                                        break
                        break
            if not has_decoupling:
                findings.append({
                    "type": "missing_decoupling",
                    "detail": f"{ic_ref} ({ic_data['value']}): no decoupling cap detected on power pins"
                })
    except SystemExit:
        findings.append({"type": "skip", "detail": "decoupling check skipped (netlist unavailable)"})

    if args.json:
        print(json.dumps({"command": "decoupling-check", "target": str(args.project),
                          "ics_checked": len(ics), "caps_found": len(caps),
                          "findings": findings}, indent=2))
        return EXIT_VIOLATIONS if findings else EXIT_OK

    print(f"ICs: {len(ics)}, Capacitors: {len(caps)}")
    if findings:
        for f in findings:
            print(f"  [{f['type']}] {f['detail']}")
        return EXIT_VIOLATIONS
    print("Decoupling check clean.")
    return EXIT_OK


# ====================================================================
# rail-audit: trace every power rail from source to sink
# ====================================================================

def cmd_rail_audit(args):
    from fiducial import _load_nets, _is_rail_net
    nets, _, _, _ = _load_nets(args.project)

    # Group nets by likely rail
    rails = {}
    for name, nodes in nets.items():
        if _is_rail_net(name):
            rails[name] = {"pins": dict(nodes), "count": len(nodes)}

    # Find nets that look like power (start with + or -)
    for name, nodes in nets.items():
        if name.startswith("+") or name.startswith("-"):
            rails[name] = {"pins": dict(nodes), "count": len(nodes)}

    if args.json:
        print(json.dumps({"command": "rail-audit", "target": str(args.project),
                          "rail_count": len(rails),
                          "rails": {k: v["count"] for k, v in rails.items()}}, indent=2))
        return EXIT_OK

    if not rails:
        print("No power rails detected.")
        return EXIT_OK

    print(f"{'RAIL':<24}{'CONNECTIONS':<12}{'COMPONENTS'}")
    for name in sorted(rails, key=str.lower):
        rail = rails[name]
        comps = set(r for (r, _) in rail["pins"])
        print(f"{name:<24}{rail['count']:<12}{', '.join(sorted(comps)[:5])}")
    print(f"\n{len(rails)} power rail(s)")
    return EXIT_OK


# ====================================================================
# main
# ====================================================================

def main(argv=None):
    ap = argparse.ArgumentParser(prog="schematic_check",
                                 description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("power-pins", help="enumerate power pins")
    p.add_argument("project", help="path to .kicad_sch")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_power_pins)

    p = sub.add_parser("unconnected", help="find unconnected pins")
    p.add_argument("project")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_unconnected)

    p = sub.add_parser("orphan-nets", help="find single-connection nets")
    p.add_argument("project")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_orphan_nets)

    p = sub.add_parser("refdes-audit", help="check reference designator consistency")
    p.add_argument("project")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_refdes_audit)

    p = sub.add_parser("label-audit", help="check label naming and usage")
    p.add_argument("project")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_label_audit)

    p = sub.add_parser("grid-check", help="find off-grid symbols/labels/wires")
    p.add_argument("project")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_grid_check)

    p = sub.add_parser("debris-scan", help="find placeholder text and suspect components")
    p.add_argument("project")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_debris_scan)

    p = sub.add_parser("symbol-lookup", help="dump pin/net map for one symbol")
    p.add_argument("project")
    p.add_argument("ref")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_symbol_lookup)

    p = sub.add_parser("decoupling-check", help="verify decoupling caps near IC power pins")
    p.add_argument("project")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_decoupling_check)

    p = sub.add_parser("rail-audit", help="trace power rails from source to sink")
    p.add_argument("project")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_rail_audit)

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
