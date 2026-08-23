# Block authoring workflow — how to build one functional block

This workflow exists because of a real failure (backplane-v0 battery entry,
2026-08-23): an agent drew a working topology in 30 minutes but left orphan
components, two series fuses, two refdes conventions, and an empty intent.csv.
The circuit was almost right; the *process* was entirely absent. Follow this
loop and the debris cannot happen.

## The loop

For each functional block (battery entry, one slot feed, debug header, ...):

### 1. Read the block spec

Find the block in the design doc (knowledge-base engineering notes or the
issue). Note every requirement: parts, protections, fail-safe behavior,
test criteria. If there is no spec, write one before drawing anything.

### 2. Write intent rows FIRST

Open `intent.csv` and add one row per connection you intend to make, before
wiring anything. This is the contract. You cannot abandon parts you have
made promises about — which is exactly the point. An intent row with no
matching schematic connection will fail `check-intent`; a schematic
connection with no intent row is unaudited and therefore not done.

### 3. Place, then annotate, then wire

- Place all symbols for the block in position per [cleanliness.md](cleanliness.md)
- Annotate references immediately, using the project's ONE refdes convention
- Only then draw wires and labels

### 4. Verify the block

```
python fiducial/scripts/fiducial.py lint <project.kicad_sch>
python fiducial/scripts/fiducial.py erc <project.kicad_sch>
python fiducial/scripts/fiducial.py check-intent <project.kicad_sch> <intent.csv>
python fiducial/scripts/fiducial.py nets <project.kicad_sch>
```

All four must pass (lint findings must be triaged, not ignored).

### 5. Reconcile debris, then declare done

Before declaring the block complete, check for your own leftovers:

- [ ] Every symbol placed is wired and in intent.csv
- [ ] No symbols from earlier iterations remain unconnected
- [ ] No duplicate parts of the same function (two fuses in series is a
      decision, not an accident — write it down if intentional)
- [ ] No placeholder text annotations left (`[pending]`, `TODO`, `⚠`)
- [ ] Every net label used exactly where intended; no single-use labels
- [ ] intent.csv rows match the netlist exactly (`check-intent` exit 0)

Only then move to the next block. A block that is "almost done" is not done.

## Why intent-first matters

Writing intent rows after wiring converts the audit into a description of
what you already did — it can catch nothing. Writing them first makes the
audit a comparison of promise versus execution, which is the only version
that catches mistakes. See [../verification/netlist-audit.md](../verification/netlist-audit.md).

## Block boundary discipline

- One block at a time. Do not open a second block while the first has
  failing checks.
- If a decision changes mid-block (e.g. part substitution), update intent
  rows and any leftover symbols from the old approach in the same sitting.
  Debris compounds; it never resolves itself.
