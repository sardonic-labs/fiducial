# SchematicBuilder — programmatic schematic authoring

`scripts/schematic_builder.py` replaces hand-rolled S-expression edits with a semantic, grid-aware Python API. It enforces the invariants that `lint` checks (`scripts/fiducial.py:849`) at construction time, so agents get errors immediately instead of after a failed audit.

```
python examples/builder_demo.py
python scripts/fiducial.py lint /tmp/builder_demo.kicad_sch
python scripts/fiducial.py sexp /tmp/builder_demo.kicad_sch | head
```

## Why

Hand-rolling `.kicad_sch` (see `skills/schematic/authoring.md:6`) requires:

* matching `lib_symbols` entry for every `lib_id`
* unique `uuid` per object, `instances` block, `Reference/Value/Footprint`
* positions on 1.27 mm grid (`fiducial.py:564`)
* wiring via labels (`authoring.md:33`) or orthogonal wires (`cleanliness.md:24`)
* power symbols (`power:GND`), not bare wires (`authoring.md:36`)

Missing any → silent KiCad corruption or invisible disconnects that pass ERC (`README.md:12`). Builder makes these impossible to forget.

## Install

Stdlib-only, no pip. Import from `scripts/`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path("fiducial/scripts").resolve()))
from schematic_builder import SchematicBuilder
```

## Quick start

```python
from schematic_builder import SchematicBuilder

b = SchematicBuilder("myboard.kicad_sch", title="My Board", rev="A")
b.add_symbol("Device:R", ref="R1", value="10k",
             footprint="Resistor_SMD:R_0603_1608Metric", at=(50.8, 50.8))
b.add_symbol("Device:C", ref="C1", value="100n", at=(81.28, 50.8))
b.add_symbol("Test:MCU", ref="U1", value="TestMCU", at=(121.92, 50.8))

# semantic connect — places label at pin endpoint, snapped to grid
b.connect("R1", "1", "/A")
b.connect("U1", "2", "/A")
b.connect("R1", "2", "/B")
b.connect("U1", "3", "/B")
b.connect("U1", "1", "/VCC")
b.connect("C1", "1", "/VCC")

# power is a symbol, not a wire
b.add_power("GND", at=(50.8, 80.01))

b.save(validate=True)          # writes + runs lint in-process
b.write_intent("intent.csv")   # ref,pin,expected_net for check-intent
```

See `examples/builder_demo.py:1` for a runnable copy of `tests/fixtures/healthy.kicad_sch:1`.

## API

### `SchematicBuilder(path, title, rev, date, paper, version)`

Create a new schematic. `path` is where `save()` writes. `paper="A4"`, `version=20250114` match KiCad defaults.

### `add_symbol(lib_id, ref, value, footprint="", datasheet="", at=(x,y), rotation=0)`

Add a symbol instance. Generates `uuid`, `instances` block, and `lib_symbols` entry.

* `lib_id`: `"Device:R"`, `"MCU_RaspberryPi:RP2040"`, `"power:GND"` etc.
* `ref`: must be unique (`lint:868` duplicate check moved to construction).
* `at`: `(x, y)` or `(x, y, rot)` in mm, must be on 1.27 mm grid — raises `BuilderError` with snap hint if not.
* `lib_symbols` stub is auto-created if not found locally; real projects should have matching `.kicad_sym` libraries so pins match the footprint/datasheet (use `scripts/find_part.py:46`).

Returns `self` for chaining.

### `connect(ref, pin, net, kind="label")`

Preferred wiring primitive. Places a label of `kind` (`label`/`global_label`) at the pin's absolute endpoint (`fiducial.py:618` math). Power-like nets (`GND`, `+3V3`, `+5V`, `VBAT`, `VCC`) auto-promote to `global_label` per `skills/schematic/hierarchy.md:33`.

Records the connection for `write_intent()` — the netlist-audit contract (`skills/verification/netlist-audit.md:7`).

### `tie(ref, pin, net)`

Alias for `connect` for power/ground ties.

### `wire(p1, p2, width=0)`

Explicit orthogonal wire. `p1`, `p2` are `(x, y)` on grid. Diagonal wires raise `BuilderError` (`cleanliness.md:24`). Prefer labels over long wires (`authoring.md:33`).

### `label(text, at, kind="label")` / `global_label` / `hierarchical_label`

Low-level label. `kind` selects `label` (local), `global_label` (power/rails everywhere), `hierarchical_label` (sheet boundary per `hierarchy.md:29`). Grid-enforced.

### `add_power(net, at, rotation=0)`

Place a power symbol (`power:GND`, `power:+3V3`, etc.) at `at`. Auto-generates `#PWRnn` reference. The symbol itself defines the global net — no extra label needed.

