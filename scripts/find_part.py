#!/usr/bin/env python3
"""find_part.py - locate KiCad symbols/footprints by name across library trees.

Stdlib-only. Walks project-local and system KiCad library directories looking
for footprint files (.kicad_mod) and symbol libraries (.kicad_sym) whose names
or contents match a query.

Exit codes: 0 = at least one hit, 1 = no hits, 2 = environment error.
"""
import argparse
import os
import sys
from pathlib import Path

FP_EXT = ".kicad_mod"
SYM_EXT = ".kicad_sym"


def default_roots(project_root=None):
    roots = []
    if project_root:
        libs = Path(project_root) / "libraries"
        if libs.is_dir():
            roots.append(libs)
    data_dirs = []
    pf = os.environ.get("KICAD_CONFIG_HOME") or os.environ.get("KICAD_PATH")
    if pf:
        data_dirs.append(Path(pf))
    for cand in (
        r"C:\Program Files\KiCad",
        "/usr/share/kicad",
        "/usr/local/share/kicad",
        "/Applications/KiCad",
    ):
        p = Path(cand)
        if p.is_dir():
            data_dirs.append(p)
    # a KiCad install contains per-version folders with footprints/ + symbols/
    for base in data_dirs:
        for child in sorted(base.glob("*")):
            if (child / "footprints").is_dir() or (child / "symbols").is_dir():
                roots.append(child)
    return [r for r in roots if r.is_dir()]


def scan(root, query, kind):
    """Yield paths under root whose filename or text content matches query."""
    q = query.lower()
    want_fp = kind in ("fp", "any")
    want_sym = kind in ("sym", "any")
    hits = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fn in filenames:
            low = fn.lower()
            path = Path(dirpath) / fn
            try:
                if want_fp and low.endswith(FP_EXT):
                    if q in low:
                        print(path)
                        hits += 1
                elif want_sym and low.endswith(SYM_EXT):
                    name_hit = q in low
                    content_hit = False
                    if not name_hit:
                        try:
                            content_hit = q in path.read_text(
                                encoding="utf-8", errors="replace").lower()
                        except OSError:
                            pass
                    if name_hit or content_hit:
                        print(path)
                        hits += 1
            except PermissionError:
                continue
    return hits


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("query", help="substring to match, e.g. 'xt30', 'pca9539', 'pcie'")
    ap.add_argument("--root", action="append", default=[],
                    help="library root to scan; repeatable. Defaults to "
                         "./libraries plus detected system KiCad dirs")
    ap.add_argument("--project", default=".",
                    help="project root whose libraries/ is searched first")
    ap.add_argument("--kind", choices=("sym", "fp", "any"), default="any")
    args = ap.parse_args(argv)

    roots = [Path(r) for r in args.root] or default_roots(args.project)
    if not roots:
        print("ERROR: no library roots found; pass --root", file=sys.stderr)
        return 2

    total = 0
    shown = set()
    for root in roots:
        root = root.resolve()
        if root in shown:
            continue
        shown.add(root)
        print(f"# scanning {root}", file=sys.stderr)
        total += scan(root, args.query, args.kind)

    if total == 0:
        print(f"no matches for '{args.query}' — escalate: LCSC/JLC catalog, "
              "vendor pages, then manual download into libraries/", file=sys.stderr)
        return 1
    print(f"\n{total} match(es)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
