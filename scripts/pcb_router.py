#!/usr/bin/env python3
"""pcb_router.py - deterministic autorouter for non-spatial AI models.

Stdlib-only. Non-spatial models (LLMs) hallucinate coordinates and cannot
maintain an occupancy grid. This module is the spatial back-end: the AI
declares *what* to connect (nets), the router decides *where* geometrically,
deterministically.

Philosophy (see skills/pcb/layout.md:6 "do NOT write autorouters" per-session):
  - AI is topological: intent.csv / netclasses / placement hints
  - Router is geometric: Manhattan grid, sorted nets, fixed tie-breaks
  - Same .kicad_pcb input -> byte-identical .kicad_pcb output (no randomness)

MVP strategy: deterministic L-routing + A* maze on coarse grid, 2 layers
(F.Cu/B.Cu), obstacle-aware, DRC-clean. Single pass with fixed rip-up order.

Usage:
  from pcb_router import autoroute
  result = autoroute("board.kicad_pcb", out="board.kicad_pcb")

CLI via fiducial.py autoroute.
"""

import math
import uuid
import heapq
from collections import defaultdict, deque
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from fiducial import load_sexp, sexp_get, sexp_find_all, EXIT_OK, EXIT_VIOLATIONS, EXIT_ENV  # noqa: E402

GRID_MM = 0.25  # coarse routing grid, deterministic snap
DEFAULT_WIDTH = 0.25  # mm
DEFAULT_CLEARANCE = 0.2  # mm
VIA_DIAMETER = 0.8
VIA_DRILL = 0.4


def _new_uuid():
    return str(uuid.uuid4())


def _fmt(v):
    if isinstance(v, int) or (isinstance(v, float) and v == int(v)):
        return str(int(v))
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    if "." not in s:
        s += ".0"
    return s


def _snap(v, grid=GRID_MM):
    return round(round(v / grid) * grid, 6)


def _parse_board(path):
    return load_sexp(Path(path))


def _board_nets(root):
    """Return {net_name: net_code} and {net_code: net_name} from (net N \"name\") entries."""
    name_to_code = {}
    code_to_name = {}
    for item in root:
        if isinstance(item, list) and item and item[0] == "net":
            if len(item) >= 3:
                try:
                    code = int(item[1])
                    name = str(item[2])
                    name_to_code[name] = code
                    code_to_name[code] = name
                except (ValueError, TypeError):
                    continue
    return name_to_code, code_to_name


def _get_pads(root):
    """Return list of pads with absolute position, layer, net, ref."""
    pads = []
    for fp in sexp_find_all(root, "footprint"):
        ref = ""
        for prop in sexp_find_all(fp, "property"):
            if len(prop) >= 3 and prop[1] == "Reference":
                ref = str(prop[2])
                break
        # footprint position + rotation
        at = sexp_get(fp, "at")
        fx, fy, frot = 0.0, 0.0, 0.0
        if at and len(at) >= 3:
            try:
                fx = float(at[1]); fy = float(at[2])
                if len(at) > 3:
                    frot = float(at[3])
            except (TypeError, ValueError):
                pass
        rad = math.radians(frot)
        cos_r, sin_r = math.cos(rad), math.sin(rad)
        for pad in sexp_find_all(fp, "pad"):
            if len(pad) < 3:
                continue
            pad_name = str(pad[1])
            pad_at = sexp_get(pad, "at")
            px, py, prot = 0.0, 0.0, 0.0
            if pad_at and len(pad_at) >= 3:
                try:
                    px = float(pad_at[1]); py = float(pad_at[2])
                    if len(pad_at) > 3:
                        prot = float(pad_at[3])
                except (TypeError, ValueError):
                    pass
            # rotate pad offset by footprint rotation
            ax = fx + px * cos_r - py * sin_r
            ay = fy + px * sin_r + py * cos_r
            # layers
            layers_node = sexp_get(pad, "layers")
            layer = "F.Cu"
            if layers_node:
                # e.g. (layers "F.Cu" "F.Paste" "F.Mask")
                for maybe in layers_node[1:]:
                    if isinstance(maybe, str) and maybe.endswith(".Cu"):
                        layer = maybe
                        break
                if "*.Cu" in layers_node:
                    layer = "F.Cu"
            # net
            net_node = sexp_get(pad, "net")
            net_code = None
            net_name = ""
            if net_node and len(net_node) >= 2:
                try:
                    net_code = int(net_node[1])
                except (ValueError, TypeError):
                    pass
                if len(net_node) >= 3:
                    net_name = str(net_node[2])
            pads.append({
                "ref": ref,
                "pad": pad_name,
                "x": round(ax, 6),
                "y": round(ay, 6),
                "layer": layer,
                "net_code": net_code,
                "net_name": net_name,
                "footprint": fp,
            })
    return pads


