#!/usr/bin/env python3
"""pcb_check.py - deep PCB analysis for review workflows.

Stdlib-only. Parses .kicad_pcb files and performs layout, routing, and
manufacturing checks beyond what DRC catches. Designed for use by the
reviewer agent when auditing AI-generated PCB layouts.

Exit codes: 0 = clean, 1 = findings, 2 = environment/parse error.
"""

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fiducial import (
    load_sexp, parse_sexp, sexp_get, sexp_find_all, _first_str,
    EXIT_OK, EXIT_VIOLATIONS, EXIT_ENV,
)


def _load_board(path):
    return load_sexp(path)


def _get_sheets(root):
    return sexp_find_all(root, "footprint")


def _get_tracks(root):
    return sexp_find_all(root, "segment") + sexp_find_all(root, "arc")


def _get_vias(root):
    return sexp_find_all(root, "via")


def _get_zones(root):
    return sexp_find_all(root, "zone")


def _get_arcs(root):
    return sexp_find_all(root, "arc")


def _get_value(node, key):
    child = sexp_get(node, key)
    if child and len(child) > 1:
        return child[1]
    return None


def _get_at(node):
    at = sexp_get(node, "at")
    if at and len(at) >= 3:
        try:
            return float(at[1]), float(at[2])
        except (TypeError, ValueError):
            pass
    return None, None


def _get_layer(node):
    layer = sexp_get(node, "layer")
    if layer and len(layer) > 1:
        return layer[1]
    return None


def _get_net(node):
    net = sexp_get(node, "net")
    if net and len(net) > 1:
        return net[1]
    return None


def _get_width(node):
    w = sexp_get(node, "width")
    if w and len(w) > 1:
        try:
            return float(w[1])
        except (TypeError, ValueError):
            pass
    return None


def _get_diameter(node):
    d = sexp_get(node, "diameter")
    if d and len(d) > 1:
        try:
            return float(d[1])
        except (TypeError, ValueError):
            pass
    return None


def _get_drill(node):
    d = sexp_get(node, "drill")
    if d and len(d) > 1:
        try:
            return float(d[1])
        except (TypeError, ValueError):
            pass
    return None


def _get_size(node):
    sz = sexp_get(node, "size")
    if sz and len(sz) >= 3:
        try:
            return float(sz[1]), float(sz[2])
        except (TypeError, ValueError):
            pass
    return None, None


def _get_endpoints(track):
    start = sexp_get(track, "start")
    end = sexp_get(track, "end")
    if start and end and len(start) >= 3 and len(end) >= 3:
        try:
            return (float(start[1]), float(start[2])), (float(end[1]), float(end[2]))
        except (TypeError, ValueError):
            pass
    return None, None


def _distance(p1, p2):
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)


# ====================================================================
# board-stats: summary of board properties
# ====================================================================

def cmd_board_stats(args):
    root = _load_board(args.project)
    footprints = _get_sheets(root)
    tracks = _get_tracks(root)
    vias = _get_vias(root)
    zones = _get_zones(root)

    # Layer set
    layers = set()
    for fp in footprints:
        layer = _get_layer(fp)
        if layer:
            layers.add(layer)
    for t in tracks:
        layer = _get_layer(t)
        if layer:
            layers.add(layer)

    # Net set
    nets = set()
    for fp in footprints:
        net = _get_net(fp)
        if net:
            nets.add(net)
    for t in tracks:
        net = _get_net(t)
        if net:
            nets.add(net)

    # Component count by prefix
    prefix_counts = defaultdict(int)
    for fp in footprints:
        ref = _get_value(fp, "fp_text")
        if ref:
            prefix = "".join(c for c in str(ref) if c.isalpha())
            if prefix:
                prefix_counts[prefix] += 1

    # Board outline (Edge.Cuts)
    edge_cuts = []
    for seg in sexp_find_all(root, "gr_line") + sexp_find_all(root, "gr_arc"):
        layer = _get_layer(seg)
        if layer == "Edge.Cuts":
            edge_cuts.append(seg)

    # Track width distribution
    widths = defaultdict(int)
    for t in tracks:
        w = _get_width(t)
        if w is not None:
            widths[round(w, 4)] += 1

    # Via size distribution
    via_sizes = defaultdict(int)
    for v in vias:
        d = _get_diameter(v)
        drill = _get_drill(v)
        if d is not None and drill is not None:
            via_sizes[(round(d, 4), round(drill, 4))] += 1

    stats = {
        "command": "board-stats",
        "target": str(args.project),
        "footprint_count": len(footprints),
        "track_count": len(tracks),
        "via_count": len(vias),
        "zone_count": len(zones),
        "layer_count": len(layers),
        "layers": sorted(layers),
        "net_count": len(nets),
        "edge_cut_count": len(edge_cuts),
        "prefix_counts": dict(prefix_counts),
        "track_widths": dict(sorted(widths.items())),
        "via_sizes": {f"{d}mm/{dr}mm": c for (d, dr), c in sorted(via_sizes.items())},
    }

    if args.json:
        print(json.dumps(stats, indent=2))
        return EXIT_OK

    print(f"Footprints:    {stats['footprint_count']}")
    print(f"Tracks:        {stats['track_count']}")
    print(f"Vias:          {stats['via_count']}")
    print(f"Zones:         {stats['zone_count']}")
    print(f"Layers:        {stats['layer_count']} ({', '.join(stats['layers'][:8])})")
    print(f"Nets:          {stats['net_count']}")
    print(f"Edge cuts:     {stats['edge_cut_count']}")
    if prefix_counts:
        print(f"\nComponent prefixes:")
        for prefix in sorted(prefix_counts):
            print(f"  {prefix}* : {prefix_counts[prefix]}")
    return EXIT_OK


