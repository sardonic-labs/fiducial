#!/usr/bin/env python3
"""fiducial.py - stdlib-only helpers for AI-driven KiCad hardware design."""

import argparse
import sys

# Implementation lives in the fidcore package; this module is the CLI
# entry point (argparse + main) and re-exports the compat surface so
# `from fiducial import X` keeps working (schematic_builder,
# schematic_check, pcb_check, bom_check, pcb_router, reviewer, tests).
from fidcore.const import EXIT_ENV, EXIT_OK, EXIT_VIOLATIONS
from fidcore.diagnostics import (cmd_label_map, cmd_pin_positions,
                                 cmd_wire_trace)
from fidcore.gate import cmd_check
from fidcore.kicad import cmd_doctor, cmd_drc, cmd_erc, kicad_cli
from fidcore.lint import (cmd_check_rules, cmd_lint, cmd_overlap_check,
                          _label_net)
from fidcore.netlist import (_cache_is_stale, _export_netlist, _first_str,
                             _is_rail_net, _load_nets, _netlist_path,
                             _orphan_clusters, _orphan_nets, _pin_sort,
                             _suspect_components,
                             cmd_check_intent, cmd_nets, cmd_netlist, cmd_pins)
from fidcore.output import cmd_bom, cmd_render
from fidcore.sexp import (load_sexp, parse_sexp, sexp_find_all, sexp_get,
                          cmd_sexp)

__all__ = [
    "EXIT_OK", "EXIT_VIOLATIONS", "EXIT_ENV",
    "parse_sexp", "load_sexp", "sexp_get", "sexp_find_all",
    "kicad_cli", "_first_str", "_load_nets", "_netlist_path",
    "_export_netlist", "_cache_is_stale", "_is_rail_net", "_label_net",
    "_orphan_nets", "_orphan_clusters", "_suspect_components", "_pin_sort",
    "main",
]


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
    p.add_argument("--rules", help="rules CSV (allow-single-use suppresses "
                   "single-use label warnings)")
    p.add_argument("--json", action="store_true",
                   help="machine-readable JSON output")
    p.set_defaults(func=cmd_lint)

    p = sub.add_parser("check", help="run the full verification gate (lint + erc + intent + rules)")
    p.add_argument("project")
    p.add_argument("--intent", help="intent.csv to audit against")
    p.add_argument("--rules", help="rules CSV (see docs/rules.md)")
    p.add_argument("--refresh", action="store_true", help="force netlist re-export")
    p.add_argument("--skip-erc", action="store_true",
                   help="skip ERC (environments without kicad-cli)")
    p.add_argument("--json", action="store_true",
                   help="machine-readable JSON output for the sub-checks")
    p.set_defaults(func=cmd_check)
    # cmd_check_intent reads args.orphans; the gate leaves it off
    p.set_defaults(orphans=False)

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

    p = sub.add_parser("sexp", help="parse S-expression file to JSON (for agents)")
    p.add_argument("file", help=".kicad_sch, .kicad_pcb, .sexpr, or any S-expr file")
    p.add_argument("--raw", action="store_true",
                   help="emit raw nested lists instead of keyed objects")
    p.set_defaults(func=cmd_sexp)

    p = sub.add_parser("overlap-check",
                        help="detect wires from different nets sharing coordinates")
    p.add_argument("project")
    p.add_argument("--json", action="store_true",
                   help="machine-readable JSON output")
    p.set_defaults(func=cmd_overlap_check)

    p = sub.add_parser("wire-trace", help="trace what net a pin connects to")
    p.add_argument("project")
    p.add_argument("ref")
    p.add_argument("pin")
    p.set_defaults(func=cmd_wire_trace)

    p = sub.add_parser("label-map", help="dump all labels with coordinates")
    p.add_argument("project")
    p.set_defaults(func=cmd_label_map)

    p = sub.add_parser("pin-positions",
                        help="show pin endpoints in schematic space")
    p.add_argument("project")
    p.add_argument("ref")
    p.set_defaults(func=cmd_pin_positions)

    p = sub.add_parser("synthesize", help="compile board-spec JSON to .kicad_sch + intent.csv")
    p.add_argument("spec", help="board spec JSON (see docs/synth.md)")
    p.add_argument("-o", "--out", default="board.kicad_sch", help="output .kicad_sch")
    p.add_argument("--intent-out", help="output intent.csv (default: <out>-intent.csv)")
    p.add_argument("--no-check", action="store_true", help="skip lint after synthesis")
    def _cmd_synth(a):
        from fidsynth.compiler import compile_spec as _cs
        try:
            _cs(a.spec, out=a.out, intent_out=a.intent_out, check=not a.no_check)
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return EXIT_ENV
        except FileNotFoundError as e:
            print(f"ERROR: spec not found: {e}", file=sys.stderr)
            return EXIT_ENV
        return EXIT_OK
    p.set_defaults(func=_cmd_synth)

    p = sub.add_parser("autoroute",
                        help="deterministic autorouter for non-spatial AI models")
    p.add_argument("board", help=".kicad_pcb to route")
    p.add_argument("--out", help="output board path (default: overwrite input)")
    p.add_argument("--width", type=float, default=0.25,
                   help="track width mm (default 0.25)")
    p.add_argument("--grid", type=float, default=0.25,
                   help="routing grid mm (default 0.25)")
    p.add_argument("--strategy", choices=["astar", "escape"], default="astar",
                   help="routing strategy: astar (maze) or escape (L-route)")
    p.add_argument("--dry-run", action="store_true",
                   help="report without writing")
    p.add_argument("--json", action="store_true",
                   help="machine-readable JSON output")
    try:
        from pcb_router import cmd_autoroute
        p.set_defaults(func=cmd_autoroute)
    except ImportError:
        pass

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
