# Hierarchical sheets — organizing a multi-block schematic

Split a design into sub-sheets when it has more than ~2 functional blocks.
The backplane battery-entry session (2026-08-23) produced a working but
cluttered flat sheet; blocks that live on separate sheets cannot bleed into
each other, and each sheet is reviewable on its own.

Fiducial requires no changes to work across hierarchy: the netlist flattens
all sheets, so `lint`, `erc`, `check-intent`, and `check-rules` run against
the root project exactly as on a flat design. This is proven nightly against
hierarchical foreign boards (KiCad `complex_hierarchy` demo, ZSWatch Watch-HW)
in the corpus harness.

## When to split

- One functional block = one sheet (battery entry, one slot feed, debug
  header, expander control).
- The root sheet holds connectors and inter-sheet links only — no block
  internals.
- Maximum 2 levels of nesting for v0-era designs. Deep trees are harder to
  audit than wide ones.

## Sheet naming

- `<block>.kicad_sch`, lowercase, same name as the sheet symbol's value
  (e.g. `battery_entry.kicad_sch`).
- The root file keeps the project name (`<project>.kicad_sch`).

## The three label types — the part everyone gets wrong

| Type | Use for | Visible where |
|---|---|---|
| **Hierarchical label** + matching sheet-symbol pin | Signals crossing this sheet's boundary | Inside this sheet, and on the parent's sheet symbol |
| **Global label** | Power rails only (`GND`, `+3V3`, `/VBAT_SW`) | Everywhere |
| **Local label** | Signals internal to one sheet | This sheet only |

Rules:

1. If a signal crosses a sheet boundary, it MUST be a hierarchical label with
   a matching pin on the parent's sheet symbol. A global label "because it's
   easier" hides the interface — the sheet symbol should read like a part
   datasheet: every pin named, every pin justified.
2. Sheet-symbol pin names match their hierarchical labels exactly.
3. Never mix a global label and a hierarchical label for the same logical
   signal — that creates two nets that look like one.

## Refdes across sheets

- One annotation scheme project-wide (see [cleanliness.md](cleanliness.md)).
- KiCad annotates globally; references stay unique across sheets automatically
  — do not re-annotate per sheet.
- Functional refdes styles (`Q-VBAT`) are allowed if declared as the project
  convention, but must then be used for every reference, on every sheet.

## Per-sheet definition of done

Each sheet independently satisfies the [cleanliness.md](cleanliness.md)
definition of done, plus:

- [ ] Every hierarchical label has a matching sheet-symbol pin (and vice versa)
- [ ] intent.csv rows for this block's connections are written and pass
      `check-intent` (intent is project-global; the netlist is flat)

## Copy-paste sheets (e.g. six identical slot feeds)

KiCad has no multi-channel annotation. Copying one slot sheet six times means
hand-fixing every reference — and one missed fix is six copies of the same
silent mistake. Mitigation:

- Copy, then immediately re-annotate the whole copied sheet
- Assert every slot's connections individually in intent.csv (six copies of
  each row, distinct refs) so `check-intent` proves all six copies stayed
  parallel
