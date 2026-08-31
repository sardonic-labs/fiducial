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
import sys
import shutil
import subprocess
import tempfile
import unittest
import importlib.util
from pathlib import Path

# SchematicBuilder lives alongside fiducial.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import schematic_builder as sb

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
        p.write_text(text, encoding="utf-8")
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

    def test_line_comment_stripped(self):
        root = fid.parse_sexp('(a b ; comment\n c)')
        self.assertEqual(root, ["a", "b", "c"])

    def test_block_comment_stripped(self):
        root = fid.parse_sexp('(a #|nested|# b)')
        self.assertEqual(root, ["a", "b"])

    def test_comment_inside_string_preserved(self):
        root = fid.parse_sexp('(a "has ; comment")')
        self.assertEqual(root[1], "has ; comment")

    def test_newline_escape_in_string(self):
        root = fid.parse_sexp(r'(a "line1\nline2")')
        self.assertEqual(root[1], "line1\nline2")

    def test_tab_escape_in_string(self):
        root = fid.parse_sexp(r'(a "col1\tcol2")')
        self.assertEqual(root[1], "col1\tcol2")

    def test_backslash_escape_in_string(self):
        root = fid.parse_sexp(r'(a "path\\to\\file")')
        self.assertEqual(root[1], "path\\to\\file")


class TestSexpJson(unittest.TestCase):
    def test_sexp_subcommand_outputs_json(self):
        import io, contextlib
        out, err = io.StringIO(), io.StringIO()
        fixture = Path(__file__).parent / "fixtures" / "healthy.kicad_sch"
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = fid.main(["sexp", str(fixture)])
        self.assertEqual(rc, 0)
        data = json.loads(out.getvalue())
        self.assertIsInstance(data, dict)
        self.assertEqual(data["_key"], "kicad_sch")

    def test_sexp_raw_mode(self):
        import io, contextlib
        out, err = io.StringIO(), io.StringIO()
        fixture = Path(__file__).parent / "fixtures" / "healthy.kicad_sch"
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = fid.main(["sexp", str(fixture), "--raw"])
        self.assertEqual(rc, 0)
        data = json.loads(out.getvalue())
        self.assertIsInstance(data, list)


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


