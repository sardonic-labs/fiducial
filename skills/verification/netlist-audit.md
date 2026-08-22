# Netlist audit — proving the schematic matches design intent

The single most valuable verification step. AI-authored schematics usually
*look* right; the bugs are in connectivity. This workflow catches them
mechanically.

## Step 1 — Write down intent before (or while) wiring

Create `intent.csv` with one row per connection that matters:

```
ref,pin,expected_net
U1,1,+3V3
U1,23,SWDIO
U1,24,SWCLK
J2,1,VBUS
J2,5,GND
```

Derive it from the datasheet pin table and the power tree, **not** from the
schematic you just wrote.

## Step 2 — Audit

```
python fiducial/scripts/fiducial.py check-intent <project.kicad_sch> intent.csv
```

Exit code 0 = every expected connection verified. Any `MISSING` or `WRONG`
row is a bug: fix the schematic, not the CSV (unless the CSV was wrong).

## Step 3 — Structural sweep

`lint` now also catches two connectivity smells mechanically:

- **single-use labels** that don't join any multi-pin net (the classic
  "cap labeled /XIN but crystal wired to Net-(U1-XIN)" bug),
- **orphan nets** with exactly one connected pin.

You can get the orphan list with intent scoring via
`check-intent <project> <csv> --orphans`.

## Step 4 — Spot-check critical parts

```
python fiducial/scripts/fiducial.py pins <project.kicad_sch> U1
python fiducial/scripts/fiducial.py nets <project.kicad_sch>
```

Check specifically:

- Every power pin of every IC reaches a power net (no floating VDD).
- Crystal/oscillator pins on the right nets.
- USB D+/D− not swapped.
- Boot/strap pins pulled to the correct rail.
- Debug connector wired to SWD pins, not neighboring GPIO.
- Connector pinouts match the mating device's datasheet (pin 1 orientation!).

## Rules

- An ERC pass does **not** imply connectivity correctness. ERC checks rules;
  this checks intent.
- When a check fails, trace it in the schematic source (`grep` for the label)
  before editing. Fix the root cause (label typo, off-grid wire), not the symptom.
- Re-run the full audit after every schematic edit batch.
