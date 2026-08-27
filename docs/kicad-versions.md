# KiCad version differences

KiCad's `.kicad_sch` and `.kicad_pcb` formats are S-expressions that change
between major versions.  fiducial targets **KiCad 10** (the current stable)
but may encounter files from KiCad 7/8/9.  This doc catalogues the format
differences agents hit in practice.

## Version field

Every `.kicad_sch` file starts with a version number:

| KiCad | `version` field | Notes |
|-------|----------------|-------|
| 7 | `20230121` | Earliest version fiducial supports for parsing |
| 8 | `20231120` | Added `instances` block inside symbols |
| 9 | `20240108` | Minor property changes |
| 10 | `20260306` | Current stable; generator_version `"10.0"` |

**Rule:** Match the existing file's version when editing.  Do not mix
versions within a file.  The `SchematicBuilder` class emits KiCad 10
format.

## Gotchas that break agents

### 1. `(at x y)` requires three parameters

**KiCad 10:** `(at x y rotation)` — always three values.

```lisp
;; WRONG — KiCad 10 will reject this or silently misplace the symbol:
(symbol (at 101.6 76.2) ...)

;; CORRECT:
(symbol (at 101.6 76.2 0) ...)
```

KiCad 7/8 accepted two-parameter `(at x y)` in some contexts.  KiCad 10
requires the rotation field everywhere: symbols, labels, wires (via
`(pts ...)`), and no-connects.

### 2. Local labels get `/` prefix in netlist

When you write `(label "USB_DP" ...)`, the netlist export produces
`/USB_DP` (with a leading slash).  This means:

- `intent.csv` must use `expected_net=/USB_DP`, not `USB_DP`.
- `check-intent` comparison is case-sensitive and prefix-sensitive.
- Global labels (`(global_label ...)`) do **not** get the prefix.

```csv
ref,pin,expected_net
U1,46,/USB_DP
U1,47,/USB_DM
```

### 3. Hidden pins create 5.08mm gaps

Some KiCad library symbols have **hidden power pins** (GND, VCC).  These
pins are electrically connected by name, not by wire.  When placing
components next to such symbols:

- Leave a 5.08mm (2-grid) gap on the side with hidden pins, or
- Use power symbols instead of routing wires to those pins.

The RP2040 symbol has hidden GND and DVDD pins on the left side — GPIO
labels placed at the standard 2.54mm grid offset will not connect.

### 4. Power symbols attach via hidden pins

`power:GND` and `power:+3V3` are symbols whose only pin is a hidden
`power_in` pin.  The net name comes from the symbol name, not from a wire.

```lisp
;; This GND symbol connects to the GND net automatically — no wire needed:
(symbol
    (lib_id "power:GND")
    (at 101.6 88.9 0)
    ...)
```

You **cannot** connect a power symbol by routing a wire to it.  The wire
must connect to a component pin; the power symbol is placed at the same
coordinate and the hidden pin does the rest.

### 5. `justify left bottom` affects text, not connection point

Labels have a `(justify left bottom)` in their effects block.  This
controls text rendering only — the electrical connection point is still at
the `(at x y)` coordinate.  Do not offset the label position to "fix"
text alignment.

### 6. `(instances)` block required in KiCad 8+

KiCad 8+ added an `(instances ...)` block inside each symbol instance.
This maps the symbol to a project and assigns the reference:

```lisp
(instances
    (project "project_name"
        (path "/root-uuid"
            (reference "R1")
            (unit 1)
        )
    )
)
```

Omitting this block causes KiCad to create a default instance on load,
which may conflict with your intended reference assignment.

### 7. UUID format

KiCad 10 uses standard UUID v4 format:

```lisp
(uuid "a1b2c3d4-e5f6-7890-abcd-ef1234567890")
```

Do not reuse UUIDs across symbols, wires, labels, or pins.  Every object
needs a unique UUID.  The `SchematicBuilder` generates these automatically.

### 8. Wire endpoints must be exact

KiCad builds its netlist from **physical wire connectivity**, not logical
label names.  Two wires sharing a coordinate (even at a T-junction) create
an electrical connection.  This is correct behavior but means:

- A wire from (100, 50) to (120, 50) and another from (120, 50) to
  (120, 70) share the point (120, 50) and will be on the same net.
- Use `fiducial overlap-check` to detect accidental shorts.

### 9. Power flags (PWR_FLAG) required for ERC

ERC reports "pin not driven" for any net that has no pin classified as
`power_out`.  Power symbols (`power:+3V3`, `power:GND`) provide this
classification automatically.  If you have a power net without a power
symbol, add a `PWR_FLAG` symbol or connect the net to a power symbol.

## Version detection in code

```python
from scripts.fiducial import load_sexp, _first_str, sexp_get

root = load_sexp("myboard.kicad_sch")
version = int(_first_str(sexp_get(root, "version")))
if version >= 20260306:
    print("KiCad 10 format")
elif version >= 20240108:
    print("KiCad 9 format")
elif version >= 20231120:
    print("KiCad 8 format")
else:
    print("KiCad 7 or earlier")
```

## References

- [KiCad S-expression format](https://dev-docs.kicad.org/en/file-formats/coordinate-system/)
- [KiCad 10 migration guide](https://www.kicad.org/blog/)
- [fiducial authoring skills](../skills/schematic/authoring.md)
