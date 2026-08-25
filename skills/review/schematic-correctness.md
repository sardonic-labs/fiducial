# Schematic correctness review — intent matching, connectivity, pin assignments

Use this skill when reviewing a schematic produced by another agent. Focuses
on whether the design matches its intended function: correct connections,
correct pin assignments, correct net assignments.

## Prerequisites

- Project file: `.kicad_sch`
- Optional: `intent.csv` with columns `ref,pin,expected_net`
- Tools: `fiducial.py`, `schematic_check.py`

## Review checklist

### 1. Intent verification (if intent.csv provided)

```
python fiducial/scripts/fiducial.py check-intent <project.kicad_sch> intent.csv --orphans --json
```

Every `MISSING` or `WRONG` row is an **error**. Every orphan net is a **warning**.

**Interactive prompt:** If no intent.csv exists, ask the user:
> "No intent.csv provided. Should I:
> (a) generate a draft from the schematic for you to review, or
> (b) proceed without intent verification?"

### 2. Power pin audit

```
python fiducial/scripts/schematic_check.py power-pins <project.kicad_sch> --json
```

Verify every IC power pin reaches the correct rail. Missing power pins = **error**.

### 3. Unconnected pins

```
python fiducial/scripts/schematic_check.py unconnected <project.kicad_sch> --json
```

Any unconnected pin that is not a no-connect = **error**.

### 4. Orphan nets

```
python fiducial/scripts/schematic_check.py orphan-nets <project.kicad_sch> --json
```

Single-connection nets = **warning** (likely dangling or typo).

### 5. Critical signal verification

Manually verify (use `pins` command for each):
- Crystal/oscillator pins on correct nets
- USB D+/D- not swapped
- Boot/strap pins pulled to correct rail
- Debug connector wired to SWD/JTAG pins
- Connector pinouts match mating device datasheet

**Interactive prompt:** For each critical IC, ask:
> "Pin X is on net Y — confirm this matches the design intent? (y/n)"

### 6. Decoupling check

```
python fiducial/scripts/schematic_check.py decoupling-check <project.kicad_sch> --json
```

ICs without nearby decoupling caps = **warning**.

## Severity rules

| Finding | Severity |
|---|---|
| Pin on wrong net | error |
| Pin unconnected | error |
| Missing power connection | error |
| Orphan net (single connection) | warning |
| No decoupling detected | warning |
| Ambiguous pin assignment | warning (interactive) |

## Verdict

- **PASS**: zero errors
- **FAIL**: one or more errors (must fix before proceeding)

Always ask the user to confirm critical pin assignments interactively before
delivering the final verdict.
