# Best practices checklists

Run the relevant checklist before calling any milestone done.

## Power

- [ ] Power tree documented: source → rails → consumers with current budget.
- [ ] Decoupling: 100 nF per power pin (plus bulk 4.7–10 µF per rail region);
      placed at pins.
- [ ] LDO dropout satisfied at min input voltage and max load; thermal check
      ((Vin−Vout)·I vs package θJA).
- [ ] Every rail has a way to be measured (test point) and ideally an LED.
- [ ] USB VBUS protected (polyfuse/TVS) if board can back-power or sink current.

## Signal integrity

- [ ] Series resistors (22–33 Ω) on fast clocks/long parallel buses when
      drivers are strong.
- [ ] Differential pairs routed together, same length, over solid ground.
- [ ] No signals crossing plane splits; ground pour stitched.
- [ ] Crystal traces short, guarded, nothing else nearby.

## ESD / robustness

- [ ] TVS on anything a human touches: USB, buttons, connectors, antennas
      adjacent circuitry.
- [ ] Reset/boot straps have defined levels — never floating inputs on MCUs.
- [ ] Pull values sane for leakage (10–100 kΩ typical).

## DFM / assembly

- [ ] Design rules = fab's rules (JLC-class: ≥0.127 mm via drill typical,
      5 mil trace/space), not KiCad defaults.
- [ ] All parts have footprints, MPNs, and are hand-solderable or assembly-
      friendly per chosen process (0402 minimum size honesty).
- [ ] Silkscreen: designator visible, pin-1 marks, no text under parts.
- [ ] Fiducials (3, asymmetric) + mounting holes present.
- [ ] No copper under wireless module antennas / keepouts respected.

## Testability

- [ ] Debug header present (SWD/JTAG) even on production boards.
- [ ] Test points on all rails and key signals.
- [ ] Bootloader entry / strap state achievable without probes.
