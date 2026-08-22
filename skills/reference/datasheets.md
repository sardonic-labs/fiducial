# Finding and reading datasheets

## Finding the right document

1. **Official source first.** Manufacturer product page → "Documentation" or
   direct PDF link (`ti.com/lit/ds/symlink/...`, `st.com/resource/en/...`).
   Aggregator copies (alldatasheet etc.) are last resort — often outdated
   revisions.
2. **Match the exact part.** Package suffix, speed grade, temperature range:
   `STM32F411CEU6` ≠ `STM32F411CEY6`. The pinout can differ between packages.
3. **Check revision/date** on the cover; use the newest unless a design is
   frozen.
4. **Errata sheets exist** for most MCUs. Search `<part> errata` before
   committing to a peripheral usage pattern; known bugs are documented there.

## Reading order (per datasheet session)

For a new IC, extract in this order:

1. **Features block** — confirm it actually does what you need (voltage range,
   peripheral count, speed).
2. **Pin configuration table** — for *your exact package*. This becomes
   `intent.csv`. Copy it mechanically; never from memory.
3. **Absolute maximum ratings** — then **recommended operating conditions**;
   design to recommended, never near absolute maximums.
4. **Typical application circuit** — replicate it. The vendor's reference
   circuit for power/USB/crystal is usually correct and tested; deviating
   needs justification.
5. **External component requirements** — decoupling values/placement, crystal
   load caps formula (CL = (C1·C2)/(C1+C2) + Cstray), pull-up/down values.
6. **Package mechanical drawing** — only when creating footprints.

## Rules

- Quote pin numbers/names from the table you just read, with the package name.
- If two documents disagree (datasheet vs reference manual), the datasheet
  governs electrical limits, the reference manual governs register behavior.
- Record the document title/revision in project notes so decisions are
  traceable.
- For connectors: read the mating cable/device spec too — pin 1 orientation
  and mirrored pinouts on board-mount vs cable-end are the classic trap.
