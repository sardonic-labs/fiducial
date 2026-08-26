# fiducial

[![CI](https://github.com/sardonic-labs/fiducial/actions/workflows/ci.yml/badge.svg)](https://github.com/sardonic-labs/fiducial/actions/workflows/ci.yml)

> AI agents hallucinate pinouts. fiducial catches them.

**fiducial** is a drop-in submodule that turns any AI coding agent (opencode,
Claude Code, Cursor, anything that reads `AGENTS.md`) into a KiCad hardware
design assistant — an instruction library plus zero-dependency verification
tools that mechanically prove a schematic does what it claims.

In our benchmark, an AI-authored RP2040 devboard passed ERC **completely
clean** while its crystal load capacitors were silently disconnected — the
board would never boot. fiducial's intent audit caught it in seconds.

## Why

LLMs write plausible-looking schematics with real bugs: label typos that split
nets, pins "wired" to nothing, wrong library symbols, missing debug headers.
ERC and DRC check *rules*, not *intent*. fiducial closes that gap:

1. Write design intent as `intent.csv` (`ref,pin,expected_net`) straight from
   the datasheet — **before** wiring anything.
2. Let the agent author the schematic under the instruction library's rules.
3. Prove it: `lint` → `erc` → `check-intent`. Exit codes work as agent gates.
4. Only then layout: `drc` until clean, `render`, inspect.

```
ref     pin    expected          actual            result
*U1     20     /XIN              Net-(U1-XIN)      WRONG
 C3     1      /XIN              /XIN              ok
 U3     6      /QSPI_SCLK        /QSPI_SCLK        ok
...
58/64 connections verified
```

## Install (one-time)

```sh
git submodule add https://github.com/sardonic-labs/fiducial fiducial
./fiducial/bootstrap.ps1      # or: ./fiducial/bootstrap.sh
```

The bootstrap appends one import line (`@fiducial/AGENTS.md`) to your project's
`AGENTS.md` and runs an environment check. Idempotent; remove with `-Remove`
/ `--remove`.

Requires: Python 3.8+ (**stdlib only** — no pip installs) and KiCad 7+ on PATH
for `kicad-cli` (CI runs against KiCad 10).

## Quick start

```sh
python scripts/fiducial.py doctor                    # environment check
python scripts/fiducial.py lint myboard.kicad_sch    # structural checks
python scripts/fiducial.py erc myboard.kicad_sch     # KiCad ERC
python scripts/fiducial.py check-intent myboard.kicad_sch intent.csv
python scripts/fiducial.py overlap-check myboard.kicad_sch  # silent short detection
python scripts/fiducial.py sexp myboard.kicad_sch    # S-expr → JSON for agents
```

## Commands

| Command | Purpose |
|---|---|
| `doctor` | Check kicad-cli availability and version |
| `erc <project.kicad_sch>` | Run ERC, summarize JSON report; exit code reflects errors |
| `drc <project.kicad_pcb>` | Run DRC, same behavior. Read-only by default; pass `--save-board` to refill zones and rewrite the board |
| `netlist <project.kicad_sch>` | Export netlist to `<project>-netlist.sexpr` |
| `nets <project.kicad_sch>` | Dump every net with its connected pins |
| `pins <project.kicad_sch> <REF>` | Dump one symbol's pins and their nets (numeric order) |
| `check-intent <project.kicad_sch> intent.csv` | Compare expected connections (`ref,pin,expected_net`) against reality; `--orphans` also flags single-pin nets |
| `lint <project.kicad_sch>` | Structural checks: duplicate refs, missing fields, unconnected pins, single-use labels, dangling nets |
| `check-rules <project.kicad_sch> rules.csv` | Verify house-style rules from CSV (`min-contacts`, `net-exclusive`, `allow-single-use`) — see [docs/rules.md](docs/rules.md) |
| `overlap-check <project.kicad_sch>` | Detect wires from different nets sharing coordinates (silent shorts) |
| `render <project...> --outdir DIR` | Export SVG renders of schematic and/or PCB so you can look at them |
| `bom <project.kicad_sch>` | Export CSV bill of materials |
| `sexp <file>` | Parse any S-expression file (`.kicad_sch`, `.kicad_pcb`, `.sexpr`) → JSON for agents; `--raw` for nested-list mode |
| `wire-trace <sch> <ref> <pin>` | Trace what net a pin connects to through wires and labels |
| `label-map <sch>` | Dump all labels with (x,y) coordinates, grouped by net |
| `pin-positions <sch> <ref>` | Show absolute pin endpoints in schematic space |

Exit codes: `0` clean, `1` violations found, `2` tool/environment error.
These hold for every command, including in `--json` mode.

### Machine-readable output

`erc`, `drc`, `check-intent`, `lint`, and `check-rules` accept `--json`,
printing a structured document instead of human text (same exit codes). This
is what CI pipelines and agent loops should consume.

### Netlist caching

Netlist-based commands (`nets`, `pins`, `check-intent`, `lint`,
`check-rules`) reuse `<project>-netlist.sexpr` only while it is newer than
the schematic; editing the `.kicad_sch` triggers automatic re-export.
`--refresh` forces regeneration regardless.

### Diagnostic commands

`wire-trace`, `label-map`, and `pin-positions` parse the schematic directly
(no kicad-cli) and answer common debugging questions: what net is this pin
actually on, where are all the labels, do pin endpoints match the wiring.

## What you get

- **Instruction library** in `skills/` — schematic authoring rules, PCB layout,
  DRC workflow, netlist auditing, datasheet reading, terminology, best-practice
  checklists. The agent reads them per-task.
- **Tools** in `scripts/fiducial.py` (see command table above) that slot into
  CI or agent loops via exit codes or `--json`.

| Tool | Catches |
|---|---|
| `lint` | duplicate refs, single-use labels (with `allow-single-use` suppression), orphan nets, missing lib entries |
| `check-intent` | any pin wired to the wrong net, missing connections, NC pin handling |
| `check-rules` | house-style violations declared as CSV data |
| `overlap-check` | wires from different nets sharing coordinates (silent shorts) |
| `erc` / `drc` | KiCad rule violations, parsed and summarized |
| `wire-trace` | what net a pin connects to through wires and labels |
| `label-map` | all labels with coordinates, grouped by net |
| `pin-positions` | absolute pin endpoints in schematic space |
| `sexp` | S-expression → JSON conversion for any KiCad file |
| `render` | SVG exports so the agent can visually inspect its own work |

See [`examples/intent.csv`](examples/intent.csv) and
[`examples/rules.csv`](examples/rules.csv) for working file formats.

## Updating

```sh
git submodule update --remote fiducial
```

## Testing

```sh
python -m unittest discover -s tests -v
```

The suite has two layers:

- `tests/test_offline.py` — pure-stdlib unit and regression tests using small
  synthetic schematic/netlist fixtures. Runs anywhere; no kicad-cli needed.
  Covers parsing, lint defect detection, intent-check paths, pin sorting,
  report/cache staleness handling, and JSON output.
- `tests/test_fiducial.py` — regression suite against a real AI-authored
  RP2040 devboard fixture with two planted connectivity bugs (floating
  crystal caps, missing SWD header); asserts the tools catch both while ERC
  stays deceptively clean. These tests additionally require `kicad-cli` and
  skip automatically when it is not installed.

CI (GitHub Actions) installs KiCad 10 from the official PPA and runs both
layers on every push — that's the version-drift canary for `kicad-cli` flag
changes.

## License

MIT — see [LICENSE](LICENSE).

## Name

A fiducial is the reference mark assembly machines align to. This repo is the
reference point that keeps AI-generated hardware aligned with reality.

## Roadmap

- **Schematic builder API** — `SchematicBuilder` class for programmatic schematic generation (addresses the biggest gap from agent use reports)
- **Rules profiles** — reusable house-style standards (e.g., a satellite pin standard) as loadable rule sets beyond per-board `rules.csv`
- **Next domains: mechanical CAD (Fusion/FreeCAD/Onshape)** — same architecture: spec-as-code rules plus a verification harness

## Status

v0 — battle-tested on one real board (RP2040 devboard), schematic side only.
PCB-side tooling (`drc`, `render`) works but is not yet regression-covered.
APIs may change while the ink is wet.

## Use reports

Agent use reports live in
[`fiducial-devboard-example/docs/`](https://github.com/sardonic-labs/fiducial-devboard-example/tree/main/docs).
These document real gaps found when agents use fiducial end-to-end.