class TestLintAllowSingleUse(OfflineTest):
    def test_single_use_label_warns_without_rules(self):
        proj = self.project("single-use-label.kicad_sch")
        self.cache_netlist(proj)
        rc, out, _ = self.run_main("lint", str(proj))
        self.assertEqual(rc, fid.EXIT_VIOLATIONS)
        self.assertIn("'TYPO' appears only once", out)

    def test_single_use_label_suppressed_with_rules(self):
        proj = self.project("single-use-label.kicad_sch")
        self.cache_netlist(proj)
        rules = self.write("rules-allow.csv",
                           "rule,net,params\nallow-single-use,TYPO,\n")
        rc, out, _ = self.run_main("lint", str(proj), "--rules", str(rules))
        self.assertNotIn("appears only once", out)

    def test_non_allowed_label_still_warns(self):
        """Two single-use labels; allowing one must still warn about the other."""
        text = (FIXTURES / "single-use-label.kicad_sch").read_text()
        text = text.rstrip().rstrip(")") + '\t(label "STILLWARN" (at 40 40 0))\n)'
        proj = self.tmp / "two-labels.kicad_sch"
        proj.write_text(text, encoding="utf-8")
        self.cache_netlist(proj)
        rules = self.write("rules-allow.csv",
                           "rule,net,params\nallow-single-use,TYPO,\n")
        rc, out, _ = self.run_main("lint", str(proj), "--rules", str(rules))
        single_use_lines = [l for l in out.splitlines()
                            if "appears only once" in l]
        self.assertEqual(len(single_use_lines), 1)
        self.assertIn("STILLWARN", single_use_lines[0])
        self.assertNotIn("TYPO", single_use_lines[0])

    def test_empty_rules_file_no_crash(self):
        proj = self.project("single-use-label.kicad_sch")
        self.cache_netlist(proj)
        rules = self.write("rules-empty.csv", "rule,net,params\n")
        rc, out, _ = self.run_main("lint", str(proj), "--rules", str(rules))
        self.assertIn("'TYPO' appears only once", out)


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

    def test_nc_pin_not_missing(self):
        proj = self.project()
        self.cache_netlist(proj)
        csvp = self.write("nc.csv",
                          "ref,pin,expected_net\nR1,1,/A\nR1,99,NC\n")
        rc, out, _ = self.run_main("check-intent", str(proj), str(csvp))
        self.assertEqual(rc, fid.EXIT_OK, out)
        self.assertIn("2/2 connections verified", out)
        self.assertNotIn("MISSING", out)

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
    """The shipped example CSVs must stay valid against the demo board.

    The demo board is a real RP2040 devboard schematic; its netlist export
    is committed as fixtures/demo-board-netlist.sexpr so this test stays
    offline while validating against real connectivity data.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fiducial-examples-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        proj = self.tmp / "demo-board.kicad_sch"
        shutil.copy(ROOT / "examples" / "demo-board.kicad_sch", proj)
        nl = fid._netlist_path(proj)
        shutil.copy(FIXTURES / "demo-board-netlist.sexpr", nl)
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
        self.assertIn("11/11 connections verified", out)

    def test_examples_rules_csv_pass(self):
        rules = ROOT / "examples" / "rules.csv"
        rc, out, _ = self.run_main("check-rules", str(self.proj), str(rules))
        self.assertEqual(rc, fid.EXIT_OK, out)


class TestOrphanClusters(unittest.TestCase):
    """The 2026-08-23 battery-entry failure: Q1+RG1 were an abandoned gate
    pull-down pair, fully connected to each other and to GND, so every
    existing check blessed them. Cluster detection must flag them."""

    def setUp(self):
        self.nets = {
            "GND": {("RG1", "1"): "GND", ("J1", "1"): "GND", ("R2", "2"): "GND"},
            "BT_GATE_N": {("Q1", "1"): "BT_GATE_N", ("RG1", "2"): "BT_GATE_N"},
            "VBAT": {("Q1", "3"): "VBAT"},
            "MAIN": {("J1", "2"): "MAIN", ("R2", "1"): "MAIN",
                     ("U1", "1"): "MAIN", ("U1", "2"): "MAIN",
                     ("U1", "3"): "MAIN", ("U1", "4"): "MAIN"},
        }

    def test_abandoned_pull_down_pair_flagged(self):
        clusters = fid._orphan_clusters(self.nets)
        self.assertEqual(clusters, [["Q1", "RG1"]])

    def test_anchored_cluster_not_flagged(self):
        nets = dict(self.nets)
        nets["BT_GATE_N"] = {("Q1", "1"): "BT_GATE_N", ("RG1", "2"): "BT_GATE_N",
                             ("J9", "5"): "BT_GATE_N"}
        self.assertEqual(fid._orphan_clusters(nets), [])

    def test_rail_only_attachment_does_not_anchor(self):
        # RG1 touches GND, but a rail is not an interface: the pair must
        # still be flagged.
        clusters = fid._orphan_clusters(self.nets)
        self.assertIn(["Q1", "RG1"], clusters)

    def test_lone_component_on_dangling_net_left_to_orphan_net_check(self):
        nets = {"GND": {("R9", "2"): "GND"}, "LONELY": {("R9", "1"): "LONELY"}}
        self.assertEqual(fid._orphan_clusters(nets), [])

    def test_tacked_on_ghost_with_live_tap_caught_by_suspect_check(self):
        # The real 2026-08-23 signature: Q1.2 taps the LIVE fuse node, so
        # island detection sees one connected graph and blesses it. The
        # suspect-component check must catch Q1 via its dangling pin and
        # point-to-point nets, while the legit chain (F1, Q-VBAT, Q2,
        # R-GS, R-PD, R-EN - parts with a >=3-connection net) stays clean.
        nets = {
            "GND": {("J-BT", "2"): "GND", ("Q2", "S"): "GND",
                    ("R-PD", "2"): "GND", ("RG1", "1"): "GND"},
            "BT_IN_P": {("J-BT", "1"): "BT_IN_P", ("F1", "2"): "BT_IN_P"},
            "VBAT_FUSED": {("F1", "1"): "VBAT_FUSED", ("F-VBAT", "1"): "VBAT_FUSED",
                           ("Q1", "2"): "VBAT_FUSED"},
            "VBAT_SW": {("F-VBAT", "2"): "VBAT_SW", ("Q-VBAT", "3"): "VBAT_SW",
                        ("R-GS", "2"): "VBAT_SW"},
            "VBAT_GATE": {("Q-VBAT", "1"): "VBAT_GATE", ("Q2", "D"): "VBAT_GATE",
                          ("R-GS", "1"): "VBAT_GATE"},
            "EN_VBAT_N": {("Q2", "G"): "EN_VBAT_N", ("R-EN", "2"): "EN_VBAT_N",
                          ("R-PD", "1"): "EN_VBAT_N"},
            "BT_GATE_N": {("Q1", "1"): "BT_GATE_N", ("RG1", "2"): "BT_GATE_N"},
            "VBAT": {("Q1", "3"): "VBAT"},
        }
        self.assertEqual(fid._suspect_components(nets), ["Q1"])


class TestLintGeometry(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fiducial-geom-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _run_lint(self, text):
        proj = self.tmp / "board.kicad_sch"
        proj.write_text(text, encoding="utf-8")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = fid.main(["lint", str(proj)])
        return rc, out.getvalue(), err.getvalue()

    def test_real_board_is_on_grid(self):
        rc, out, _ = self._run_lint((FIXTURES / "rp2040-devboard.kicad_sch").read_text())
        self.assertNotIn("off-grid", out)

    def test_off_grid_symbol_detected(self):
        text = (FIXTURES / "healthy.kicad_sch").read_text().replace(
            "(at 81.28 50.8 0)", "(at 81.3 50.8 0)")
        rc, out, _ = self._run_lint(text)
        self.assertEqual(rc, fid.EXIT_VIOLATIONS)
        self.assertIn("C1: symbol position off-grid (81.3, 50.8)", out)

    def test_off_grid_wire_detected(self):
        text = (FIXTURES / "healthy.kicad_sch").read_text()
        # inject an off-grid wire (31.0 mm is not a multiple of 1.27 mm)
        wire = "\n\t(wire (pts (xy 30.48 12.7) (xy 31.0 12.7)))\n"
        text = text.rstrip()[:-1] + wire + ")"
        rc, out, _ = self._run_lint(text)
        self.assertIn("wire endpoint off-grid (31.0, 12.7)", out)


class TestOverlapCheck(OfflineTest):
    def test_overlap_detected(self):
        proj = self.project("overlap-wires.kicad_sch")
        rc, out, _ = self.run_main("overlap-check", str(proj))
        self.assertEqual(rc, fid.EXIT_VIOLATIONS, out)
        self.assertIn("OVERLAP", out)
        self.assertIn("USB_DP", out)
        self.assertIn("QSPI_SCLK", out)

    def test_no_overlap_clean(self):
        proj = self.project("no-overlap.kicad_sch")
        rc, out, _ = self.run_main("overlap-check", str(proj))
        self.assertEqual(rc, fid.EXIT_OK, out)
        self.assertIn("clean", out)

    def test_same_net_no_overlap(self):
        """Two wires from the same net meeting at a point is valid."""
        proj = self.project("no-overlap.kicad_sch")
        rc, out, _ = self.run_main("overlap-check", str(proj))
        self.assertEqual(rc, fid.EXIT_OK, out)
        self.assertNotIn("OVERLAP", out)

    def test_json_output_overlap(self):
        proj = self.project("overlap-wires.kicad_sch")
        rc, out, _ = self.run_main("overlap-check", str(proj), "--json")
        self.assertEqual(rc, fid.EXIT_VIOLATIONS)
        doc = json.loads(out)
        self.assertEqual(doc["command"], "overlap-check")
        self.assertGreaterEqual(doc["overlap_count"], 1)
        self.assertTrue(any("USB_DP" in o["nets"] for o in doc["overlaps"]))

    def test_json_output_clean(self):
        proj = self.project("no-overlap.kicad_sch")
        rc, out, _ = self.run_main("overlap-check", str(proj), "--json")
        self.assertEqual(rc, fid.EXIT_OK)
        doc = json.loads(out)
        self.assertEqual(doc["overlap_count"], 0)

    def test_missing_file_exits_env(self):
        rc, _, err = self.run_main("overlap-check",
                                   str(self.tmp / "nope.kicad_sch"))
        self.assertEqual(rc, fid.EXIT_ENV)


class TestCheckGate(unittest.TestCase):
    def test_gate_passes_healthy_board_without_kicad(self):
        tmp = Path(tempfile.mkdtemp(prefix="fiducial-check-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        proj = tmp / "healthy.kicad_sch"
        shutil.copy(FIXTURES / "healthy.kicad_sch", proj)
        nl = fid._netlist_path(proj)
        nl.write_text(NETLIST_HEALTHY, encoding="utf-8")
        st = proj.stat()
        os.utime(nl, (st.st_mtime + 100,) * 2)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = fid.main(["check", str(proj), "--skip-erc"])
        self.assertEqual(rc, fid.EXIT_OK, out.getvalue())
        self.assertIn("== check: PASS ==", out.getvalue())

    def test_gate_reports_findings(self):
        tmp = Path(tempfile.mkdtemp(prefix="fiducial-check-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        proj = tmp / "duplicate-ref.kicad_sch"
        shutil.copy(FIXTURES / "duplicate-ref.kicad_sch", proj)
        nl = fid._netlist_path(proj)
        nl.write_text("(components)\n(nets)", encoding="utf-8")
        st = proj.stat()
        os.utime(nl, (st.st_mtime + 100,) * 2)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = fid.main(["check", str(proj), "--skip-erc"])
        self.assertEqual(rc, fid.EXIT_VIOLATIONS)
        self.assertIn("== check: FINDINGS ==", out.getvalue())


WIRED_NETLIST = """(export (version "E")
\t(components
\t\t(comp (ref "R1") (value "10k") (footprint "R_0603"))
\t)
\t(nets
\t\t(net (code "1") (name "NET_A")
\t\t\t(node (ref "R1") (pin "1")))
\t\t(net (code "2") (name "NET_B")
\t\t\t(node (ref "R1") (pin "2")))
\t)
)"""


class TestLabelMap(OfflineTest):
    def test_label_map_healthy_board(self):
        proj = self.project()
        rc, out, _ = self.run_main("label-map", str(proj))
        self.assertEqual(rc, fid.EXIT_OK, out)
        self.assertIn("/A", out)
        self.assertIn("/B", out)
        self.assertIn("/VCC", out)
        self.assertIn("/GND", out)

    def test_label_map_shows_coordinates(self):
        proj = self.project()
        rc, out, _ = self.run_main("label-map", str(proj))
        self.assertEqual(rc, fid.EXIT_OK, out)
        self.assertRegex(out, r"\(12\.70, 12\.70\)")

    def test_label_map_empty_schematic(self):
        proj = self.tmp / "empty.kicad_sch"
        proj.write_text('(kicad_sch (version 20250114) (generator "eeschema")'
                        ' (uuid "00000000-0000-0000-0000-000000000003")'
                        ' (paper "A4"))', encoding="utf-8")
        rc, out, _ = self.run_main("label-map", str(proj))
        self.assertEqual(rc, fid.EXIT_OK, out)
        self.assertEqual(out.strip(), "")

    def test_label_map_grouped_by_name(self):
        proj = self.project()
        rc, out, _ = self.run_main("label-map", str(proj))
        self.assertEqual(rc, fid.EXIT_OK, out)
        lines = out.strip().splitlines()
        # /A appears twice, then next group starts with /B
        a_line_idx = next(i for i, l in enumerate(lines) if l.strip() == "/A")
        # entries under /A are indented lines starting with (
        entries = []
        for l in lines[a_line_idx + 1:]:
            if l.startswith("  ("):
                entries.append(l)
            elif l.strip() and not l.startswith("  ("):
                break
        self.assertEqual(len(entries), 2)


class TestPinPositions(OfflineTest):
    def test_pin_positions_wired_fixture(self):
        proj = self.project("wired.kicad_sch")
        self.cache_netlist(proj, WIRED_NETLIST)
        rc, out, _ = self.run_main("pin-positions", str(proj), "R1")
        self.assertEqual(rc, fid.EXIT_OK, out)
        self.assertIn("Pin 1:", out)
        self.assertIn("Pin 2:", out)

    def test_pin_positions_shows_coordinates(self):
        proj = self.project("wired.kicad_sch")
        self.cache_netlist(proj, WIRED_NETLIST)
        rc, out, _ = self.run_main("pin-positions", str(proj), "R1")
        self.assertEqual(rc, fid.EXIT_OK, out)
        self.assertRegex(out, r"Pin 1: \(50\.80, 46\.99\)")
        self.assertRegex(out, r"Pin 2: \(50\.80, 54\.61\)")

    def test_pin_positions_shows_net(self):
        proj = self.project("wired.kicad_sch")
        self.cache_netlist(proj, WIRED_NETLIST)
        rc, out, _ = self.run_main("pin-positions", str(proj), "R1")
        self.assertEqual(rc, fid.EXIT_OK, out)
        self.assertIn("-> NET_A", out)
        self.assertIn("-> NET_B", out)

    def test_pin_positions_unknown_ref(self):
        proj = self.project("wired.kicad_sch")
        self.cache_netlist(proj, WIRED_NETLIST)
        rc, _, err = self.run_main("pin-positions", str(proj), "X99")
        self.assertEqual(rc, fid.EXIT_ENV)
        self.assertIn("X99", err)

    def test_pin_positions_demo_board(self):
        proj = self.project("rp2040-devboard.kicad_sch")
        nl = fid._netlist_path(proj)
        shutil.copy(FIXTURES / "demo-board-netlist.sexpr", nl)
        st = proj.stat()
        os.utime(nl, (st.st_mtime + 100,) * 2)
        rc, out, _ = self.run_main("pin-positions", str(proj), "U1")
        self.assertEqual(rc, fid.EXIT_OK, out)
        self.assertIn("Pin 1:", out)


class TestWireTrace(OfflineTest):
    def test_wire_trace_to_label(self):
        proj = self.project("wired.kicad_sch")
        self.cache_netlist(proj, WIRED_NETLIST)
        rc, out, _ = self.run_main("wire-trace", str(proj), "R1", "1")
        self.assertEqual(rc, fid.EXIT_OK, out)
        self.assertIn("R1.1", out)
        self.assertIn("NET_A", out)

    def test_wire_trace_pin2(self):
        proj = self.project("wired.kicad_sch")
        self.cache_netlist(proj, WIRED_NETLIST)
        rc, out, _ = self.run_main("wire-trace", str(proj), "R1", "2")
        self.assertEqual(rc, fid.EXIT_OK, out)
        self.assertIn("R1.2", out)
        self.assertIn("NET_B", out)

    def test_wire_trace_unknown_ref(self):
        proj = self.project("wired.kicad_sch")
        self.cache_netlist(proj, WIRED_NETLIST)
        rc, _, err = self.run_main("wire-trace", str(proj), "X99", "1")
        self.assertEqual(rc, fid.EXIT_ENV)
        self.assertIn("X99", err)

    def test_wire_trace_unknown_pin(self):
        proj = self.project("wired.kicad_sch")
        self.cache_netlist(proj, WIRED_NETLIST)
        rc, _, err = self.run_main("wire-trace", str(proj), "R1", "99")
        self.assertEqual(rc, fid.EXIT_ENV)
        self.assertIn("99", err)

    def test_wire_trace_no_wires_falls_back_to_netlist(self):
        proj = self.project("wired.kicad_sch")
        self.cache_netlist(proj, WIRED_NETLIST)
        # Remove wires from schematic so wire graph is empty
        text = proj.read_text(encoding="utf-8")
        import re
        text = re.sub(r'\t\(wire.*?\n\t\)\n', '', text, flags=re.DOTALL)
        proj.write_text(text, encoding="utf-8")
        rc, out, _ = self.run_main("wire-trace", str(proj), "R1", "1")
        self.assertEqual(rc, fid.EXIT_OK, out)
        self.assertIn("R1.1", out)
        self.assertIn("NET_A", out)


class TestDrcRenderOffline(OfflineTest):
    """P0 regression: drc/render must match schematic-side coverage.

    Covers: exit codes, --json, --save-board, --parity, missing file,
    malformed board, outdir creation, and temp-report cleanup (same
    unique-temp logic as erc)."""

    def setUp(self):
        super().setUp()
        self.calls = []
        self._orig = fid.kicad_cli
        self.addCleanup(setattr, fid, "kicad_cli", self._orig)

    def test_drc_clean_offline(self):
        self.calls.clear()
        fid.kicad_cli = fake_kicad_cli(self.calls, {"drc": []})
        rc, out, _ = self.run_main("drc", str(FIXTURES / "healthy.kicad_pcb"))
        self.assertEqual(rc, fid.EXIT_OK)
        self.assertIn("0 errors", out)
        self.assertIn("DRC on", out)

    def test_drc_violations_are_findings(self):
        payload = {"drc": [
            {"severity": "severity_error", "type": "clearance",
             "description": "clearance violation", "pos": "10,10", "items": []},
            {"severity": "severity_warning", "type": "annular",
             "description": "thin ring", "pos": "20,20", "items": []},
        ]}
        fid.kicad_cli = fake_kicad_cli(self.calls, payload)
        rc, out, _ = self.run_main("drc", str(FIXTURES / "healthy.kicad_pcb"))
        self.assertEqual(rc, fid.EXIT_VIOLATIONS)
        self.assertIn("1 errors", out)
        self.assertIn("1 warnings", out)

    def test_drc_json_counts(self):
        payload = {"drc": [
            {"severity": "severity_error", "type": "err", "description": "e", "pos": "0,0", "items": []},
        ]}
        fid.kicad_cli = fake_kicad_cli(self.calls, payload)
        rc, out, _ = self.run_main("drc", str(FIXTURES / "healthy.kicad_pcb"), "--json")
        self.assertEqual(rc, fid.EXIT_VIOLATIONS)
        doc = json.loads(out)
        self.assertEqual(doc["tool"], "DRC")
        self.assertEqual(doc["error_count"], 1)
        self.assertEqual(doc["warning_count"], 0)

    def test_drc_human_output_shape(self):
        fid.kicad_cli = fake_kicad_cli(self.calls, {"drc": []})
        rc, out, _ = self.run_main("drc", str(FIXTURES / "healthy.kicad_pcb"))
        self.assertIn("DRC on", out)
        self.assertIn("0 errors, 0 warnings", out)

    def test_drc_missing_file_env(self):
        # payload None simulates kicad_cli ran but produced no report -> env
        fid.kicad_cli = fake_kicad_cli(self.calls, payload=None)
        rc, _, err = self.run_main("drc", str(FIXTURES / "healthy.kicad_pcb"))
        self.assertEqual(rc, fid.EXIT_ENV)
        self.assertIn("no DRC report", err)

    def test_drc_parity_and_save_board_flags(self):
        fid.kicad_cli = fake_kicad_cli(self.calls, {"drc": []})
        self.run_main("drc", str(FIXTURES / "healthy.kicad_pcb"), "--parity")
        self.assertIn("--schematic-parity", self.calls[-1])
        self.calls.clear()
        self.run_main("drc", str(FIXTURES / "healthy.kicad_pcb"), "--save-board")
        self.assertIn("--save-board", self.calls[-1])
        self.assertIn("--refill-zones", self.calls[-1])
        self.calls.clear()
        self.run_main("drc", str(FIXTURES / "healthy.kicad_pcb"))
        self.assertNotIn("--save-board", self.calls[-1])

    def test_render_pcb_mock_creates_svg(self):
        outdir = self.tmp / "render_out"
        def fake_render(args, timeout=180):
            self.calls.append(list(args))
            # mimic kicad_cli pcb export svg: find --output predecessor
            if "-o" in args:
                idx = args.index("-o")
                target = Path(args[idx+1])
                target.parent.mkdir(parents=True, exist_ok=True)
                # sch export creates dir, pcb export creates file
                if "pcb" in args:
                    target.write_text("<svg></svg>")
                else:
                    Path(target).mkdir(parents=True, exist_ok=True)
                    (Path(target) / "board.svg").write_text("<svg></svg>")
            return subprocess.CompletedProcess(args, returncode=0, stdout="", stderr="")
        fid.kicad_cli = fake_render
        rc, out, _ = self.run_main("render", str(FIXTURES / "healthy.kicad_pcb"), "--outdir", str(outdir))
        self.assertEqual(rc, fid.EXIT_OK)
        self.assertIn("rendered", out)
        self.assertTrue((outdir / "healthy.svg").exists() or outdir.exists())

    def test_render_sch_mock(self):
        outdir = self.tmp / "render_sch"
        def fake_render(args, timeout=180):
            self.calls.append(list(args))
            if "-o" in args:
                idx = args.index("-o")
                target = Path(args[idx+1])
                target.mkdir(parents=True, exist_ok=True)
            return subprocess.CompletedProcess(args, returncode=0, stdout="", stderr="")
        fid.kicad_cli = fake_render
        rc, out, _ = self.run_main("render", str(FIXTURES / "healthy.kicad_sch"), "--outdir", str(outdir))
        self.assertEqual(rc, fid.EXIT_OK)
        self.assertIn("rendered", out)

    def test_render_missing_file_env(self):
        fid.kicad_cli = fake_kicad_cli(self.calls, {"drc": []})
        # render of nonexistent file should still attempt kicad_cli but fail gracefully
        def fail_render(args, timeout=180):
            return subprocess.CompletedProcess(args, returncode=1, stdout="", stderr="file not found")
        fid.kicad_cli = fail_render
        rc, _, err = self.run_main("render", str(self.tmp / "nope.kicad_pcb"), "--outdir", str(self.tmp / "out"))
        self.assertEqual(rc, fid.EXIT_ENV)


class TestPcbFixtures(OfflineTest):
    """Offline parsing of minimal PCB fixtures - proves pcb_check handles them."""

    def test_healthy_pcb_parseable_and_closed(self):
        import pcb_check as pcb
        root = pcb._load_board(FIXTURES / "healthy.kicad_pcb")
        self.assertEqual(root[0], "kicad_pcb")
        # board-outline via fiducial's pcb_check helper
        rc, out, _ = self.run_main("sexp", str(FIXTURES / "healthy.kicad_pcb"))
        self.assertEqual(rc, fid.EXIT_OK)
        # via pcb_check module directly
        out_s, err_s = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out_s), contextlib.redirect_stderr(err_s):
            rc2 = pcb.main(["board-outline", str(FIXTURES / "healthy.kicad_pcb")])
        self.assertEqual(rc2, fid.EXIT_OK)
        self.assertIn("closed", out_s.getvalue())

    def test_open_outline_not_closed(self):
        import pcb_check as pcb
        out_s, err_s = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out_s), contextlib.redirect_stderr(err_s):
            rc = pcb.main(["board-outline", str(FIXTURES / "open-outline.kicad_pcb"), "--json"])
        self.assertEqual(rc, fid.EXIT_VIOLATIONS)
        doc = json.loads(out_s.getvalue())
        self.assertFalse(doc["closed"])
        self.assertEqual(doc["segment_count"], 3)


class TestSchematicBuilder(unittest.TestCase):
    """Tests for the schematic_builder.py module."""

    def test_build_empty_schematic(self):
        content = sb.build_schematic("Empty Board")
        self.assertIn('(version 20260306)', content)
        self.assertIn('(title "Empty Board")', content)
        self.assertIn('(generator "fiducial_schematic_builder")', content)

    def test_add_symbol(self):
        sch = sb.SchematicBuilder("Test")
        sch.add_symbol("Device:R", "R1", x=101.6, y=76.2, value="10k")
        content = sch.build()
        self.assertIn('(lib_id "Device:R")', content)
        self.assertIn('(reference "R1")', content)
        self.assertIn('(at 101.6 76.2 0)', content)
        self.assertIn('(property "Value" "10k"', content)

    def test_add_wire(self):
        sch = sb.SchematicBuilder("Test")
        sch.add_wire(101.6, 76.2, 114.3, 76.2)
        content = sch.build()
        self.assertIn('(wire', content)
        self.assertIn('(xy 101.6 76.2)', content)
        self.assertIn('(xy 114.3 76.2)', content)

    def test_add_label(self):
        sch = sb.SchematicBuilder("Test")
        sch.add_label("SIG_IN", 101.6, 76.2, rotation=180)
        content = sch.build()
        self.assertIn('(label "SIG_IN"', content)
        self.assertIn('(at 101.6 76.2 180)', content)

    def test_add_global_label(self):
        sch = sb.SchematicBuilder("Test")
        sch.add_global_label("CLK", 50.0, 50.0)
        content = sch.build()
        self.assertIn('(global_label "CLK"', content)

    def test_add_power(self):
        sch = sb.SchematicBuilder("Test")
        sch.add_power("power:GND", 101.6, 88.9)
        content = sch.build()
        self.assertIn('(lib_id "power:GND")', content)
        self.assertIn('#PWR001', content)
        self.assertIn('(property "Value" "GND"', content)

    def test_add_no_connect(self):
        sch = sb.SchematicBuilder("Test")
        sch.add_no_connect(127.0, 99.06)
        content = sch.build()
        self.assertIn('(no_connect', content)
        self.assertIn('127', content)
        self.assertIn('99.06', content)

    def test_power_counter_increments(self):
        sch = sb.SchematicBuilder("Test")
        sch.add_power("power:GND", 100, 100)
        sch.add_power("power:GND", 110, 100)
        sch.add_power("power:+3V3", 100, 90)
        content = sch.build()
        self.assertIn('#PWR001', content)
        self.assertIn('#PWR002', content)
        self.assertIn('#PWR003', content)

    def test_all_uuids_unique(self):
        sch = sb.SchematicBuilder("Test")
        sch.add_symbol("Device:R", "R1", 100, 100)
        sch.add_wire(100, 100, 120, 100)
        sch.add_label("A", 100, 100)
        sch.add_no_connect(130, 100)
        content = sch.build()
        import re
        uuids = re.findall(r'\(uuid "([^"]+)"\)', content)
        self.assertEqual(len(uuids), len(set(uuids)), "duplicate UUIDs found")

    def test_build_round_trip_parseable(self):
        sch = sb.SchematicBuilder("Parseable")
        sch.add_symbol("Device:R", "R1", 101.6, 76.2)
        sch.add_wire(101.6, 76.2, 114.3, 76.2)
        sch.add_label("NET_A", 101.6, 76.2)
        sch.add_power("power:GND", 101.6, 88.9)
        sch.add_no_connect(127.0, 99.06)
        content = sch.build()
        # Should parse without errors
        tree = fid.parse_sexp(content)
        self.assertEqual(tree[0], "kicad_sch")

    def test_convenience_function(self):
        content = sb.build_schematic(
            "Quick Board",
            symbols=[("Device:R", "R1", 100, 100)],
            wires=[(100, 100, 120, 100)],
            labels=[("SIG", 100, 100)],
            power=[("power:GND", 100, 112)],
            no_connects=[(130, 100)],
        )
        self.assertIn('(title "Quick Board")', content)
        self.assertIn('(lib_id "Device:R")', content)
        self.assertIn('(label "SIG"', content)

    def test_format_float_strips_trailing_zeros(self):
        self.assertEqual(sb._fmt(101.6000), "101.6")
        self.assertEqual(sb._fmt(100.0), "100")
        self.assertEqual(sb._fmt(0.0), "0")
        self.assertEqual(sb._fmt(180), "180")
        self.assertEqual(sb._fmt(99.06), "99.06")


if __name__ == "__main__":
    unittest.main()
