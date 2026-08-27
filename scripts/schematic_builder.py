#!/usr/bin/env python3
"""SchematicBuilder — programmatic KiCad .kicad_sch generation.

Eliminates the need for agents to hand-roll S-expression strings when
creating schematics from scratch.  Every method emits valid KiCad 10
S-expression fragments; ``build()`` assembles them into a complete
.kicad_sch file.

Stdlib-only — no pip installs.

Usage::

    from scripts.schematic_builder import SchematicBuilder

    sch = SchematicBuilder("My Board")
    sch.add_symbol("Device:R", "R1", x=101.6, y=76.2, value="10k")
    sch.add_wire(101.6, 76.2, 114.3, 76.2)
    sch.add_label("SIG_IN", 101.6, 76.2, rotation=180)
    sch.add_power("+3V3", 101.6, 63.5)
    sch.add_no_connect(127.0, 99.06)
    Path("myboard.kicad_sch").write_text(sch.build(), encoding="utf-8")
"""

import uuid as _uuid_mod
from pathlib import Path


def _new_uuid():
    return str(_uuid_mod.uuid4())


def _fmt(v):
    """Format a float, stripping trailing zeros but keeping at least one
    decimal place so KiCad accepts it.  Integer-valued floats like 180.0
    are rendered as ``180``."""
    if isinstance(v, int) or (isinstance(v, float) and v == int(v)):
        return str(int(v))
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    if "." not in s:
        s += ".0"
    return s


def _indent(text, level=1):
    """Indent every line of *text* by *level* tabs."""
    prefix = "\t" * level
    return "\n".join(prefix + line if line.strip() else "" for line in text.splitlines())


