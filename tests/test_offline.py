"""Offline unit and regression tests for fiducial.py.

These run on plain CPython with no kicad-cli installed: connectivity data is
provided by small synthetic netlist fixtures, and kicad-cli interactions are
faked at the module boundary.

Run:  python -m unittest discover -s tests -v
(The sibling test_fiducial.py additionally exercises real kicad-cli paths
and skips itself when kicad-cli is not available.)
"""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"

_spec = importlib.util.spec_from_file_location(
    "fiducial_under_test", ROOT / "scripts" / "fiducial.py")
fid = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fid)

# Matches tests/fixtures/healthy.kicad_sch (refs R1, C1, U1).
NETLIST_HEALTHY = """(export (version "E")
\t(components
\t\t(comp (ref "R1") (value "10k") (footprint "R_0603"))
\t\t(comp (ref "C1") (value "100n") (footprint "C_0603"))
\t\t(comp (ref "U1") (value "TestMCU") (footprint "QFN"))
\t)
\t(nets
\t\t(net (code "1") (name "/A")
\t\t\t(node (ref "R1") (pin "1")) (node (ref "U1") (pin "2")))
\t\t(net (code "2") (name "/B")
\t\t\t(node (ref "R1") (pin "2")) (node (ref "U1") (pin "3")))
\t\t(net (code "3") (name "/VCC")
\t\t\t(node (ref "U1") (pin "1")) (node (ref "C1") (pin "1")))
\t\t(net (code "4") (name "/GND")
\t\t\t(node (ref "U1") (pin "4")) (node (ref "C1") (pin "2")))
\t)
)"""

NETLIST_ORPHAN = """(export (version "E")
\t(components
\t\t(comp (ref "R1") (value "10k") (footprint "R_0603"))
\t\t(comp (ref "C1") (value "100n") (footprint "C_0603"))
\t\t(comp (ref "U1") (value "TestMCU") (footprint "QFN"))
\t)
\t(nets
\t\t(net (code "1") (name "/A")
\t\t\t(node (ref "R1") (pin "1")) (node (ref "U1") (pin "2")))
\t\t(net (code "2") (name "/B")
\t\t\t(node (ref "R1") (pin "2")) (node (ref "U1") (pin "3")))
\t\t(net (code "3") (name "/VCC")
\t\t\t(node (ref "U1") (pin "1")) (node (ref "C1") (pin "1")))
\t\t(net (code "4") (name "/GND")
\t\t\t(node (ref "U1") (pin "4")) (node (ref "C1") (pin "2")))
\t\t(net (code "5") (name "/LONELY") (node (ref "U1") (pin "99")))
\t)
)"""

NETLIST_PINS = """(export (version "E")
\t(components
\t\t(comp (ref "R1") (value "10k") (footprint "R_0603"))
\t\t(comp (ref "C1") (value "100n") (footprint "C_0603"))
\t\t(comp (ref "U1") (value "TestMCU") (footprint "QFN"))
\t)
\t(nets
\t\t(net (code "1") (name "/A")
\t\t\t(node (ref "R1") (pin "1")) (node (ref "U1") (pin "2")))
\t\t(net (code "2") (name "/B")
\t\t\t(node (ref "R1") (pin "2")) (node (ref "U1") (pin "3")))
\t\t(net (code "3") (name "/VCC")
\t\t\t(node (ref "U1") (pin "1")) (node (ref "C1") (pin "1")))
\t\t(net (code "4") (name "/GND")
\t\t\t(node (ref "U1") (pin "4")) (node (ref "C1") (pin "2")))
\t\t(net (code "5") (name "/BUS")
\t\t\t(node (ref "U1") (pin "10")) (node (ref "U1") (pin "11")))
\t)
)"""

NETLIST_RULES = """(export (version "E")
\t(components
\t\t(comp (ref "EPS1") (value "EPS") (footprint ""))
\t\t(comp (ref "J1") (value "HDR") (footprint ""))
\t)
\t(nets
\t\t(net (code "1") (name "/VBAT")
\t\t\t(node (ref "EPS1") (pin "1")) (node (ref "J1") (pin "1")))
\t)
)"""

INTENT_OK = "ref,pin,expected_net\nR1,1,/A\nR1,2,/B\nU1,1,/VCC\nC1,2,/GND\n"

# one ok row, one WRONG row (R1.1 is actually on /A), one MISSING row
INTENT_MIXED = ("ref,pin,expected_net\n"
                "R1,1,/A\n"
                "R1,1,/B\n"
                "U1,99,/NOPE\n")


