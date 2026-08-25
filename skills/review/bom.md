# BOM review — part availability, ratings, alternatives

Use this skill when reviewing a design produced by another agent. Focuses on
the bill of materials: are parts available, correctly rated, and appropriate?

## Prerequisites

- Project file: `.kicad_sch`
- Tools: `fiducial.py`, `bom_check.py`

## Review checklist

### 1. Generate BOM

```
python fiducial/scripts/bom_check.py parse <project.kicad_sch> --json
```

Verify BOM is non-empty and all components have values and footprints.

### 2. Component ratings

```
python fiducial/scripts/bom_check.py ratings <project.kicad_sch> --json
```

- Missing footprint = **error**
- Suspiciously low/high values = **warning**

### 3. Lifecycle status

```
python fiducial/scripts/bom_check.py lifecycle <project.kicad_sch> --json
```

- Placeholder values (`?`, `TBD`, `XXX`) = **error**
- Generic footprints = **warning**

**Interactive prompt:** Ask:
> "Component X has value 'TBD'. Should I suggest a specific part? (y/n)"

### 4. Alternative suggestions

```
python fiducial/scripts/bom_check.py alternates <project.kicad_sch> --json
```

Review suggestions and confirm with user.

### 5. Package verification

For each component, verify:
- Footprint matches physical package
- Pin count matches symbol
- Pad pitch matches datasheet

**Interactive prompt:** For critical components, ask:
> "Component X uses footprint Y. Confirm this matches the physical part? (y/n)"

### 6. Supplier availability (manual check)

Note: Full supplier check requires external API. Flag components that are:
- Very old/legacy parts
- Single-source
- Custom/proprietary

## Severity rules

| Finding | Severity |
|---|---|
| Placeholder value | error |
| Missing footprint | error |
| Pin count mismatch | error |
| Generic/special footprint | warning |
| Single-source part | warning |
| Very old part | info |
| Common value - verify rating | info |

## Verdict

- **PASS**: zero errors
- **FAIL**: one or more errors
