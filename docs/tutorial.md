# Tutorial — 5-minute blinky (human + agent)

> One path, same for both: `intent.csv` → `SchematicBuilder` → `lint` → `check-intent`.

## For humans (copy-paste in terminal)

```sh
git clone https://github.com/sardonic-labs/fiducial && cd fiducial
python examples/builder_demo.py          # writes /tmp/builder_demo.kicad_sch + intent.csv
python scripts/fiducial.py lint /tmp/builder_demo.kicad_sch
python scripts/fiducial.py check-intent /tmp/builder_demo.kicad_sch /tmp/builder_demo-intent.csv
python scripts/fiducial.py sexp /tmp/builder_demo.kicad_sch | head -n 20  # S-exp → JSON
```

Expected: `Lint clean (5 symbols)` (`test_offline.py:228`), `8/8 connections verified` (`netlist-audit.md:7`). Open `/tmp/builder_demo.kicad_sch` in KiCad 10 — it renders.

## For agents (same steps, machine-readable)

```sh
python scripts/fiducial.py lint /tmp/builder_demo.kicad_sch --json | jq .problems
python scripts/fiducial.py check-intent /tmp/builder_demo.kicad_sch /tmp/builder_demo-intent.csv --json | jq .results
```

Exit codes are the gate (`reference/exit-codes.md`): `0` clean, `1` violations, `2` env error (`fiducial.py:15`).

## What you just built

`examples/builder_demo.py:1` rebuilds `tests/fixtures/healthy.kicad_sch:1` (R1/C1/U1):

```python
from pathlib import Path
import sys
sys.path.insert(0, str(Path("scripts").resolve()))
from schematic_builder import SchematicBuilder

b = SchematicBuilder("/tmp/builder_demo.kicad_sch", title="Fiducial demo", rev="A")
b.add_symbol("Device:R", ref="R1", value="10k", at=(50.8, 50.8))
b.add_symbol("Device:C", ref="C1", value="100n", at=(81.28, 50.8))
b.add_symbol("Test:MCU", ref="U1", value="TestMCU", at=(121.92, 50.8))
b.connect("R1","1","/A")  # places label at pin endpoint (authoring.md:33)
b.connect("U1","2","/A")  # same net → lint sees multi-pin, not single-use (fiducial.py:905)
b.save(validate=True)     # runs lint in-process (schematic_builder.py:548)
b.write_intent("/tmp/builder_demo-intent.csv")  # ref,pin,expected_net
```

Key invariants enforced at construction (`docs/builder.md:62`):

* unique `uuid` + `instances` block (otherwise `lint:868` `duplicate reference`)
* `lib_symbols` entry per `lib_id` (`lint:877` `not in lib_symbols`)
* grid 1.27 mm (`fiducial.py:564`) — `50.8` ok, `50.9` raises `BuilderError` with snap hint

## Next

* **Add your own `intent.csv`:** `howto/add-intent.md`
* **Migrate hand-rolled S-exp:** `howto/migrate-handrolled.md`
* **All commands:** `reference/cli.md` | **Builder API:** `reference/api-builder.md`
* **Why this works:** `explanation/architecture.md`

## Troubleshooting (shared)

| Symptom | Fix |
|---|---|
| `kicad-cli not found` | `lint` still runs structure checks (`fiducial.py:898` `skipped connectivity`); install KiCad 10 for `check-intent` netlist |
| `off-grid (50.9, 50.8)` | Use `50.8` (grid) or `101.6` multiples — see `kicad-versions.md:10` |
| `label appears only once` | Add second label on same net or add `allow-single-use` in `rules.md:1` |

```json
{"tutorial": "blinky", "source": "examples/builder_demo.py:1", "verifies": ["lint", "check-intent"], "time": "5m"}
```
