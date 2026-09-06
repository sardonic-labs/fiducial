# Synthesis — spec → schematic

Board spec is JSON validated without dependencies (`scripts/fidsynth/spec.py:1`).

```json
{
  "title": "Demo",
  "components": [{"ref":"R1","part":"R","value":"10k"},{"ref":"C1","part":"C"},{"ref":"U1","part":"TEST_MCU"}],
  "nets": {"/A":["R1.1","U1.2"],"/B":["R1.2","U1.3"],"/VCC":["U1.1","C1.1"],"/GND":["U1.4","C1.2"]}
}
```

```sh
python scripts/fiducial.py synthesize spec.json -o board.kicad_sch
# writes board.kicad_sch + board-intent.csv + lint check
python scripts/fiducial.py lint board.kicad_sch
```

Only parts in `scripts/fidsynth/registry.py` can be used — no guessed pinouts. Add ICs with datasheet URL + pin map.

## Examples

`examples/synth/` — `blinky.json`, `power-entry.json`, `sensor-node.json`. Each synthesizes lint-clean.

```sh
python scripts/fiducial.py synthesize examples/synth/blinky.json -o /tmp/blinky.kicad_sch
```

## Rules

`scripts/fidsynth/rules.py` warns on missing decoupling caps and missing GND.
