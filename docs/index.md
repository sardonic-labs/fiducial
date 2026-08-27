# Docs hub

> **For humans:** start at `tutorial.md`. **For agents:** start at `../AGENTS.md` + `skills/index.md`. This file is the map for both.

## TL;DR

| You are… | Read this | Then this |
|---|---|---|
| Human, first time | `tutorial.md:1` (5 min blinky) | `howto/add-intent.md` → `reference/cli.md` |
| Human, reviewer | `explanation/architecture.md` | `reference/exit-codes.md` |
| Agent, authoring | `AGENTS.md:10` + `skills/schematic/authoring.md:1` | `reference/api-builder.md` (`docs/builder.md:1`) |
| Agent, verifying | `skills/verification/netlist-audit.md:1` | `reference/exit-codes.md` + `--json` examples |

## Map (Diátaxis)

* **Tutorial** — `tutorial.md` — one path, 5 min, copy-paste. Humans + agents share the same `intent.csv` → `build()` flow.
* **How-to** — `howto/` — problem-oriented recipes:
  * `howto/add-intent.md` — write `intent.csv` before wiring.
  * `howto/migrate-handrolled.md` — hand-rolled S-exp → `SchematicBuilder`.
* **Reference** — `reference/` — authoritative, machine-parseable:
  * `reference/cli.md` — every `fiducial.py` command (`fiducial.py:1252`), flags, generated from `--help`.
  * `reference/api-builder.md` — auto-extracted from `schematic_builder.py:144` (human table + `builder.json` for agents).
  * `reference/sexp.md` — S-exp dialect, version table (`kicad-versions.md:10`).
  * `reference/exit-codes.md` — `0/1/2` contract (`fiducial.py:15`) + JSON shapes.
  * `reference/rules.md` → `rules.md:1` (CSV spec) — stable contract.
* **Explanation** — `explanation/` — why:
  * `explanation/architecture.md` — why ERC ≠ intent (`README.md:12`), netlist cache (`fiducial.py:311`), checks (`fiducial.py:849`).
  * `explanation/compatibility.md` — what `v0.1` promises (CSV/CLI/exit codes).
  * `kicad-versions.md:1` — KiCad 7–10 gotchas.

## Agent vs human conventions

* `skills/` is **agent-authoritative** — frontmatter `agent: true`, humans may read but `docs/` is human-authoritative.
* Every `docs/reference/*.md` has a fenced ` ```json ` block with the same spec — agents `grep` the JSON, humans read the table.
* Checklists in `howto/` are 1:1 with `check-intent` rows — agent can copy `intent.csv` verbatim.

```sh
# Verify docs stay in sync (stdlib-only, CI-friendly):
python scripts/docs_check.py
python scripts/docs_check.py --json  # machine output for agents
```

## Source of truth

* CLI surface → `scripts/fiducial.py:1252` (argparse) → `reference/cli.md` (generated).
* Builder API → `scripts/schematic_builder.py:144` docstrings → `reference/api-builder.md` + `reference/api-builder.json`.
* S-exp grammar → `fiducial.py:68` `parse_sexp` → `reference/sexp.md`.

> If a doc contradicts the parser, the parser wins. File a bug — `docs_check.py` will fail.
