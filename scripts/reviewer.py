#!/usr/bin/env python3
"""reviewer.py - design review orchestrator for AI agent workflows.

Runs a structured review of a schematic or PCB design, producing
severity-rated findings (error/warning/info) with interactive prompts
for ambiguous cases.

Usage:
    python scripts/reviewer.py <skill> <project_file> [--json] [--intent intent.csv]

Skills:
    schematic-correctness   Intent matching, connectivity, pin assignments
    schematic-completeness  Missing parts, unconnected pins, decoupling
    schematic-style         House style, naming, labeling
    power-tree              Voltage margins, current paths, protection
    pcb-layout              Placement, board outline, clearances
    pcb-routing             Trace widths, via sizing, signal integrity
    dfm                     Manufacturing constraints, copper balance
    bom                     Part availability, ratings, alternatives
    connectivity            Cross-block connectivity, connector pinouts
    documentation           Title block, annotations, revision history

Exit codes: 0 = pass (no errors), 1 = errors found, 2 = environment error.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fiducial import EXIT_OK, EXIT_VIOLATIONS, EXIT_ENV


class Finding:
    def __init__(self, severity, check, detail, interactive_prompt=None):
        self.severity = severity  # "error", "warning", "info"
        self.check = check
        self.detail = detail
        self.interactive_prompt = interactive_prompt

    def to_dict(self):
        d = {"severity": self.severity, "check": self.check, "detail": self.detail}
        if self.interactive_prompt:
            d["interactive_prompt"] = self.interactive_prompt
        return d


def _run_script(script_name, args_list):
    """Run a check script and return its output and exit code."""
    script_path = Path(__file__).parent / script_name
    cmd = [sys.executable, str(script_path)] + args_list + ["--json"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                              encoding="utf-8", errors="replace")
        if proc.returncode == 2:
            return None, proc.returncode, proc.stderr
        return proc.stdout, proc.returncode, proc.stderr
    except subprocess.TimeoutExpired:
        return None, 2, f"timeout running {script_name}"


def _parse_json_output(output):
    """Parse JSON output from a check script."""
    if not output:
        return {}
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return {}


# ====================================================================
# Review skill implementations
# ====================================================================

def review_schematic_correctness(project, intent_csv=None):
    """Intent matching, connectivity, pin assignments."""
    findings = []

    # Check intent if provided
    if intent_csv:
        out, rc, err = _run_script("fiducial.py",
                                    ["check-intent", project, intent_csv, "--orphans"])
        data = _parse_json_output(out)
        for result in data.get("results", []):
            if result["status"] == "MISSING":
                findings.append(Finding("error", "intent-check",
                    f"Pin {result['ref']}.{result['pin']}: expected net '{result['expected']}' not found"))
            elif result["status"] == "WRONG":
                findings.append(Finding("error", "intent-check",
                    f"Pin {result['ref']}.{result['pin']}: on net '{result['actual']}' "
                    f"but expected '{result['expected']}'"))
        for orphan in data.get("orphans", []):
            findings.append(Finding("warning", "orphan-net",
                f"Net '{orphan['net']}' has only one connection ({orphan['ref']}.{orphan['pin']})"))
    else:
        findings.append(Finding("info", "intent-check",
            "No intent.csv provided - skipping intent verification",
            interactive_prompt="Provide intent.csv for full connectivity verification? (y/n)"))

    # Power pin audit
    out, rc, err = _run_script("schematic_check.py", ["power-pins", project])
    data = _parse_json_output(out)
    if data.get("count", 0) == 0:
        findings.append(Finding("warning", "power-pins",
            "No power pins found in schematic symbols - verify power connections exist"))

    # Unconnected pins
    out, rc, err = _run_script("schematic_check.py", ["unconnected", project])
    data = _parse_json_output(out)
    for pin in data.get("pins", []):
        findings.append(Finding("error", "unconnected-pin",
            f"Pin {pin['ref']}.{pin['pin']} is unconnected"))

    # Orphan nets
    out, rc, err = _run_script("schematic_check.py", ["orphan-nets", project])
    data = _parse_json_output(out)
    for orphan in data.get("orphans", []):
        findings.append(Finding("warning", "orphan-net",
            f"Net '{orphan['net']}' has only one connection ({orphan['ref']}.{orphan['pin']})"))

    return findings


def review_schematic_completeness(project):
    """Missing parts, unconnected pins, decoupling."""
    findings = []

    # Unconnected pins
    out, rc, err = _run_script("schematic_check.py", ["unconnected", project])
    data = _parse_json_output(out)
    pins = data.get("pins", [])
    if pins:
        findings.append(Finding("error", "unconnected-pins",
            f"{len(pins)} unconnected pin(s) found"))
        for pin in pins[:10]:
            findings.append(Finding("error", "unconnected-pin",
                f"Pin {pin['ref']}.{pin['pin']} is unconnected"))
        if len(pins) > 10:
            findings.append(Finding("error", "unconnected-pin-more",
                f"... and {len(pins) - 10} more unconnected pins"))

    # Orphan nets
    out, rc, err = _run_script("schematic_check.py", ["orphan-nets", project])
    data = _parse_json_output(out)
    orphans = data.get("orphans", [])
    if orphans:
        findings.append(Finding("warning", "orphan-nets",
            f"{len(orphans)} orphan net(s) with single connection"))

    # Decoupling check
    out, rc, err = _run_script("schematic_check.py", ["decoupling-check", project])
    data = _parse_json_output(out)
    for f in data.get("findings", []):
        severity = "warning" if f["type"] == "missing_decoupling" else "info"
        findings.append(Finding(severity, "decoupling", f["detail"]))

    # Debris scan
    out, rc, err = _run_script("schematic_check.py", ["debris-scan", project])
    data = _parse_json_output(out)
    for f in data.get("findings", []):
        severity = "error" if f["type"] == "suspect_component" else "warning"
        findings.append(Finding(severity, "debris", f["detail"]))

    return findings


def review_schematic_style(project):
    """House style, naming, labeling."""
    findings = []

    # Grid check
    out, rc, err = _run_script("schematic_check.py", ["grid-check", project])
    data = _parse_json_output(out)
    count = data.get("count", 0)
    if count:
        findings.append(Finding("warning", "grid-check",
            f"{count} off-grid item(s) found"))
        for p in data.get("problems", [])[:5]:
            findings.append(Finding("warning", "off-grid", p))
        if count > 5:
            findings.append(Finding("warning", "off-grid-more",
                f"... and {count - 5} more off-grid items"))

    # Refdes audit
    out, rc, err = _run_script("schematic_check.py", ["refdes-audit", project])
    data = _parse_json_output(out)
    for issue in data.get("issues", []):
        severity = "error" if issue["type"] == "duplicate" else "warning"
        findings.append(Finding(severity, "refdes", f"[{issue['type']}] {issue['detail']}"))

    # Label audit
    out, rc, err = _run_script("schematic_check.py", ["label-audit", project])
    data = _parse_json_output(out)
    for issue in data.get("issues", []):
        findings.append(Finding("warning", "label", f"[{issue['type']}] {issue['detail']}"))
    for issue in data.get("naming_issues", []):
        findings.append(Finding("info", "label-naming", issue))

    # Debris scan
    out, rc, err = _run_script("schematic_check.py", ["debris-scan", project])
    data = _parse_json_output(out)
    for f in data.get("findings", []):
        if f["type"] == "placeholder":
            findings.append(Finding("warning", "debris", f["detail"]))

    return findings


def review_power_tree(project):
    """Voltage margins, current paths, protection."""
    findings = []

    # Rail audit
    out, rc, err = _run_script("schematic_check.py", ["rail-audit", project])
    data = _parse_json_output(out)
    rail_count = data.get("rail_count", 0)
    if rail_count == 0:
        findings.append(Finding("warning", "power-rails",
            "No power rails detected - verify power distribution exists"))
    else:
        findings.append(Finding("info", "power-rails",
            f"{rail_count} power rail(s) detected"))

    # Power pins
    out, rc, err = _run_script("schematic_check.py", ["power-pins", project])
    data = _parse_json_output(out)
    count = data.get("count", 0)
    if count == 0:
        findings.append(Finding("warning", "power-pins",
            "No power pins found in schematic symbols"))

    # Decoupling
    out, rc, err = _run_script("schematic_check.py", ["decoupling-check", project])
    data = _parse_json_output(out)
    for f in data.get("findings", []):
        findings.append(Finding("warning", "decoupling", f["detail"]))

    # BOM ratings check (for voltage ratings)
    out, rc, err = _run_script("bom_check.py", ["ratings", project])
    data = _parse_json_output(out)
    for f in data.get("findings", []):
        findings.append(Finding(f["severity"], "component-rating", f["detail"]))

    return findings


def review_pcb_layout(project):
    """Placement, board outline, clearances."""
    findings = []

    # Board stats
    out, rc, err = _run_script("pcb_check.py", ["board-stats", project])
    data = _parse_json_output(out)
    if data:
        findings.append(Finding("info", "board-stats",
            f"Board: {data.get('footprint_count', 0)} footprints, "
            f"{data.get('layer_count', 0)} layers, "
            f"{data.get('net_count', 0)} nets"))

    # Board outline
    out, rc, err = _run_script("pcb_check.py", ["board-outline", project])
    data = _parse_json_output(out)
    if not data.get("closed", True):
        findings.append(Finding("error", "board-outline",
            "Board outline is not closed - manufacturing will fail"))

    # Placement density
    out, rc, err = _run_script("pcb_check.py", ["placement-density", project])
    data = _parse_json_output(out)
    for f in data.get("findings", []):
        findings.append(Finding("warning", "placement", f["detail"]))

    return findings


def review_pcb_routing(project):
    """Trace widths, via sizing, signal integrity."""
    findings = []

    # Trace widths
    out, rc, err = _run_script("pcb_check.py", ["trace-widths", project])
    data = _parse_json_output(out)
    for f in data.get("findings", []):
        findings.append(Finding("error", "trace-width",
            f"Net '{f['net']}': {f['width']}mm on {f['layer']} (min {f['minimum']}mm)"))

    # Via audit
    out, rc, err = _run_script("pcb_check.py", ["via-audit", project])
    data = _parse_json_output(out)
    for f in data.get("findings", []):
        severity = "error" if f["type"] == "thin_annular_ring" else "warning"
        findings.append(Finding(severity, "via", f["detail"]))

    return findings


def review_dfm(project):
    """Manufacturing constraints, copper balance."""
    findings = []

    # Drill table
    out, rc, err = _run_script("pcb_check.py", ["drill-table", project])
    data = _parse_json_output(out)
    for f in data.get("findings", []):
        severity = "error" if f["type"] == "below_minimum" else "warning"
        findings.append(Finding(severity, "drill", f["detail"]))

    # Trace widths (DFM relevant)
    out, rc, err = _run_script("pcb_check.py", ["trace-widths", project])
    data = _parse_json_output(out)
    for f in data.get("findings", []):
        findings.append(Finding("warning", "trace-dfm",
            f"Net '{f['net']}': {f['width']}mm may be too narrow for reliable manufacturing"))

    # Via audit (DFM relevant)
    out, rc, err = _run_script("pcb_check.py", ["via-audit", project])
    data = _parse_json_output(out)
    for f in data.get("findings", []):
        findings.append(Finding("warning", "via-dfm", f["detail"]))

    return findings


def review_bom(project):
    """Part availability, ratings, alternatives."""
    findings = []

    # Parse BOM
    out, rc, err = _run_script("bom_check.py", ["parse", project])
    data = _parse_json_output(out)
    if data.get("total_lines", 0) == 0:
        findings.append(Finding("warning", "bom-empty",
            "BOM is empty or could not be generated"))
        return findings

    # Ratings check
    out, rc, err = _run_script("bom_check.py", ["ratings", project])
    data = _parse_json_output(out)
    for f in data.get("findings", []):
        findings.append(Finding(f["severity"], "component-rating", f["detail"]))

    # Lifecycle check
    out, rc, err = _run_script("bom_check.py", ["lifecycle", project])
    data = _parse_json_output(out)
    for f in data.get("findings", []):
        findings.append(Finding(f["severity"], "lifecycle", f["detail"]))

    # Alternates
    out, rc, err = _run_script("bom_check.py", ["alternates", project])
    data = _parse_json_output(out)
    for s in data.get("suggestions", []):
        findings.append(Finding("info", "alternates",
            f"{s['ref']} ({s['value']}): {s['note']}"))

    return findings


def review_connectivity(project):
    """Cross-block connectivity, connector pinouts."""
    findings = []

    # Run lint for connectivity issues
    out, rc, err = _run_script("fiducial.py", ["lint", project])
    data = _parse_json_output(out)
    for problem in data.get("problems", []):
        if "dangling" in problem.lower() or "orphan" in problem.lower():
            findings.append(Finding("warning", "connectivity-lint", problem))
        elif "single-use" in problem.lower() or "typo" in problem.lower():
            findings.append(Finding("warning", "label-lint", problem))
        elif "isolated" in problem.lower():
            findings.append(Finding("error", "isolated-cluster", problem))
        elif "suspect" in problem.lower():
            findings.append(Finding("warning", "suspect-component", problem))

    # Label audit
    out, rc, err = _run_script("schematic_check.py", ["label-audit", project])
    data = _parse_json_output(out)
    for issue in data.get("issues", []):
        findings.append(Finding("warning", "label-issue", f"[{issue['type']}] {issue['detail']}"))

    # Orphan nets
    out, rc, err = _run_script("schematic_check.py", ["orphan-nets", project])
    data = _parse_json_output(out)
    for orphan in data.get("orphans", []):
        findings.append(Finding("warning", "orphan-net",
            f"Net '{orphan['net']}' connects only {orphan['ref']}.{orphan['pin']}"))

    return findings


def review_documentation(project):
    """Title block, annotations, revision history."""
    findings = []

    # Check for placeholder text
    out, rc, err = _run_script("schematic_check.py", ["debris-scan", project])
    data = _parse_json_output(out)
    for f in data.get("findings", []):
        if f["type"] == "placeholder":
            findings.append(Finding("warning", "placeholder-text", f["detail"]))

    # Check label naming (auto-generated names are poor documentation)
    out, rc, err = _run_script("schematic_check.py", ["label-audit", project])
    data = _parse_json_output(out)
    for issue in data.get("naming_issues", []):
        findings.append(Finding("info", "label-naming", issue))

    # Refdes consistency (good documentation requires consistent naming)
    out, rc, err = _run_script("schematic_check.py", ["refdes-audit", project])
    data = _parse_json_output(out)
    for issue in data.get("issues", []):
        if issue["type"] == "mixed_case":
            findings.append(Finding("warning", "refdes-consistency", issue["detail"]))

    return findings


# ====================================================================
# Skill registry
# ====================================================================

SKILLS = {
    "schematic-correctness": review_schematic_correctness,
    "schematic-completeness": review_schematic_completeness,
    "schematic-style": review_schematic_style,
    "power-tree": review_power_tree,
    "pcb-layout": review_pcb_layout,
    "pcb-routing": review_pcb_routing,
    "dfm": review_dfm,
    "bom": review_bom,
    "connectivity": review_connectivity,
    "documentation": review_documentation,
}


def _format_report(skill_name, project, findings, as_json=False):
    """Format findings into a report."""
    errors = [f for f in findings if f.severity == "error"]
    warnings = [f for f in findings if f.severity == "warning"]
    infos = [f for f in findings if f.severity == "info"]
    interactive = [f for f in findings if f.interactive_prompt]

    verdict = "PASS" if not errors else "FAIL"

    if as_json:
        return json.dumps({
            "skill": skill_name,
            "target": project,
            "verdict": verdict,
            "error_count": len(errors),
            "warning_count": len(warnings),
            "info_count": len(infos),
            "errors": [f.to_dict() for f in errors],
            "warnings": [f.to_dict() for f in warnings],
            "infos": [f.to_dict() for f in infos],
            "interactive_prompts": [f.interactive_prompt for f in interactive],
        }, indent=2)

    lines = []
    lines.append(f"=" * 60)
    lines.append(f"REVIEW: {skill_name}")
    lines.append(f"TARGET: {project}")
    lines.append(f"=" * 60)

    if errors:
        lines.append(f"\nERRORS ({len(errors)}):")
        for f in errors:
            lines.append(f"  [{f.check}] {f.detail}")

    if warnings:
        lines.append(f"\nWARNINGS ({len(warnings)}):")
        for f in warnings:
            lines.append(f"  [{f.check}] {f.detail}")

    if infos:
        lines.append(f"\nINFO ({len(infos)}):")
        for f in infos:
            lines.append(f"  [{f.check}] {f.detail}")

    if interactive:
        lines.append(f"\nINTERACTIVE PROMPTS:")
        for f in interactive:
            lines.append(f"  {f.interactive_prompt}")

    lines.append(f"\n{'=' * 60}")
    lines.append(f"VERDICT: {verdict}")
    lines.append(f"  Errors:   {len(errors)}")
    lines.append(f"  Warnings: {len(warnings)}")
    lines.append(f"  Info:     {len(infos)}")
    lines.append(f"{'=' * 60}")

    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="reviewer",
                                 description=__doc__)
    ap.add_argument("skill", choices=sorted(SKILLS.keys()),
                    help="review skill to run")
    ap.add_argument("project", help="path to .kicad_sch or .kicad_pcb")
    ap.add_argument("--json", action="store_true",
                    help="machine-readable JSON output")
    ap.add_argument("--intent", help="path to intent.csv for connectivity checks")

    args = ap.parse_args(argv)

    # Validate project file exists
    project_path = Path(args.project)
    if not project_path.exists():
        print(f"ERROR: project file not found: {args.project}", file=sys.stderr)
        return EXIT_ENV

    # Run the review skill
    skill_fn = SKILLS[args.skill]
    try:
        if args.skill == "schematic-correctness":
            findings = skill_fn(args.project, intent_csv=args.intent)
        else:
            findings = skill_fn(args.project)
    except Exception as e:
        print(f"ERROR: review failed: {e}", file=sys.stderr)
        return EXIT_ENV

    # Format and output report
    report = _format_report(args.skill, args.project, findings, as_json=args.json)
    print(report)

    # Exit code: errors = FAIL, otherwise PASS
    has_errors = any(f.severity == "error" for f in findings)
    return EXIT_VIOLATIONS if has_errors else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
