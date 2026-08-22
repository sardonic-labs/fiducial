# Finding symbols and footprints

Every part in a schematic needs a symbol; every part in a layout needs a
footprint. Hunting these is high-friction toil — this skill plus
`scripts/find_part.py` exist to make it mechanical.

## Search order (cheapest first)

1. **Project-local libraries** (`<repo>/libraries/`) — anything a previous
   board already sourced. Check here before anywhere else.
2. **KiCad bundled libraries** — installed under the KiCad data directory.
   Commodity THT connectors, common packages, and passives almost always live
   here. `find_part.py --system` scans them.
3. **JLCPCB/LCSC catalog** (`C######` numbers) — preferred for anything SMD,
   because assembly is sponsored and parts ship with matched footprints.
   Search on lcsc.com / jlcpcb.com/parts; download or note the C-number.
4. **Vendor direct pages** — TI/NXP/Samtec/Molex publish reference designs and
   sometimes step/footprint files on product pages.
5. **Manual escalation** — SnapEDA, UltraLibrarian, Component Search Engine.
   These require login/click-agreements: do NOT bulk-scrape them. One manual
   download per missing part is fine; record it in `libraries/SOURCES.md`.

## Using find_part.py

```
python fiducial/scripts/find_part.py <query> [--root DIR]... [--kind sym|fp|any]
```

- Walks the given roots (default: project `libraries/`, then system KiCad dirs)
  matching `<query>` against `.kicad_mod` filenames and symbol-library names/content
- Prints `path` for every hit; exit code 0 = at least one hit, 1 = none found
- No hits ⇒ escalate to steps 3–5 above and add what you download to
  `libraries/` so the next search finds it locally

## Rules

- **Verify pin mapping against the datasheet**, even when the footprint came
  from a trusted library. Wrong-pin footprints are the classic silent killer.
- **Footprint pad numbers must equal symbol pin numbers** (`"1"` ≠ `"A1"`).
- Prefer footprints with slightly LARGER pads over exact-minimum when hand
  soldering is expected.
- Record provenance: every non-bundled part gets a row in
  `libraries/SOURCES.md`.
