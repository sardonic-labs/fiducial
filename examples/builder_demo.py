#!/usr/bin/env python3
"""builder_demo.py - minimal example of SchematicBuilder vs hand-rolled S-exp.

Rebuilds the healthy test fixture programmatically; the output is parseable
and lint-clean without touching S-expressions by hand.

Run:
    python examples/builder_demo.py
    python scripts/fiducial.py lint /tmp/builder_demo.kicad_sch
"""
import sys
from pathlib import Path

# allow import when run from project root or examples/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from schematic_builder import SchematicBuilder

OUT = Path("/tmp/builder_demo.kicad_sch")

def main():
    b = SchematicBuilder(OUT, title="Fiducial demo (built)", rev="A")

    # Three symbols like tests/fixtures/healthy.kicad_sch: R1, C1, U1
    b.add_symbol("Device:R", ref="R1", value="10k", footprint="Resistor_SMD:R_0603_1608Metric", at=(50.8, 50.8))
    b.add_symbol("Device:C", ref="C1", value="100n", footprint="Capacitor_SMD:C_0603_1608Metric", at=(81.28, 50.8))
    b.add_symbol("Test:MCU", ref="U1", value="TestMCU", footprint="QFN", at=(121.92, 50.8))

    # Preferred wiring: labels, not long wires (authoring.md)
    b.connect("R1", "1", "/A")
    b.connect("U1", "2", "/A")
    b.connect("R1", "2", "/B")
    b.connect("U1", "3", "/B")
    b.connect("U1", "1", "/VCC")
    b.connect("C1", "1", "/VCC")
    b.connect("U1", "4", "/GND")
    b.connect("C1", "2", "/GND")

    # Power symbols are symbols (power:GND), not bare wires
    b.add_power("GND", at=(50.8, 80.01))
    b.add_power("+3V3", at=(50.8, 20.32))

    # Intent is emitted, not guessed after wiring
    b.save(validate=True)
    intent = OUT.with_name("builder_demo-intent.csv")
    b.write_intent(intent)

    print(f"wrote {OUT}")
    print(f"wrote {intent}")
    print(intent.read_text())

    # Optional: add a wire example (orthogonal only, cleanliness.md)
    b2 = SchematicBuilder("/tmp/builder_demo_wired.kicad_sch", title="Wired demo")
    b2.add_symbol("Test:Resistor", ref="R1", value="10k", at=(50.8, 50.8))
    b2.wire((50.8, 46.99), (50.8, 38.1))
    b2.wire((50.8, 38.1), (63.5, 38.1))
    b2.wire((50.8, 54.61), (50.8, 63.5))
    b2.wire((50.8, 63.5), (63.5, 63.5))
    b2.label("NET_A", at=(63.5, 38.1))
    b2.label("NET_B", at=(63.5, 63.5))
    b2.save(validate=True)
    print(f"wrote {b2.path}")

if __name__ == "__main__":
    main()
