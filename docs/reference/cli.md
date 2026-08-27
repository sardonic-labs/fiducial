# CLI reference (`fiducial.py:1252`)

> Source of truth: `scripts/fiducial.py:1252` argparse. This doc is generated; if it drifts, `scripts/docs_check.py` fails.

```sh
python fiducial/scripts/fiducial.py <command> [--help] [--json]
# all logged via scripts/fiducial.py:1368 main()
```

## Commands (human table) + JSON (agent block)

| Command | Human | Agent `--json` shape |
|---|---|---|
| `doctor` | `kicad-cli` + python check (`fiducial.py:230`) | — |
| `erc <sch>` | ERC → `tool/target/error_count/warnings` (`fiducial.py:199`) | `{"tool":"ERC","error_count":n,"warnings":[…]}` |
| `drc <pcb>` | DRC, `--save-board` rewrites (`fiducial.py:261`) | same as ERC |
| `netlist <sch>` | export `-netlist.sexpr` (`fiducial.py:294`) | — |
| `nets <sch>` | every net → `ref.pin` (`fiducial.py:358`) | — |
| `pins <sch> <REF>` | one symbol sorted (`fiducial.py:368`, `_pin_sort:386`) | — |
| `check-intent <sch> intent.csv` | `ref,pin,expected_net` → WRONG/MISSING (`fiducial.py:391`) | `{"verified":n,"total":m,"results":[…],"orphans":[…]}` |
| `lint <sch>` | structure/or orphan/ off-grid (`fiducial.py:849`) | `{"problems":[…]}` |
| `check-rules <sch> rules.csv` | `min-contacts`/`net-exclusive` (`fiducial.py:934`) | `{"checked":n,"violations":[…]}` |
| `check <sch>` | gate: `lint→erc→intent→rules` (`fiducial.py:1166`) | — |
| `overlap-check <sch>` | wires sharing coord (`fiducial.py:1001`) | `{"overlap_count":n,"overlaps":[…]}` |
| `render … --outdir` | SVG (`fiducial.py:1127`) | — |
| `bom <sch>` | BOM CSV (`fiducial.py:1151`) | — |
| `sexp <file>` | S-exp → JSON (`fiducial.py:1234`) | `{"_key":…}` or `--raw` list |
| `wire-trace <sch> <ref> <pin>` | trace to label/net (`fiducial.py:742`) | — |
| `label-map <sch>` | labels grouped (`fiducial.py:799`) | — |
| `pin-positions <sch> <ref>` | absolute endpoints (`fiducial.py:667`, `_compute_pin_positions:618`) | — |

Flags: `--json` (`erc/drc/check-intent/lint/check-rules`), `--refresh` (bypass cache `fiducial.py:311`), `--orphans` (`check-intent:391`), `--allow` via `rules.csv` `allow-single-use` (`fiducial.py:846`).

## Examples (both)

```sh
python fiducial/scripts/fiducial.py lint myboard.kicad_sch
python fiducial/scripts/fiducial.py lint myboard.kicad_sch --json | jq .problems
python fiducial/scripts/fiducial.py check-intent myboard.kicad_sch intent.csv --orphans --refresh --json
python fiducial/scripts/fiducial.py sexp myboard.kicad_sch --raw | jq .
```

## Machine block

```json
{
  "cli": "fiducial.py:1252",
  "commands": ["doctor","erc","drc","netlist","nets","pins","check-intent","lint","check","check-rules","render","bom","sexp","overlap-check","wire-trace","label-map","pin-positions"],
  "json_flags": ["erc","drc","check-intent","lint","check-rules","overlap-check"],
  "exit_codes": {"0":"clean","1":"violations","2":"env"},
  "netlist_cache": "fiducial.py:311"
}
```

> Update this file by re-running `python fiducial/scripts/fiducial.py --help` in CI.
