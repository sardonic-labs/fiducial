# S-expression reference (`fiducial.py:68`)

> KiCad files are S-expressions. Parser at `fiducial.py:68` `parse_sexp` handles `;` line comments, `#|…|#` block comments (nested), quoted strings with `\n\t\r\\` escapes.

## Grammar (human)

```
file := "(kicad_sch" version generator uuid paper title_block lib_symbols symbols wires labels ")"
symbol_instance := "(symbol" lib_id at uuid properties pin_instances ")"
lib_symbol      := "(symbol \"" lib_id "\"" properties pins ")"
wire            := "(wire (pts (xy x y) (xy x y)) (stroke …) (uuid …))"
label           := "(label \"text\" (at x y rot) … (uuid …))"  // or global_label/hierarchical_label
```

Version field: `20230121` (7) → `20231120` (8) → `20240108` (9) → `20260306` (10) — see `kicad-versions.md:10`; builder emits `20250114` (`schematic_builder.py:171`) or `20260306` title-mode.

## For agents (parse)

```sh
python fiducial/scripts/fiducial.py sexp myboard.kicad_sch --json | jq ._key  # → "kicad_sch"
python fiducial/scripts/fiducial.py sexp myboard.kicad_sch --raw | jq '.[0]'  # nested lists
```

```python
from scripts.fiducial import load_sexp, sexp_get, sexp_find_all, _first_str
root = load_sexp("myboard.kicad_sch")  # fiducial.py:128
for sym in sexp_find_all(root, "symbol"):
    if sexp_get(sym, "instances"):  # instance vs definition (authoring.md:21)
        ref = _first_str(sexp_get(sym, "property"))  # not reliable — iterate properties
```

* `parse_sexp:68` → nested `list`; `sexp_get:132` first child list head==key; `sexp_find_all:140` DFS.
* `load_sexp:128` reads `Path.read_text(utf-8)`.

## Diagnostic commands built on this

* `pin-positions <sch> <REF>` — `lib_symbols` + `symbol at` → absolute pin (`_compute_pin_positions:618`, `_pin_sort:386`).
* `wire-trace` — `wire` graph (`_build_wire_graph:702`) + nearest label (`_find_nearest_label:729`).
* `label-map` — grouped by `net` (`label-map:799`).

## Machine block

```json
{
  "parser": "fiducial.py:68",
  "helpers": ["load_sexp:128","sexp_get:132","sexp_find_all:140","_first_str:348","_strip_comments:25"],
  "cli": "sexp --json/--raw (fiducial.py:1234)",
  "diagnostics": ["wire-trace:742","label-map:799","pin-positions:667"]
}
```
