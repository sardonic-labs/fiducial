"""Design-rule engine — auto-decoupling and rail checks (stdlib-only)."""

def apply_rules(spec):
    """Mutate/validate spec in place. Returns list of warnings."""
    warns = []
    # Rule: every IC needs a decoupling cap on its VCC pin (heuristic: any net named VCC/VDD/3V3)
    refs_by_part = {c["ref"]: c for c in spec["components"]}
    import re
    from fidsynth.registry import get_part
    power_pat = re.compile(r"^(/)?(VCC|VDD|3V3|3\.3V|AVCC)", re.I)
    power_nets = [n for n in spec["nets"] if power_pat.search(n)]
    ic_refs = [r for r,c in refs_by_part.items() if get_part(c["part"])["kind"]=="ic"]
    for ref in ic_refs:
        # check if IC has a pin on a power net — if yes, need at least one C on same net
        ic_nets = {n for n,pins in spec["nets"].items() if any(p.startswith(ref+".") for p in pins)}
        needs = ic_nets & set(power_nets)
        for net in needs:
            caps = [p for p in spec["nets"][net] if p.split(".")[0].startswith("C")]
            if not caps:
                warns.append(f"{ref}: no decoupling cap on {net} — add C on {net}")
    # Rule: GND must exist
    if not any(n.upper() in ("/GND","GND") or n=="/GND" for n in spec["nets"]):
        warns.append("no GND net — add GND")
    return warns
