# fiducial

Instructions + stdlib-only tooling that turns an AI coding agent (opencode or
any agent that reads `AGENTS.md`) into a KiCad hardware design assistant.

## Install (one-time)

```sh
git submodule add <this-url> fiducial
./fiducial/bootstrap.ps1      # or: ./fiducial/bootstrap.sh
```

The bootstrap appends one import line (`@fiducial/AGENTS.md`) to your project's
`AGENTS.md` and runs an environment check. Idempotent; remove with `-Remove`
/ `--remove`.

Requires: Python 3.7+ (stdlib only) and KiCad 7+ on PATH for `kicad-cli`.

## What you get

- **Instruction library** in `skills/` — schematic authoring rules, PCB layout,
  DRC workflow, netlist auditing, datasheet reading, terminology, best-practice
  checklists. The agent reads them per-task.
- **Tools** in `scripts/fiducial.py` — see the table in
  [`AGENTS.md`](AGENTS.md): `doctor`, `erc`, `drc`, `netlist`, `nets`, `pins`,
  `check-intent`, `lint`, `render`, `bom`. All exit `0` clean / `1` violations /
  `2` environment error so they work as agent gates.

## Core idea

LLMs hallucinate pinouts and silently miswire nets. So fiducial is built around
mechanical verification:

1. Write design intent as `intent.csv` (`ref,pin,expected_net`) from the
   datasheet — before wiring.
2. Author the schematic.
3. Prove it: `lint` → `erc` → `check-intent`.
4. Only then layout: `drc` until clean, `render`, inspect.

## Updating

```sh
git submodule update --remote fiducial
```

## Name

A fiducial is the reference mark assembly machines align to. This repo is the
reference point that keeps AI-generated hardware aligned with reality.