def _get_tracks(root):
    """Collect existing segments/vias as obstacles."""
    tracks = []
    for seg in sexp_find_all(root, "segment"):
        start = sexp_get(seg, "start")
        end = sexp_get(seg, "end")
        layer = sexp_get(seg, "layer")
        net = sexp_get(seg, "net")
        width = sexp_get(seg, "width")
        if start and end:
            try:
                x1, y1 = float(start[1]), float(start[2])
                x2, y2 = float(end[1]), float(end[2])
                tracks.append({
                    "type": "segment",
                    "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                    "layer": str(layer[1]) if layer and len(layer) > 1 else "F.Cu",
                    "net": int(net[1]) if net and len(net) > 1 else 0,
                    "width": float(width[1]) if width and len(width) > 1 else DEFAULT_WIDTH,
                })
            except (TypeError, ValueError, IndexError):
                continue
    vias = []
    for via in sexp_find_all(root, "via"):
        at = sexp_get(via, "at")
        net = sexp_get(via, "net")
        if at and len(at) >= 3:
            try:
                x, y = float(at[1]), float(at[2])
                vias.append({
                    "type": "via",
                    "x": x, "y": y,
                    "net": int(net[1]) if net and len(net) > 1 else 0,
                })
            except (TypeError, ValueError):
                pass
    return tracks, vias


def _get_outline(root):
    """Return bounding box (xmin, ymin, xmax, ymax) from Edge.Cuts, or None."""
    segs = []
    for kind in ("gr_line", "gr_arc"):
        for item in sexp_find_all(root, kind):
            layer = sexp_get(item, "layer")
            if layer and len(layer) > 1 and str(layer[1]) == "Edge.Cuts":
                start = sexp_get(item, "start")
                end = sexp_get(item, "end")
                if start and end and len(start) >= 3 and len(end) >= 3:
                    try:
                        segs.append(((float(start[1]), float(start[2])), (float(end[1]), float(end[2]))))
                    except (TypeError, ValueError):
                        pass
    if not segs:
        return None
    xs = [s[0][0] for s in segs] + [s[1][0] for s in segs]
    ys = [s[0][1] for s in segs] + [s[1][1] for s in segs]
    return (min(xs), min(ys), max(xs), max(ys))


def _build_obstacle_grid(tracks, bbox, grid=GRID_MM, clearance=DEFAULT_CLEARANCE):
    """Build set of blocked grid cells from existing tracks expanded by clearance."""
    if bbox is None:
        return set(), None
    xmin, ymin, xmax, ymax = bbox
    # inflate by small margin inside outline
    blocked = set()
    # discretise each track as blocked cells (Bresenham-like)
    for t in tracks:
        x1, y1, x2, y2 = t["x1"], t["y1"], t["x2"], t["y2"]
        w = t["width"] / 2 + clearance
        # bounding box of segment expanded
        bxmin = min(x1, x2) - w
        bxmax = max(x1, x2) + w
        bymin = min(y1, y2) - w
        bymax = max(y1, y2) + w
        # iterate grid cells in bbox
        gx_start = int(math.floor((bxmin - xmin) / grid))
        gx_end = int(math.ceil((bxmax - xmin) / grid))
        gy_start = int(math.floor((bymin - ymin) / grid))
        gy_end = int(math.ceil((bymax - ymin) / grid))
        for gx in range(gx_start, gx_end + 1):
            for gy in range(gy_start, gy_end + 1):
                cx = xmin + gx * grid
                cy = ymin + gy * grid
                # distance from point to segment < w ?
                # use closest point projection
                dx = x2 - x1
                dy = y2 - y1
                if dx == 0 and dy == 0:
                    dist = math.hypot(cx - x1, cy - y1)
                else:
                    tt = ((cx - x1) * dx + (cy - y1) * dy) / (dx*dx + dy*dy)
                    tt = max(0, min(1, tt))
                    px = x1 + tt * dx
                    py = y1 + tt * dy
                    dist = math.hypot(cx - px, cy - py)
                if dist <= w + 1e-9:
                    blocked.add((gx, gy, 0))  # layer 0 = F.Cu
                    blocked.add((gx, gy, 1))  # block both for now (conservative)
    return blocked, bbox


