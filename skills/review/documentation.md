# Documentation review — title block, annotations, revision history

Use this skill when reviewing a schematic produced by another agent. Focuses
on documentation quality: is the design self-describing?

## Prerequisites

- Project file: `.kicad_sch`
- Tools: `fiducial.py`, `schematic_check.py`

## Review checklist

### 1. Title block

Verify the schematic title block contains:
- Project name
- Revision number
- Date
- Author/company name

Missing title block info = **warning**.

### 2. Sheet titles

Each sheet should have a descriptive title (not "Sheet1", "Sheet2").
Generic sheet names = **warning**.

### 3. Net label quality

```
python fiducial/scripts/schematic_check.py label-audit <project.kicad_sch> --json
```

- Auto-generated names (`Net-(U1-1)`) = **warning** (rename for clarity)
- Power rail labels should be descriptive

### 4. Placeholder text

```
python fiducial/scripts/schematic_check.py debris-scan <project.kicad_sch> --json
```

Any `TODO`, `[pending]`, `TBD`, `???` = **warning**.

### 5. Reference designator consistency

```
python fiducial/scripts/schematic_check.py refdes-audit <project.kicad_sch> --json
```

- Mixed conventions = **warning**
- Gaps in numbering = **info**

### 6. Power rail labeling

- Power rails should be clearly labeled
- Global labels for power: `GND`, `+3V3`, `VBAT`, etc.
- No ambiguous power net names

### 7. Design notes

Verify:
- Functional blocks are annotated
- Complex circuits have explanatory notes
- Critical design decisions are documented

**Interactive prompt:** Ask:
> "Should I check for missing design annotations on each functional block? (y/n)"

## Severity rules

| Finding | Severity |
|---|---|
| Placeholder text | warning |
| Auto-generated net name | warning |
| Generic sheet title | warning |
| Missing title block info | warning |
| Mixed refdes conventions | warning |
| Missing design annotations | info |
| Numbering gap | info |

## Verdict

- **PASS**: zero errors (documentation is a warning-level concern, not error)
- **FAIL**: N/A (documentation issues are always warnings or info)
