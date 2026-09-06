"""Read-only diagnostics: pin positions, wire tracing, and label maps."""

import math
import sys

from fidcore.const import EXIT_ENV, EXIT_OK
from fidcore.netlist import _first_str, _load_nets, _pin_sort
from fidcore.sexp import load_sexp, sexp_find_all, sexp_get


def _compute_pin_positions(root, sym):
    """Return [(pin_name, pin_number, abs_x, abs_y)] for a symbol instance.

    Uses the symbol's ``(at x y rot)`` and its library definition inside
    ``(lib_symbols ...)`` to compute absolute pin endpoint positions in
    schematic space.
    """
    lib_syms = sexp_get(root, "lib_symbols")
    if lib_syms is None:
        return []
    lib_id_node = sexp_get(sym, "lib_id")
    if lib_id_node is None:
        return []
    lib_id = _first_str(lib_id_node)
    lib_sym = None
    for s in sexp_find_all(lib_syms, "symbol"):
        if s[1] == lib_id:
            lib_sym = s
            break
    if lib_sym is None:
        return []
    at = sexp_get(sym, "at")
    if at is None or len(at) < 3:
        return []
    try:
        sx, sy, srot = float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0
    except (TypeError, ValueError):
        return []
    srot_rad = srot * math.pi / 180.0
    cos_r, sin_r = math.cos(srot_rad), math.sin(srot_rad)
    pins = []
    for pin in sexp_find_all(lib_sym, "pin"):
        pat = sexp_get(pin, "at")
        if pat is None or len(pat) < 3:
            continue
        try:
            px, py = float(pat[1]), float(pat[2])
        except (TypeError, ValueError):
            continue
        ax = sx + px * cos_r - py * sin_r
        ay = sy + px * sin_r + py * cos_r
        name_node = sexp_get(pin, "name")
        number_node = sexp_get(pin, "number")
        pname = _first_str(name_node) if name_node else "?"
        pnum = _first_str(number_node) if number_node else "?"
        pins.append((pname, pnum, ax, ay))
    return pins


def cmd_pin_positions(args):
    root = load_sexp(args.project)
    ref = args.ref
    sym = None
    for s in sexp_find_all(root, "symbol"):
        for prop in sexp_find_all(s, "property"):
            if len(prop) >= 3 and prop[1] == "Reference" and prop[2] == ref:
                sym = s
                break
        if sym is not None:
            break
    if sym is None:
        print(f"ERROR: component '{ref}' not found in schematic", file=sys.stderr)
        return EXIT_ENV
    pins = _compute_pin_positions(root, sym)
    if not pins:
        lib_id_node = sexp_get(sym, "lib_id")
        lib_id = _first_str(lib_id_node) if lib_id_node else "?"
        print(f"WARNING: no pin definitions found for '{ref}' (lib_id={lib_id})",
              file=sys.stderr)
        return EXIT_OK
    nets, _, _, _ = _load_nets(args.project)
    pin2net = {}
    for name, nodes in nets.items():
        for (r, p) in nodes:
            if r == ref:
                pin2net[p] = name
    for pname, pnum, px, py in sorted(pins, key=lambda t: _pin_sort(t[1])):
        net = pin2net.get(pnum, "")
        suffix = f" -> {net}" if net else ""
        print(f"Pin {pnum}: ({px:.2f}, {py:.2f}){suffix}")
    return EXIT_OK


def _build_wire_graph(root):
    """Build an adjacency graph from wire endpoints.

    Returns dict mapping (x, y) -> set of (x, y) neighbours.
    """
    graph = {}
    for wire in sexp_find_all(root, "wire"):
        pts = sexp_get(wire, "pts")
        if pts is None:
            continue
        xys = sexp_find_all(pts, "xy")
        coords = []
        for pt in xys:
            if len(pt) >= 3:
                try:
                    coords.append((float(pt[1]), float(pt[2])))
                except (TypeError, ValueError):
                    continue
        for i in range(len(coords) - 1):
            a, b = coords[i], coords[i + 1]
            graph.setdefault(a, set()).add(b)
            graph.setdefault(b, set()).add(a)
    return graph


def _find_nearest_label(root, x, y, tol=0.05):
    """Find a label at approximately (x, y). Returns (kind, name) or None."""
    for kind in ("label", "global_label", "hierarchical_label"):
        for lab in sexp_find_all(root, kind):
            at = sexp_get(lab, "at")
            if at is None or len(at) < 3:
                continue
            try:
                lx, ly = float(at[1]), float(at[2])
            except (TypeError, ValueError):
                continue
            if abs(lx - x) <= tol and abs(ly - y) <= tol:
                return kind, _first_str(lab)
    return None


def cmd_wire_trace(args):
    root = load_sexp(args.project)
    ref, pin = args.ref, args.pin
    sym = None
    for s in sexp_find_all(root, "symbol"):
        for prop in sexp_find_all(s, "property"):
            if len(prop) >= 3 and prop[1] == "Reference" and prop[2] == ref:
                sym = s
                break
        if sym is not None:
            break
    if sym is None:
        print(f"ERROR: component '{ref}' not found", file=sys.stderr)
        return EXIT_ENV
    pins = _compute_pin_positions(root, sym)
    pin_pos = None
    for pname, pnum, px, py in pins:
        if pnum == pin or pname == pin:
            pin_pos = (px, py)
            break
    if pin_pos is None:
        print(f"ERROR: pin '{pin}' not found on '{ref}'", file=sys.stderr)
        return EXIT_ENV
    graph = _build_wire_graph(root)
    visited = set()
    stack = [pin_pos]
    found_label = None
    while stack:
        cur = stack.pop()
        if cur in visited:
            continue
        visited.add(cur)
        lab = _find_nearest_label(root, cur[0], cur[1])
        if lab is not None:
            found_label = lab
            break
        for nb in graph.get(cur, ()):
            if nb not in visited:
                stack.append(nb)
    x, y = pin_pos
    if found_label:
        kind, name = found_label
        print(f"{ref}.{pin} -> wire -> label \"{name}\" -> net {name}")
    else:
        nets, _, _, _ = _load_nets(args.project)
        net_name = None
        for n, nodes in nets.items():
            if (ref, pin) in nodes:
                net_name = n
                break
        if net_name:
            print(f"{ref}.{pin} -> net {net_name}")
        else:
            print(f"{ref}.{pin} -> (no connection found)")
    return EXIT_OK


def cmd_label_map(args):
    root = load_sexp(args.project)
    labels = []
    for kind in ("label", "global_label", "hierarchical_label"):
        for lab in sexp_find_all(root, kind):
            at = sexp_get(lab, "at")
            if at is None or len(at) < 3:
                continue
            try:
                x, y = float(at[1]), float(at[2])
            except (TypeError, ValueError):
                continue
            name = _first_str(lab)
            labels.append((name, kind, x, y))
    labels.sort(key=lambda t: (t[0], t[1], t[2], t[3]))
    by_name = {}
    for name, kind, x, y in labels:
        by_name.setdefault(name, []).append((kind, x, y))
    for name in sorted(by_name):
        entries = by_name[name]
        print(f"{name}")
        for kind, x, y in entries:
            tag = "" if kind == "label" else f" [{kind}]"
            print(f"  ({x:.2f}, {y:.2f}){tag}")
    return EXIT_OK
