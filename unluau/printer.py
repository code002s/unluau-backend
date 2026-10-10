"""Pretty-printer: turns the syntax tree back into consistently formatted Luau."""

from __future__ import annotations

import re

from .syntax import (
    BINARY_PRIORITY, KEYWORDS, UNARY_PRIORITY, Assign, Binary, Block, Break, Call,
    CallStmt, Chunk, CompoundAssign, Const, Continue, Do, Field, FuncExpr,
    FunctionStmt, GenericFor, If, IfExpr, Index, Interp, Local, LocalFunction,
    Method, Name, Node, Number, NumericFor, Paren, Repeat, Return, Str, TableExpr,
    Unary, Vararg, While,
)

INDENT = "    "
MAX_INLINE_TABLE = 90
_RIGHT_ASSOCIATIVE = frozenset({"..", "^"})
_PREFIX_TYPES = (Name, Field, Index, Call, Method, Paren)
_COMPOUND_STATEMENTS = (If, While, Repeat, NumericFor, GenericFor, Do,
                        FunctionStmt, LocalFunction)
_SIMPLE_KEY = re.compile(r"^[\"']([A-Za-z_][A-Za-z0-9_]*)[\"']$")


def print_chunk(chunk: Chunk) -> str:
    lines = _block(chunk.body, 0)
    return "\n".join(lines) + "\n" if lines else ""


# -- blocks and statements --------------------------------------------------- #

def _block(block: Block, level: int) -> list[str]:
    lines: list[str] = []
    previous: Node | None = None
    for statement in block.stmts:
        text = _statement(statement, level)
        if previous is not None and _needs_blank_line(previous, statement, text):
            lines.append("")
        lines.extend(_comment_lines(statement.comments, level))
        if previous is not None and text.lstrip().startswith("("):
            text = text.replace("(", ";(", 1)  # a bare `(` would continue the previous line
        lines.append(text)
        previous = statement
    lines.extend(_comment_lines(block.trailing, level))
    return lines


def _comment_lines(comments: list[str] | tuple[str, ...], level: int) -> list[str]:
    return [INDENT * level + comment.strip() for comment in comments]


def _is_compound(statement: Node, text: str) -> bool:
    return isinstance(statement, _COMPOUND_STATEMENTS) or "\n" in text


def _is_service_alias(statement: Node) -> bool:
    match statement:
        case Local(decls=[_], values=[Method(obj=Name(ident="game"), name="GetService")]):
            return True
        case _:
            return False


def _needs_blank_line(previous: Node, current: Node, current_text: str) -> bool:
    if _is_compound(current, current_text) or isinstance(previous, _COMPOUND_STATEMENTS):
        return True
    if _is_service_alias(previous) and not _is_service_alias(current):
        return True
    return bool(current.comments)


def _statement(node: Node, level: int) -> str:
    pad = INDENT * level
    match node:
        case Local(decls=decls, values=values):
            names = ", ".join(decl.name for decl in decls)
            return f"{pad}local {names}{_assigned(values, level)}"
        case LocalFunction(decl=decl, func=func):
            return pad + _function(func, level, f"local function {decl.name}")
        case FunctionStmt(target=target, method=method, func=func):
            name = _expression(target, level) + (f":{method}" if method else "")
            return pad + _function(func, level, f"function {name}")
        case Assign(targets=targets, values=values):
            left = ", ".join(_expression(target, level) for target in targets)
            return f"{pad}{left}{_assigned(values, level)}"
        case CompoundAssign(target=target, op=op, value=value):
            return f"{pad}{_expression(target, level)} {op} {_expression(value, level)}"
        case CallStmt(call=call):
            return pad + _expression(call, level)
        case If():
            return _if(node, level)
        case While(cond=cond, body=body):
            return _compound(f"while {_expression(cond, level)} do", body, level)
        case Repeat(body=body, cond=cond):
            lines = [pad + "repeat", *_block(body, level + 1),
                     f"{pad}until {_expression(cond, level)}"]
            return "\n".join(lines)
        case NumericFor(var=var, start=start, stop=stop, step=step, body=body):
            parts = [_expression(start, level), _expression(stop, level)]
            if step is not None:
                parts.append(_expression(step, level))
            return _compound(f"for {var.name} = {', '.join(parts)} do", body, level)
        case GenericFor(vars=variables, exprs=exprs, body=body):
            names = ", ".join(variable.name for variable in variables)
            sources = ", ".join(_expression(expr, level) for expr in exprs)
            return _compound(f"for {names} in {sources} do", body, level)
        case Do(body=body):
            return _compound("do", body, level)
        case Return(values=values):
            if not values:
                return pad + "return"
            return pad + "return " + ", ".join(_expression(value, level) for value in values)
        case Break():
            return pad + "break"
        case Continue():
            return pad + "continue"
    raise TypeError(f"cannot print statement {type(node).__name__}")


def _assigned(values: list[Node], level: int) -> str:
    if not values:
        return ""
    return " = " + ", ".join(_expression(value, level) for value in values)


