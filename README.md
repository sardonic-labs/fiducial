# fiducial

[![CI](https://github.com/sardonic-labs/fiducial/actions/workflows/ci.yml/badge.svg)](https://github.com/sardonic-labs/fiducial/actions/workflows/ci.yml)

> AI agents hallucinate pinouts. fiducial catches them.

**fiducial** is a drop-in submodule that turns any AI coding agent (opencode, Claude Code, Cursor — anything that reads `AGENTS.md`) into a KiCad hardware design assistant with zero-dependency verification that mechanically proves a schematic is correct.

In our benchmark, an AI-authored RP2040 devboard passed ERC **completely clean** while its crystal caps were silently disconnected — the board would never boot. fiducial's intent audit caught it in seconds:

```
ref     pin    expected          actual            result
*U1     20     /XIN              Net-(U1-XIN)      WRONG
58/64 connections verified
```

## Why

LLMs write plausible schematics with real bugs: label typos that split nets, pins wired to nothing, wrong symbols, missing debug headers. ERC/DRC check *rules*, not *intent*.

1. Write intent as `intent.csv` (`ref,pin,expected_net`) from the datasheet — **before** wiring.
2. Let the agent author the schematic (`skills/` + `SchematicBuilder`).
3. Prove it: `lint` → `erc` → `check-intent` (exit codes are agent gates).
4. Then layout: `drc` → `render` → inspect.

## Install

```sh
git submodule add https://github.com/sardonic-labs/fiducial fiducial
./fiducial/bootstrap.sh  # or bootstrap.ps1 — appends @fiducial/AGENTS.md, runs doctor
# remove: ./fiducial/bootstrap.sh --remove
```

Requires Python 3.8+ (stdlib only) and KiCad 7+ on PATH for `kicad-cli` (CI uses KiCad 10).

## Quick start

```sh
python fiducial/scripts/fiducial.py doctor
python fiducial/scripts/fiducial.py lint myboard.kicad_sch          # structure
python fiducial/scripts/fiducial.py erc myboard.kicad_sch            # ERC
python fiducial/scripts/fiducial.py check-intent myboard.kicad_sch intent.csv  # intent
```

Full command reference: `docs/reference/cli.md` (`fiducial.py:1252`). Diagnostic helpers: `wire-trace`, `label-map`, `pin-positions`, `overlap-check`, `sexp` — all work without `kicad-cli`.

```sh
# Programmatic authoring (replaces hand-rolled S-exp)
python examples/builder_demo.py  # writes /tmp/builder_demo.kicad_sch
```

See `docs/tutorial.md:1` (5 min), `docs/howto/add-intent.md`, `docs/builder.md:1`.

## What you get

* **Instruction library** in `skills/` — per-task rules the agent reads (schematic, PCB, verification, reference). See `skills/index.md`.
* **Verification tools** (`scripts/fiducial.py`) — `lint` / `check-intent` / `check-rules` / `overlap-check` / `erc`/`drc` / diagnostics. All return `0` clean / `1` violations / `2` env, and `--json` for CI.
* **SchematicBuilder** (`scripts/schematic_builder.py:144`) — grid-aware, `lint`-clean generation. See `docs/builder.md:1` and `docs/reference/api-builder.md`.

| Tool | Catches |
|---|---|
| `lint` | duplicate refs, single-use labels, orphan nets, missing libs, off-grid |
| `check-intent` | any pin on wrong net, `NC` handling |
| `check-rules` | house-style `rules.csv` (`min-contacts`, `net-exclusive`) |
| `overlap-check` | silent shorts (wires sharing `xy`) |

Examples: `examples/intent.csv`, `examples/rules.csv`. Netlist caching and `--refresh` / `--orphans` documented in `docs/reference/cli.md`.

## Docs

Single-sourced for humans + agents — `docs/index.md:1` is the hub:

* Tutorial → `docs/tutorial.md:1` · How-to → `docs/howto/` · Reference → `docs/reference/` · Explanation → `docs/explanation/`
* Verify docs ↔ code: `python scripts/docs_check.py`

## Updating

```sh
git submodule update --remote fiducial
```

## Testing

```sh
python -m unittest discover -s tests -v
```

* `test_offline.py` — stdlib-only, no `kicad-cli` (parsing, lint, intent, cache, overlap, builder).
* `test_fiducial.py` — real RP2040 fixture with two planted bugs; skips without `kicad-cli`.

CI installs KiCad 10 and runs both.

## License

MIT — see [LICENSE](LICENSE).

## Name

A fiducial is the reference mark assembly machines align to. This repo keeps AI-generated hardware aligned with reality.

## Roadmap

- [x] **Schematic builder API** — `SchematicBuilder` (`scripts/schematic_builder.py:144`, `docs/builder.md:1`)
- [ ] **Rules profiles** — loadable house-style sets (`satellite` from Pin Standard v0.3) beyond per-board `rules.csv`
- [ ] **PCB regression coverage** — `drc` + `render` fixtures/tests (last “works but untested” corner)
- Next domains: mechanical CAD (Fusion/FreeCAD/Onshape) — same verification architecture

See `ROADMAP.md:1` for the 30-day plan (v0.1 contract → v0.2 + Show HN gate).

## Status

v0 — builder + schematic-side verification battle-tested on RP2040 devboard; PCB-side `drc`/`render` works but not yet regression-covered. APIs may change while the ink is wet.