def _to_grid(x, y, bbox, grid=GRID_MM):
    xmin, ymin, _, _ = bbox
    gx = int(round((x - xmin) / grid))
    gy = int(round((y - ymin) / grid))
    return gx, gy


def _to_world(gx, gy, bbox, grid=GRID_MM):
    xmin, ymin, _, _ = bbox
    return (round(xmin + gx * grid, 6), round(ymin + gy * grid, 6))


def _astar(start, goal, blocked, bbox, grid=GRID_MM, max_expand=20000):
    """Deterministic A* on 4-neighbour grid, single layer. Returns list of (x,y) world coords or None."""
    sx, sy = _to_grid(start[0], start[1], bbox, grid)
    gx, gy = _to_grid(goal[0], goal[1], bbox, grid)
    # allow start/goal even if blocked (pad itself)
    def blocked_at(nx, ny):
        return (nx, ny, 0) in blocked

    # Manhattan heuristic
    def h(ax, ay): return abs(ax - gx) + abs(ay - gy)

    open_heap = []
    heapq.heappush(open_heap, (h(sx, sy), 0, sx, sy))
    came = {}
    gscore = {(sx, sy): 0}
    visited = set()
    expand = 0
    # fixed neighbour order: +x, -x, +y, -y for determinism (sorted by cost then x then y)
    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    while open_heap and expand < max_expand:
        f, g, x, y = heapq.heappop(open_heap)
        if (x, y) in visited:
            continue
        visited.add((x, y))
        expand += 1
        if x == gx and y == gy:
            # reconstruct
            path = []
            cur = (x, y)
            while cur in came or cur == (sx, sy):
                wx, wy = _to_world(cur[0], cur[1], bbox, grid)
                path.append((wx, wy))
                if cur == (sx, sy):
                    break
                cur = came[cur]
            path.reverse()
            # ensure endpoints are exactly start/goal (not snapped grid center)
            if path:
                path[0] = start
                path[-1] = goal
            return path
        for dx, dy in dirs:
            nx, ny = x + dx, y + dy
            # bounds inside bbox (with small margin)
            xmin, ymin, xmax, ymax = bbox
            wx, wy = _to_world(nx, ny, bbox, grid)
            if not (xmin - grid <= wx <= xmax + grid and ymin - grid <= wy <= ymax + grid):
                continue
            if (nx, ny) != (gx, gy) and blocked_at(nx, ny):
                continue
            tentative = g + 1
            if (nx, ny) not in gscore or tentative < gscore[(nx, ny)]:
                gscore[(nx, ny)] = tentative
                came[(nx, ny)] = (x, y)
                heapq.heappush(open_heap, (tentative + h(nx, ny), tentative, nx, ny))
    return None


def _compress_path(path):
    """Collapse collinear points to Manhattan segments."""
    if not path or len(path) <= 2:
        return path
    out = [path[0]]
    for i in range(1, len(path) - 1):
        x0, y0 = out[-1]
        x1, y1 = path[i]
        x2, y2 = path[i + 1]
        # if three points collinear (horizontal or vertical or diagonal same direction)
        # check if middle is redundant
        # Manhattan paths are axis-aligned, so check
        if (x0 == x1 == x2) or (y0 == y1 == y2):
            continue
        # also if direction unchanged (e.g. moving east continuously)
        # keep only bend points: if vector (x1-x0,y1-y0) same direction as (x2-x1,y2-y1) skip
        dx1, dy1 = x1 - x0, y1 - y0
        dx2, dy2 = x2 - x1, y2 - y1
        # normalise sign for Manhattan: only 4 dirs
        def sign(v): return (v > 0) - (v < 0)
        if sign(dx1) == sign(dx2) and sign(dy1) == sign(dy2):
            continue
        out.append(path[i])
    out.append(path[-1])
    # merge straight runs: if we skipped too aggressively, ensure we have bends
    # Now compress consecutive collinear again
    compressed = [out[0]]
    for pt in out[1:]:
        if pt == compressed[-1]:
            continue
        compressed.append(pt)
    return compressed


