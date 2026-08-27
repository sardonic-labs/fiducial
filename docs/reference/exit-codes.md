# Exit codes (`fiducial.py:15`)

> Contract: `EXIT_OK=0`, `EXIT_VIOLATIONS=1`, `EXIT_ENV=2` (`fiducial.py:15`). Stable since `v0.1` (`explanation/compatibility.md`).

| Code | Meaning | When |
|---|---|---|
| `0` | clean | `erc` 0 errors, `lint` clean, `check-intent` `verified==total` (`fiducial.py:447`), `overlap-check` 0 overlaps |
| `1` | violations | any `WRONG`/`MISSING`/orphan/single-use/`min-contacts` fail — human must fix schematic, not CSV |
| `2` | env / tool | `kicad-cli` missing, malformed S-exp (`fiducial.py:123`), missing columns (`fiducial.py:398`), bad `rules.csv` (`fiducial.py:977`) |

All commands respect this, including `--json` mode. `check:1166` gate returns worst (`max`) of sub-commands.

## For humans

* `0` → gate passes, next step (`check-intent` → layout).
* `1` → read human text: `*R1 1 /B /A WRONG` (`fiducial.py:439`), `LINT: ...` (`fiducial.py:926`), fix then re-run.
* `2` → `doctor` first (`fiducial.py:230`).

## For agents (machine)

```sh
python fiducial/scripts/fiducial.py lint myboard.kicad_sch --json; echo $?
python fiducial/scripts/fiducial.py check-intent myboard.kicad_sch intent.csv --json
# {"command":"check-intent","verified":58,"total":64,"results":[{"status":"WRONG",...}]} → exit 1
```

```json
{"exit_codes": {"0":"clean","1":"violations","2":"env"}, "source": "fiducial.py:15", "json_commands": ["erc","drc","check-intent","lint","check-rules","overlap-check"]}
```

> CI/agent loops should branch on exit code, then `jq` the JSON. Human text is not parsed.
