"""Lexer, syntax tree and parser for the Luau subset that decompilers emit.

The parser is deliberately strict: anything it does not understand (type
annotations, `goto`, ...) raises `SyntaxProblem`, and the cleanup pipeline then
leaves the decompiler output untouched instead of guessing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Iterator, Optional


class SyntaxProblem(Exception):
    """The source uses syntax this module does not handle."""


# --------------------------------------------------------------------------- #
# Lexer
# --------------------------------------------------------------------------- #

KEYWORDS = frozenset(
    "and break do else elseif end false for function if in local nil not or "
    "repeat return then true until while".split()
)

_NUMBER = re.compile(
    r"0[xX][0-9a-fA-F_]+|0[bB][01_]+"
    r"|(?:\d[\d_]*(?:\.(?!\.)[\d_]*)?|\.\d[\d_]*)(?:[eE][+-]?\d[\d_]*)?"
)
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_LONG_BRACKET = re.compile(r"\[(=*)\[")
_OPERATORS = ("...", "..=", "//=", "==", "~=", "<=", ">=", "..", "::", "->",
              "+=", "-=", "*=", "/=", "%=", "^=", "//")
_SINGLE_CHAR_OPERATORS = "+-*/%^#&<>=(){}[];:,.|?~"


@dataclass(slots=True)
class Token:
    kind: str  # name | keyword | number | string | interp | op | comment | eof
    text: str
    line: int


def tokenize(source: str) -> list[Token]:
    tokens: list[Token] = []
    position = 0
    line = 1
    while position < len(source):
        char = source[position]
        if char == "\n":
            line += 1
            position += 1
            continue
        if char in " \t\r\f\v":
            position += 1
            continue
        kind, end = _scan_token(source, position)
        text = source[position:end]
        tokens.append(Token(kind, text, line))
        line += text.count("\n")
        position = end
    tokens.append(Token("eof", "", line))
    return tokens


def _scan_token(source: str, start: int) -> tuple[str, int]:
    char = source[start]
    if source.startswith("--", start):
        return "comment", _scan_comment(source, start)
    if char == "[":
        long_end = _scan_long_bracket(source, start)
        if long_end is not None:
            return "string", long_end
    if char in "\"'":
        return "string", _scan_quoted(source, start)
    if char == "`":
        return "interp", _scan_interpolated(source, start)

    number = _NUMBER.match(source, start)
    if number:
        return "number", number.end()

    name = _NAME.match(source, start)
    if name:
        return ("keyword" if name.group() in KEYWORDS else "name"), name.end()

    for operator in _OPERATORS:
        if source.startswith(operator, start):
            return "op", start + len(operator)
    if char in _SINGLE_CHAR_OPERATORS:
        return "op", start + 1
    raise SyntaxProblem(f"unexpected character {char!r}")


def _scan_comment(source: str, start: int) -> int:
    long_end = _scan_long_bracket(source, start + 2)
    if long_end is not None:
        return long_end
    newline = source.find("\n", start)
    return len(source) if newline < 0 else newline


def _scan_long_bracket(source: str, start: int) -> Optional[int]:
    opening = _LONG_BRACKET.match(source, start)
    if not opening:
        return None
    closing = "]" + opening.group(1) + "]"
    index = source.find(closing, opening.end())
    if index < 0:
        raise SyntaxProblem("unfinished long bracket")
    return index + len(closing)


def _scan_quoted(source: str, start: int) -> int:
    quote = source[start]
    index = start + 1
    while index < len(source):
        char = source[index]
        if char == "\\":
            index = _skip_escape(source, index)
            continue
        if char == quote:
            return index + 1
        if char == "\n":
            break
        index += 1
    raise SyntaxProblem("unfinished string")


def _skip_escape(source: str, index: int) -> int:
    """Index just past the escape sequence that starts at `source[index]` (a backslash)."""
    escaped = source[index + 1:index + 2]
    if escaped == "z":  # `\z` swallows all following whitespace, newlines included
        index += 2
        while index < len(source) and source[index] in " \t\r\n\f\v":
            index += 1
        return index
    if source.startswith("\r\n", index + 1):
        return index + 3
    return index + 2


def _scan_interpolated(source: str, start: int) -> int:
    depth = 0
    index = start + 1
    while index < len(source):
        char = source[index]
        if char == "\\":
            index += 2
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif char == "`" and depth == 0:
            return index + 1
        elif char in "\"'" and depth > 0:
            index = _scan_quoted(source, index)
            continue
        index += 1
    raise SyntaxProblem("unfinished interpolated string")


# --------------------------------------------------------------------------- #
# Syntax tree
# --------------------------------------------------------------------------- #

class Node:
    """Base class. Statements may carry the comments written above them."""

    comments: tuple[str, ...] | list[str] = ()


@dataclass(eq=False)
class Decl:
    """A variable declaration; every `Name` that refers to it points here."""

    name: str
    kind: str  # local | param | loop | function | self
    original: str = ""
    scope: object = None
    refs: list = field(default_factory=list)
    hint: Optional[Callable[[], Optional[str]]] = None

    def __post_init__(self) -> None:
        self.original = self.original or self.name


# Expressions -------------------------------------------------------------- #

@dataclass(eq=False)
class Const(Node):
    text: str  # nil | true | false


@dataclass(eq=False)
class Number(Node):
    text: str


@dataclass(eq=False)
class Str(Node):
    text: str  # raw token, quotes included


@dataclass(eq=False)
class Interp(Node):
    text: str


@dataclass(eq=False)
class Vararg(Node):
    pass


@dataclass(eq=False)
class Name(Node):
    ident: str
    decl: Optional[Decl] = None
    scope: object = None


@dataclass(eq=False)
class Field(Node):
    obj: Node
    name: str


@dataclass(eq=False)
class Index(Node):
    obj: Node
    key: Node


@dataclass(eq=False)
class Call(Node):
    fn: Node
    args: list


@dataclass(eq=False)
class Method(Node):
    obj: Node
    name: str
    args: list


@dataclass(eq=False)
class Binary(Node):
    op: str
    left: Node
    right: Node


@dataclass(eq=False)
class Unary(Node):
    op: str
    operand: Node


@dataclass(eq=False)
class Paren(Node):
    inner: Node


@dataclass(eq=False)
class TableItem(Node):
    kind: str  # pos | name | expr
    key: object  # str for `name`, expression for `expr`, None for `pos`
    value: Node


@dataclass(eq=False)
class TableExpr(Node):
    items: list


@dataclass(eq=False)
class IfExpr(Node):
    arms: list  # [(condition, value), ...]
    orelse: Node


@dataclass(eq=False)
class Block(Node):
    stmts: list
    trailing: list = field(default_factory=list)


@dataclass(eq=False)
class FuncExpr(Node):
    params: list
    vararg: bool
    body: Block
    self_decl: Optional[Decl] = None


# Statements --------------------------------------------------------------- #

@dataclass(eq=False)
class Local(Node):
    decls: list
    values: list


@dataclass(eq=False)
class LocalFunction(Node):
    decl: Decl
    func: FuncExpr


@dataclass(eq=False)
class FunctionStmt(Node):
    target: Node
    method: Optional[str]
    func: FuncExpr


@dataclass(eq=False)
class Assign(Node):
    targets: list
    values: list


@dataclass(eq=False)
class CompoundAssign(Node):
    target: Node
    op: str
    value: Node


@dataclass(eq=False)
class CallStmt(Node):
    call: Node


@dataclass(eq=False)
class If(Node):
    arms: list  # [(condition, Block), ...]
    orelse: Optional[Block]


@dataclass(eq=False)
class While(Node):
    cond: Node
    body: Block


@dataclass(eq=False)
class Repeat(Node):
    body: Block
    cond: Node


@dataclass(eq=False)
class NumericFor(Node):
    var: Decl
    start: Node
    stop: Node
    step: Optional[Node]
    body: Block


@dataclass(eq=False)
class GenericFor(Node):
    vars: list
    exprs: list
    body: Block


@dataclass(eq=False)
class Do(Node):
    body: Block


@dataclass(eq=False)
class Return(Node):
    values: list


@dataclass(eq=False)
class Break(Node):
    pass


@dataclass(eq=False)
class Continue(Node):
    pass


@dataclass(eq=False)
class Chunk(Node):
    body: Block


EXPRESSION_TYPES = (Const, Number, Str, Interp, Vararg, Name, Field, Index, Call,
                    Method, Binary, Unary, Paren, TableExpr, IfExpr, FuncExpr)


def children(node: Node) -> list[Node]:
    """Direct children of `node` in (approximate) source order, blocks flattened."""
    match node:
        case Chunk(body=body) | Do(body=body):
            return list(body.stmts)
        case Local(values=values) | Return(values=values):
            return list(values)
        case LocalFunction(func=func):
            return [func]
        case FunctionStmt(target=target, func=func):
            return [target, func]
        case Assign(targets=targets, values=values):
            return [*targets, *values]
        case CompoundAssign(target=target, value=value):
            return [target, value]
        case CallStmt(call=call):
            return [call]
        case If(arms=arms, orelse=orelse):
            nodes: list[Node] = []
            for condition, block in arms:
                nodes.append(condition)
                nodes.extend(block.stmts)
            if orelse is not None:
                nodes.extend(orelse.stmts)
            return nodes
        case While(cond=cond, body=body):
            return [cond, *body.stmts]
        case Repeat(body=body, cond=cond):
            return [*body.stmts, cond]
        case NumericFor(start=start, stop=stop, step=step, body=body):
            return [start, stop, *([step] if step else []), *body.stmts]
        case GenericFor(exprs=exprs, body=body):
            return [*exprs, *body.stmts]
        case Field(obj=obj) | Paren(inner=obj) | Unary(operand=obj):
            return [obj]
        case Index(obj=obj, key=key):
            return [obj, key]
        case Call(fn=fn, args=args):
            return [fn, *args]
        case Method(obj=obj, args=args):
            return [obj, *args]
        case Binary(left=left, right=right):
            return [left, right]
        case FuncExpr(body=body):
            return list(body.stmts)
        case TableExpr(items=items):
            nodes = []
            for item in items:
                if item.kind == "expr":
                    nodes.append(item.key)
                nodes.append(item.value)
            return nodes
        case IfExpr(arms=arms, orelse=orelse):
            return [*(part for arm in arms for part in arm), orelse]
        case _:
            return []


def iter_nodes(node: Node) -> Iterator[Node]:
    """Pre-order walk over every statement and expression below `node`."""
    for child in children(node):
        yield child
        yield from iter_nodes(child)


def iter_blocks(node: Node) -> Iterator[Block]:
    """Every `Block` below (and including, for a chunk) `node`."""
    if isinstance(node, Chunk):
        yield node.body
    for child in iter_nodes(node):
        yield from _blocks_of(child)


def _blocks_of(node: Node) -> list[Block]:
    match node:
        case If(arms=arms, orelse=orelse):
            blocks = [block for _, block in arms]
            return blocks + ([orelse] if orelse else [])
        case While(body=body) | Repeat(body=body) | NumericFor(body=body) \
                | GenericFor(body=body) | Do(body=body) | FuncExpr(body=body):
            return [body]
        case _:
            return []


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #

BINARY_PRIORITY = {
    "or": (1, 1), "and": (2, 2),
    "<": (3, 3), ">": (3, 3), "<=": (3, 3), ">=": (3, 3), "~=": (3, 3), "==": (3, 3),
    "..": (5, 4), "+": (6, 6), "-": (6, 6),
    "*": (7, 7), "/": (7, 7), "//": (7, 7), "%": (7, 7), "^": (10, 9),
}
UNARY_PRIORITY = 8
COMPOUND_OPERATORS = frozenset({"+=", "-=", "*=", "/=", "//=", "%=", "^=", "..="})
_BLOCK_END = frozenset({"end", "else", "elseif", "until"})
_CONTINUE_BLOCKERS = frozenset({"=", ".", ":", "(", "[", ",", "{"}) | COMPOUND_OPERATORS


def parse(source: str) -> Chunk:
    return Parser(tokenize(source)).parse_chunk()


class Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens: list[Token] = []
        self.comments_before: dict[int, list[str]] = {}
        pending: list[str] = []
        for token in tokens:
            if token.kind == "comment":
                pending.append(token.text)
                continue
            if pending:
                self.comments_before[len(self.tokens)] = pending
                pending = []
            self.tokens.append(token)
        self.position = 0

    # -- token helpers ------------------------------------------------------ #

    def peek(self, offset: int = 0) -> Token:
        return self.tokens[min(self.position + offset, len(self.tokens) - 1)]

    def advance(self) -> Token:
        token = self.tokens[self.position]
        if token.kind != "eof":
            self.position += 1
        return token

    def check(self, text: str) -> bool:
        token = self.peek()
        return token.text == text and token.kind in ("op", "keyword")

    def accept(self, text: str) -> bool:
        if not self.check(text):
            return False
        self.advance()
        return True

    def fail(self, message: str) -> SyntaxProblem:
        token = self.peek()
        return SyntaxProblem(f"line {token.line}: {message} (found {token.text!r})")

    def expect(self, text: str) -> Token:
        if not self.check(text):
            raise self.fail(f"expected {text!r}")
        return self.advance()

    def expect_name(self) -> str:
        if self.peek().kind != "name":
            raise self.fail("expected a name")
        return self.advance().text

    def at_block_end(self) -> bool:
        token = self.peek()
        return token.kind == "eof" or (token.kind == "keyword" and token.text in _BLOCK_END)

    # -- blocks and statements ---------------------------------------------- #

    def parse_chunk(self) -> Chunk:
        body = self.block()
        if self.peek().kind != "eof":
            raise self.fail("unexpected token")
        return Chunk(body)

    def block(self) -> Block:
        statements: list[Node] = []
        while True:
            while self.accept(";"):
                pass
            if self.at_block_end():
                break
            statement = self.statement()
            statements.append(statement)
            if isinstance(statement, (Return,)):
                while self.accept(";"):
                    pass
                if not self.at_block_end():
                    raise self.fail("`return` must be the last statement of a block")
                break
        return Block(statements, list(self.comments_before.get(self.position, ())))

    def statement(self) -> Node:
        comments = list(self.comments_before.get(self.position, ()))
        statement = self._statement()
        statement.comments = comments
        return statement

    def _statement(self) -> Node:
        token = self.peek()
        if self._is_type_declaration():
            raise self.fail("type declarations are not supported")
        if token.kind == "keyword":
            handler = self._keyword_statements().get(token.text)
            if handler:
                return handler()
        if self._is_continue():
            self.advance()
            return Continue()
        return self.expression_statement()

    def _keyword_statements(self) -> dict[str, Callable[[], Node]]:
        return {
            "if": self.if_statement, "while": self.while_statement,
            "do": self.do_statement, "for": self.for_statement,
            "repeat": self.repeat_statement, "function": self.function_statement,
            "local": self.local_statement, "return": self.return_statement,
            "break": self._break_statement,
        }

    def _break_statement(self) -> Node:
        self.advance()
        return Break()

    def _is_continue(self) -> bool:
        token = self.peek()
        if token.kind != "name" or token.text != "continue":
            return False
        following = self.peek(1)
        if following.kind in ("string", "interp"):
            return False
        return not (following.kind == "op" and following.text in _CONTINUE_BLOCKERS)

    def _is_type_declaration(self) -> bool:
        token = self.peek()
        if token.kind != "name":
            return False
        following = self.peek(1)
        if token.text == "type":
            return following.kind == "name" and self.peek(2).text in ("=", "<")
        return token.text == "export" and following.text == "type"

    def if_statement(self) -> Node:
        self.expect("if")
        arms = []
        while True:
            condition = self.expr()
            self.expect("then")
            arms.append((condition, self.block()))
            if not self.accept("elseif"):
                break
        orelse = self.block() if self.accept("else") else None
        self.expect("end")
        return If(arms, orelse)

    def while_statement(self) -> Node:
        self.expect("while")
        condition = self.expr()
        self.expect("do")
        body = self.block()
        self.expect("end")
        return While(condition, body)

    def do_statement(self) -> Node:
        self.expect("do")
        body = self.block()
        self.expect("end")
        return Do(body)

    def repeat_statement(self) -> Node:
        self.expect("repeat")
        body = self.block()
        self.expect("until")
        return Repeat(body, self.expr())

    def for_statement(self) -> Node:
        self.expect("for")
        first = self.expect_name()
        if self.check(":"):
            raise self.fail("type annotations are not supported")
        if self.accept("="):
            return self._numeric_for(first)
        return self._generic_for(first)

    def _numeric_for(self, variable: str) -> Node:
        start = self.expr()
        self.expect(",")
        stop = self.expr()
        step = self.expr() if self.accept(",") else None
        self.expect("do")
        body = self.block()
        self.expect("end")
        return NumericFor(Decl(variable, "loop"), start, stop, step, body)

    def _generic_for(self, first: str) -> Node:
        names = [first]
        while self.accept(","):
            names.append(self.expect_name())
        self.expect("in")
        expressions = self.expression_list()
        self.expect("do")
        body = self.block()
        self.expect("end")
        return GenericFor([Decl(name, "loop") for name in names], expressions, body)

    def function_statement(self) -> Node:
        self.expect("function")
        target: Node = Name(self.expect_name())
        method = None
        while True:
            if self.accept("."):
                target = Field(target, self.expect_name())
            elif self.accept(":"):
                method = self.expect_name()
                break
            else:
                break
        return FunctionStmt(target, method, self.function_body(is_method=method is not None))

    def local_statement(self) -> Node:
        self.expect("local")
        if self.accept("function"):
            name = self.expect_name()
            return LocalFunction(Decl(name, "function"), self.function_body())
        names = [self._declared_name()]
        while self.accept(","):
            names.append(self._declared_name())
        values = self.expression_list() if self.accept("=") else []
        return Local([Decl(name, "local") for name in names], values)

    def _declared_name(self) -> str:
        name = self.expect_name()
        if self.check(":") or self.check("<"):
            raise self.fail("type annotations and attributes are not supported")
        return name

    def return_statement(self) -> Node:
        self.expect("return")
        if self.at_block_end() or self.check(";"):
            return Return([])
        return Return(self.expression_list())

    def expression_statement(self) -> Node:
        first = self.suffixed_expression()
        token = self.peek()
        if token.kind == "op" and token.text in (",", "="):
            return self._assignment(first)
        if token.kind == "op" and token.text in COMPOUND_OPERATORS:
            self._require_assignable(first)
            self.advance()
            return CompoundAssign(first, token.text, self.expr())
        if not isinstance(first, (Call, Method)):
            raise self.fail("expected a statement")
        return CallStmt(first)

    def _assignment(self, first: Node) -> Node:
        targets = [first]
        while self.accept(","):
            targets.append(self.suffixed_expression())
        self.expect("=")
        for target in targets:
            self._require_assignable(target)
        return Assign(targets, self.expression_list())

    def _require_assignable(self, target: Node) -> None:
        if not isinstance(target, (Name, Field, Index)):
            raise self.fail("cannot assign to this expression")

    # -- functions ---------------------------------------------------------- #

    def function_body(self, is_method: bool = False) -> FuncExpr:
        self.expect("(")
        params: list[Decl] = []
        vararg = False
        while not self.check(")"):
            if self.accept("..."):
                vararg = True
                break
            params.append(Decl(self.expect_name(), "param"))
            if self.check(":"):
                raise self.fail("type annotations are not supported")
            if not self.accept(","):
                break
        self.expect(")")
        if self.check(":"):
            raise self.fail("return type annotations are not supported")
        body = self.block()
        self.expect("end")
        self_decl = Decl("self", "self") if is_method else None
        return FuncExpr(params, vararg, body, self_decl)

    # -- expressions -------------------------------------------------------- #

    def expression_list(self) -> list[Node]:
        expressions = [self.expr()]
        while self.accept(","):
            expressions.append(self.expr())
        return expressions

    def expr(self, limit: int = 0) -> Node:
        token = self.peek()
        if self._is_unary(token):
            self.advance()
            left: Node = Unary(token.text, self.expr(UNARY_PRIORITY))
        else:
            left = self.simple_expression()
        while True:
            operator = self._binary_operator()
            if operator is None:
                return left
            left_priority, right_priority = BINARY_PRIORITY[operator]
            if left_priority <= limit:
                return left
            self.advance()
            left = Binary(operator, left, self.expr(right_priority))

    @staticmethod
    def _is_unary(token: Token) -> bool:
        if token.kind == "keyword":
            return token.text == "not"
        return token.kind == "op" and token.text in ("-", "#")

    def _binary_operator(self) -> Optional[str]:
        token = self.peek()
        if token.kind in ("op", "keyword") and token.text in BINARY_PRIORITY:
            return token.text
        return None

    def simple_expression(self) -> Node:
        token = self.peek()
        if token.kind == "number":
            return Number(self.advance().text)
        if token.kind == "string":
            return Str(self.advance().text)
        if token.kind == "interp":
            return Interp(self.advance().text)
        if token.kind == "keyword" and token.text in ("nil", "true", "false"):
            return Const(self.advance().text)
        if self.accept("..."):
            return Vararg()
        if self.check("{"):
            return self.table_constructor()
        if self.accept("function"):
            return self.function_body()
        if self.accept("if"):
            return self._if_expression()
        return self.suffixed_expression()

    def _if_expression(self) -> Node:
        arms = []
        while True:
            condition = self.expr()
            self.expect("then")
            arms.append((condition, self.expr()))
            if not self.accept("elseif"):
                break
        self.expect("else")
        return IfExpr(arms, self.expr())

    def primary_expression(self) -> Node:
        token = self.peek()
        if token.kind == "name":
            self.advance()
            return Name(token.text)
        if self.accept("("):
            inner = self.expr()
            self.expect(")")
            return Paren(inner)
        raise self.fail("expected an expression")

    def suffixed_expression(self) -> Node:
        expression = self.primary_expression()
        while True:
            token = self.peek()
            if token.kind in ("string", "interp") or (token.kind == "op" and token.text in ("(", "{")):
                expression = Call(expression, self.call_arguments())
            elif self.accept("."):
                expression = Field(expression, self.expect_name())
            elif self.accept("["):
                key = self.expr()
                self.expect("]")
                expression = Index(expression, key)
            elif self.accept(":"):
                name = self.expect_name()
                expression = Method(expression, name, self.call_arguments())
            else:
                return expression

    def call_arguments(self) -> list[Node]:
        token = self.peek()
        if token.kind == "string":
            return [Str(self.advance().text)]
        if token.kind == "interp":
            return [Interp(self.advance().text)]
        if self.check("{"):
            return [self.table_constructor()]
        self.expect("(")
        arguments: list[Node] = []
        if not self.check(")"):
            arguments = self.expression_list()
        self.expect(")")
        return arguments

    def table_constructor(self) -> Node:
        self.expect("{")
        items: list[TableItem] = []
        while not self.check("}"):
            items.append(self._table_item())
            if not (self.accept(",") or self.accept(";")):
                break
        self.expect("}")
        return TableExpr(items)

    def _table_item(self) -> TableItem:
        if self.accept("["):
            key = self.expr()
            self.expect("]")
            self.expect("=")
            return TableItem("expr", key, self.expr())
        following = self.peek(1)
        if self.peek().kind == "name" and following.kind == "op" and following.text == "=":
            name = self.advance().text
            self.advance()
            return TableItem("name", name, self.expr())
        return TableItem("pos", None, self.expr())
