# Schematic authoring (editing `.kicad_sch` safely)

`.kicad_sch` files are S-expressions. KiCad is forgiving on read but strict on
structure — a malformed file can silently lose symbols. Follow these rules.

## Before editing

- Read the relevant section of the file first. Never edit from memory.
- Note the file's `version` field; syntax varies between KiCad 7/8/9. Match the
  existing file's style exactly rather than mixing versions.
- Find the symbol you care about by `(property "Reference" "U1" ...)` inside a
  top-level `(symbol ...)` block. Symbol *definitions* live in the separate
  `(lib_symbols ...)` section — do not confuse them.

## Rules

1. **Every new symbol needs:**
   - a matching entry in `lib_symbols` (copy the definition from the library
     file it came from — never invent pin definitions),
   - a unique `(uuid ...)`,
   - `(property "Reference" ...)`, `(property "Value" ...)`, and ideally
     `(property "Footprint" ...)`.
2. **Never reuse UUIDs.** Generate fresh ones per object.
3. **Connect with labels, not long wires.** Prefer net labels (`(label ...)`)
   or global labels for power/buses. Long routed wires are fragile under
   hand-editing and hard to audit.
4. **Power symbols are symbols.** `GND`/`+3V3` connections come from placing
   power symbols (e.g. `power:GND`), which attach their net name via a hidden
   power pin. A wire that merely *looks* connected to nothing is not GND.
5. **One edit at a time, then re-run** `lint` + `erc`. Do not batch ten edits
   before verifying.
6. **Pin numbers are strings and must match the footprint pads exactly**
   (`"1"` ≠ `"A1"`). Verify against `lib_symbols` pin definitions, which must
   match the datasheet.
7. **Do not reorder or delete unknown blocks.** If a block looks like noise,
   leave it alone unless you understand its role.

## Common failure modes seen in AI-authored schematics

| Symptom | Usual cause |
|---|---|
| ERC "pin not driven" everywhere | Missing power flags / PWR_FLAG |
| Net exists but part doesn't respond | Label typo — `+3V3` vs `3V3` creates two nets |
| Pin "connected" but not in netlist | Wire endpoint off-grid or not touching the pin |
| Wrong pin wired | Trusting an LLM memory of the pinout instead of the datasheet |
| Two nets that should be one | Global label vs local label mismatch |

## After every edit

```
python fiducial/scripts/fiducial.py lint <project.kicad_sch>
python fiducial/scripts/fiducial.py erc <project.kicad_sch>
python fiducial/scripts/fiducial.py pins <project.kicad_sch> <REF>
```
