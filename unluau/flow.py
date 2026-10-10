"""Flatten nested control flow into guard clauses.

Every rewrite here is semantics-preserving by construction:

* `if c then <rest of function> end`  ->  `if not c then return end <rest>`
* the same at the end of a loop body with `continue`
* `if c then <exit> else <rest> end`  ->  `if c then <exit> end <rest>`
* `else if` -> `elseif`, redundant trailing `return` / `continue` removed
"""

from __future__ import annotations

from .syntax import (
    Binary, Block, Break, Chunk, Const, Continue, FuncExpr, GenericFor, If, Node,
    NumericFor, Paren, Return, Unary, While, Local, LocalFunction, iter_nodes,
)

_LOCAL_DECLARATIONS = (Local, LocalFunction)
_LOOP_TYPES = (While, NumericFor, GenericFor)


def flatten_control_flow(chunk: Chunk) -> None:
    _process(chunk.body, "function")
    for node in iter_nodes(chunk):
        if isinstance(node, FuncExpr):
            _process(node.body, "function")
        elif isinstance(node, _LOOP_TYPES):
            _process(node.body, "loop")
        elif isinstance(node, If):
            _process_if_blocks(node)


def _process_if_blocks(node: If) -> None:
    for _, block in node.arms:
        _process(block, "plain")
    if node.orelse is not None:
        _process(node.orelse, "plain")


# -- one block ---------------------------------------------------------------- #

def _process(block: Block, kind: str) -> None:
    index = 0
    while index < len(block.stmts):
        statement = block.stmts[index]
        if isinstance(statement, If):
            _merge_else_if(statement)
            replacement = _rewrite_if(statement, is_last=index == len(block.stmts) - 1, kind=kind)
            if replacement is not None:
                block.stmts[index:index + 1] = replacement
                continue
        index += 1
    _drop_redundant_exit(block, kind)


def _rewrite_if(node: If, is_last: bool, kind: str) -> list[Node] | None:
    return (
        _split_terminating_arm(node, is_last)
        or _invert_trailing_else(node, is_last)
        or (_guard_trailing_if(node, kind) if is_last else None)
    )


def _merge_else_if(node: If) -> None:
    """`else` holding exactly one `if` becomes an `elseif` arm."""
    while node.orelse is not None and _is_lone_if(node.orelse):
        nested = node.orelse.stmts[0]
        node.arms.extend(nested.arms)
        node.orelse = nested.orelse


def _is_lone_if(block: Block) -> bool:
    return (len(block.stmts) == 1 and isinstance(block.stmts[0], If)
            and not block.stmts[0].comments and not block.trailing)


def _terminates(block: Block) -> bool:
    return bool(block.stmts) and isinstance(block.stmts[-1], (Return, Break, Continue))


def _declares_locals(block: Block) -> bool:
    return any(isinstance(statement, _LOCAL_DECLARATIONS) for statement in block.stmts)


def _can_lift(block: Block, is_last: bool) -> bool:
    """Moving `block`'s statements into the parent must not leak locals or comments."""
    if block.trailing:
        return False
    return is_last or not _declares_locals(block)


def _with_comments(statements: list[Node], comments) -> list[Node]:
    if statements and comments:
        statements[0].comments = [*comments, *statements[0].comments]
    return statements


def _split_terminating_arm(node: If, is_last: bool) -> list[Node] | None:
    """`if a then <exit> elseif b ... end` -> `if a then <exit> end if b ... end`."""
    first_condition, first_block = node.arms[0]
    if not _terminates(first_block):
        return None
    if len(node.arms) == 1 and node.orelse is None:
        return None
    if len(node.arms) == 1 and not _can_lift(node.orelse, is_last):
        return None
    head = If([(first_condition, first_block)], None)
    if len(node.arms) == 1:
        return _with_comments([head, *node.orelse.stmts], node.comments)
    tail = If(node.arms[1:], node.orelse)
    return _with_comments([head, tail], node.comments)


def _invert_trailing_else(node: If, is_last: bool) -> list[Node] | None:
    """`if c then <body> else <exit> end` -> `if not c then <exit> end <body>`."""
    if len(node.arms) != 1 or node.orelse is None:
        return None
    condition, body = node.arms[0]
    if not _terminates(node.orelse) or not _can_lift(body, is_last):
        return None
    guard = If([(negate(condition), node.orelse)], None)
    return _with_comments([guard, *body.stmts], node.comments)


def _guard_trailing_if(node: If, kind: str) -> list[Node] | None:
    """`if c then <long body> end` at the end of a function/loop -> guard clause."""
    if kind == "plain" or len(node.arms) != 1 or node.orelse is not None:
        return None
    condition, body = node.arms[0]
    if not _worth_flattening(body) or body.trailing:
        return None
    exit_statement = Return([]) if kind == "function" else Continue()
    guard = If([(negate(condition), Block([exit_statement]))], None)
    return _with_comments([guard, *body.stmts], node.comments)


def _worth_flattening(body: Block) -> bool:
    """Guarding a one-line body would make the code longer, not clearer."""
    if len(body.stmts) >= 2:
        return True
    return bool(body.stmts) and isinstance(body.stmts[0], (If, *_LOOP_TYPES))


def _drop_redundant_exit(block: Block, kind: str) -> None:
    if not block.stmts:
        return
    last = block.stmts[-1]
    if kind == "function" and isinstance(last, Return) and not last.values:
        block.stmts.pop()
    elif kind == "loop" and isinstance(last, Continue):
        block.stmts.pop()


# -- conditions --------------------------------------------------------------- #

_OPPOSITE = {"==": "~=", "~=": "=="}


def negate(condition: Node) -> Node:
    """`not condition`, simplified. Only used where the result is tested for truthiness."""
    match condition:
        case Paren(inner=inner):
            return negate(inner)
        case Unary(op="not", operand=operand):
            return operand
        case Binary(op=("==" | "~=") as op, left=left, right=right):
            return Binary(_OPPOSITE[op], left, right)
        case Binary(op="and", left=left, right=right):
            return Binary("or", negate(left), negate(right))
        case Binary(op="or", left=left, right=right):
            return Binary("and", negate(left), negate(right))
        case Const(text="true"):
            return Const("false")
        case Const(text=("false" | "nil")):
            return Const("true")
    return Unary("not", condition)
