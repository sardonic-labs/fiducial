# kicad-cli cookbook

`kicad-cli` ships with KiCad 7+ (Windows: `C:\Program Files\KiCad\<ver>\bin\kicad-cli.exe`,
must be on PATH — verify with `doctor`). All commands below are also wrapped by
`fiducial.py`; drop to raw kicad-cli when the wrapper doesn't cover a case.

Conventions: `PROJ` = `path/to/project.kicad_sch`, `BOARD` = `path/to/board.kicad_pcb`.

## Schematic

```
# ERC (JSON report)
kicad-cli sch erc PROJ --format json --output erc.json

# Netlist exports
kicad-cli sch export netlist PROJ -o net.net --format kicadsexpr
kicad-cli sch export netlist PROJ -o net.json --format json

# BOM
kicad-cli sch export bom PROJ --fields "Reference,Value,Footprint,\${QUANTITY}" -o bom.csv

# SVG / PDF renders (one file per sheet)
kicad-cli sch export svg PROJ -o svgdir
kicad-cli sch export pdf PROJ -o out.pdf

# Symbol library browser
kicad-cli sch export python-bom ...   # rarely; prefer lib table + files on disk
```

## Board

```
# DRC (JSON report); add --schematic-parity if project has matching schematic
kicad-cli pcb drc BOARD --format json --output drc.json

# Renders
kicad-cli pcb export svg BOARD -o svgdir --layers "F.Cu,B.Cu,F.Silkscreen,Edge.Cuts"
kicad-cli pcb export pdf BOARD -o out.pdf --layers F.Cu,F.Mask

# Fabrication outputs
kicad-cli pcb export gerbers BOARD -o gerbdir/ --drill --map
kicad-cli pcb export drill  BOARD -o gerbdir/
kicad-cli pcb export step   BOARD -o board.step
```

## Libraries

- KiCad symbol libraries: `<share>/kicad/symbols/*.kicad_sym`
- Footprints: `<share>/kicad/footprints/*.pretty/*.kicad_mod`
- These are plain text/S-expressions; `grep` them to find symbols and read pin
  definitions. Never invent symbol content from memory.

## Gotchas

- Exit codes: ERC/DRC return nonzero only on *errors*; warnings still exit 0.
  Parse the JSON report for the full picture.
- `--output` for multi-file exports is a *directory*.
- Layer names in `--layers` are comma-separated without spaces.
- Version drift: flags changed between 7→8→9. If a flag errors, run
  `kicad-cli <cmd> --help` and adapt instead of assuming.