### `no_connect(ref, pin)`

Add a `no_connect` marker at the pin endpoint.

### `add_text(text, at)`

Schematic text note (block headers etc.).

### `save(validate=False)`

Serialize to S-expression (`fiducial.py:68` parser compatible) and write to `path`. If `validate=True`, runs `fiducial.py lint` in-process and raises `BuilderError` on violations.

### `write_intent(csv_path)`

Write `intent.csv` (`ref,pin,expected_net`) from all `connect()` calls. Use directly with `check-intent`:

```
python scripts/fiducial.py check-intent myboard.kicad_sch intent.csv
```

### `SchematicBuilder.load(path)`

Load an existing `.kicad_sch` for incremental edits (best-effort for simple boards). Re-parses via `fiducial.py load_sexp:128` and repopulates `lib_symbols`, `symbols`, `labels`, `wires`, `no_connects`. Returns a builder you can extend and `save()`.

```python
b = SchematicBuilder.load("myboard.kicad_sch")
b.add_symbol("Device:R", "R3", "1k", at=(63.5, 50.8))
b.save(validate=True)
```

## Errors → lint mapping

| Builder raises `BuilderError` | `lint:849` would later catch |
|---|---|
| `duplicate reference: R1` | `duplicate reference: R1` |
| `position (x,y) off-grid` | `symbol position off-grid` / `wire endpoint off-grid` (`_geometry_problems:572`) |
| `diagonal wire ... forbidden` | `wire endpoint off-grid` + visual audit |
| `symbol 'R1' not found` | `symbol without Reference property` |
| missing `lib_symbols` entry | `uses '...' but not in lib_symbols` |

Wiring via `connect()` avoids the classic single-use label bug (`lint:905` `appears only once`) by creating duplicate net labels that merge into a multi-pin net — the same fix `lint` suggests.

## Grid and placement

All coordinates are mm, snapped to 1.27 mm. Builder enforces `_on_grid:568` strictly — e.g. `50.8` is grid, `50.9` is not (`50.8` hint). This matches `cleanliness.md:24` and the off-grid sweep that caught real bugs (`tests/test_offline.py:714`).

## Limitations (v0)

* Single-sheet only; hierarchy (`hierarchy.md:1`) via future `add_sheet()`.
* Generic pin stubs for unknown libs — replace with real library parts via `find_part.py` for production; stubs are parseable but not footprint-accurate.
* No auto-placement; `at` is explicit. Use `cleanliness.md:24` left-to-right block layout manually.
* No copy-paste multi-channel; use per-instance `add_symbol` + per-slot `connect()` so `check-intent` proves each copy (`hierarchy.md:67`).

## Testing

```sh
python -m unittest discover -s tests -v               # existing offline + kicad tests
python examples/builder_demo.py && python scripts/fiducial.py lint /tmp/builder_demo.kicad_sch --json
python scripts/fiducial.py sexp /tmp/builder_demo.kicad_sch --raw | head
```

`lint:849` clean (`0`) and `parse_sexp:68` round-trip are the correctness gates.