def fake_kicad_cli(calls, payload=None):
    """Return a stand-in for fid.kicad_cli that records args and, when
    payload is not None, writes a JSON report to the requested --output."""
    def _fake(args, timeout=180):
        calls.append(list(args))
        if payload is not None:
            out = Path(args[args.index("--output") + 1])
            out.write_text(json.dumps(payload), encoding="utf-8")
        return subprocess.CompletedProcess(args, returncode=0,
                                           stdout="", stderr="")
    return _fake


class OfflineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fiducial-offline-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def project(self, fixture="healthy.kicad_sch"):
        dst = self.tmp / fixture
        shutil.copy(FIXTURES / fixture, dst)
        return dst

    def cache_netlist(self, project, text=NETLIST_HEALTHY, newer_by=100):
        nl = fid._netlist_path(project)
        nl.write_text(text, encoding="utf-8")
        st = project.stat()
        os.utime(nl, (st.st_mtime + newer_by,) * 2)
        return nl

    def write(self, name, text):
        p = self.tmp / name
        p.write_text(text, encoding="utf-8", newline="")
        return p

    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = fid.main(list(argv))
        return rc, out.getvalue(), err.getvalue()


class TestParseSexp(unittest.TestCase):
    def test_round_trip_simple(self):
        self.assertEqual(fid.parse_sexp("(a b (c d))"),
                         ["a", "b", ["c", "d"]])

    def test_quoted_strings_with_spaces(self):
        root = fid.parse_sexp('(net (name "/A B") (pin "1"))')
        self.assertEqual(fid._first_str(fid.sexp_get(root, "name")), "/A B")

    def test_escaped_quote_inside_string(self):
        root = fid.parse_sexp(r'(desc "a \"quoted\" word")')
        self.assertEqual(root[1], 'a "quoted" word')

    def test_unbalanced_open_raises(self):
        with self.assertRaises(ValueError):
            fid.parse_sexp("(a (b c)")

    def test_missing_open_paren_raises(self):
        with self.assertRaises(ValueError):
            fid.parse_sexp("a b c)")

    def test_lone_close_paren_raises(self):
        with self.assertRaises(ValueError):
            fid.parse_sexp(")")


class TestLint(OfflineTest):
    def test_healthy_board_is_clean(self):
        proj = self.project()
        self.cache_netlist(proj)
        rc, out, _ = self.run_main("lint", str(proj))
        self.assertEqual(rc, fid.EXIT_OK, out)
        self.assertIn("Lint clean (3 symbols)", out)

    def test_duplicate_reference_caught(self):
        proj = self.project("duplicate-ref.kicad_sch")
        self.cache_netlist(proj, "(components)\n(nets)")
        rc, out, _ = self.run_main("lint", str(proj))
        self.assertEqual(rc, fid.EXIT_VIOLATIONS)
        self.assertIn("duplicate reference: R1", out)

    def test_single_use_label_caught(self):
        proj = self.project("single-use-label.kicad_sch")
        self.cache_netlist(proj)
        rc, out, _ = self.run_main("lint", str(proj))
        self.assertEqual(rc, fid.EXIT_VIOLATIONS)
        self.assertIn("'TYPO' appears only once", out)
        # paired labels merged into multi-pin nets must stay unflagged
        self.assertNotIn("'/A' appears only once", out)

    def test_orphan_net_detected(self):
        proj = self.project()
        self.cache_netlist(proj, NETLIST_ORPHAN)
        rc, out, _ = self.run_main("lint", str(proj))
        self.assertEqual(rc, fid.EXIT_VIOLATIONS)
        self.assertIn("net '/LONELY' has a single connection (U1.99)", out)

    def test_malformed_sexpression_exits_env(self):
        proj = self.project("malformed.kicad_sch")
        rc, _, err = self.run_main("lint", str(proj))
        self.assertEqual(rc, fid.EXIT_ENV)
        self.assertIn("malformed S-expression", err)

    def test_missing_project_file_exits_env(self):
        rc, _, err = self.run_main("lint", str(self.tmp / "nope.kicad_sch"))
        self.assertEqual(rc, fid.EXIT_ENV)


