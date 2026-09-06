import json, tempfile, unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from fidsynth import compile_spec

SPEC = {"title":"T","components":[{"ref":"R1","part":"R"},{"ref":"C1","part":"C"},{"ref":"U1","part":"TEST_MCU"}],
        "nets":{"/A":["R1.1","U1.2"],"/B":["R1.2","U1.3"],"/VCC":["U1.1","C1.1"],"/GND":["U1.4","C1.2"]}}

class TestSynth(unittest.TestCase):
    def test_compile_ok(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)/"b.kicad_sch"
            r = compile_spec(SPEC, out=str(out), check=False)
            self.assertTrue(out.exists())
            self.assertTrue(Path(r["intent"]).exists())
    def test_unknown_part_fails(self):
        bad = dict(SPEC); bad["components"]=[{"ref":"X1","part":"NOPE"}]
        with self.assertRaises(ValueError): compile_spec(bad, out="/tmp/x.kicad_sch", check=False)
    def test_bad_pin_fails(self):
        bad = json.loads(json.dumps(SPEC)); bad["nets"]["/A"]=["R1.9","U1.2"]
        with self.assertRaises(ValueError): compile_spec(bad, out="/tmp/x.kicad_sch", check=False)
    def test_intent_rows(self):
        from fidsynth.spec import spec_to_intent_rows
        rows = spec_to_intent_rows(SPEC)
        self.assertEqual(len(rows), 8)
    def test_examples_lint_clean(self):
        import subprocess
        fid = Path(__file__).resolve().parent.parent / "scripts" / "fiducial.py"
        for spec in (Path(__file__).resolve().parent.parent / "examples" / "synth").glob("*.json"):
            with tempfile.TemporaryDirectory() as d:
                out = Path(d)/"b.kicad_sch"
                compile_spec(str(spec), out=str(out), check=False)
                proc = subprocess.run([sys.executable, str(fid), "lint", str(out)], capture_output=True, text=True)
                self.assertEqual(proc.returncode, 0, f"{spec.name}: {proc.stdout}{proc.stderr}")
    def test_rules_warn_missing_decoupling(self):
        from fidsynth.rules import apply_rules
        spec = {"title":"T","components":[{"ref":"U1","part":"TEST_MCU"}],"nets":{"/VCC":["U1.1"],"/GND":["U1.4"]}}
        warns = apply_rules(spec)
        self.assertTrue(any("decoupling" in w for w in warns))
