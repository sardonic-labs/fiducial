# Architecture — why `lint` + `check-intent` exist

> ERC checks *rules*, not *intent*. Fiducial closes that gap (`README.md:12`).

## The benchmark that created this

AI-authored RP2040 devboard passed ERC **clean** while `C3/C4` crystal load caps were `Net-(U1-XIN)` not `/XIN` (`README.md:30` `*U1 20 /XIN → Net-(U1-XIN) WRONG`). ERC sees “nets exist”; `check-intent` sees `ref,pin,expected_net` mismatch (`fiducial.py:391`).

Same for battery-entry `2026-08-23`: orphan island `Q1+RG1` on `BT_GATE_N` (`test_offline.py:644` `TestOrphanClusters`) — every `existing` check blessed them, `lint:913` flagged `isolated cluster`.

## Pipeline

```
.kicad_sch  ──(S-exp parse 68)──┬─→ lint:849 (structure, grid 564, orphan 450, ghost 528)
            │                   ├─→ overlap-check:1001 (wires sharing xy → silent shorts)
            │                   └─→ sexp/wire-trace/label-map (diagnostics, no kicad-cli)
            └─(kicad-cli sch export netlist)──→ -netlist.sexpr ──→ check-intent:391 / check-rules:934
```

* `kicad-cli` wrapper `fiducial.py:155` `kicad_cli`, report `_summarize_report:167` via temp `fiducial-erc-*.json` (never stale path `test_offline.py:437`).
* Netlist cache `fiducial.py:311` `_load_nets` — reuse `-netlist.sexpr` if newer than `.kicad_sch`; `--refresh` forces re-export. `doctor:230` checks `kicad-cli version`.
* Power-rail heuristic `_is_rail_net:463` (`GND` + `/^\\d+V/`) excludes rails from island grouping — otherwise ground masks ghosts.

## What each layer catches

| Tool | Impl | Catches (see table `README.md:113`) |
|---|---|---|
| `lint:849` | `_geometry_problems:572`, `_orphan_nets:450`, `_orphan_clusters:477`, `_suspect_components:528` | duplicate `uuid`/`ref`, missing `lib_symbols`, off-grid, single-use label (`905`, `allow-single-use`), dangling nets |
| `check-intent:391` | netlist `nodes[(ref,pin)]` vs CSV | `WRONG`/`MISSING`, `NC` (`405`), `--orphans` |
| `check-rules:934` | CSV `rule,net,params` | `min-contacts`, `net-exclusive` (VBAT exclusivity) |
| `overlap-check:1001` | wire graph `adj` + label flood | wires from different nets sharing `xy` |
| `erc/drc:250` | `kicad_cli sch/pcb erc/drc --format json` | KiCad rule violations (summary) |
| `SchematicBuilder:144` | grid `1.27`, `uuid`, `lib_symbols`, `connect()` → label at `_compute_pin_positions:618` | prevents above at construction |

## Agent vs human gates

* Agent loop: `check:1166` gate (`lint→erc→intent→rules`, worst `max`) + `--json` (`reference/exit-codes.md`) → branch on `exit 1` vs `2`.
* Human review: `reviewer.py:22` orchestrates 10 skills (`schematic-correctness` … `documentation`) via `schematic_check.py`/`pcb_check.py`/`bom_check.py`.

## Invariants

* Files are S-exprs (`sexp:1234` `_sexp_to_json:1201`); version field `20250114…20260306` (`kicad-versions.md:10`) — builder matches existing file's version, never mixes.
* `skills/` is agent-authoritative; `docs/` is human-authoritative — `docs_check.py` asserts both mention the same CLI surface.

```json
{"architecture": "lint+intent", "netlist_cache": "fiducial.py:311", "lint_checks": ["orphan:450","cluster:477","suspect:528","grid:572"], "gate": "check:1166"}
```
