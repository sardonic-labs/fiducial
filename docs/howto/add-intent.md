# How-to: write `intent.csv` before wiring

> Intent is the contract. Write it from the datasheet **before** you place a wire — otherwise `check-intent` can only describe what you already did (`verification/netlist-audit.md:7`).

## For humans

1. Open the datasheet pin table + your power tree.
2. Create `intent.csv`:

```csv
ref,pin,expected_net
R1,1,/A
R1,2,/B
U1,1,/VCC
C1,2,/GND
```

Rules from `fiducial.py:391`:

* Header must be `ref,pin,expected_net` (case-sensitive, extra columns ignored, BOM ok `encoding="utf-8-sig"`).
* `pin` is string, must match footprint pad exactly (`"1"` ≠ `"A1"` — `authoring.md:36`).
* `expected_net` must be netlist name (`/A` local, `GND` or `+3V3` global — `kicad-versions.md:42`).
* `NC` means “no-connect” — skipped (`fiducial.py:405` `want.upper() == "NC"`), use for DNC pins.

3. Save next to `myboard.kicad_sch` and run:

```sh
python scripts/fiducial.py check-intent myboard.kicad_sch intent.csv
# or: python scripts/fiducial.py lint myboard.kicad_sch --json | jq .problems
```

## For agents (checklist → CSV)

Checklist (1:1 with rows):

```md
- [ ] R1.1 → /A  (datasheet p.12, crystal load)
- [ ] U1.20 → /XIN  (net "Net-(U1-XIN)" in buggy fixture → WRONG, caught in README.md:30)
- [ ] J1.A6 → /USB_DP (verify pin 1 orientation!)
```

Emit:

```json
{"ref": "R1", "pin": "1", "expected_net": "/A"}
```

Builder shortcut — `docs/builder.md:62` `write_intent()`:

```python
b.connect("R1","1","/A")          # records (ref,pin,net)
b.write_intent("intent.csv")      # writes header + rows
```

## Verify

```sh
python scripts/fiducial.py check-intent myboard.kicad_sch intent.csv --json
# {"verified": 58, "total": 64, "results": [...], "orphans": []}  (fiducial.py:428)
# Exit 0 → pass, 1 → WRONG/MISSING, 2 → bad CSV (fiducial.py:15)
```

Add `--orphans` to flag single-pin nets (`fiducial.py:450`); `--refresh` forces netlist re-export (`fiducial.py:311`).

## When `lint` disagrees

* `label appears only once and does not join any multi-pin net` (`fiducial.py:905`) → you typed `/XIN` but crystal is `Net-(U1-XIN)` — fix the label, not the CSV (the planted bug in `tests/fixtures/rp2040-devboard.kicad_sch:20`).
* `net '/LONELY' has a single connection (U1.99)` (`fiducial.py:909`) → dangling, add to intent or add `no_connect`.
* `allow-single-use` in `docs/rules.md:1` suppresses intentional single-use (e.g. testpoint).

## Machine block

```json
{"howto": "add-intent", "source": "skills/verification/netlist-audit.md:1", "inputs": ["datasheet pin table"], "outputs": ["intent.csv"], "gate": "check-intent --json"}
```
