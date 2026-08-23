# Power-path part selection — show the math

Fiducial verifies connections; it cannot verify that a part *survives* its
job. That is on you, and it is done with arithmetic, not intuition. This skill
exists because a real AI-authored design (backplane-v0 battery entry,
2026-08-23) chose a SOT-23 P-FET for a 3 A rail — I²R dissipation ~0.5 W in a
package rated ~0.35 W. ERC passed. The part would have cooked.

## The rule

**Every part in the power path carries a dissipation and margin calculation,
written into the PR or commit message, before it is considered selected.**
No math, no part.

## MOSFET / load-switch checklist (high-side switches)

For a switch carrying current I on a rail of maximum voltage Vmax:

1. **Dissipation:** P = I² × RDS(on)_at_actual_VGS. Compute at the *worst*
   gate drive (minimum VGS), not the datasheet's headline number.
2. **Package limit:** find θJA in the datasheet; P_max = (Tj_max − Ta_ambient)
   / θJA. Require **P ≤ 0.5 × P_max** (2× thermal margin — enclosures and
   sun exist).
   - Rule of thumb: SOT-23 ≈ 0.35 W, SOT-89 ≈ 0.5–0.8 W, DPAK/TO-252 ≈ 1.5–2.5 W
     `[typical figures — always confirm the specific datasheet]`
3. **VGS max:** rail voltage fully applied gate-to-source when OFF must be
   within the absolute maximum (±12 V parts are marginal on a 2S Li-ion 8.4 V
   rail — check, don't assume).
4. **VGS(th) is NOT RDS(on) territory.** A "−1 V threshold" part may only be
   half-enhanced at −2.5 V. Use the RDS(on) spec at your real VGS.
5. **Fail-safe polarity:** for a high-side P-FET driven by a logic signal,
   gate pulled UP to source = OFF by default (unpowered controller ⇒ rail
   off). State the fail state in one sentence in the commit message.

## Diodes / reverse protection

- Series Schottky at current I costs P = I × Vf — compute it (at 3 A a 0.4 V
  Schottky burns 1.2 W continuously; that is a heater, not protection).
- Ideal-diode controllers or P-FET active blockers move that loss into milliwatts
  at ~$0.30–1. Justify any choice of the lossy option in writing.

## Fuses

- PPTC hold rating must exceed worst-case continuous current **at the real
  ambient temperature** (PPTCs derate significantly above 25 °C — read the
  derating curve, not the headline).
- Trip current must be below what the wiring/PCB traces survive.

## Worked example (the failure that created this skill)

Backplane VBAT rail: 2S Li-ion, Vmax = 8.4 V, I = 3 A shared.

- Candidate: AO3401A (P-FET, SOT-23). RDS(on) ≈ 50–60 mΩ at VGS = −4.5 V.
  P = 9 A² × 0.055 Ω ≈ 0.50 W.
- SOT-23 P_max ≈ (150 °C − 40 °C) / 350 °C/W ≈ 0.31 W.
- 0.50 W > 0.5 × 0.31 W. **Reject.** Need RDS(on) ≤ 30 mΩ in a package with
  θJA ≤ ~100 °C/W, or a parallel pair with balancing caveats.

Write that paragraph for every power part. It takes two minutes and it is
the difference between a bring-up and a bonfire.

## Where the numbers come from

- Datasheets: use [../reference/datasheets.md](../reference/datasheets.md) —
  never from memory.
- Find candidate parts: `scripts/find_part.py` searches local/system libraries;
  prefer JLCPCB-stocked parts (C-numbers) for assemblability.
