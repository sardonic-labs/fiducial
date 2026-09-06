"""Parts registry — no guessed pinouts.

Only parts listed here can be synthesized. Passives are generic;
ICs must be added with a datasheet URL and explicit pin map.
"""
PARTS = {
    # Passives — generic, no pinout risk
    "R": {"lib_id": "Device:R", "pins": ["1","2"], "datasheet": "generic", "kind": "passive", "footprint": "Resistor_SMD:R_0603_1608Metric"},
    "C": {"lib_id": "Device:C", "pins": ["1","2"], "datasheet": "generic", "kind": "passive", "footprint": "Capacitor_SMD:C_0603_1608Metric"},
    "L": {"lib_id": "Device:L", "pins": ["1","2"], "datasheet": "generic", "kind": "passive", "footprint": "Inductor_SMD:L_0603_1608Metric"},
    "LED": {"lib_id": "Device:LED", "pins": ["1","2"], "datasheet": "generic", "kind": "passive", "footprint": "LED_SMD:LED_0603_1608Metric"},
    # Connectors / power — single-pin power symbols handled via add_power in builder, but allow as generic
    "GND": {"lib_id": "power:GND", "pins": ["1"], "datasheet": "generic", "kind": "power"},
    # Verified ICs — pin maps reviewed against datasheet; do not add without URL + review
    "TEST_MCU": {"lib_id": "Test:MCU", "pins": ["1","2","3","4"], "datasheet": "https://example.com/test_mcu_ds.pdf", "kind": "ic", "footprint": "Test:QFN-16"},
    "REG_3V3": {"lib_id": "Regulator_Linear:AP2112K-3.3", "pins": ["1","2","3","4","5"], "datasheet": "https://www.diodes.com/datasheet/AP2112.pdf", "kind": "ic", "footprint": "Package_TO_SOT_SMD:SOT-23-5"},
    "AT24C02": {"lib_id": "Memory_EEPROM:AT24C02", "pins": ["1","2","3","4","5","6","7","8"], "datasheet": "https://ww1.microchip.com/downloads/en/DeviceDoc/doc0180.pdf", "kind": "ic", "footprint": "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"},
}

def get_part(part_key):
    p = PARTS.get(part_key)
    if not p:
        raise ValueError(f"unknown part '{part_key}'. Allowed: {sorted(PARTS)} — add new ICs only with datasheet + pin map (see registry.py)")
    return p

def validate_component(comp):
    part = get_part(comp["part"])
    # For passives, value/footprint recommended but not required; for ICs enforce pin validity
    # Pin validity is checked at compile time against nets
    return part
