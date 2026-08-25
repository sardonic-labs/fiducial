# PCB layout review — placement, board outline, clearances

Use this skill when reviewing a PCB layout produced by another agent. Focuses
on component placement, board setup, and manufacturing readiness.

## Prerequisites

- Project file: `.kicad_pcb`
- Tools: `fiducial.py`, `pcb_check.py`

## Review checklist

### 1. Board statistics

```
python fiducial/scripts/pcb_check.py board-stats <project.kicad_pcb> --json
```

Verify:
- Layer count matches design intent
- Component count matches schematic
- Net count matches schematic

**Interactive prompt:** Ask:
> "Board has X layers and Y components. Confirm this matches intent? (y/n)"

### 2. Board outline

```
python fiducial/scripts/pcb_check.py board-outline <project.kicad_pcb> --json
```

Open outline = **error** (manufacturing will fail).

### 3. Component placement

```
python fiducial/scripts/pcb_check.py placement-density <project.kicad_pcb> --json
```

- Tight spacing (< 0.5mm) = **warning**
- Connectors accessible from board edge = verify manually
- High-speed components near their load = verify manually
- Thermal proximity = verify manually

### 4. Mounting holes

Verify:
- Sufficient mounting holes for mechanical stability
- Mounting holes in corners/edges
- Clearance around mounting holes for hardware

### 5. Connector placement

Verify:
- Connectors at board edges
- Correct orientation for mating connector
- Keying features present
- Accessible after assembly

### 6. Test point accessibility

Verify test points are:
- Not under components
- Accessible from one side
- Labeled clearly

## Severity rules

| Finding | Severity |
|---|---|
| Open board outline | error |
| Component count mismatch | error |
| Tight spacing | warning |
| Connector not at edge | warning |
| Mounting hole missing | warning |
| Test point under component | warning |
| Layer count mismatch | info |

## Verdict

- **PASS**: zero errors
- **FAIL**: one or more errors