class SchematicBuilder:
    """Build a KiCad 10 ``.kicad_sch`` file programmatically.

    Parameters
    ----------
    title : str
        Title block title.
    paper : str
        Paper size (default ``"A4"``).
    date : str or None
        Date string; defaults to today if *None*.
    revision : str
        Revision letter/code.
    comment : str
        Title block comment 1.
    """

    def __init__(self, title, paper="A4", date=None, revision="A", comment=""):
        self.title = title
        self.paper = paper
        self.date = date or "2026-08-25"
        self.revision = revision
        self.comment = comment
        self._root_uuid = _new_uuid()
        self._lib_symbols = {}       # lib_id → raw S-expression definition
        self._symbols = []           # instance S-expressions
        self._wires = []
        self._labels = []
        self._no_connects = []
        self._power_counter = 0     # auto-number #PWR0xx

    # ------------------------------------------------------------------
    # Library symbols
    # ------------------------------------------------------------------

    def load_lib_symbol(self, lib_id, sexpr_text):
        """Register a library symbol definition.

        *lib_id* is the KiCad library identifier (e.g. ``"Device:R"``).
        *sexpr_text* is the raw S-expression from the library file —
        everything inside the ``(symbol "Device:R" ...)`` block, including
        the outer parens.
        """
        self._lib_symbols[lib_id] = sexpr_text.strip()

    def _lib_symbols_block(self):
        if not self._lib_symbols:
            return "\t(lib_symbols)\n"
        parts = ["\t(lib_symbols"]
        for definition in self._lib_symbols.values():
            parts.append(_indent(definition, 2))
        parts.append("\t)")
        return "\n".join(parts) + "\n"

    # ------------------------------------------------------------------
    # Symbols
    # ------------------------------------------------------------------

    def add_symbol(self, lib_id, ref, x, y, rotation=0, value=None,
                   footprint="", unit=1):
        """Place a component symbol.

        Parameters
        ----------
        lib_id : str
            Library identifier (e.g. ``"Device:R"``).
        ref : str
            Reference designator (e.g. ``"R1"``).
        x, y : float
            Placement coordinates in mm.
        rotation : float
            Rotation in degrees (0, 90, 180, 270).
        value : str or None
            Component value; defaults to the lib_id basename.
        footprint : str
            Footprint library identifier.
        unit : int
            Symbol unit number (for multi-unit symbols).
        """
        if value is None:
            value = lib_id.split(":")[-1] if ":" in lib_id else lib_id
        sym_uuid = _new_uuid()
        pin_uuids = {f"pin{i}": _new_uuid() for i in range(1, 20)}  # pre-generate

        inst = f"""(symbol
\t\t(lib_id "{lib_id}")
\t\t(at {_fmt(x)} {_fmt(y)} {_fmt(rotation)})
\t\t(unit {unit})
\t\t(exclude_from_sim no)
\t\t(in_bom yes)
\t\t(on_board yes)
\t\t(dnp no)
\t\t(uuid "{sym_uuid}")
		(property "Reference" "{ref}"
			(at {_fmt(x)} {_fmt(y - 2.54)} 0)
			(effects (font (size 1.27 1.27)))
		)
		(property "Value" "{value}"
			(at {_fmt(x)} {_fmt(y + 2.54)} 0)
			(effects (font (size 1.27 1.27)))
		)
\t\t(property "Footprint" "{footprint}"
\t\t\t(at {_fmt(x)} {_fmt(y)} 0)
\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t)
\t\t(property "Datasheet" "~"
\t\t\t(at {_fmt(x)} {_fmt(y)} 0)
\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t)
\t\t(property "Description" ""
\t\t\t(at {_fmt(x)} {_fmt(y)} 0)
\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t)"""
        # Pin placeholders — KiCad needs these; the exact count depends on
        # the symbol but extra pin entries are harmless (ignored if not in
        # the lib definition).
        for i in range(1, 10):
            inst += f'\n\t\t(pin "{i}" (uuid "{_new_uuid()}"))'
        inst += """
\t\t(instances
\t\t\t(project "project"
\t\t\t\t(path "/{root}"
\t\t\t\t\t(reference "{ref}")
\t\t\t\t\t(unit {unit})
\t\t\t\t)
\t\t\t)
\t\t)
\t)""".format(root=self._root_uuid, ref=ref, unit=unit)
        self._symbols.append(inst)

    def add_power(self, lib_id, x, y, ref=None, value=None):
        """Place a power symbol (e.g. ``power:GND``, ``power:+3V3``).

        Power symbols have a hidden power-in pin that attaches the net
        name automatically — no wire needed to the power rail.
        """
        if ref is None:
            self._power_counter += 1
            ref = f"#PWR{self._power_counter:03d}"
        if value is None:
            value = lib_id.split(":")[-1] if ":" in lib_id else lib_id
        sym_uuid = _new_uuid()

        inst = f"""(symbol
\t\t(lib_id "{lib_id}")
\t\t(at {_fmt(x)} {_fmt(y)} 0)
\t\t(unit 1)
\t\t(exclude_from_sim no)
\t\t(in_bom yes)
\t\t(on_board yes)
\t\t(dnp no)
\t\t(uuid "{sym_uuid}")
\t\t(property "Reference" "{ref}"
\t\t\t(at {_fmt(x)} {_fmt(y - 3.81)} 0)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t)
\t\t(property "Value" "{value}"
\t\t\t(at {_fmt(x)} {_fmt(y + 2.54)} 0)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t)
\t\t(property "Footprint" ""
\t\t\t(at {_fmt(x)} {_fmt(y)} 0)
\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t)
\t\t(property "Datasheet" "~"
\t\t\t(at {_fmt(x)} {_fmt(y)} 0)
\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t)
\t\t(property "Description" ""
\t\t\t(at {_fmt(x)} {_fmt(y)} 0)
\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t)
\t\t(pin "1" (uuid "{_new_uuid()}"))
\t\t(instances
\t\t\t(project "project"
\t\t\t\t(path "/{self._root_uuid}"
\t\t\t\t\t(reference "{ref}")
\t\t\t\t\t(unit 1)
\t\t\t\t)
\t\t\t)
\t\t)
\t)"""
        self._symbols.append(inst)

    # ------------------------------------------------------------------
    # Wires
    # ------------------------------------------------------------------

    def add_wire(self, x1, y1, x2, y2):
        """Add a wire segment from ``(x1, y1)`` to ``(x2, y2)``."""
        self._wires.append(
            f'(wire\n'
            f'\t\t(pts (xy {_fmt(x1)} {_fmt(y1)}) (xy {_fmt(x2)} {_fmt(y2)}))\n'
            f'\t\t(stroke (width 0) (type default))\n'
            f'\t\t(uuid "{_new_uuid()}")\n'
            f'\t)'
        )

    def add_bus(self, x1, y1, x2, y2):
        """Add a bus segment (thicker line, same syntax as wire)."""
        self._wires.append(
            f'(bus\n'
            f'\t\t(pts (xy {_fmt(x1)} {_fmt(y1)}) (xy {_fmt(x2)} {_fmt(y2)}))\n'
            f'\t\t(stroke (width 0) (type default))\n'
            f'\t\t(uuid "{_new_uuid()}")\n'
            f'\t)'
        )

    # ------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------

    def add_label(self, name, x, y, rotation=0):
        """Add a local net label at ``(x, y)``.

        Local labels get a ``/`` prefix in the netlist (KiCad convention).
        """
        self._labels.append(
            f'(label "{name}"\n'
            f'\t\t(at {_fmt(x)} {_fmt(y)} {_fmt(rotation)})\n'
            f'\t\t(effects (font (size 1.27 1.27)) (justify left bottom))\n'
            f'\t\t(uuid "{_new_uuid()}")\n'
            f'\t)'
        )

    def add_global_label(self, name, x, y, rotation=0):
        """Add a global label (visible name, connects across sheets)."""
        self._labels.append(
            f'(global_label "{name}"\n'
            f'\t\t(shape bidirectional)\n'
            f'\t\t(at {_fmt(x)} {_fmt(y)} {_fmt(rotation)})\n'
            f'\t\t(effects (font (size 1.27 1.27)) (justify left bottom))\n'
            f'\t\t(uuid "{_new_uuid()}")\n'
            f'\t)'
        )

    # ------------------------------------------------------------------
    # No-connects
    # ------------------------------------------------------------------

    def add_no_connect(self, x, y):
        """Place a no-connect marker at ``(x, y)``."""
        self._no_connects.append(
            f'(no_connect\n'
            f'\t\t(at {_fmt(x)} {_fmt(y)})\n'
            f'\t\t(uuid "{_new_uuid()}")\n'
            f'\t)'
        )

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self):
        """Assemble the complete .kicad_sch file as a string."""
        header = f"""(kicad_sch
\t(version 20260306)
\t(generator "fiducial_schematic_builder")
\t(generator_version "10.0")
\t(uuid "{self._root_uuid}")
\t(paper "{self.paper}")
\t(title_block
\t\t(title "{self.title}")
\t\t(date "{self.date}")
\t\t(rev "{self.revision}")
\t\t(comment 1 "{self.comment}")
\t)"""
        body = header + "\n"
        body += self._lib_symbols_block()
        # no_connects before wires/labels (KiCad ordering)
        for nc in self._no_connects:
            body += "\t" + _indent(nc, 1).strip() + "\n"
        for w in self._wires:
            body += "\t" + _indent(w, 1).strip() + "\n"
        for lab in self._labels:
            body += "\t" + _indent(lab, 1).strip() + "\n"
        for sym in self._symbols:
            body += "\t" + _indent(sym, 1).strip() + "\n"
        body += ")\n"
        return body