def _compound(header: str, body: Block, level: int) -> str:
    pad = INDENT * level
    return "\n".join([pad + header, *_block(body, level + 1), pad + "end"])


def _if(node: If, level: int) -> str:
    pad = INDENT * level
    lines: list[str] = []
    for position, (condition, block) in enumerate(node.arms):
        keyword = "if" if position == 0 else "elseif"
        lines.append(f"{pad}{keyword} {_expression(condition, level)} then")
        lines.extend(_block(block, level + 1))
    if node.orelse is not None:
        lines.append(pad + "else")
        lines.extend(_block(node.orelse, level + 1))
    lines.append(pad + "end")
    return "\n".join(lines)


def _function(func: FuncExpr, level: int, prefix: str) -> str:
    parameters = [param.name for param in func.params]
    if func.vararg:
        parameters.append("...")
    header = f"{prefix}({', '.join(parameters)})"
    body = _block(func.body, level + 1)
    if not body:
        return header + " end"
    return "\n".join([header, *body, INDENT * level + "end"])


# -- expressions ------------------------------------------------------------- #

def _priority(node: Node) -> int:
    match node:
        case Binary(op=op):
            return BINARY_PRIORITY[op][0]
        case Unary():
            return UNARY_PRIORITY
        case IfExpr():
            return 0
        case _:
            return 100


def _operand(node: Node, level: int, minimum: int, wrap_equal: bool) -> str:
    text = _expression(node, level)
    priority = _priority(node)
    if priority < minimum or (wrap_equal and priority == minimum):
        return f"({text})"
    return text


def _expression(node: Node, level: int) -> str:
    match node:
        case Const(text=text) | Number(text=text) | Interp(text=text):
            return text
        case Str(text=text):
            return text
        case Vararg():
            return "..."
        case Name(ident=ident, decl=decl):
            return decl.name if decl else ident
        case Paren(inner=inner):
            return f"({_expression(inner, level)})"
        case Field(obj=obj, name=name):
            return f"{_prefix(obj, level)}.{name}"
        case Index(obj=obj, key=Str(text=text)) if _SIMPLE_KEY.match(text) \
                and _SIMPLE_KEY.match(text).group(1) not in KEYWORDS:
            return f"{_prefix(obj, level)}.{_SIMPLE_KEY.match(text).group(1)}"
        case Index(obj=obj, key=key):
            return f"{_prefix(obj, level)}[{_expression(key, level)}]"
        case Call(fn=fn, args=args):
            return f"{_prefix(fn, level)}({_arguments(args, level)})"
        case Method(obj=obj, name=name, args=args):
            return f"{_prefix(obj, level)}:{name}({_arguments(args, level)})"
        case Binary(op=op, left=left, right=right):
            priority = BINARY_PRIORITY[op][0]
            right_associative = op in _RIGHT_ASSOCIATIVE
            left_text = _operand(left, level, priority, right_associative)
            right_text = _operand(right, level, priority, not right_associative)
            return f"{left_text} {op} {right_text}"
        case Unary(op=op, operand=operand):
            text = _operand(operand, level, UNARY_PRIORITY, False)
            if op == "not":
                return f"not {text}"
            return f"{op} {text}" if text.startswith("-") else f"{op}{text}"
        case FuncExpr():
            return _function(node, level, "function")
        case TableExpr(items=items):
            return _table(items, level)
        case IfExpr(arms=arms, orelse=orelse):
            text = ""
            for position, (condition, value) in enumerate(arms):
                keyword = "if" if position == 0 else " elseif"
                text += f"{keyword} {_expression(condition, level)} then {_expression(value, level)}"
            return f"{text} else {_expression(orelse, level)}"
    raise TypeError(f"cannot print expression {type(node).__name__}")


def _prefix(node: Node, level: int) -> str:
    text = _expression(node, level)
    return text if isinstance(node, _PREFIX_TYPES) else f"({text})"


def _arguments(args: list[Node], level: int) -> str:
    return ", ".join(_expression(arg, level) for arg in args)


def _table(items: list, level: int) -> str:
    if not items:
        return "{}"
    rendered = [_table_item(item, level + 1) for item in items]
    inline = "{" + ", ".join(rendered) + "}"
    if "\n" not in inline and len(inline) <= MAX_INLINE_TABLE:
        return inline
    inner = INDENT * (level + 1)
    body = "".join(f"{inner}{text},\n" for text in rendered)
    return "{\n" + body + INDENT * level + "}"


def _table_item(item, level: int) -> str:
    value = _expression(item.value, level)
    if item.kind == "pos":
        return value
    if item.kind == "name":
        return f"{item.key} = {value}"
    key = item.key
    simple = _SIMPLE_KEY.match(key.text) if isinstance(key, Str) else None
    if simple and simple.group(1) not in KEYWORDS:
        return f"{simple.group(1)} = {value}"
    return f"[{_expression(key, level)}] = {value}"
