# How to fix a seeded fault (practice loop)

Each fault in `tests/fixtures/faults/<name>/` is a broken board with a
known-good `intent.csv`. Your job: find the bug and fix `board.kicad_sch`
until `lint` and `check-intent` pass.

```sh
# pick a fault, e.g. label-typo
cd tests/fixtures/faults/label-typo
python ../../../scripts/fiducial.py lint board.kicad_sch
python ../../../scripts/fiducial.py check-intent board.kicad_sch intent.csv
```

## Loop

1. `lint` first — read every `LINT:` line; fix structure (typos,
   duplicates, off-grid) before connectivity.
2. `check-intent` — each `WRONG` row names the pin and both nets:
   fix the schematic, not the CSV (the CSV is the datasheet).
3. `pins <REF>` / `nets` to confirm the fix; re-run both commands
   until exit `0`.
4. After editing the `.sch`, delete `board-netlist.sexpr` (or pass
   `--refresh`) so the netlist is re-exported; the shipped cache is
   only for offline CI.

## Fault guide

| Fault | Symptom | Fix |
|---|---|---|
| `label-typo` | `appears only once` + `WRONG` | rename `/AX` back to `/A` |
| `floating-pin` | `single connection` + `WRONG` on `unconnected-*` | reconnect C1.2 to `/GND` |
| `wrong-net` | `single connection` on `/B` + `WRONG` | move R1.2 back to `/B` |
| `missing-part` | `single connection`s + `MISSING` | restore C1 symbol + wiring |
| `duplicate-ref` | `duplicate reference` only (intent clean) | rename second `R1` to `C1` |
| `off-grid` | `off-grid` only (intent clean) | move R1 back to `(50.8, 50.8)` |
| `power-short` | `appears only once` + `WRONG` on `/VCC` | restore `/VCC` label, split rail |
| `nc-violation` | `appears only once` + `WRONG` on `unconnected-*` | reconnect R1.2 to `/B` |

## Regenerate

```sh
python scripts/seed_faults.py --check   # rebuild + assert all 16 checks
python -m unittest tests.test_seeded_faults -v
```
