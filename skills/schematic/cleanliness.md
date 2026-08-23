# Schematic cleanliness standard

What "clean" means, mechanically. Every rule here was violated by a real
AI-authored schematic on 2026-08-23 (backplane-v0 battery entry, first pass):
scattered placement, two coexisting refdes conventions, rotated labels in
every direction, leftover placeholder annotations, and orphan components that
survived three design iterations. None of it affected ERC. All of it made the
schematic harder to audit, review, and trust.

Clean is not aesthetic. Clean is auditability.

## Grid

- Every symbol, wire endpoint, and label sits on the schematic grid
  (50 mil / 1.27 mm multiples in default KiCad settings).
- No free-floating symbols "roughly near" their wires. A wire that touches a
  pin off-grid silently fails to connect — this is the classic invisible bug.

## Layout

- Signal flows left to right: inputs on the left of a block, outputs on the
  right, power rails entering from the top, ground exiting the bottom.
- A block is drawn as its block diagram: a battery entry is a literal
  left-to-right chain (connector → fuse → protection → switch → output).
- One functional block per region. Whitespace separates regions. A region
  header comment (text note) names the block — and is removed when the block
  is done, not left as debris.
- No diagonal wires. Orthogonal only. If two points need a diagonal, you need
  a net label instead.

## Wiring

- Prefer net labels over long wires (see [authoring.md](authoring.md)). A wire
  longer than ~10 grid units to reach a same-block neighbor is a label.
- Every junction explicit. No wire "passing through" a pin hoping KiCad
  infers a connection.

## Labels and references

- ONE refdes convention per project, chosen before the first symbol:
  either `Q1`, `R2`, `F1` (KiCad default style) or functional names
  (`Q-VBAT`, `R-GS`), never both. Mixing conventions in one schematic
  (observed 2026-08-23) makes BOMs and intent rows ambiguous.
- Label text orientation: horizontal labels read left-to-right, vertical
  labels read bottom-to-top. Do not rotate labels to arbitrary angles to
  "fit" — move the label.
- Power rails are global labels (`GND`, `+3V3`, `/VBAT_SW`). Block-internal
  signals are local labels. Signals crossing blocks are hierarchical labels
  (see [hierarchy.md](hierarchy.md)).

## Debris

The following must not survive into a completed block:

- Placeholder text: `[pending]`, `TODO`, `⚠`, question marks
- Symbols from abandoned iterations (an orphan pair of parts connected only
  to each other is still debris — see lint's orphan-island check)
- Duplicate parts of the same function, unless the duplication is a written
  design decision
- Comment text from earlier iterations that no longer matches the design

## Definition of done (per block)

1. All symbols on grid, placed per layout rules
2. One refdes convention, applied everywhere
3. Zero debris items from the list above
4. `lint` findings triaged to zero unexplained
5. `erc` clean
6. `check-intent` exit 0
7. Block region named; placeholder notes removed
