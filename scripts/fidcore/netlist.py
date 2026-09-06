"""Netlist cache, connectivity queries, intent audit, and graph analysis."""

import csv
import json
import sys
from pathlib import Path

import fidcore.kicad as kicad_mod
from fidcore.const import EXIT_ENV, EXIT_OK, EXIT_VIOLATIONS
from fidcore.sexp import load_sexp, sexp_find_all, sexp_get


def _first_str(node):
    """Value of a (key "value" ...) node - skips the key itself."""
    if node is None:
        return ""
    for x in node[1:]:
        if isinstance(x, str):
            return x
    return ""


def _netlist_path(project):
    return Path(str(project).rsplit(".", 1)[0] + "-netlist.sexpr")


def _export_netlist(project):
    """Export the netlist for project. Returns (path, exit_code)."""
    out = _netlist_path(project)
    proc = kicad_mod.kicad_cli(["sch", "export", "netlist", str(project),
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
        if want.upper() == "NC":
            results.append({"ref": ref, "pin": pin, "expected": want,
                            "actual": None, "status": "ok"})
            continue
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


_RAIL_NETS = {"GND", "VCC", "VDD", "VSS", "AGND", "DGND", "AVDD", "AVSS", "VBUS"}


def _is_rail_net(name):
    """Conservative power-rail heuristic. Rails are excluded from orphan-cluster
    grouping because ground connects everything and would mask real islands.
    Matches: canonical rail names, +/- prefixed nets, and voltage patterns
    like 3V3, 5V_SYS, 12V, 1V8, etc."""
    n = name.strip().upper()
    if n in _RAIL_NETS or n.startswith("+") or n.startswith("-"):
        return True
    # Voltage rail pattern: optional +/- prefix, digit(s), V, optional suffix
    # Examples: 3V3, 5V, 5V_SYS, 12V, 1V8, 3V3_ANALOG
    import re
    return bool(re.match(r'^[+-]?\d+V\d*[A-Z_]*$', n))


def _orphan_clusters(nets):
    """Groups of components linked only to each other (plus power rails) with
    no connector, no IC, and no >=4-pin part anchoring them to the outside
    world. These are almost always leftovers from an earlier design iteration.

    A cluster is flagged when it contains at least one multi-pin non-rail net
    (so lone components on dangling nets are left to the orphan-net warning)
    and has no anchor: J* connector, U* part, or any component with >= 4
    connected pins.
    """
    comp_nets = {}
    net_comps = {}
    for name, nodes in nets.items():
        if _is_rail_net(name):
            continue
        for (r, _p) in nodes:
            comp_nets.setdefault(r, set()).add(name)
            net_comps.setdefault(name, set()).add(r)
    visited = set()
    flagged = []
    for start in sorted(comp_nets):
        if start in visited:
            continue
        stack, cluster, cluster_nets = [start], set(), set()
        while stack:
            c = stack.pop()
            if c in visited:
                continue
            visited.add(c)
            cluster.add(c)
            for n in comp_nets.get(c, ()):
                cluster_nets.add(n)
                for c2 in net_comps.get(n, ()):
                    if c2 not in visited:
                        stack.append(c2)
        def _pin_count(r):
            return sum(1 for nodes in nets.values() for (rr, _p) in nodes if rr == r)
        anchored = any(
            r.upper().startswith("J")
            or r.upper().startswith("U")
            or _pin_count(r) >= 4
            for r in cluster
        )
        has_structure = any(
            len(nets[n]) >= 2 for n in cluster_nets if not _is_rail_net(n)
        )
        if not anchored and has_structure:
            flagged.append(sorted(cluster))
    return flagged


def _suspect_components(nets):
    """Components tacked onto a real circuit without participating in it.

    A ghost from an abandoned iteration often survives because ONE of its
    pins taps a live net (Q1.2 on VBAT_FUSED, 2026-08-23), which defeats
    island detection: the graph looks connected. The signature instead:
    a small part (not a connector, not an IC, < 4 connected pins) whose
    every non-rail net is dangling or point-to-point (<= 2 connections),
    with at least one dangling pin.

    Review-level finding: some legitimate circuits (high-impedance sense
    taps) look like this; the message asks for review, not deletion.
    """
    pin_counts = {}
    for name, nodes in nets.items():
        for (r, _p) in nodes:
            pin_counts[r] = pin_counts.get(r, 0) + 1
    suspects = []
    for r in sorted(pin_counts):
        if r.upper().startswith(("J", "U")) or pin_counts[r] >= 4:
            continue
        own = [(name, len(nodes)) for name, nodes in nets.items()
               if any(rr == r for (rr, _p) in nodes)]
        non_rail = [(n, c) for n, c in own if not _is_rail_net(n)]
        if not non_rail:
            continue
        has_dangling = any(c == 1 for n, c in non_rail if not n.startswith("unconnected"))
        # At most one substantial net = at most a passive tap into the real
        # circuit. Parts that BRIDGE two or more substantial nets (R-GS
        # bridging VBAT_GATE and VBAT_SW) are participants, not ghosts.
        taps_at_most_one = sum(1 for _n, c in non_rail if c >= 3) <= 1
        if has_dangling and taps_at_most_one:
            suspects.append(r)
    return suspects
