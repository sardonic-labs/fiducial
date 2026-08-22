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

Requires: Python 3.8+ (stdlib only — no pip installs) and KiCad 7+ on PATH for
`kicad-cli` (CI runs against KiCad 10).

## What you get

- **Instruction library** in `skills/` — schematic authoring rules, PCB layout,
  DRC workflow, netlist auditing, datasheet reading, terminology, best-practice
  checklists. The agent reads them per-task.
- **Tools** in `scripts/fiducial.py`: `doctor`, `erc`, `drc`, `netlist`,
  `nets`, `pins`, `check-intent`, `lint`, `render`, `bom` — all exit
  `0` clean / `1` violations / `2` environment error so they slot into CI or
  agent loops.

| Tool | Catches |
|---|---|
| `lint` | duplicate refs, single-use labels, orphan nets, missing lib entries |
| `check-intent` | any pin wired to the wrong net, missing connections |
| `erc` / `drc` | KiCad rule violations, parsed and summarized |
| `render` | SVG exports so the agent can visually inspect its own work |

## Updating

```sh
git submodule update --remote fiducial
```

## Testing

```sh
python -m unittest discover -s tests -v
```

The suite runs against a real AI-authored RP2040 devboard fixture with two
planted connectivity bugs (floating crystal caps, missing SWD header) and
asserts the tools catch both while ERC stays deceptively clean. Connectivity
tests are skipped if `kicad-cli` is not installed.

CI (GitHub Actions) installs KiCad 10 from the official PPA and runs the same
suite on every push — that's the version-drift canary for `kicad-cli` flag
changes.

## Name

A fiducial is the reference mark assembly machines align to. This repo is the
reference point that keeps AI-generated hardware aligned with reality.

## Status

v0 — battle-tested on one real board (RP2040 devboard), schematic side only.
PCB-side tooling (`drc`, `render`) works but is not yet regression-covered.
APIs may change while the ink is wet.
