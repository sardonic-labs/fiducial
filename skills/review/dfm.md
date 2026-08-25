# DFM review — manufacturing constraints, copper balance

Use this skill when reviewing a PCB layout produced by another agent. Focuses
on design for manufacturability: can this board be reliably fabricated?

## Prerequisites

- Project file: `.kicad_pcb`
- Tools: `fiducial.py`, `pcb_check.py`

## Review checklist

### 1. Drill sizes

```
python fiducial/scripts/pcb_check.py drill-table <project.kicad_pcb> --json
```

- Below fab minimum (0.15mm) = **error**
- Below recommended (0.2mm) = **warning**

### 2. Trace and space

Verify against fab house capabilities:
- Minimum trace width (typical: 0.15mm / 6mil)
- Minimum space (typical: 0.15mm / 6mil)
- Run `trace-widths` to verify

### 3. Via sizing

```
python fiducial/scripts/pcb_check.py via-audit <project.kicad_pcb> --json
```

- Via drill below minimum = **error**
- Annular ring below minimum = **error**

### 4. Solder mask

Verify:
- Solder mask expansion adequate (typical: 0.05mm)
- No silkscreen over pads
- Solder mask between fine-pitch pads

### 5. Copper balance

```
python fiducial/scripts/pcb_check.py copper-pours <project.kicad_pcb> --json
```

- Uneven copper distribution can cause warping
- Verify ground/power fills on all layers

### 6. Edge clearance

- Components near board edge need clearance for routing/v-scoring
- Minimum 1mm from edge for panelization

### 7. Footprint verification

Run `bom_check.py parse` to verify all footprints are assigned and valid.

## Severity rules

| Finding | Severity |
|---|---|
| Drill below fab minimum | error |
| Trace width below minimum | error |
| Annular ring below minimum | error |
| Silkscreen over pad | error |
| Component too close to edge | warning |
| Uneven copper distribution | warning |
| Solder mask expansion tight | warning |

## Verdict

- **PASS**: zero errors
- **FAIL**: one or more errors