# ------------------------------------------------------------------
# Convenience function
# ------------------------------------------------------------------

def build_schematic(title, symbols=None, wires=None, labels=None,
                    power=None, no_connects=None, paper="A4",
                    date=None, revision="A", comment=""):
    """One-shot schematic builder.

    Returns the complete .kicad_sch content as a string.

    Example::

        content = build_schematic(
            "LED Board",
            symbols=[("Device:R", "R1", 101.6, 76.2)],
            labels=[("SIG", 101.6, 76.2)],
            power=[("power:GND", 101.6, 88.9)],
        )
        Path("led.kicad_sch").write_text(content, encoding="utf-8")
    """
    sch = SchematicBuilder(title, paper=paper, date=date,
                           revision=revision, comment=comment)
    for args in (symbols or []):
        if isinstance(args, dict):
            sch.add_symbol(**args)
        else:
            sch.add_symbol(*args)
    for args in (wires or []):
        sch.add_wire(*args)
    for args in (labels or []):
        if isinstance(args, dict):
            sch.add_label(**args)
        else:
            sch.add_label(*args)
    for args in (power or []):
        if isinstance(args, dict):
            sch.add_power(**args)
        else:
            sch.add_power(*args)
    for args in (no_connects or []):
        sch.add_no_connect(*args)
    return sch.build()
