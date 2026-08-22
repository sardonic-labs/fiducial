# Rules profiles (`check-rules`)

`check-rules` verifies structural *house-style* rules against a project's
netlist. Rules live in a plain CSV, so a project can carry its standards as
data instead of tribal knowledge.

```
python scripts/fiducial.py check-rules myboard.kicad_sch rules.csv
```

## CSV format

Header row, three columns:

| column  | meaning                                              |
|---------|------------------------------------------------------|
| `rule`  | rule type (see below)                                |
| `net`   | the net the rule applies to (exact netlist name)     |
| `params`| rule-specific parameters                             |

Extra columns are ignored. Blank lines are skipped.

```csv
rule,net,params
min-contacts,/VBAT,2
net-exclusive,/VBAT,EPS1 J1
```

## Rule types

### `min-contacts`

The named net must have at least N connected pins. Catches power nets that
silently ended up connected to nothing, or buses that lost a member.

```csv
min-contacts,/GND,4
```

Params: an integer. A net absent from the netlist counts as 0 connections
and fails any N >= 1.

### `net-exclusive`

The named net may only connect to pins of the listed references. Catches,
say, VBAT accidentally routed to a non-power-role module ref.

```csv
net-exclusive,/VBAT,EPS1 J1
```

Params: reference designators separated by spaces and/or commas. If the net
does not exist in the netlist at all, that is reported as one violation
(`net not found`) — a rule about a net that was never created is usually a
sign something got deleted or renamed.

## Behavior

- Exit codes follow the fiducial contract: `0` all rules pass, `1` at least
  one violation, `2` environment/config error (unreadable netlist, unknown
  rule type, missing columns, non-integer min-contacts).
- The netlist is reused from cache like every other command; pass
  `--refresh` to force re-export after schematic edits.
- `--json` prints `{"command", "target", "checked", "violations": [...]}`.
- An example lives in [`examples/rules.csv`](../examples/rules.csv) and
  matches the test fixture board used by `tests/test_offline.py`.
