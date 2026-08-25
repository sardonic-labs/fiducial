# Connectivity review — cross-block connectivity, connector pinouts

Use this skill when reviewing a schematic produced by another agent. Focuses
on global connectivity: are signals properly routed between blocks, and do
connector pinouts match their mating devices?

## Prerequisites

- Project file: `.kicad_sch`
- Optional: `intent.csv`
- Tools: `fiducial.py`, `schematic_check.py`

## Review checklist

### 1. Lint for connectivity issues

```
python fiducial/scripts/fiducial.py lint <project.kicad_sch> --json
```

- Isolated clusters = **error**
- Single-use labels (likely typo) = **warning**
- Suspect components = **warning**
- Orphan nets = **warning**

### 2. Label consistency

```
python fiducial/scripts/schematic_check.py label-audit <project.kicad_sch> --json
```

- Single-use labels joining no multi-pin net = **warning**
- Auto-generated names = **warning** (poor documentation)

### 3. Orphan nets

```
python fiducial/scripts/schematic_check.py orphan-nets <project.kicad_sch> --json
```

Single-connection nets = **warning**.

### 4. Hierarchical label consistency

For multi-sheet designs:
- Verify hierarchical labels match between parent and child sheets
- Verify net names are consistent across sheets

**Interactive prompt:** Ask:
> "Sheet X has hierarchical label 'SIG_IN'. Confirm this matches the parent sheet connection? (y/n)"

### 5. Connector pinout verification

For each connector, cross-check against mating device datasheet:
- Pin 1 orientation
- Signal assignments
- Power pin locations
- Keying/polarization

**Interactive prompt:** For each connector, ask:
> "Connector J_X pin 1 is on net Y. Confirm this matches the mating device? (y/n)"

### 6. Power distribution across sheets

- Verify power rails reach all sheets
- Verify ground connections are consistent
- Check for power islanding between sheets

## Severity rules

| Finding | Severity |
|---|---|
| Isolated component cluster | error |
| Connector pinout mismatch | error |
| Power rail not reaching sheet | error |
| Single-use label (likely typo) | warning |
| Orphan net | warning |
| Hierarchical label mismatch | warning |
| Auto-generated net name | warning |
| Suspect tacked-on component | warning |

## Verdict

- **PASS**: zero errors
- **FAIL**: one or more errors
