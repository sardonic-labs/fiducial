# Compatibility contract

> `v0.1` changelog *is* the compatibility contract (`ROADMAP.md:41`). From `v0.1` onward: CSV formats, CLI surface, exit codes are stable (`ROADMAP.md:22`).

## What is stable

| Surface | Spec | Since |
|---|---|---|
| `intent.csv` | header `ref,pin,expected_net`, UTF-8-SIG, `NC` means skip (`fiducial.py:396`) | `v0.1` |
| `rules.csv` | header `rule,net,params`, `min-contacts`/`net-exclusive`/`allow-single-use` (`docs/rules.md:14`) | `v0.1` |
| CLI commands | `fiducial.py:1252` `doctor/erc/drc/netlist/nets/pins/check-intent/lint/check-rules/render/bom/sexp/overlap-check/wire-trace/label-map/pin-positions/check` + flags `--json/--refresh/--orphans/--rules/--save-board` | `v0.1` |
| Exit codes | `0` clean / `1` violations / `2` env (`fiducial.py:15`) — holds even for `--json` | `v0.1` |
| `SchematicBuilder` API | `schematic_builder.py:144` `add_symbol/connect/save/write_intent/load/build` | `v0.1` (builder.md) |
| JSON shapes | `erc/drc` `{tool,error_count,…}`, `check-intent` `{verified,total,results,orphans}`, `lint` `{problems}` | `v0.1` |

## What may change (minor)

* PCB `drc`/`render` flags (behind `ROADMAP Week 2` gap-close).
* `rules` profiles (`--profile satellite` stretch `ROADMAP.md:46`) — additive.
* `skills/` wording (agent prompts) — non-breaking.

## Version detection

```python
from scripts.fiducial import load_sexp, sexp_get, _first_str
root = load_sexp("myboard.kicad_sch")
version = int(_first_str(sexp_get(root, "version")) or 0)
# 20230121 (7), 20231120 (8), 20240108 (9), 20260306 (10) — see kicad-versions.md:10
```

## Show HN gate (`ROADMAP.md:64`)

Launch only when: backplane demo exists, corpus ≥3-week green (`corpus/MANIFEST.csv:1`), PCB regression-covered, contract published (`v0.1→v0.2`), soft-launch friendly. Gate rolls month if not met.

## For agents

```json
{"contract": "v0.1", "stable": ["intent.csv","rules.csv","CLI:1252","exit:15","builder:144"], "unstable": ["pcb drc flags","skills wording"]}
```

> CI (`ci.yml:1`) installs KiCad 10 and runs `python -m unittest discover -s tests`; nightly `corpus_harness.py:1` pins 142 boards. Any CLI/exit change must update `docs/reference/cli.md` + `reference/exit-codes.md` + this file — `docs_check.py` enforces.