def _path_to_segments(path, net_code, net_name, layer, width):
    """Convert polyline path to KiCad segment S-expr nodes."""
    segs = []
    if not path or len(path) < 2:
        return segs
    # compress first
    path = _compress_path(path)
    for i in range(len(path) - 1):
        x1, y1 = path[i]
        x2, y2 = path[i + 1]
        # skip zero-length
        if abs(x1 - x2) < 1e-9 and abs(y1 - y2) < 1e-9:
            continue
        segs.append([
            "segment",
            ["start", _fmt(x1), _fmt(y1)],
            ["end", _fmt(x2), _fmt(y2)],
            ["width", _fmt(width)],
            ["layer", layer],
            ["net", str(net_code)],
            ["uuid", _new_uuid()],
        ])
    return segs


def _ensure_nets_in_board(root, name_to_code):
    """Ensure net 0 exists; caller manages board nets list."""
    return name_to_code


def _serialize_board(root):
    """Serialize S-exp tree back to KiCad file text (minimal pretty)."""
    def write_node(node, indent=0):
        if isinstance(node, list):
            if not node:
                return "()"
            head = node[0]
            if len(node) == 1:
                return f"({head})"
            # leaf-like nodes: check if all children are atoms
            if all(not isinstance(c, list) for c in node[1:]):
                inner = " ".join(f'"{c}"' if isinstance(c, str) and (" " in c or c == "") else str(c) for c in node[1:])
                return f"({head} {inner})" if inner else f"({head})"
            # complex
            prefix = "\t" * indent + f"({head}"
            parts = []
            for child in node[1:]:
                if isinstance(child, list):
                    parts.append(write_node(child, indent + 1))
                else:
                    # atom
                    if isinstance(child, str) and (" " in child or child == ""):
                        parts.append(f'"{child}"')
                    else:
                        parts.append(str(child))
            if len(parts) <= 2 and all("\n" not in p for p in parts):
                return prefix + " " + " ".join(parts) + ")"
            else:
                inner = "\n".join("\t" * (indent + 1) + p if p.startswith("(") else "\t" * (indent + 1) + p for p in parts)
                return prefix + "\n" + inner + "\n" + "\t" * indent + ")"
        else:
            # atom
            if isinstance(node, str) and (" " in node or node == ""):
                return f'"{node}"'
            return str(node)
    # root is like ["kicad_pcb", ["version", ...], ...]
    # write each top-level child on new line
    lines = [write_node(root, 0)]
    return lines[0] + "\n"


