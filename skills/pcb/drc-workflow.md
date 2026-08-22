# DRC workflow

Goal: `drc` exit code 0, and *understood* clean — not just an empty report.

## Loop

1. Run:
   ```
   python fiducial/scripts/fiducial.py drc <project.kicad_pcb>
   ```
2. Fix violations **in order of severity**: errors first, then warnings.
3. Re-run after each batch. Do not declare done until exit code is 0.

## Interpreting common violations

| Violation | Typical fix |
|---|---|
| clearance | Net class/track width too aggressive for fab; widen gap or fix netclass |
| track_dangling / via_dangling | Leftover stubs from autoroute or manual edits; delete |
| unconnected_items | Missing route — check the net in `nets` output first |
| courtyard_overlap | Parts physically colliding; move one |
| silk_over_courtyard | Move silkscreen text or accept if cosmetic |
| hole_clearance | Via/pad too close to another hole or board edge |
| missing_courtyard | Footprint without courtyard — replace footprint |

## Rules

- Never suppress a violation (`--severity-error` tricks, exclusions) without
  recording why in the project notes. Suppressed DRC = hidden defect.
- "Unconnected items" often indicates a schematic problem, not a routing
  miss — re-run `nets` on the affected part before hunting in layout.
- After any fix, re-render and visually inspect the region you touched.

## Before fabrication

- Run DRC with the fab's design rules loaded (min trace/space, annular ring,
  drill), not KiCad defaults.
- Export gerbers per `skills/reference/kicad-cli-cookbook.md` and render them
  (e.g. gerbv/kicad gerber viewer) for a final visual check.
