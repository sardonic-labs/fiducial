"""Structural checks: geometry, lint, house rules, and overlap detection."""

import csv
import json
import sys

from fidcore.const import EXIT_ENV, EXIT_OK, EXIT_VIOLATIONS
from fidcore.netlist import (_first_str, _is_rail_net, _load_nets, _orphan_clusters,
                              _orphan_nets, _suspect_components)
from fidcore.sexp import load_sexp, sexp_find_all, sexp_get

_GRID_MM = 1.27  # KiCad default schematic placement grid (50 mil)
_GRID_TOL = 0.01


def _on_grid(v):
    return abs(v / _GRID_MM - round(v / _GRID_MM)) <= _GRID_TOL


def _geometry_problems(root):
    """Off-grid positions for symbol instances, wire endpoints, and labels."""
    problems = []
    for sym in [s for s in sexp_find_all(root, "symbol")
                if any(isinstance(i, list) and i and i[0] == "instances" for i in s)]:
        ref = None
        for prop in sexp_find_all(sym, "property"):
            if len(prop) >= 3 and prop[1] == "Reference":
                ref = prop[2]
        at = sexp_get(sym, "at")
        if at is None or len(at) < 3:
            continue
        try:
            x, y = float(at[1]), float(at[2])
        except (TypeError, ValueError):
            continue
        if not (_on_grid(x) and _on_grid(y)):
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
            if at is None or len(at) < 3:
                continue
            try:
                x, y = float(at[1]), float(at[2])
            except (TypeError, ValueError):
                continue
            if not (_on_grid(x) and _on_grid(y)):
                problems.append(f"{kind} '{val}' off-grid ({x}, {y})")
    return problems


def _label_net(val, nets):
    """Net a sheet label merges into, or None."""
    for cand in ("/" + val, val):
        if cand in nets:
            return cand
    return None


def _load_allow_single_use(rules_path):
    """Load label names from a rules CSV that have rule == allow-single-use."""
    allowed = set()
    if not rules_path:
        return allowed
    with open(rules_path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row.get("rule", "").strip() == "allow-single-use":
                name = row.get("net", "").strip()
                if name:
                    allowed.add(name)
    return allowed


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
    problems.extend(_geometry_problems(root))
    allow_single = _load_allow_single_use(getattr(args, "rules", None))
    if nets is not None:
        for (kind, val), count in sorted(label_counts.items(), key=lambda kv: str(kv[0])):
            net = _label_net(val, nets)
            merged = net is not None and len(nets[net]) > 1
            if count == 1 and not merged and val not in allow_single:
                problems.append(f"{kind} '{val}' appears only once and does not "
                                f"join any multi-pin net - likely a typo")
        for name, ref, pin in _orphan_nets(nets):
            problems.append(f"net '{name}' has a single connection "
                            f"({ref}.{pin}) - dangling?")
        for cluster in _orphan_clusters(nets):
            problems.append("isolated cluster without connector or IC: "
                            + ", ".join(cluster)
                            + " - leftover from an earlier iteration?")
        for ref in _suspect_components(nets):
            problems.append(f"{ref}: suspect tacked-on component (all nets "
                            f"dangling or point-to-point) - review, likely "
                            f"leftover from an earlier iteration")
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
        elif rule == "allow-single-use":
            # Handled by lint; no-op in check-rules.
            pass
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


def _coord_key(x, y):
    """Canonical string key for a coordinate pair."""
    return f"{x:.6f},{y:.6f}"


def cmd_overlap_check(args):
    """Detect wires from different nets sharing a coordinate (silent shorts)."""
    root = load_sexp(args.project)

    # --- collect wires ---
    wires = []
    for wire in sexp_find_all(root, "wire"):
        pts = sexp_find_all(wire, "xy")
        if len(pts) < 2:
            continue
        try:
            x1, y1 = float(pts[0][1]), float(pts[0][2])
            x2, y2 = float(pts[1][1]), float(pts[1][2])
        except (TypeError, ValueError, IndexError):
            continue
        wires.append({"p1": (x1, y1), "p2": (x2, y2)})

    # --- build adjacency: coord -> set of wire indices ---
    adj = {}
    for i, w in enumerate(wires):
        for pt in (w["p1"], w["p2"]):
            adj.setdefault(_coord_key(*pt), set()).add(i)

    # --- collect nets from labels ---
    coord_nets = {}
    for kind in ("label", "global_label", "hierarchical_label"):
        for lab in sexp_find_all(root, kind):
            val = _first_str(lab)
            if not val:
                continue
            at = sexp_get(lab, "at")
            if at is None or len(at) < 3:
                continue
            try:
                x, y = float(at[1]), float(at[2])
            except (TypeError, ValueError):
                continue
            coord_nets.setdefault(_coord_key(x, y), set()).add(val)

    # --- collect no-connect markers ---
    for nc in sexp_find_all(root, "no_connect"):
        at = sexp_get(nc, "at")
        if at is None or len(at) < 3:
            continue
        try:
            x, y = float(at[1]), float(at[2])
        except (TypeError, ValueError):
            continue
        coord_nets.setdefault(_coord_key(x, y), set()).add("no_connect")

    # --- collect power symbols (lib_id starting with "power:") ---
    for sym in sexp_find_all(root, "symbol"):
        lib_node = sexp_get(sym, "lib_id")
        lib_id = _first_str(lib_node) if lib_node else ""
        if not lib_id.startswith("power:"):
            continue
        at = sexp_get(sym, "at")
        if at is None or len(at) < 3:
            continue
        try:
            x, y = float(at[1]), float(at[2])
        except (TypeError, ValueError):
            continue
        power_net = lib_id.split(":", 1)[1]
        coord_nets.setdefault(_coord_key(x, y), set()).add(power_net)

    # --- assign nets to wires by flood fill from labeled coordinates ---
    wire_nets = [None] * len(wires)
    for coord, nets in coord_nets.items():
        if coord not in adj:
            continue
        for wi in adj[coord]:
            if wire_nets[wi] is None:
                wire_nets[wi] = nets

    changed = True
    while changed:
        changed = False
        for coord, wire_ids in adj.items():
            wire_list = list(wire_ids)
            assigned = [wire_nets[i] for i in wire_list if wire_nets[i] is not None]
            if assigned:
                merged = set()
                for s in assigned:
                    merged |= s
                for i in wire_list:
                    if wire_nets[i] is None:
                        wire_nets[i] = merged
                        changed = True

    # --- detect overlaps: coord with 2+ different non-trivial nets ---
    overlaps = []
    for coord, wire_ids in adj.items():
        nets_here = set()
        for wi in wire_ids:
            if wire_nets[wi] is not None:
                nets_here |= wire_nets[wi]
        nets_here -= {"no_connect"}
        if len(nets_here) < 2:
            continue
        wires_here = sorted(wire_ids)
        overlaps.append({
            "coord": coord,
            "nets": sorted(nets_here),
            "wires": wires_here,
        })

    if args.json:
        print(json.dumps({
            "command": "overlap-check",
            "target": str(args.project),
            "overlap_count": len(overlaps),
            "overlaps": overlaps,
        }, indent=2))
        return EXIT_VIOLATIONS if overlaps else EXIT_OK

    if not overlaps:
        print(f"overlap-check: clean ({len(wires)} wires)")
        return EXIT_OK
    for o in overlaps:
        print(f"OVERLAP at ({o['coord']}): nets {o['nets']} "
              f"(wire indices {o['wires']})")
    print(f"\n{len(overlaps)} overlap(s) found")
    return EXIT_VIOLATIONS