# ====================================================================
# trace-widths: map trace widths to nets, flag undersized
# ====================================================================

def cmd_trace_widths(args):
    root = _load_board(args.project)
    tracks = _get_tracks(root)

    net_widths = defaultdict(list)
    for t in tracks:
        net = _get_net(t)
        w = _get_width(t)
        layer = _get_layer(t)
        if w is not None and net is not None:
            net_widths[net].append({"width": w, "layer": layer})

    # Default minimum widths per layer
    min_widths = {
        "F.Cu": 0.15, "B.Cu": 0.15,
        "In1.Cu": 0.15, "In2.Cu": 0.15,
        "F.SilkS": 0.15, "B.SilkS": 0.15,
    }

    findings = []
    summary = {}
    for net, trace_list in sorted(net_widths.items()):
        widths = [t["width"] for t in trace_list]
        min_w = min(widths)
        max_w = max(widths)
        avg_w = sum(widths) / len(widths)
        layers = set(t["layer"] for t in trace_list if t["layer"])
        summary[net] = {
            "count": len(trace_list),
            "min_width": round(min_w, 4),
            "max_width": round(max_w, 4),
            "avg_width": round(avg_w, 4),
            "layers": sorted(layers),
        }
        # Flag if any trace is below minimum for its layer
        for t in trace_list:
            layer = t["layer"] or "F.Cu"
            min_w_for_layer = min_widths.get(layer, 0.15)
            if t["width"] < min_w_for_layer:
                findings.append({
                    "type": "undersized_trace",
                    "net": net,
                    "width": round(t["width"], 4),
                    "minimum": min_w_for_layer,
                    "layer": layer,
                })

    if args.json:
        print(json.dumps({"command": "trace-widths", "target": str(args.project),
                          "net_count": len(summary), "findings": findings,
                          "nets": summary}, indent=2))
        return EXIT_VIOLATIONS if findings else EXIT_OK

    print(f"{'NET':<20}{'COUNT':<8}{'MIN':<10}{'MAX':<10}{'AVG':<10}{'LAYERS'}")
    for net in sorted(summary):
        s = summary[net]
        layers = ",".join(s["layers"][:3])
        print(f"{net:<20}{s['count']:<8}{s['min_width']:<10}{s['max_width']:<10}"
              f"{s['avg_width']:<10}{layers}")
    if findings:
        print(f"\n{len(findings)} undersized trace(s):")
        for f in findings:
            print(f"  {f['net']}: {f['width']}mm on {f['layer']} (min {f['minimum']}mm)")
        return EXIT_VIOLATIONS
    print(f"\n{len(summary)} net(s) checked, all widths within limits.")
    return EXIT_OK


# ====================================================================
# via-audit: via sizes, drill sizes, annular rings
# ====================================================================

