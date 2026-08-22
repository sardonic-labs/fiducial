"""Regression tests for fiducial.py, run against a real AI-authored schematic
with two known planted bugs (floating crystal caps, missing SWD header).

Run:  python -m unittest discover -s tests -v
Requires kicad-cli on PATH for the connectivity tests; they skip otherwise.
"""

import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "fiducial.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
SCH = FIXTURES / "rp2040-devboard.kicad_sch"
CSV = FIXTURES / "rp2040-intent.csv"
GENERATED = [FIXTURES / "rp2040-devboard-netlist.sexpr",
             FIXTURES / "rp2040-devboard-bom.csv"]


def run_cli(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, encoding="utf-8")


def has_kicad():
    return shutil.which("kicad-cli") is not None


class TestNoKiCad(unittest.TestCase):
    def test_help_exits_zero(self):
        proc = run_cli("--help")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("check-intent", proc.stdout)


@unittest.skipUnless(has_kicad(), "kicad-cli not on PATH")
class TestWithKiCad(unittest.TestCase):
    def tearDown(self):
        for f in GENERATED:
            f.unlink(missing_ok=True)

    def test_erc_clean(self):
        """The fixture passes ERC - proving ERC alone misses the planted bugs."""
        proc = run_cli("erc", str(SCH))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("0 errors", proc.stdout)

    def test_lint_catches_orphans_and_labels(self):
        proc = run_cli("lint", str(SCH))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("net '/XIN' has a single connection (C3.1)", proc.stdout)
        self.assertIn("net '/XOUT' has a single connection (C4.1)", proc.stdout)
        self.assertIn("'XIN' appears only once", proc.stdout)
        # power labels merged into real nets must NOT be flagged
        self.assertNotIn("'+3V3' appears only once", proc.stdout)

    def test_check_intent_counts(self):
        proc = run_cli("check-intent", str(SCH), str(CSV))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("WRONG", proc.stdout)
        self.assertIn("58/64 connections verified", proc.stdout)
        # crystal mismatch rows
        self.assertRegex(proc.stdout, r"U1\s+20\s+/XIN\s+Net-\(U1-XIN\)\s+WRONG")
        # missing SWD header rows
        self.assertIn("/SWCLK", proc.stdout)

    def test_check_intent_orphans(self):
        proc = run_cli("check-intent", str(SCH), str(CSV), "--orphans")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("32 orphan net(s)", proc.stdout)
        self.assertIn("ORPHAN", proc.stdout)

    def test_nets_dump(self):
        run_cli("netlist", str(SCH))
        proc = run_cli("nets", str(SCH))
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Net-(U1-XIN)", proc.stdout)
        self.assertIn("+3V3", proc.stdout)

    def test_pins_dump(self):
        proc = run_cli("pins", str(SCH), "U3")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("W25Q16JVSS", proc.stdout)
        self.assertIn("/QSPI_SS", proc.stdout)


if __name__ == "__main__":
    unittest.main()
