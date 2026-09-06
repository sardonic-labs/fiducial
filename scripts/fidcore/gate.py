"""The `check` verification gate: lint + erc + intent + rules in one run."""

from argparse import Namespace

from fidcore.const import EXIT_ENV, EXIT_OK, EXIT_VIOLATIONS
from fidcore.kicad import cmd_erc
from fidcore.lint import cmd_check_rules, cmd_lint
from fidcore.netlist import cmd_check_intent


def cmd_check(args):
    """Run the full verification gate in one invocation: lint, erc, and
    optionally check-intent / check-rules. Exit code is the worst of the
    parts, so CI and block-completion checks need one command only.
    A sub-command crashing (e.g. netlist export without kicad-cli) counts
    as ENV-ERROR for the gate rather than aborting it."""

    def run(label, fn):
        nonlocal worst
        print(f"== {label} ==")
        try:
            rc = fn()
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else EXIT_ENV
        worst = max(worst, rc)

    worst = EXIT_OK
    run("lint", lambda: cmd_lint(args))
    if not getattr(args, "skip_erc", False):
        run("erc", lambda: cmd_erc(args))
    else:
        print("== erc: skipped (--skip-erc) ==")
    if args.intent:
        run("check-intent", lambda: cmd_check_intent(
            Namespace(**{**vars(args), "csv": args.intent})))
    if args.rules:
        run("check-rules", lambda: cmd_check_rules(args))
    verdict = {EXIT_OK: "PASS", EXIT_VIOLATIONS: "FINDINGS", EXIT_ENV: "ENV-ERROR"}.get(
        worst, str(worst))
    print(f"\n== check: {verdict} ==")
    return worst
