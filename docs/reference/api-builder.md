# API — `SchematicBuilder` (`schematic_builder.py:144`)

> Human table + agent JSON from same docstrings. Source: `schematic_builder.py:144`.

This is the reference; tutorial is `tutorial.md:1`, how-to `howto/migrate-handrolled.md`.

```sh
python scripts/schematic_builder.py --help  # (no CLI yet — import)
python -c "import schematic_builder, json; print(json.dumps([m for m in dir(schematic_builder.SchematicBuilder) if not m.startswith('_')]))"
```

## Construction

| Signature | Human | Notes |
|---|---|---|
| `SchematicBuilder(path, title, rev, date, paper, version, generator)` | path-based, strict grid 1.27 mm (`builder.md:64`) | `path` where `save()` writes; `version=20250114` |
| `SchematicBuilder(title, paper, date, revision, comment)` | title-based, relaxed grid (remote tests) (`kicad-versions.md:10`) | `build()` returns string (`version 20260306 / fiducial_schematic_builder`) |
| `SchematicBuilder.load(path)` | reload existing `.kicad_sch` (`builder.md:122`) | best-effort via `load_sexp:128` |

## Methods

| Method | Human | Agent snippet |
|---|---|---|
| `add_symbol(lib_id, ref, value, at, footprint, rotation, unit)` | unique `uuid`+`instances`, `lib_symbols` stub (`builder.md:68`) | `b.add_symbol("Device:R","R1","10k", at=(50.8,50.8))` |
| `add_symbol(lib_id, ref, x, y, value)` | remote alias (title-mode) | `sch.add_symbol("Device:R","R1", 101.6, 76.2, value="10k")` |
| `connect(ref,pin,net, kind="label")` | label at pin endpoint (`_compute_pin_positions:618`), power→`global_label` (`hierarchy.md:33`) | `b.connect("R1","1","/A"); b.write_intent("intent.csv")` |
| `tie(ref,pin,net)` | alias | — |
| `wire(p1,p2)` / `add_wire(x1,y1,x2,y2)` | orthogonal only (`cleanliness.md:24`) | `b.wire((50.8,46.99),(50.8,38.1))` |
| `label/global_label/hierarchical_label` | `kind` selects scope (`hierarchy.md:29`) | `b.global_label("GND", at=(50.8,80.01))` |
| `add_power(net, at)` / `add_power(lib_id,x,y)` | `power:GND` symbol (`kicad-versions.md:69`) | `b.add_power("GND", at=(50.8,80.01))` |
| `no_connect(ref,pin)` / `add_no_connect(x,y)` | NC marker | — |
| `add_text(text, at)` | text note | `b.add_text("BLOCK", at=(50.8,30))` |
| `save(path, validate)` / `build()` | `validate` runs `lint` in-process (`builder.md:109`) | `b.save(validate=True)` / `sch.build()` |
| `write_intent(csv_path)` | `ref,pin,expected_net` | `b.write_intent("intent.csv")` |
| `load_lib_symbol(lib_id, sexpr)` | raw lib registration | — |
| `build_schematic(title, symbols, wires, …)` | one-shot convenience | `build_schematic("Board", symbols=[...])` |

Helpers for agents: `_fmt(v)` (`101.6→"101.6"`, `100.0→"100"`), `_indent`, `_new_uuid`.

## Machine block (generated)

```json
{
  "module": "schematic_builder.py:144",
  "classes": ["SchematicBuilder"],
  "methods": ["add_symbol","connect","tie","wire","label","global_label","hierarchical_label","add_power","no_connect","save","write_intent","load","build","add_wire","add_bus","add_label","add_global_label","add_no_connect","load_lib_symbol"],
  "functions": ["build_schematic","_fmt","_indent","_new_uuid"],
  "invariants": ["uuid per object","grid 1.27 (path mode)","lib_symbols per lib_id","instances block"],
  "source": "builder.md:1"
}
```

> Regenerate table via CI: `python -c "import schematic_builder; help(schematic_builder.SchematicBuilder)"` → update this file; `docs_check.py` asserts method list.