class TestCheckIntent(OfflineTest):
    def test_all_ok(self):
        proj = self.project()
        self.cache_netlist(proj)
        csvp = self.write("ok.csv", INTENT_OK)
        rc, out, _ = self.run_main("check-intent", str(proj), str(csvp))
        self.assertEqual(rc, fid.EXIT_OK, out)
        self.assertIn("4/4 connections verified", out)

    def test_wrong_and_missing_flagged(self):
        proj = self.project()
        self.cache_netlist(proj)
        csvp = self.write("mixed.csv", INTENT_MIXED)
        rc, out, _ = self.run_main("check-intent", str(proj), str(csvp))
        self.assertEqual(rc, fid.EXIT_VIOLATIONS)
        self.assertRegex(out, r"\*R1\s+1\s+/B\s+/A\s+WRONG")
        self.assertRegex(out, r"\*U1\s+99\s+/NOPE\s+None\s+MISSING")
        self.assertIn("1/3 connections verified", out)

    def test_orphans_flagged_with_switch(self):
        proj = self.project()
        self.cache_netlist(proj, NETLIST_ORPHAN)
        csvp = self.write("ok.csv", INTENT_OK)
        rc, out, _ = self.run_main("check-intent", str(proj), str(csvp),
                                   "--orphans")
        self.assertEqual(rc, fid.EXIT_VIOLATIONS)
        self.assertIn("/LONELY", out)
        self.assertIn("ORPHAN", out)
        self.assertIn("1 orphan net(s)", out)

    def test_bad_csv_columns_exit_env(self):
        proj = self.project()
        self.cache_netlist(proj)
        csvp = self.write("bad.csv", "foo,bar\nx,y\n")
        rc, _, err = self.run_main("check-intent", str(proj), str(csvp))
        self.assertEqual(rc, fid.EXIT_ENV)

    def test_json_output(self):
        proj = self.project()
        self.cache_netlist(proj)
        csvp = self.write("mixed.csv", INTENT_MIXED)
        rc, out, _ = self.run_main("check-intent", str(proj), str(csvp),
                                   "--json")
        self.assertEqual(rc, fid.EXIT_VIOLATIONS)
        doc = json.loads(out)
        statuses = {r["status"] for r in doc["results"]}
        self.assertEqual(statuses, {"ok", "WRONG", "MISSING"})
        self.assertEqual(doc["verified"], 1)
        self.assertEqual(doc["total"], 3)


class TestPins(OfflineTest):
    def test_pins_sorted_numerically(self):
        proj = self.project()
        self.cache_netlist(proj, NETLIST_PINS)
        rc, out, _ = self.run_main("pins", str(proj), "U1")
        self.assertEqual(rc, fid.EXIT_OK, out)
        order = [line.split()[1] for line in out.splitlines()
                 if line.lstrip().startswith("pin ")]
        self.assertEqual(order, ["1", "2", "3", "4", "10", "11"])

    def test_unknown_ref_is_env_error_not_violation(self):
        proj = self.project()
        self.cache_netlist(proj)
        rc, _, err = self.run_main("pins", str(proj), "X99")
        self.assertEqual(rc, fid.EXIT_ENV)
        self.assertIn("X99", err)

    def test_pin_sort_key(self):
        ordered = sorted(["10", "NC", "2", "A1"], key=fid._pin_sort)
        self.assertEqual(ordered, ["A1", "2", "10", "NC"])


class TestStaleNetlistCache(OfflineTest):
    """P0 regression: schematic newer than cache must auto-regenerate."""

    def setUp(self):
        super().setUp()
        self.calls = []
        self._orig = fid._export_netlist
        fid._export_netlist = self._fake_export
        self.addCleanup(setattr, fid, "_export_netlist", self._orig)

    def _fake_export(self, project):
        self.calls.append(str(project))
        out = fid._netlist_path(project)
        out.write_text(NETLIST_HEALTHY, encoding="utf-8")
        return out, fid.EXIT_OK

    def test_fresh_cache_not_regenerated(self):
        proj = self.project()
        self.cache_netlist(proj)  # netlist newer than schematic
        nets, _, _, fresh = fid._load_nets(proj)
        self.assertFalse(fresh)
        self.assertEqual(self.calls, [])
        self.assertIn("/A", nets)

    def test_stale_cache_auto_regenerates(self):
        proj = self.project()
        self.cache_netlist(proj, newer_by=-100)  # schematic newer than cache
        nets, _, _, fresh = fid._load_nets(proj)
        self.assertTrue(fresh)
        self.assertEqual(len(self.calls), 1)

    def test_refresh_forces_regeneration(self):
        proj = self.project()
        self.cache_netlist(proj)  # cache is fresh
        _, _, _, fresh = fid._load_nets(proj, refresh=True)
        self.assertTrue(fresh)
        self.assertEqual(len(self.calls), 1)


