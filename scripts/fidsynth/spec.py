"""Board spec schema — JSON/YAML-ish dict validated without dependencies."""
import json
import csv
from pathlib import Path

REQUIRED_TOP = {"title", "nets", "components"}

def load_spec(path_or_dict):
    if isinstance(path_or_dict, dict):
        spec = path_or_dict
    else:
        p = Path(path_or_dict)
        text = p.read_text(encoding="utf-8")
        spec = json.loads(text)
    validate_spec(spec)
    return spec

def validate_spec(spec):
    if not isinstance(spec, dict):
        raise ValueError("spec must be a dict")
    missing = REQUIRED_TOP - set(spec.keys())
    if missing:
        raise ValueError(f"spec missing keys: {sorted(missing)}")
    if not isinstance(spec["components"], list):
        raise ValueError("spec['components'] must be a list")
    if not isinstance(spec["nets"], dict):
        raise ValueError("spec['nets'] must be a dict (net -> [ref.pin, ...])")
    for c in spec["components"]:
        if not {"ref","part"} <= set(c.keys()):
            raise ValueError(f"component missing ref/part: {c}")
        # value/footprint optional for passives; required for ICs is enforced in registry
    # validate net refs exist
    refs = {c["ref"] for c in spec["components"]}
    for net, pins in spec["nets"].items():
        if not isinstance(pins, list):
            raise ValueError(f"net {net}: expected list of 'REF.PIN'")
        for p in pins:
            if "." not in p:
                raise ValueError(f"net {net}: bad pin '{p}' expected REF.PIN")
            r,_ = p.split(".",1)
            if r not in refs:
                raise ValueError(f"net {net}: unknown ref '{r}' in '{p}'")

def spec_to_intent_rows(spec):
    rows = []
    for net, pins in spec["nets"].items():
        for rp in pins:
            r,p = rp.split(".",1)
            rows.append({"ref": r, "pin": p, "expected_net": net})
    return rows

def write_intent_csv(rows, path):
    p = Path(path)
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["ref","pin","expected_net"])
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r:(r["ref"], r["pin"])))
    return p
