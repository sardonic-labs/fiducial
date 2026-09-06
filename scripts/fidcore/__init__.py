"""fidcore - implementation modules behind the fiducial CLI.

`scripts/fiducial.py` remains the CLI entry point (argparse + main) and
re-exports this package's public surface so `from fiducial import X`
keeps working. Internal cross-module calls use module-attribute access
(`import fidcore.kicad as kicad_mod`) so tests can monkeypatch
`fidcore.kicad.kicad_cli` at the module boundary.
"""
