# Changelog

> `v0.1.0` changelog *is* the compatibility contract (`docs/explanation/compatibility.md:1`, `ROADMAP.md:21`). From `v0.1.0` onward: CSV formats, CLI surface, exit codes, and JSON shapes are stable; see compatibility doc for the table. Any breaking change requires a minor version bump and an entry here.

## v0.1.0 — 2026-08-31

First release — contract frozen.

**Stable surfaces (since `v0.1.0`):**

| Surface | Spec | Source |
|---|---|---|
| `intent.csv` | header `ref,pin,expected_net`, UTF-8-SIG, `NC` means skip | `fiducial.py:396`, `docs/rules.md:14` |
| `rules.csv` | header `rule,net,params`, `min-contacts` / `net-exclusive` / `allow-single-use` | `fiducial.py:934`, `docs/rules.md:14` |
| CLI commands | 17 commands: `doctor/erc/drc/netlist/nets/pins/check-intent/lint/check-rules/check/render/bom/sexp/overlap-check/wire-trace/label-map/pin-positions` + flags `--json/--refresh/--orphans/--rules/--save-board/--parity/--outdir` | `fiducial.py:1252`, `docs/reference/cli.md` |
| Exit codes | `0` clean / `1` violations / `2` env — holds even for `--json` (`check:1166` returns `max`) | `fiducial.py:15`, `docs/reference/exit-codes.md` |
| JSON shapes | `erc/drc` `{tool,error_count,warning_count,errors,warnings}`, `check-intent` `{verified,total,results,orphans}`, `lint` `{problems}`, `check-rules` `{checked,violations}`, `overlap-check` `{overlap_count,overlaps}` | `fiducial.py:199`, `docs/reference/cli.md` |
| `SchematicBuilder` API | `add_symbol/add_wire/add_label/add_global_label/add_power/add_no_connect/build/save/write_intent/load` — grid-aware, `lint`-clean | `schematic_builder.py:144`, `docs/reference/api-builder.md` |

**What is tested at `v0.1.0`:**

- Tests: `117 OK (10 skipped)` (`test_offline.py` stdlib-only 107 + schematic builder 12, `test_fiducial.py` kicad-cli 6) — PCB `drc`/`render` now regression-covered (`tests/fixtures/healthy.kicad_pcb:1`, `ROADMAP.md:32` closed in `08bc7b6`)
- Foreign corpus: `153` schematics pinned (`corpus/MANIFEST.csv:1` kicad-demos 116 + ZSWatch 9 + cynthion 17 + launch 11), nightly `corpus.yml:1`, 9-day green streak at tag
- Docs: `docs_check.py` clean (17 cli, 23 skills, 16 builder methods) — every CLI/skill has ` ```json ` machine block

**What may still change (minor, additive):**

- PCB `drc`/`render` flag wording (behind `ROADMAP Week 2` gap-close — now closed, but flags may gain options)
- `rules` profiles (`--profile satellite` stretch `ROADMAP.md:46`) — additive, no break to `rules.csv`
- `skills/` prompt wording — non-breaking

**From this tag forward:** any CLI/exit/CSV/JSON break must update `docs/reference/cli.md` + `reference/exit-codes.md` + `explanation/compatibility.md` + this file — `docs_check.py` enforces.
