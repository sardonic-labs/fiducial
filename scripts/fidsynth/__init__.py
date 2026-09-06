"""fidsynth — spec → schematic synthesis for fiducial.

Public API:
    from fidsynth import compile_spec, load_spec
    compile_spec(spec_dict_or_path, out="board.kicad_sch") -> {"sch": path, "intent": path}
"""
from fidsynth.compiler import compile_spec
from fidsynth.spec import load_spec

__all__ = ["compile_spec", "load_spec"]
