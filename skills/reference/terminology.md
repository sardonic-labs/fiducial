# Terminology

Use these terms consistently in code, comments, and communication.

## Documents and parts

- **Datasheet** — electrical/mechanical spec for a part. **Reference manual** —
  programming/registers for an MCU family. **Errata** — documented silicon bugs.
- **MPN** — manufacturer part number. **Symbol** — schematic representation.
  **Footprint** — PCB land pattern. **Land pattern** = footprint's pad geometry.

## KiCad files

| Extension | Contents |
|---|---|
| `.kicad_pro` | Project settings, DRC/ERC rules |
| `.kicad_sch` | One schematic sheet (S-expression) |
| `.kicad_pcb` | Board (S-expression) |
| `.kicad_sym` / `.kicad_mod` / `.pretty` | Symbol lib / footprint / footprint dir |

## Electrical

- **Net** — the logical connection set; **wire** — drawn line; a net can exist
  with no wires (labels only).
- **VDD/VSS** — positive supply / ground (MOSFET-style naming); **VCC/GND**
  same idea (bipolar naming). Use whatever the datasheet uses.
- **Pull-up/pull-down** — resistor holding an input at a defined level.
- **Open-drain/open-collector** — can only pull low; needs external pull-up
  (I²C is open-drain).
- **Push-pull** — drives both levels actively (normal GPIO output).
- **Strapping pins** — pins sampled at reset that configure boot mode; must be
  at defined level during power-up.

## Debug / buses

- **SWD** — ARM Serial Wire Debug (SWCLK, SWDIO). **JTAG** — older, more pins.
- **UART/SPI/I²C/USB/CAN** — know which are push-pull vs open-drain, master/
  slave roles, and typical speeds before routing.
- **VBUS** — USB +5 V supply line. **CC pins** — USB-C orientation/config pins,
  need 5.1 kΩ Rd pulldowns on sinks.

## Verification

- **ERC** — electrical rules check (schematic). **DRC** — design rules check
  (PCB vs fab capabilities). Neither proves functional correctness.
- **Intent audit** — this repo's term: mechanical comparison of expected vs
  actual connectivity (`check-intent`).
