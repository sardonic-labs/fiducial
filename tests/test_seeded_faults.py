"""Seeded-fault benchmark: each fault class must be caught by the right tool.

Offline (no kicad-cli): fixtures ship a pre-exported netlist cache
(board-netlist.sexpr) newer than board.kicad_sch, so lint/check-intent
reuse it instead of invoking kicad-cli.

Regenerate: python scripts/seed_faults.py
Verify:     python scripts/seed_faults.py --check
Run:        python -m unittest discover -s tests -v
"""

import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "fiducial.py"
FAULTS = ROOT / "tests" / "fixtures" / "faults"


def run_cli(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, encoding="utf-8")


def fault_cases():
    cases = []
    for exp_path in sorted(FAULTS.glob("*/expected.json")):
        exp = json.loads(exp_path.read_text(encoding="utf-8"))
        cases.append((exp_path.parent, exp))
    return cases


class TestSeededFaults(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Git does not preserve mtimes, so the "netlist newer than sch"
        # invariant from seed_faults.py is lost at checkout. Refresh it
        # here so lint/check-intent reuse the shipped cache instead of
        # invoking kicad-cli (which would re-export from the synthetic
        # mutant boards and fail). Makes the test hermetic with or
        # without kicad-cli on PATH.
        now = time.time() + 10
        for exp_path in sorted(FAULTS.glob("*/expected.json")):
            d = exp_path.parent
            sch_mtime = (d / "board.kicad_sch").stat().st_mtime
            stamp = max(now, sch_mtime + 1)
            os.utime(d / "board-netlist.sexpr", (stamp, stamp))

    def test_all_faults_present(self):
        self.assertTrue(FAULTS.is_dir(), f"missing {FAULTS}; run seed_faults.py")
        names = sorted(p.parent.name for p in FAULTS.glob("*/expected.json"))
        self.assertEqual(names, ["duplicate-ref", "floating-pin", "label-typo",
                                 "missing-part", "nc-violation", "off-grid",
                                 "power-short", "wrong-net"])
        for d, _ in fault_cases():
            for f in ("board.kicad_sch", "intent.csv",
                      "board-netlist.sexpr", "expected.json"):
                self.assertTrue((d / f).exists(), f"missing {d / f}")

    def test_netlist_cache_fresh(self):
        """Cache must be newer than the sch so no kicad-cli is needed."""
        for d, _ in fault_cases():
            sch = d / "board.kicad_sch"
            nl = d / "board-netlist.sexpr"
            self.assertGreaterEqual(nl.stat().st_mtime, sch.stat().st_mtime,
                                    f"stale cache in {d.name}")

    def test_each_fault_caught(self):
        for d, exp in fault_cases():
            with self.subTest(fault=exp["fault"]):
                lint = run_cli("lint", str(d / "board.kicad_sch"))
                self.assertEqual(lint.returncode, exp["lint_exit"],
                                 lint.stdout + lint.stderr)
                self.assertIn(exp["lint_match"], lint.stdout + lint.stderr)
                intent = run_cli("check-intent", str(d / "board.kicad_sch"),
                                 str(d / "intent.csv"))
                self.assertEqual(intent.returncode, exp["intent_exit"],
                                 intent.stdout + intent.stderr)
                self.assertIn(exp["intent_match"], intent.stdout + intent.stderr)


if __name__ == "__main__":
    unittest.main()