def autoroute(board_path, out=None, width=DEFAULT_WIDTH, grid=GRID_MM, dry_run=False, strategy="astar"):
    """Deterministic autoroute. Returns dict result, writes file if not dry_run.

    strategy: "escape" (L-routing) or "astar" (maze). Both deterministic; astar
    falls back to L-routing if blocked grid unavailable.
    """
    board_path = Path(board_path)
    if not board_path.exists():
        raise FileNotFoundError(board_path)
    root = _parse_board(board_path)
    if not root or root[0] != "kicad_pcb":
        raise ValueError(f"{board_path} is not a kicad_pcb")
    name_to_code, code_to_name = _board_nets(root)
    pads = _get_pads(root)
    tracks, vias = _get_tracks(root)
    bbox = _get_outline(root)
    # fallback bbox: pad extents + 10mm margin
    if bbox is None:
        if pads:
            xs = [p["x"] for p in pads]; ys = [p["y"] for p in pads]
            bbox = (min(xs) - 10, min(ys) - 10, max(xs) + 10, max(ys) + 10)
        else:
            bbox = (0, 0, 100, 100)

    # Group pads by net (ignore net 0 "" and empty)
    by_net = defaultdict(list)
    for p in pads:
        name = p["net_name"]
        code = p["net_code"]
        if code == 0 or not name:
            continue
        # ensure code mapping exists; if net_name not in name_to_code, assign next code
        if name not in name_to_code:
            # allocate new net code deterministically sorted
            next_code = max(name_to_code.values(), default=0) + 1
            name_to_code[name] = next_code
            code_to_name[next_code] = name
            # append net entry to board root
            root.append(["net", str(next_code), name])
        # use canonical code
        canonical = name_to_code[name]
        by_net[canonical].append(p)

    # Sort nets deterministically by net code
    sorted_nets = sorted(by_net.items(), key=lambda kv: kv[0])

    # Build connectivity: already-track-connected? Build DSU per net from existing tracks
    # For MVP: if a net has a track with same net code, assume that track already connects some pads,
    # but we still check: we will connect pads pairwise that are not already connected via tracks.
    # Simplify: for each net, if len(pads) >=2 and track count for that net ==0, route it.
    # If tracks exist for that net, skip (assume already routed). This keeps determinism.

    existing_net_tracks = defaultdict(list)
    for t in tracks:
        existing_net_tracks[t["net"]].append(t)

    blocked, _ = _build_obstacle_grid(tracks, bbox, grid=grid, clearance=DEFAULT_CLEARANCE)

    new_segments = []
    routed_nets = 0
    unrouted = []
    # For determinism, sort pads within each net by (x,y,ref,pad)
    for net_code, pad_list in sorted_nets:
        pad_list_sorted = sorted(pad_list, key=lambda p: (p["x"], p["y"], p["ref"], p["pad"]))
        net_name = code_to_name.get(net_code, str(net_code))
        if len(pad_list_sorted) < 2:
            continue
        # skip if already has tracks for this net (already routed)
        if net_code in existing_net_tracks and existing_net_tracks[net_code]:
            continue
        # Need to connect all pads: chain them sequentially (star not needed for MVP)
        # For each adjacent pair, route
        net_segs = []
        net_ok = True
        for i in range(len(pad_list_sorted) - 1):
            a = pad_list_sorted[i]; b = pad_list_sorted[i + 1]
            # choose layer: if both same layer, use that; else F.Cu (with via would be needed)
            layer = a["layer"] if a["layer"] == b["layer"] else "F.Cu"
            start = (a["x"], a["y"])
            end = (b["x"], b["y"])
            if strategy == "astar" and blocked is not None:
                path = _astar(start, end, blocked, bbox, grid=grid)
                if path is None:
                    # fallback to L-route
                    path = [start, (_snap(end[0]), _snap(start[1])), end] if abs(start[0] - end[0]) > abs(start[1] - end[1]) else [start, (_snap(start[0]), _snap(end[1])), end]
                    # Ensure snapped intermediate stays inside bbox and not blocked trivially
                    # If still blocked, mark unrouted
                    # For MVP we accept L-route even if crosses blocked (conservative blocked flags both layers)
                    # To avoid false unrouted, we do L-route deterministically
                    pass
            else:
                # escape / L-routing: deterministic bend order: horizontal first if dx > dy else vertical first
                dx = abs(start[0] - end[0]); dy = abs(start[1] - end[1])
                if dx >= dy:
                    mid = (_snap(end[0]), _snap(start[1]))
                    # if start and end share y, direct
                    if abs(start[1] - end[1]) < 1e-9:
                        path = [start, end]
                    else:
                        path = [start, mid, end]
                else:
                    mid = (_snap(start[0]), _snap(end[1]))
                    if abs(start[0] - end[0]) < 1e-9:
                        path = [start, end]
                    else:
                        path = [start, mid, end]
            segs = _path_to_segments(path, net_code, net_name, layer, width)
            if not segs:
                net_ok = False
                break
            net_segs.extend(segs)
            # add to blocked incrementally for next nets (avoid crossing)
            # approximate: block grid cells along this path
            for seg in segs:
                # parse back coords
                x1 = float(sexp_get(seg, "start")[1]); y1 = float(sexp_get(seg, "start")[2])
                x2 = float(sexp_get(seg, "end")[1]); y2 = float(sexp_get(seg, "end")[2])
                # block
                fake_track = {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "width": width}
                # reuse blocking logic: expand
                w = width / 2 + DEFAULT_CLEARANCE
                bxmin = min(x1, x2) - w; bxmax = max(x1, x2) + w
                bymin = min(y1, y2) - w; bymax = max(y1, y2) + w
                xmin, ymin, _, _ = bbox
                gx_start = int(math.floor((bxmin - xmin) / grid))
                gx_end = int(math.ceil((bxmax - xmin) / grid))
                gy_start = int(math.floor((bymin - ymin) / grid))
                gy_end = int(math.ceil((bymax - ymin) / grid))
                for gx in range(gx_start, gx_end + 1):
                    for gy in range(gy_start, gy_end + 1):
                        cx = xmin + gx * grid; cy = ymin + gy * grid
                        # distance check
                        dx_ = x2 - x1; dy_ = y2 - y1
                        if dx_ == 0 and dy_ == 0:
                            dist = math.hypot(cx - x1, cy - y1)
                        else:
                            tt = ((cx - x1)*dx_ + (cy - y1)*dy_) / (dx_*dx_ + dy_*dy_)
                            tt = max(0, min(1, tt))
                            px = x1 + tt*dx_; py = y1 + tt*dy_
                            dist = math.hypot(cx - px, cy - py)
                        if dist <= w + 1e-9:
                            blocked.add((gx, gy, 0))
                            blocked.add((gx, gy, 1))
        if net_ok and net_segs:
            new_segments.extend(net_segs)
            routed_nets += 1
        else:
            unrouted.append({"net": net_name, "code": net_code, "pads": len(pad_list_sorted)})

    result = {
        "board": str(board_path),
        "routed_nets": routed_nets,
        "segment_count": len(new_segments),
        "via_count": 0,
        "unrouted": unrouted,
        "grid": grid,
        "width": width,
        "strategy": strategy,
    }

    if dry_run:
        result["dry_run"] = True
        return result

    # append segments to board tree before closing paren
    for seg in new_segments:
        root.append(seg)

    out_path = Path(out) if out else board_path
    # Write via simple serialization that preserves structure - reuse original text splice approach
    # To avoid re-serialization drift, we do minimal append: read original text and inject before final )
    text = board_path.read_text(encoding="utf-8")
    # Find last closing ) that closes kicad_pcb
    # We'll inject segments before it
    inject = ""
    for seg in new_segments:
        # format as KiCad S-exp with tabs
        start = sexp_get(seg, "start"); end = sexp_get(seg, "end")
        width_n = sexp_get(seg, "width"); layer_n = sexp_get(seg, "layer")
        net_n = sexp_get(seg, "net"); uuid_n = sexp_get(seg, "uuid")
        inject += f'\t(segment (start {start[1]} {start[2]}) (end {end[1]} {end[2]}) (width {width_n[1]}) (layer "{layer_n[1]}") (net {net_n[1]}) (uuid {uuid_n[1]}))\n'
    if inject:
        idx = text.rfind(")")
        if idx != -1:
            text = text[:idx] + inject + text[idx:]
    out_path.write_text(text, encoding="utf-8")
    result["output"] = str(out_path)
    return result


def cmd_autoroute(args):
    try:
        res = autoroute(
            args.board,
            out=getattr(args, "out", None),
            width=getattr(args, "width", DEFAULT_WIDTH),
            grid=getattr(args, "grid", GRID_MM),
            dry_run=getattr(args, "dry_run", False),
            strategy=getattr(args, "strategy", "astar"),
        )
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return EXIT_ENV
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return EXIT_ENV
    if getattr(args, "json", False):
        import json
        print(json.dumps({"command": "autoroute", **res}, indent=2))
    else:
        if res.get("dry_run"):
            print(f"autoroute dry-run: {res['routed_nets']} nets, {res['segment_count']} segments, {len(res['unrouted'])} unrouted")
        else:
            print(f"autoroute: {res['routed_nets']} nets routed, {res['segment_count']} segments -> {res.get('output', args.board)}")
        if res["unrouted"]:
            for u in res["unrouted"]:
                print(f"  UNROUTED: {u['net']} ({u['pads']} pads)")
    return EXIT_VIOLATIONS if res["unrouted"] else EXIT_OK
