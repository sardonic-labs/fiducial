# PCB routing review — trace widths, via sizing, signal integrity

Use this skill when reviewing a PCB layout produced by another agent. Focuses
on trace routing quality, via sizing, and signal integrity.

## Prerequisites

- Project file: `.kicad_pcb`
- Tools: `fiducial.py`, `pcb_check.py`

## Review checklist

### 1. Trace width analysis

```
python fiducial/scripts/pcb_check.py trace-widths <project.kicad_pcb> --json
```

Undersized traces = **error**. Power traces must carry rated current.

### 2. Via audit

```
python fiducial/scripts/pcb_check.py via-audit <project.kicad_pcb> --json
```

- Thin annular ring (< 0.15mm) = **error**
- Small drill (< 0.2mm) = **warning**

### 3. Ground plane continuity

Verify:
- Ground plane is continuous (no isolated copper islands)
- Signal return paths are clear
- No signals routing over gaps in ground plane

**Interactive prompt:** Ask:
> "Can you confirm the ground plane is continuous on all layers? (y/n)"

### 4. Differential pair routing

For high-speed differential pairs:
- Length matching within tolerance
- Consistent spacing
- No via asymmetry

### 5. Analog vs digital isolation

- Analog signals routed away from digital
- No digital signals crossing analog ground plane
- Sensitive analog traces shielded

### 6. Power trace widths

Power traces must be wide enough for rated current:
- USB VBUS (500mA): minimum 0.3mm
- Battery input (1A+): minimum 0.5mm
- 3.3V rail: depends on total current

## Severity rules

| Finding | Severity |
|---|---|
| Undersized power trace | error |
| Thin annular ring | error |
| Ground plane gap under high-speed signal | error |
| Small via drill | warning |
| Differential pair length mismatch | warning |
| Analog signal near digital noise | warning |
| Signal over ground plane gap | warning |

## Verdict

- **PASS**: zero errors
- **FAIL**: one or more errors
