# Power tree review — voltage margins, current paths, protection

Use this skill when reviewing a schematic produced by another agent. Focuses
on power distribution: voltage rails, current capacity, protection, and
sequencing.

## Prerequisites

- Project file: `.kicad_sch`
- Optional: `intent.csv`
- Tools: `fiducial.py`, `schematic_check.py`, `bom_check.py`

## Review checklist

### 1. Rail inventory

```
python fiducial/scripts/schematic_check.py rail-audit <project.kicad_sch> --json
```

Verify all expected rails are present. Missing rail = **error**.

### 2. Power pin connectivity

```
python fiducial/scripts/schematic_check.py power-pins <project.kicad_sch> --json
```

Every IC power pin must reach a power net. Floating VDD/VSS = **error**.

### 3. Decoupling strategy

```
python fiducial/scripts/schematic_check.py decoupling-check <project.kicad_sch> --json
```

Every IC power pin pair needs a local decoupling cap. Missing = **warning**.

### 4. Current path verification

For each rail, trace current from source to sink:
- Is the trace/fuse rated for the current?
- Is there a complete path (no floating connections)?
- Are there current-sense resistors or ferrites as needed?

**Interactive prompt:** Ask:
> "Rail X carries ~Y mA. Is this within the design budget? (y/n)"

### 5. Protection components

Check for:
- Reverse polarity protection (MOSFET, diode) on battery input
- Overcurrent protection (fuse, polyfuse) on power entry
- TVS/clamping on sensitive rails
- Brown-out/reset circuitry

Missing protection = **warning** (or **error** for safety-critical rails).

### 6. Voltage margin analysis

For each regulator/converter:
- Input voltage range vs source
- Output tolerance vs load requirements
- Dropout voltage margins
- Efficiency at expected load

**Interactive prompt:** Ask:
> "Regulator U_X has Vout=3.3V with Vin=5V. Is the dropout margin sufficient? (y/n)"

### 7. BOM ratings cross-check

```
python fiducial/scripts/bom_check.py ratings <project.kicad_sch> --json
```

Components with inadequate voltage/current ratings = **error**.

## Severity rules

| Finding | Severity |
|---|---|
| Floating power pin | error |
| Missing rail | error |
| Inadequate component rating | error |
| Missing reverse polarity protection | error |
| Missing decoupling cap | warning |
| Missing overcurrent protection | warning |
| Tight voltage margin | warning |
| Missing ESD on power input | warning |

## Verdict

- **PASS**: zero errors
- **FAIL**: one or more errors
