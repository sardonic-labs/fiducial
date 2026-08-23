# examples

A complete worked example: one tiny board plus the two CSVs that audit it.
Everything here matches `tests/fixtures/`, so CI keeps these honest.

## Files

| File | Purpose |
|---|---|
| `demo-board.kicad_sch` | Minimal 4-net schematic (R1 pulls A and B; U1 consumes them) |
| `intent.csv` | "These are the connections I meant to make" — audited by `check-intent` |
| `rules.csv` | "This is what healthy looks like structurally" — audited by `check-rules` |

## 5-minute walkthrough

With KiCad 8+ installed (`kicad-cli` on PATH):

```bash
# 0. sanity check your environment
python scripts/fiducial.py doctor

# 1. structural lint (pure python, no KiCad needed)
python scripts/fiducial.py lint examples/demo-board.kicad_sch

# 2. electrical rules check via KiCad
python scripts/fiducial.py erc examples/demo-board.kicad_sch

# 3. does the schematic match declared intent?
python scripts/fiducial.py check-intent examples/demo-board.kicad_sch examples/intent.csv

# 4. does it satisfy house-style rules?
python scripts/fiducial.py check-rules examples/demo-board.kicad_sch examples/rules.csv

# 5. see every net the way fiducial sees them
python scripts/fiducial.py nets examples/demo-board.kicad_sch
```

All four checks exit `0` on this example. To see a failure, delete any row's
connection from the schematic — or try the broken fixtures in `tests/fixtures/`
(`duplicate-ref`, `single-use-label`, `malformed`) and watch each get caught.

## Why CSVs instead of config files?

Because intent should be reviewable in the same PR as the schematic, diffable,
and boring. See [docs/rules.md](../docs/rules.md) for the full rule grammar.
