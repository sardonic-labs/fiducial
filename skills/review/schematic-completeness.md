# Schematic completeness review — missing parts, unconnected pins, decoupling

Use this skill when reviewing a schematic produced by another agent. Focuses
on whether the design is complete: all required components placed, all pins
connected, all necessary support circuitry present.

## Prerequisites

- Project file: `.kicad_sch`
- Tools: `fiducial.py`, `schematic_check.py`

## Review checklist

### 1. Unconnected pins

```
python fiducial/scripts/schematic_check.py unconnected <project.kicad_sch> --json
```

Any unexpected unconnected pin = **error**.

### 2. Orphan nets

```
python fiducial/scripts/schematic_check.py orphan-nets <project.kicad_sch> --json
```

Single-connection nets = **warning** (incomplete connection or dangling wire).

### 3. Decoupling completeness

```
python fiducial/scripts/schematic_check.py decoupling-check <project.kicad_sch> --json
```

Every IC power pin pair should have a decoupling cap. Missing = **warning**.

### 4. Pull-ups/pull-downs

Check open-drain/open-collector signals for pull-up/pull-down resistors.
Missing pull on open-drain = **warning**.

### 5. ESD protection

External connectors should have ESD protection (TVS diodes, etc.).
Missing ESD on user-facing connector = **warning**.

### 6. Current limiting

LEDs and similar components should have current limiting resistors.
Missing current limiting = **error**.

### 7. Debris scan

```
python fiducial/scripts/schematic_check.py debris-scan <project.kicad_sch> --json
```

Placeholder text, suspect components, abandoned parts = **warning** or **error**.

## Severity rules

| Finding | Severity |
|---|---|
| Missing current limiting | error |
| Suspect abandoned component | error |
| Unconnected pin (unexpected) | error |
| Missing decoupling cap | warning |
| Missing pull-up/down | warning |
| Missing ESD protection | warning |
| Orphan net | warning |
| Placeholder text | warning |

## Verdict

- **PASS**: zero errors
- **FAIL**: one or more errors