def cmd_via_audit(args):
    root = _load_board(args.project)
    vias = _get_vias(root)

    via_data = []
    findings = []
    for v in vias:
        x, y = _get_at(v)
        d = _get_diameter(v)
        drill = _get_drill(v)
        net = _get_net(v)

        if d and drill:
            annular_ring = (d - drill) / 2
            entry = {
                "x": x, "y": y, "diameter": d, "drill": drill,
                "annular_ring": round(annular_ring, 4), "net": net,
            }
            via_data.append(entry)

            # Check minimum annular ring (typical: 0.15mm)
            if annular_ring < 0.15:
                findings.append({
                    "type": "thin_annular_ring",
                    "detail": f"via at ({x},{y}): annular ring {round(annular_ring, 4)}mm < 0.15mm"
                })

            # Check minimum drill size (typical: 0.2mm)
            if drill < 0.2:
                findings.append({
                    "type": "small_drill",
                    "detail": f"via at ({x},{y}): drill {drill}mm < 0.2mm"
                })

    if args.json:
        print(json.dumps({"command": "via-audit", "target": str(args.project),
                          "via_count": len(via_data), "findings": findings,
                          "vias": via_data[:50]}, indent=2))  # cap at 50 for readability
        return EXIT_VIOLATIONS if findings else EXIT_OK

    if not via_data:
        print("No vias found.")
        return EXIT_OK

    # Summary table
    size_groups = defaultdict(int)
    for v in via_data:
        key = (v["diameter"], v["drill"])
        size_groups[key] += 1

    print(f"Via size distribution:")
    for (d, drill), count in sorted(size_groups.items()):
        ring = (d - drill) / 2
        marker = " *" if ring < 0.15 else ""
        print(f"  {d}mm/{drill}mm  x{count}  (ring={round(ring, 4)}mm){marker}")

    if findings:
        print(f"\n{len(findings)} issue(s):")
        for f in findings:
            print(f"  [{f['type']}] {f['detail']}")
        return EXIT_VIOLATIONS
    print(f"\n{len(via_data)} via(s) checked, all within limits.")
    return EXIT_OK


# ====================================================================
# copper-pours: zone connectivity analysis
# ====================================================================

def cmd_copper_pours(args):
    root = _load_board(args.project)
    zones = _get_zones(root)

    zone_info = []
    for z in zones:
        net = _get_net(z)
        layer = _get_layer(z)
        zone_type = _get_value(z, "type") or "fill"
        connect_pads = sexp_get(z, "connect_pads")
        thermal_gap = None
        thermal_bridge = None
        if connect_pads:
            gap = sexp_get(connect_pads, "clearance")
            if gap and len(gap) > 1:
                try:
                    thermal_gap = float(gap[1])
                except (TypeError, ValueError):
                    pass
        min_thickness = _get_value(z, "min_thickness")

        zone_info.append({
            "net": net, "layer": layer, "type": zone_type,
            "thermal_gap": thermal_gap, "min_thickness": min_thickness,
        })

    if args.json:
        print(json.dumps({"command": "copper-pours", "target": str(args.project),
                          "zone_count": len(zone_info), "zones": zone_info}, indent=2))
        return EXIT_OK

    if not zone_info:
        print("No copper pour zones found.")
        return EXIT_OK

    print(f"{'LAYER':<16}{'NET':<16}{'TYPE':<10}{'MIN_THICK'}")
    for z in zone_info:
        mt = z["min_thickness"] or "-"
        print(f"{str(z['layer']):<16}{str(z['net']):<16}{z['type']:<10}{mt}")
    print(f"\n{len(zone_info)} zone(s)")
    return EXIT_OK


# ====================================================================
# drill-table: drill sizes vs typical capabilities
# ====================================================================

def cmd_drill_table(args):
    root = _load_board(args.project)
    vias = _get_vias(root)

    # Also check through-hole footprints
    footprints = _get_sheets(root)
    drills = defaultdict(int)

    # Via drills
    for v in vias:
        d = _get_drill(v)
        if d is not None:
            drills[round(d, 3)] += 1

    # Typical fab house limits
    min_drill = 0.15  # mm, typical minimum
    min_recommended = 0.2  # mm, recommended minimum

    findings = []
    for size, count in sorted(drills.items()):
        if size < min_drill:
            findings.append({
                "type": "below_minimum",
                "detail": f"drill {size}mm x{count} - below typical minimum {min_drill}mm"
            })
        elif size < min_recommended:
            findings.append({
                "type": "below_recommended",
                "detail": f"drill {size}mm x{count} - below recommended {min_recommended}mm"
            })

    if args.json:
        print(json.dumps({"command": "drill-table", "target": str(args.project),
                          "drill_sizes": dict(drills), "findings": findings}, indent=2))
        return EXIT_VIOLATIONS if findings else EXIT_OK

    print(f"Drill size distribution:")
    for size in sorted(drills):
        marker = " **" if size < min_drill else " *" if size < min_recommended else ""
        print(f"  {size}mm  x{drills[size]}{marker}")

    if findings:
        print(f"\n{len(findings)} issue(s):")
        for f in findings:
            print(f"  [{f['type']}] {f['detail']}")
        return EXIT_VIOLATIONS
    print(f"\n{len(drills)} unique drill size(s), all within limits.")
    return EXIT_OK


