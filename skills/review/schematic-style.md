# Schematic style review — house style, naming, labeling

Use this skill when reviewing a schematic produced by another agent. Focuses
on readability, consistency, and house style compliance.

## Prerequisites

- Project file: `.kicad_sch`
- Optional: `rules.csv` for house style rules
- Tools: `fiducial.py`, `schematic_check.py`

## Review checklist

### 1. Grid compliance

```
python fiducial/scripts/schematic_check.py grid-check <project.kicad_sch> --json
```

Symbols, wires, and labels off-grid = **warning**. Off-grid connections are
invisible bugs — a wire that touches a pin off-grid silently fails to connect.

### 2. Reference designator consistency

```
python fiducial/scripts/schematic_check.py refdes-audit <project.kicad_sch> --json
```

- Duplicate refs = **error**
- Mixed case conventions = **warning**
- Numbering gaps = **info**

### 3. Label audit

```
python fiducial/scripts/schematic_check.py label-audit <project.kicad_sch> --json
```

- Single-use labels that join no multi-pin net = **warning** (likely typo)
- Auto-generated names like `Net-(U1-1)` = **warning** (poor documentation)
- Whitespace in labels = **warning**

### 4. Debris scan

```
python fiducial/scripts/schematic_check.py debris-scan <project.kicad_sch> --json
```

- Placeholder text (`TODO`, `[pending]`, `???`) = **warning**
- Suspect abandoned components = **warning**

### 5. Visual layout rules

Verify manually or via rendered SVG:
- Signal flows left to right
- Power rails enter from top, ground exits bottom
- One functional block per region
- No diagonal wires
- Labels horizontal (left-to-right) or vertical (bottom-to-top)

**Interactive prompt:** Ask:
> "Should I render the schematic to SVG for visual layout inspection? (y/n)"

### 6. House rules (if rules.csv provided)

```
python fiducial/scripts/fiducial.py check-rules <project.kicad_sch> rules.csv --json
```

Violations = **warning** or **error** depending on rule type.

## Severity rules

| Finding | Severity |
|---|---|
| Duplicate reference designator | error |
| Off-grid symbol/label/wire | warning |
| Single-use label (likely typo) | warning |
| Auto-generated net name | warning |
| Mixed refdes conventions | warning |
| Placeholder text | warning |
| Numbering gap | info |

## Verdict

- **PASS**: zero errors
- **FAIL**: one or more errors