class TestUniqueTempReports(OfflineTest):
    """P0 regression: ERC/DRC reports must never be read from a stale path."""

    def setUp(self):
        super().setUp()
        self.calls = []
        self._orig = fid.kicad_cli
        self.addCleanup(setattr, fid, "kicad_cli", self._orig)

    def test_report_paths_are_unique_and_cleaned_up(self):
        fid.kicad_cli = fake_kicad_cli(self.calls, {"erc": []})
        paths = []
        for _ in range(2):
            rc, out, _ = self.run_main("erc", "board.kicad_sch")
            self.assertEqual(rc, fid.EXIT_OK, out)
            i = self.calls[-1].index("--output")
            paths.append(Path(self.calls[-1][i + 1]))
        self.assertNotEqual(paths[0], paths[1])
        predictable = Path(tempfile.gettempdir()) / "fiducial-erc.json"
        for p in paths:
            self.assertNotEqual(p, predictable)
            self.assertFalse(p.exists())  # cleaned up after parsing
        leftovers = list(Path(tempfile.gettempdir()).glob("fiducial-erc-*.json"))
        self.assertEqual(leftovers, [])

    def test_predictable_legacy_path_never_used(self):
        fid.kicad_cli = fake_kicad_cli(self.calls, {"drc": []})
        legacy = Path(tempfile.gettempdir()) / "fiducial-drc.json"
        legacy.write_text('{"drc": [{"severity": "severity_error"}]}',
                          encoding="utf-8")
        self.addCleanup(legacy.unlink, missing_ok=True)
        rc, out, _ = self.run_main("drc", "board.kicad_pcb")
        # If the stale file had been parsed we would see 1 error and exit 1.
        self.assertEqual(rc, fid.EXIT_OK, out)
        self.assertIn("0 errors", out)

    def test_failed_run_reports_env_error(self):
        fid.kicad_cli = fake_kicad_cli(self.calls, payload=None)
        rc, _, err = self.run_main("erc", "board.kicad_sch")
        self.assertEqual(rc, fid.EXIT_ENV)
        self.assertIn("no ERC report produced", err)


class TestDrcMutation(OfflineTest):
    """P0 regression: drc must not rewrite the board unless asked."""

    def setUp(self):
        super().setUp()
        self.calls = []
        self._orig = fid.kicad_cli
        fid.kicad_cli = fake_kicad_cli(self.calls, {"drc": []})
        self.addCleanup(setattr, fid, "kicad_cli", self._orig)

    def test_default_does_not_save_board(self):
        rc, out, _ = self.run_main("drc", "board.kicad_pcb")
        self.assertEqual(rc, fid.EXIT_OK, out)
        args = self.calls[-1]
        self.assertNotIn("--save-board", args)
        self.assertNotIn("--refill-zones", args)

    def test_save_board_opt_in_refills_zones(self):
        rc, _, _ = self.run_main("drc", "board.kicad_pcb", "--save-board")
        self.assertEqual(rc, fid.EXIT_OK)
        args = self.calls[-1]
        self.assertIn("--save-board", args)
        self.assertIn("--refill-zones", args)

    def test_parity_flag_still_works(self):
        self.run_main("drc", "board.kicad_pcb", "--parity")
        self.assertIn("--schematic-parity", self.calls[-1])


class TestJsonReports(OfflineTest):
    def setUp(self):
        super().setUp()
        self.calls = []
        self._orig = fid.kicad_cli
        self.addCleanup(setattr, fid, "kicad_cli", self._orig)

    def test_erc_json_counts_violations(self):
        payload = {"erc": [
            {"severity": "severity_error", "type": "err_type",
             "description": "pins not connected", "pos": "0,0", "items": []},
            {"severity": "severity_warning", "type": "warn_type",
             "description": "warning text", "pos": "1,1", "items": []},
        ]}
        fid.kicad_cli = fake_kicad_cli(self.calls, payload)
        rc, out, _ = self.run_main("erc", "board.kicad_sch", "--json")
        self.assertEqual(rc, fid.EXIT_VIOLATIONS)
        doc = json.loads(out)
        self.assertEqual(doc["error_count"], 1)
        self.assertEqual(doc["warning_count"], 1)
        self.assertEqual(doc["errors"][0]["description"],
                         "pins not connected")

    def test_erc_human_output_unchanged_shape(self):
        fid.kicad_cli = fake_kicad_cli(self.calls, {"erc": []})
        rc, out, _ = self.run_main("erc", "board.kicad_sch")
        self.assertEqual(rc, fid.EXIT_OK)
        self.assertIn("ERC on board.kicad_sch: 0 errors, 0 warnings", out)

    def test_lint_json_lists_problems(self):
        proj = self.project("duplicate-ref.kicad_sch")
        self.cache_netlist(proj, "(components)\n(nets)")
        rc, out, _ = self.run_main("lint", str(proj), "--json")
        self.assertEqual(rc, fid.EXIT_VIOLATIONS)
        doc = json.loads(out)
        self.assertIn("duplicate reference: R1", doc["problems"])


