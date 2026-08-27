# Skills index — agent map (humans may read, agents `grep`)

> Entry: `AGENTS.md:1`. Import via `@fiducial/AGENTS.md:1` → bootstrap appends one line. All skills are `agent: true` (humans see `docs/` for narrative; agents `grep skills/`).

## When to load (per-task, not all)

| Task | Load this skill | Why |
|---|---|---|
| Any schematic edit | `schematic/authoring.md:1` | S-exp mechanics, never reuse UUID, labels over wires |
| Block workflow | `schematic/authoring-workflow.md:1` | intent-first loop, debris reconciliation |
| Cleanliness gate | `schematic/cleanliness.md:1` | grid 1.27 mm, orthogonal, one refdes convention |
| Hierarchy | `schematic/hierarchy.md:1` | `label` vs `global_label` vs `hierarchical_label` |
| Power parts | `schematic/power-parts-selection.md:1` | dissipation/margin math before selection |
| Power/ground | `pcb/layout.md` / `pcb/drc-workflow.md` | placement, DRC fix loop |
| Prove intent | `verification/netlist-audit.md:1` | `intent.csv` before wiring, `check-intent` gate |
| Datasheets | `reference/datasheets.md` | find + read, never guess pinouts (`AGENTS.md:11`) |
| Best practices | `reference/best-practices.md` | power/SI/ESD/DFM checklists |
| Terminology | `reference/terminology.md` | canonical vocab |
| KiCad CLI | `reference/kicad-cli-cookbook.md` | every useful `kicad-cli` invocation |
| Footprints | `reference/footprints.md` | `find_part.py` + JLC catalog |
| Builder | `docs/builder.md:1` / `docs/reference/api-builder.md` | `SchematicBuilder` replaces hand-rolling |
| S-exp | `docs/reference/sexp.md` | `parse_sexp:68` grammar |

## Review skills (standalone, severity-rated)

Orchestrator: `python fiducial/scripts/reviewer.py <skill> <file> [--json] [--intent intent.csv]` (`reviewer.py:22`)

| Skill file | What it checks | Commands behind |
|---|---|---|
| `review/schematic-correctness.md` | intent matching, pin assignments | `check-intent`, `unconnected`, `orphan-nets` |
| `review/schematic-completeness.md` | missing parts, decoupling | `unconnected`, `decoupling-check`, `debris-scan` |
| `review/schematic-style.md` | naming, labeling | `grid-check`, `refdes-audit`, `label-audit` |
| `review/power-tree.md` | margins, protection | `rail-audit`, `power-pins`, `bom ratings` |
| `review/pcb-layout.md` | placement, outline | `board-stats`, `board-outline`, `placement-density` |
| `review/pcb-routing.md` | widths, vias, SI | `trace-widths`, `via-audit` |
| `review/dfm.md` | manufacturability | `drill-table`, `trace-widths`, `via-audit` |
| `review/bom.md` | availability, ratings | `bom_check parse/ratings/lifecycle` |
| `review/connectivity.md` | cross-block, connectors | `lint`, `label-audit`, `orphan-nets` |
| `review/documentation.md` | title, revision | `debris-scan`, `label-naming`, `refdes` |

Low-level: `schematic_check.py:28` (`power-pins` … `rail-audit`), `pcb_check.py:138`, `bom_check.py:28`.

## Machine index

```json
{
  "entry": "AGENTS.md:1",
  "golden_rules": "AGENTS.md:10",
  "tools": "AGENTS.md:28 (fiducial.py:1252 + exit 0/1/2)",
  "skills": ["schematic/authoring.md:1","schematic/authoring-workflow.md:1","schematic/cleanliness.md:1","schematic/hierarchy.md:1","schematic/power-parts-selection.md:1","pcb/layout.md","pcb/drc-workflow.md","verification/netlist-audit.md:1","reference/*"],
  "review": ["review/*.md","reviewer.py:22","schematic/pcb/bom_check.py"],
  "builder": "docs/builder.md:1"
}
```
