# How-to: migrate hand-rolled S-exp → `SchematicBuilder`

> Every rule here was violated by real AI-authored S-exp on 2026-08-23 (`authoring.md:6`).

## Identify hand-rolled smells

```sh
rg -n '"Reference" "R1"' myboard.kicad_sch | head
rg -n '\(uuid ' myboard.kicad_sch | wc -l   # should be unique per object
python scripts/fiducial.py lint myboard.kicad_sch  # expect: duplicate ref, off-grid, single-use label
```

## For humans (3 steps)

### 1. Replace `lib_symbols` + `symbol` boilerplate with `add_symbol`

**Before (hand-rolled):**

```lisp
(symbol
  (lib_id "Device:R")
  (uuid f000...)  ; reused → lint: duplicate uuid (fiducial.py:883)
  (at 81.3 50.8 0) ; off-grid (fiducial.py:572)
  (property "Reference" "R1" ...)
)
;; forgot lib_symbols entry → lint: not in lib_symbols (fiducial.py:877)
```

**After (builder):**

```python
from schematic_builder import SchematicBuilder
b = SchematicBuilder("myboard.kicad_sch", title="My Board")
b.add_symbol("Device:R", ref="R1", value="10k", footprint="Resistor_SMD:R_0603", at=(81.28, 50.8))
# enforces: uuid, instances block, lib_symbols stub, grid 1.27 mm (builder.md:74), raises BuilderError with snap hint
```

### 2. Replace long wires with `connect()` (labels)

**Before:** 4 `(wire (pts (xy 50.8 46.99) ...))` + one `(label "NET_A" ...)` — fragile, diagonal risk (`cleanliness.md:24`).

**After:**

```python
b.connect("R1","1","/A")  # label at pin endpoint (fiducial.py:618 math), auto global_label for power (hierarchy.md:33)
b.connect("U1","2","/A")  # same net → lint sees multi-pin, not “appears only once” (fiducial.py:905)
```

### 3. Power + NC

**Before:** `GND` as wire to nowhere — ERC “pin not driven” (`authoring.md:36`).

**After:**

```python
b.add_power("GND", at=(50.8, 80.01))  # power:GND symbol, hidden power_in pin (kicad-versions.md:69)
b.no_connect("U1","4")               # NC marker (fiducial.py:883)
```

## For agents (mechanical transform)

```python
# 1. Parse existing (fiducial.py:128)
root = load_sexp("myboard.kicad_sch")
# 2. Iterate (property "Reference" "U1") in (symbol ...) blocks (authoring.md:21)
# 3. Emit builder calls:
#    add_symbol(lib_id, ref, value, at=(x,y))
# 4. Replace (wire ...) + (label ...) with connect(ref,pin,net)
# 5. b.save(validate=True)  # runs lint in-process (schematic_builder.py:548)
```

## Verify

```sh
python examples/builder_demo.py  # reference
python scripts/fiducial.py lint myboard.kicad_sch --json | jq .problems
python scripts/fiducial.py sexp myboard.kicad_sch --json | jq ._key  # → "kicad_sch"
```

Exit `0` clean (`reference/exit-codes.md`). Add incremental edits via `SchematicBuilder.load("myboard.kicad_sch").add_symbol(...).save()` (`builder.md:122`).

```json
{"howto": "migrate", "source": "authoring.md:6", "inputs": ["myboard.kicad_sch"], "outputs": ["SchematicBuilder calls"], "gate": "lint --json"}
```
