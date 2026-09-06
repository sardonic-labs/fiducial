"""S-expression parsing and JSON conversion for KiCad files."""

import json
import sys
from pathlib import Path

from fidcore.const import EXIT_ENV, EXIT_OK

_ESCAPE = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\"}


def _strip_comments(text):
    """Remove ``;`` line comments and ``#|…|#`` block comments from KiCad
    S-expression text *before* tokenising.  Handles nested block comments
    and comments inside quoted strings (which should be preserved)."""
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c == '"':
            # copy the whole quoted string verbatim (comments inside are literal)
            j = i + 1
            while j < n:
                if text[j] == "\\" and j + 1 < n:
                    j += 2
                elif text[j] == '"':
                    j += 1
                    break
                else:
                    j += 1
            out.append(text[i:j])
            i = j
        elif c == ";":
            # line comment — skip to end of line
            while i < n and text[i] != "\n":
                i += 1
        elif c == "#" and i + 1 < n and text[i + 1] == "|":
            # block comment — skip to matching |#
            depth = 1
            i += 2
            while i < n and depth > 0:
                if text[i] == "#" and i + 1 < n and text[i + 1] == "|":
                    depth += 1
                    i += 2
                elif text[i] == "|" and i + 1 < n and text[i + 1] == "#":
                    depth -= 1
                    i += 2
                else:
                    i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def parse_sexp(text):
    text = _strip_comments(text)
    tokens = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
        elif c == "(":
            tokens.append("(")
            i += 1
        elif c == ")":
            tokens.append(")")
            i += 1
        elif c == '"':
            j = i + 1
            buf = []
            while j < n:
                if text[j] == "\\" and j + 1 < n:
                    buf.append(_ESCAPE.get(text[j + 1], text[j + 1]))
                    j += 2
                elif text[j] == '"':
                    break
                else:
                    buf.append(text[j])
                    j += 1
            tokens.append(("str", "".join(buf)))
            i = j + 1
        else:
            j = i
            while j < n and text[j] not in ' \t\r\n()"':
                j += 1
            tokens.append(text[i:j])
            i = j
    pos = 0

    def walk():
        nonlocal pos
        assert tokens[pos] == "(", f"expected ( at token {pos}"
        pos += 1
        items = []
        while tokens[pos] != ")":
            t = tokens[pos]
            if isinstance(t, tuple):
                items.append(t[1])
                pos += 1
            elif t == "(":
                items.append(walk())
            else:
                items.append(t)
                pos += 1
        pos += 1
        return items

    try:
        return walk()
    except (IndexError, AssertionError) as e:
        raise ValueError(f"malformed S-expression: {e}")


def load_sexp(path):
    return parse_sexp(Path(path).read_text(encoding="utf-8"))


def sexp_get(node, key):
    """First direct child list whose head == key."""
    for item in node:
        if isinstance(item, list) and item and item[0] == key:
            return item
    return None


def sexp_find_all(node, key):
    out = []
    stack = [node]
    while stack:
        cur = stack.pop()
        for item in cur:
            if isinstance(item, list):
                if item and item[0] == key:
                    out.append(item)
                stack.append(item)
    return out


def _sexp_to_json(node):
    """Convert a parsed S-expression tree to a JSON-serialisable structure."""
    if isinstance(node, list):
        # (key args…) → {"_key": key, …children}
        if node and isinstance(node[0], str):
            out = {"_key": node[0]}
            for item in node[1:]:
                if isinstance(item, list):
                    child = _sexp_to_json(item)
                    k = child.pop("_key", "_list")
                    # multi-valued keys become lists
                    if k in out:
                        if not isinstance(out[k], list):
                            out[k] = [out[k]]
                        out[k].append(child)
                    else:
                        out[k] = child
                else:
                    # bare atom after the key → _val (or _val if first)
                    if "_val" not in out:
                        out["_val"] = item
                    elif "_rest" not in out:
                        out["_rest"] = item
                    else:
                        # accumulate trailing atoms
                        if not isinstance(out["_rest"], list):
                            out["_rest"] = [out["_rest"]]
                        out["_rest"].append(item)
            return out
        return [_sexp_to_json(x) for x in node]
    return node


def cmd_sexp(args):
    """Parse an S-expression file and emit JSON to stdout."""
    path = Path(args.file)
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return EXIT_ENV
    try:
        tree = load_sexp(path)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return EXIT_ENV
    if args.raw:
        print(json.dumps(tree, indent=2))
    else:
        print(json.dumps(_sexp_to_json(tree), indent=2))
    return EXIT_OK
