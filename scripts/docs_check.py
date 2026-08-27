#!/usr/bin/env python3
"""docs_check.py — docs ↔ code coverage for humans + agents (stdlib-only).

Checks:
  * every CLI command in fiducial.py:1252 appears in docs/reference/cli.md
  * every skill file is listed in skills/index.md
  * every docs/reference file has a ```json machine block
  * examples/builder_demo.py is referenced from docs/tutorial.md
  * SchematcBuilder methods match docs/reference/api-builder.md

Exit: 0 clean, 1 violations (like fiducial contract), 2 env.

Usage:
  python scripts/docs_check.py
  python scripts/docs_check.py --json
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIDUCIAL = ROOT / "scripts" / "fiducial.py"
BUILDER = ROOT / "scripts" / "schematic_builder.py"
CLI_REF = ROOT / "docs" / "reference" / "cli.md"
SKILLS_IDX = ROOT / "skills" / "index.md"
API_REF = ROOT / "docs" / "reference" / "api-builder.md"
TUTORIAL = ROOT / "docs" / "tutorial.md"

EXIT_OK = 0
EXIT_VIOLATIONS = 1
EXIT_ENV = 2

def get_cli_commands():
    text = FIDUCIAL.read_text(encoding="utf-8")
    # parse add_parser lines: sub.add_parser("erc"
    cmds = re.findall(r'\.add_parser\("([^"]+)"', text)
    # also from usage line
    return sorted(set(cmds))

def check_cli_ref(cmds):
    if not CLI_REF.exists():
        return [f"missing {CLI_REF.relative_to(ROOT)}"]
    txt = CLI_REF.read_text(encoding="utf-8")
    missing = [c for c in cmds if c not in txt]
    if missing:
        return [f"cli.md missing commands: {missing} (source fiducial.py:1252)"]
    return []

def get_skills():
    return sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "skills").rglob("*.md") if p.name != "index.md")

def check_skills_index(skills):
    if not SKILLS_IDX.exists():
        return [f"missing {SKILLS_IDX.relative_to(ROOT)}"]
    txt = SKILLS_IDX.read_text(encoding="utf-8")
    missing = [s for s in skills if Path(s).name not in txt and s not in txt]
    if missing:
        return [f"skills/index.md missing {len(missing)} skills e.g. {missing[:2]}"]
    return []

def check_machine_blocks():
    probs = []
    for ref in (ROOT / "docs" / "reference").rglob("*.md"):
        txt = ref.read_text(encoding="utf-8")
        if "```json" not in txt:
            probs.append(f"{ref.relative_to(ROOT)} missing ```json machine block (agent parseable)")
    return probs

def check_tutorial_example():
    if not TUTORIAL.exists():
        return [f"missing {TUTORIAL.relative_to(ROOT)}"]
    txt = TUTORIAL.read_text(encoding="utf-8")
    if "examples/builder_demo.py" not in txt:
        return ["tutorial.md should reference examples/builder_demo.py:1"]
    return []

def get_builder_methods():
    if not BUILDER.exists():
        return []
    txt = BUILDER.read_text(encoding="utf-8")
    # find def add_*, def build, def save, def connect, etc. in class SchematicBuilder
    methods = re.findall(r'\n\s*def (add_\w+|build|save|connect|tie|wire|label|write_intent|load)\b', txt)
    return sorted(set(methods))

def check_api_ref(methods):
    if not API_REF.exists():
        return [f"missing {API_REF.relative_to(ROOT)}"]
    txt = API_REF.read_text(encoding="utf-8")
    missing = [m for m in methods if m not in txt]
    if missing:
        return [f"api-builder.md missing methods: {missing} (source schematic_builder.py:144)"]
    return []

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="machine output")
    args = ap.parse_args(argv)
    problems = []
    try:
        cmds = get_cli_commands()
        problems += check_cli_ref(cmds)
        skills = get_skills()
        problems += check_skills_index(skills)
        problems += check_machine_blocks()
        problems += check_tutorial_example()
        methods = get_builder_methods()
        problems += check_api_ref(methods)
    except FileNotFoundError as e:
        print(f"ENV: {e}", file=sys.stderr)
        return EXIT_ENV
    if args.json:
        cmds = get_cli_commands()
        print(json.dumps({
            "command": "docs_check",
            "target": str(ROOT),
            "cli_commands": cmds,
            "skills_count": len(get_skills()),
            "builder_methods": get_builder_methods(),
            "problems": problems,
            "ok": not problems,
        }, indent=2))
    else:
        if problems:
            for p in problems:
                print(f"DOCS_CHECK: {p}")
            print(f"\n{len(problems)} problem(s)")
        else:
            print(f"Docs check clean ({len(get_cli_commands())} cli commands, {len(get_skills())} skills, {len(get_builder_methods())} builder methods)")
    return EXIT_VIOLATIONS if problems else EXIT_OK

if __name__ == "__main__":
    sys.exit(main())