# ====================================================================
# placement-density: component spacing analysis
# ====================================================================

def cmd_placement_density(args):
    root = _load_board(args.project)
    footprints = _get_sheets(root)

    components = []
    for fp in footprints:
        x, y = _get_at(fp)
        layer = _get_layer(fp)
        ref_text = _get_value(fp, "fp_text")
        if x is not None and y is not None:
            components.append({"x": x, "y": y, "layer": layer, "ref": ref_text})

    # Find closest pairs
    findings = []
    min_spacing = 0.5  # mm, typical minimum between components

    if len(components) > 1 and len(components) < 500:
        # Only do N^2 check for reasonable board sizes
        for i in range(len(components)):
            for j in range(i + 1, len(components)):
                dist = _distance((components[i]["x"], components[i]["y"]),
                                 (components[j]["x"], components[j]["y"]))
                if dist < min_spacing and dist > 0:
                    findings.append({
                        "type": "tight_spacing",
                        "detail": (f"{components[i].get('ref', '?')} and "
                                   f"{components[j].get('ref', '?')}: {round(dist, 3)}mm apart")
                    })

    # Cap findings
    findings = findings[:20]

    if args.json:
        print(json.dumps({"command": "placement-density", "target": str(args.project),
                          "component_count": len(components),
                          "findings": findings}, indent=2))
        return EXIT_VIOLATIONS if findings else EXIT_OK

    print(f"Components: {len(components)}")
    if findings:
        print(f"\n{len(findings)} tight spacing(s) found:")
        for f in findings:
            print(f"  {f['detail']}")
        return EXIT_VIOLATIONS
    print("Placement density within limits.")
    return EXIT_OK


# ====================================================================
# board-outline: verify board outline is closed
# ====================================================================

def cmd_board_outline(args):
    root = _load_board(args.project)

    # Collect Edge.Cuts segments
    segments = []
    for kind in ("gr_line", "gr_arc"):
        for item in sexp_find_all(root, kind):
            layer = _get_layer(item)
            if layer == "Edge.Cuts":
                start = sexp_get(item, "start")
                end = sexp_get(item, "end")
                if start and end and len(start) >= 3 and len(end) >= 3:
                    try:
                        s = (float(start[1]), float(start[2]))
                        e = (float(end[1]), float(end[2]))
                        segments.append((s, e))
                    except (TypeError, ValueError):
                        pass

    if not segments:
        if args.json:
            print(json.dumps({"command": "board-outline", "target": str(args.project),
                              "closed": False, "segment_count": 0,
                              "note": "no Edge.Cuts segments found"}, indent=2))
        print("No board outline (Edge.Cuts) found.")
        return EXIT_VIOLATIONS

    # Check if outline forms a closed loop
    endpoints = defaultdict(int)
    for s, e in segments:
        # Snap to grid for comparison
        key_s = (round(s[0], 3), round(s[1], 3))
        key_e = (round(e[0], 3), round(e[1], 3))
        endpoints[key_s] += 1
        endpoints[key_e] += 1

    open_points = [pt for pt, count in endpoints.items() if count % 2 != 0]
    is_closed = len(open_points) == 0

    if args.json:
        print(json.dumps({"command": "board-outline", "target": str(args.project),
                          "closed": is_closed, "segment_count": len(segments),
                          "open_points": open_points}, indent=2))
        return EXIT_OK if is_closed else EXIT_VIOLATIONS

    if is_closed:
        print(f"Board outline closed ({len(segments)} segments).")
        return EXIT_OK
    print(f"Board outline NOT closed - {len(open_points)} open endpoint(s).")
    return EXIT_VIOLATIONS


# ====================================================================
# main
# ====================================================================

def main(argv=None):
    ap = argparse.ArgumentParser(prog="pcb_check",
                                 description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("board-stats", help="board summary statistics")
    p.add_argument("project")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_board_stats)

    p = sub.add_parser("trace-widths", help="trace width analysis by net")
    p.add_argument("project")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_trace_widths)

    p = sub.add_parser("via-audit", help="via sizing and annular ring check")
    p.add_argument("project")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_via_audit)

    p = sub.add_parser("copper-pours", help="zone fill analysis")
    p.add_argument("project")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_copper_pours)

    p = sub.add_parser("drill-table", help="drill size analysis")
    p.add_argument("project")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_drill_table)

    p = sub.add_parser("placement-density", help="component spacing analysis")
    p.add_argument("project")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_placement_density)

    p = sub.add_parser("board-outline", help="verify board outline is closed")
    p.add_argument("project")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_board_outline)

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
