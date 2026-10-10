"""Small, exactly-equivalent expression rewrites.

* `x.Method(x, ...)`   ->  `x:Method(...)`      (the receiver is a plain name, so it is
                                                  read once instead of twice, same value)
* `not (a == b)`       ->  `a ~= b`
* `not (a ~= b)`       ->  `a == b`

Deliberately NOT done: `not (a < b)` -> `a >= b`. That is wrong for NaN and for types with
`__lt` but no `__le`, so it is not an identical program.
"""

from __future__ import annotations

from dataclasses import fields

from .syntax import Binary, Call, Chunk, Field, Method, Name, Node, Paren, Unary

_OPPOSITE = {"==": "~=", "~=": "=="}


def simplify_expressions(chunk: Chunk) -> int:
    """Rewrite in place; returns how many rewrites were applied."""
    counter = [0]
    _walk(chunk, counter)
    return counter[0]


def _walk(node: Node, counter: list[int]) -> None:
    for field in fields(node):
        value = getattr(node, field.name)
        if isinstance(value, (Node, list, tuple)):
            setattr(node, field.name, _visit(value, counter))


def _visit(value, counter: list[int]):
    if isinstance(value, Node):
        _walk(value, counter)
        return _rewrite(value, counter)
    if isinstance(value, list):
        return [_visit(item, counter) for item in value]
    if isinstance(value, tuple):
        return tuple(_visit(item, counter) for item in value)
    return value


def _rewrite(node: Node, counter: list[int]) -> Node:
    replacement = _method_call(node) or _negated_equality(node)
    if replacement is None:
        return node
    replacement.comments = node.comments
    counter[0] += 1
    return replacement


def _same_name(left: Node, right: Node) -> bool:
    if not (isinstance(left, Name) and isinstance(right, Name)):
        return False
    if left.decl is not None or right.decl is not None:
        return left.decl is right.decl
    return left.ident == right.ident


def _method_call(node: Node) -> Node | None:
    if not (isinstance(node, Call) and isinstance(node.fn, Field) and node.args):
        return None
    receiver = node.fn.obj
    if isinstance(receiver, Name) and _same_name(receiver, node.args[0]):
        return Method(receiver, node.fn.name, node.args[1:])
    return None


def _negated_equality(node: Node) -> Node | None:
    if not (isinstance(node, Unary) and node.op == "not"):
        return None
    inner = node.operand
    if isinstance(inner, Paren):
        inner = inner.inner
    if isinstance(inner, Binary) and inner.op in _OPPOSITE:
        return Binary(_OPPOSITE[inner.op], inner.left, inner.right)
    return None