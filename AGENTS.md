# fiducial — AI hardware design instructions

This file is the entry point. A project that includes this repo (usually as a
submodule at `fiducial/`) imports it from its own `AGENTS.md` with:

```
@fiducial/AGENTS.md
```

## Golden rules

1. **Never guess pinouts, net names, or electrical characteristics.** Verify
   against the datasheet and against the actual files on disk.
2. **Verify after every change.** Run `erc`, `drc`, and the connectivity audit
   (see Tools below). An unverified schematic is a broken schematic.
3. **Read before editing.** KiCad files are S-expressions. Read the relevant
   section, understand it, then make a minimal, targeted edit.
4. **Prefer kicad-cli over hand-editing** for anything it can do (exports,
   reports, BOMs). Hand-edit only what it cannot.

## Tools

All tools are Python 3 stdlib-only. Run them from the project root:

```
python fiducial/scripts/fiducial.py <command>
```

| Command | Purpose |
|---|---|
| `doctor` | Check kicad-cli availability and version |
| `erc <project.kicad_sch>` | Run ERC, summarize JSON report, exit code reflects errors |
| `drc <project.kicad_pcb>` | Run DRC, same behavior |
| `netlist <project.kicad_sch>` | Export netlist to `<project>-netlist.sexpr` |
| `nets <project.kicad_sch>` | Dump every net with its connected pins |
| `pins <project.kicad_sch> <REF>` | Dump one symbol's pins and their nets |
| `check-intent <project.kicad_sch> intent.csv` | Compare expected connections (`ref,pin,expected_net`) against reality |
| `lint <project.kicad_sch>` | Structural checks: duplicate refs, missing fields, unconnected pins |
| `render <project...> --outdir DIR` | Export SVG renders of schematic and/or PCB so you can look at them |
| `bom <project.kicad_sch>` | Export CSV bill of materials |

Exit codes: `0` clean, `1` violations found, `2` tool/environment error.

## Instruction library

Read these when doing the corresponding task — not all up front:

- `skills/schematic/authoring.md` — editing `.kicad_sch` safely (read before any schematic edit)
- `skills/pcb/layout.md` — placement and routing rules (read before PCB work)
- `skills/pcb/drc-workflow.md` — running and fixing DRC violations
- `skills/verification/netlist-audit.md` — proving the schematic matches design intent
- `skills/reference/kicad-cli-cookbook.md` — every useful kicad-cli invocation
- `skills/reference/datasheets.md` — finding and reading datasheets correctly
- `skills/reference/best-practices.md` — power, signal integrity, ESD, DFM, testability checklists
- `skills/reference/terminology.md` — canonical vocabulary; use these terms consistently

## Workflow

For any board project:

1. `doctor` first.
2. Write down design intent (power tree, buses, connector pinout) as a flat
   list or `intent.csv` **before** wiring nets.
3. Author/edit the schematic per `authoring.md`.
4. `lint` → fix → `erc` → fix.
5. `nets` / `pins` spot-check critical parts; `check-intent` for full coverage.
6. Only then move to layout. After layout: `drc` until clean, `render` and
   visually inspect both copper layers.
