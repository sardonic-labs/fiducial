"""Render/BOM export commands (both require kicad-cli)."""

import sys
from pathlib import Path

import fidcore.kicad as kicad_mod
from fidcore.const import EXIT_ENV, EXIT_OK


def cmd_render(args):
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    rc = EXIT_OK
    for path in args.projects:
        stem = Path(path).stem
        if str(path).lower().endswith(".kicad_pcb"):
            target = str(outdir / (stem + ".svg"))
            sub = kicad_mod.kicad_cli(["pcb", "export", "svg", str(path), "-o", target,
                                       "--layers", "F.Cu,B.Cu,F.Mask,B.Mask,"
                                                   "F.Silkscreen,B.Silkscreen,Edge.Cuts"])
        else:
            # sch export svg writes one file per sheet into the -o directory
            target = str(outdir / (stem + "-sch"))
            sub = kicad_mod.kicad_cli(["sch", "export", "svg", str(path), "-o", target])
        if sub.returncode != 0:
            print(sub.stderr.strip() or sub.stdout.strip(), file=sys.stderr)
            print(f"ERROR: could not render {path}", file=sys.stderr)
            rc = EXIT_ENV
        else:
            print(f"rendered {path} -> {target}")
    return rc


def cmd_bom(args):
    out = Path(str(args.project).rsplit(".", 1)[0] + "-bom.csv")
    proc = kicad_mod.kicad_cli(["sch", "export", "bom", str(args.project),
                                "--fields", "Reference,Value,Footprint,${QUANTITY}",
                                "--group-by", "Value,Footprint",
                                "-o", str(out)])
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        return EXIT_ENV
    print(out)
    return EXIT_OK