class TestCheckRules(OfflineTest):
    def setUp(self):
        super().setUp()
        proj = self.project()
        self.cache_netlist(proj, NETLIST_RULES)
        self.proj = proj

    def test_rules_pass(self):
        rules = ("rule,net,params\n"
                 "min-contacts,/VBAT,2\n"
                 "net-exclusive,/VBAT,EPS1 J1\n")
        csvp = self.write("rules-ok.csv", rules)
        rc, out, _ = self.run_main("check-rules", str(self.proj), str(csvp))
        self.assertEqual(rc, fid.EXIT_OK, out)
        self.assertIn("All 2 rule(s) pass", out)

    def test_min_contacts_violation(self):
        rules = "rule,net,params\nmin-contacts,/VBAT,5\n"
        csvp = self.write("rules-min.csv", rules)
        rc, out, _ = self.run_main("check-rules", str(self.proj), str(csvp))
        self.assertEqual(rc, fid.EXIT_VIOLATIONS)
        self.assertIn("2 connection(s), need >= 5", out)

    def test_net_exclusive_violation(self):
        rules = "rule,net,params\nnet-exclusive,/VBAT,EPS1\n"
        csvp = self.write("rules-excl.csv", rules)
        rc, out, _ = self.run_main("check-rules", str(self.proj), str(csvp))
        self.assertEqual(rc, fid.EXIT_VIOLATIONS)
        self.assertIn("J1.1 connected", out)

    def test_unknown_rule_type_exit_env(self):
        rules = "rule,net,params\nno-vias,/VBAT,\n"
        csvp = self.write("rules-bad.csv", rules)
        rc, _, err = self.run_main("check-rules", str(self.proj), str(csvp))
        self.assertEqual(rc, fid.EXIT_ENV)
        self.assertIn("unknown rule type", err)

    def test_missing_columns_exit_env(self):
        csvp = self.write("rules-cols.csv", "rule,target\na,b\n")
        rc, _, err = self.run_main("check-rules", str(self.proj), str(csvp))
        self.assertEqual(rc, fid.EXIT_ENV)
        self.assertIn("columns", err)

    def test_json_output(self):
        rules = "rule,net,params\nnet-exclusive,/VBAT,EPS1\n"
        csvp = self.write("rules-excl.csv", rules)
        rc, out, _ = self.run_main("check-rules", str(self.proj), str(csvp),
                                   "--json")
        self.assertEqual(rc, fid.EXIT_VIOLATIONS)
        doc = json.loads(out)
        self.assertEqual(doc["checked"], 1)
        self.assertEqual(doc["violations"][0]["detail"],
                         "J1.1 connected but only ['EPS1'] allowed")


class TestExamples(unittest.TestCase):
    """The shipped example CSVs must stay valid against the test fixture."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fiducial-examples-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        proj = self.tmp / "healthy.kicad_sch"
        shutil.copy(FIXTURES / "healthy.kicad_sch", proj)
        nl = fid._netlist_path(proj)
        nl.write_text(NETLIST_HEALTHY, encoding="utf-8")
        st = proj.stat()
        os.utime(nl, (st.st_mtime + 100,) * 2)
        self.proj = proj

    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = fid.main(list(argv))
        return rc, out.getvalue(), err.getvalue()

    def test_examples_intent_csv_all_ok(self):
        csvp = ROOT / "examples" / "intent.csv"
        rc, out, _ = self.run_main("check-intent", str(self.proj), str(csvp))
        self.assertEqual(rc, fid.EXIT_OK, out)
        self.assertIn("8/8 connections verified", out)

    def test_examples_rules_csv_pass(self):
        rules = ROOT / "examples" / "rules.csv"
        rc, out, _ = self.run_main("check-rules", str(self.proj), str(rules))
        self.assertEqual(rc, fid.EXIT_OK, out)


if __name__ == "__main__":
    unittest.main()
