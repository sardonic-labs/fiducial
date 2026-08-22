# PCB layout and routing

Read before placing or routing. Assumes schematic passed ERC and the
connectivity audit.

## Placement order

1. **Fix connectors and mounting holes first** — they are constrained by the
   enclosure/external world, everything else flows from them.
2. **MCU / main IC next**, near its connectors (crystal within a few mm,
   decoupling caps on the same side, as close to their pins as possible).
3. **Power section** at the board edge away from sensitive analog/RF; keep
   switching loops (buck converters) tight and away from signals.
4. **Decoupling**: one cap per power pin of every IC, <2 mm from pin when
   possible, via to plane right at the cap.
5. Group by function (USB section, debug header, user IO) before fine-tuning.

## Placement rules

- No components under/near board edge (< 0.5 mm mechanical clearance, more if
  panelized).
- Crystals: close to MCU, short traces, guard with ground, no other signals
  under or beside them.
- Keep analog references (VREF, ENET magnetics, RF matching) isolated.
- Orient passives consistently for assembly sanity.
- Test points and fiducials on accessible side; fiducials are mandatory
  (this repo is named after them).

## Routing rules

- **Trace width by current** (1 oz Cu, ~10 °C rise): 0.2 mm ≈ 0.5 A,
  0.5 mm ≈ 1.5 A, 1 mm ≈ 3 A. Verify against a calculator for real designs;
  never route 3 A through a default-width trace.
- **Differential pairs**: USB 2.0 = 90 Ω diff, length matched ±0.15 mm
  between pairs (not critical intra-pair at FS), solid ground under them,
  no plane splits underneath.
- **Impedance**: single-ended high-speed ≈ 50 Ω. Use the fab's stackup numbers
  in the board setup (net classes), not guesses.
- **Vias**: one per direction change is fine for low speed; avoid stitching
  random vias into planes; every via has a pad-size/annular-ring check in DRC —
  respect the fab's minimums.
- **Never** route over plane splits; return current follows under the trace.
- Ground pour both layers where possible; stitch with vias.

## After layout

```
python fiducial/scripts/fiducial.py drc <project.kicad_pcb>
python fiducial/scripts/fiducial.py render <project.kicad_pcb> --outdir render
```

Look at both copper layers rendered. Check: unbroken ground return under
high-speed routes, thermal relief on pads connecting to pours, silkscreen
readability.
