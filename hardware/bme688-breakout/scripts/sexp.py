"""Minimal reader/writer for the s-expression dialect KiCad uses.

Parsing yields nested lists of str/float; bare atoms and quoted strings are
distinguished by wrapping quoted ones in Str so a round-trip keeps its quotes.
"""


class Str(str):
    """A string that was quoted in the source and must stay quoted."""
    __slots__ = ()


def parse(text):
    """Parse one or more top-level s-expressions into nested lists."""
    pos = 0
    end = len(text)
    stack = []
    out = []
    while pos < end:
        ch = text[pos]
        if ch.isspace():
            pos += 1
        elif ch == '(':
            node = []
            if stack:
                stack[-1].append(node)
            stack.append(node)
            pos += 1
        elif ch == ')':
            node = stack.pop()
            if not stack:
                out.append(node)
            pos += 1
        elif ch == '"':
            pos += 1
            buf = []
            while text[pos] != '"':
                if text[pos] == '\\':
                    pos += 1
                buf.append(text[pos])
                pos += 1
            pos += 1
            stack[-1].append(Str(''.join(buf)))
        else:
            start = pos
            while pos < end and not text[pos].isspace() and text[pos] not in '()"':
                pos += 1
            stack[-1].append(text[start:pos])
    return out


def num(atom):
    return float(atom)


def get(node, key):
    """First child list whose head is key, else None."""
    for child in node:
        if isinstance(child, list) and child and child[0] == key:
            return child
    return None


def getall(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


def quote(text):
    return '"' + str(text).replace('\\', '\\\\').replace('"', '\\"') + '"'


def fmt(value):
    """Format a float the way KiCad does: shortest round-trip, no trailing .0."""
    if isinstance(value, float):
        if value == int(value):
            return str(int(value))
        return ('%.6f' % value).rstrip('0')
    return str(value)


def dump(node, depth=0):
    """Render a parsed node back to KiCad's tab-indented layout."""
    pad = '\t' * depth
    if not isinstance(node, list):
        return quote(node) if isinstance(node, Str) else str(node)
    head = node[0] if node else ''
    simple = all(not isinstance(c, list) for c in node[1:])
    if simple:
        parts = [dump(c) for c in node[1:]]
        return pad + '(' + ' '.join([str(head)] + parts) + ')'
    lines = [pad + '(' + str(head)]
    for child in node[1:]:
        if isinstance(child, list):
            lines.append(dump(child, depth + 1))
        else:
            lines.append('\t' * (depth + 1) + dump(child))
    lines.append(pad + ')')
    return '\n'.join(lines)
