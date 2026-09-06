"""Compiler: spec dict → .kicad_sch + intent.csv via SchematicBuilder."""
import sys
from pathlib import Path

# ensure scripts/ is on path for SchematicBuilder imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schematic_builder import SchematicBuilder
from fidsynth.spec import load_spec, spec_to_intent_rows, write_intent_csv
from fidsynth.registry import get_part, validate_component
from fidsynth.rules import apply_rules

GRID = 1.27

def compile_spec(spec_or_path, out="board.kicad_sch", intent_out=None, check=True):
    spec = load_spec(spec_or_path)
    warns = apply_rules(spec)
    # validate parts + pins
    for c in spec["components"]:
        part = validate_component(c)
        # pin existence check
        allowed = set(part["pins"])
        for net, pins in spec["nets"].items():
            for rp in pins:
                r,p = rp.split(".",1)
                if r==c["ref"] and p not in allowed:
                    raise ValueError(f"{r}.{p} not in part {c['part']} pins {sorted(allowed)}")
    b = SchematicBuilder(out, title=spec.get("title","Synth Board"))
    # place symbols in a row, 25.4mm apart
    x0, y0 = 50.8, 50.8
    for i, c in enumerate(spec["components"]):
        part = get_part(c["part"])
        x = x0 + i*25.4
        # snap handled by builder; use at tuple
        b.add_symbol(part["lib_id"], ref=c["ref"], value=c.get("value", c["part"]), at=(x, y0), footprint=c.get("footprint",""))
    # connect nets via labels at pin endpoints (builder.connect handles it)
    # For passives, pins 1/2 map to two nets; we need to place labels accordingly.
    # Simplest: for each net, call b.connect for each pin in that net — builder creates label at pin endpoint.
    # Need to map pin numbers to actual nets; builder will deduplicate labels per net.
    for net, pins in spec["nets"].items():
        for rp in pins:
            r,p = rp.split(".",1)
            b.connect(r, p, net)
    b.save()
    rows = spec_to_intent_rows(spec)
    if intent_out is None:
        intent_out = str(Path(out).with_suffix("")) + "-intent.csv"
        # actually want board-intent.csv alongside: use out stem
        intent_out = str(Path(out).parent / (Path(out).stem + "-intent.csv"))
    write_intent_csv(rows, intent_out)
    if check:
        # run lint in-process for fast feedback
        from fidcore.lint import cmd_lint
        from argparse import Namespace
        rc = cmd_lint(Namespace(project=out, rules=None, json=False))
        if rc != 0:
            print(f"WARNING: lint found issues after synthesis (rc={rc}) — inspect {out}", file=sys.stderr)
    for w in warns:
        print(f"RULE WARN: {w}", file=sys.stderr)
    return {"sch": out, "intent": intent_out, "warnings": warns}
