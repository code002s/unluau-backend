"""Scope resolution: which declaration does every `Name` refer to?

`Resolver(bind=True)` records the answer on the tree (`Name.decl`, `Decl.refs`).
`Resolver(bind=False)` re-resolves using the *current* variable names and counts
how many references would now point somewhere else. After any rename or
restructuring a count of zero proves that no name was captured or shadowed.
"""

from __future__ import annotations

from typing import Optional

from .syntax import (
    Assign, Block, Call, Chunk, CompoundAssign, CallStmt, Decl, Do, Field,
    FuncExpr, FunctionStmt, GenericFor, If, IfExpr, Index, Local,
    LocalFunction, Method, Name, Node, NumericFor, Paren, Repeat, Return,
    TableExpr, Binary, Unary, While,
)


class Scope:
    __slots__ = ("parent", "names")

    def __init__(self, parent: Optional["Scope"]) -> None:
        self.parent = parent
        self.names: dict[str, Decl] = {}

    def lookup(self, name: str) -> Optional[Decl]:
        scope: Optional[Scope] = self
        while scope is not None:
            found = scope.names.get(name)
            if found is not None:
                return found
            scope = scope.parent
        return None


def scope_within(inner: Optional[Scope], outer: Optional[Scope]) -> bool:
    """True when `inner` is `outer` or nested anywhere below it."""
    while inner is not None:
        if inner is outer:
            return True
        inner = inner.parent
    return False


class Resolver:
    def __init__(self, bind: bool = True) -> None:
        self.bind = bind
        self.root = Scope(None)
        self.decls: list[Decl] = []
        self.free_names: list[Name] = []
        self.mismatches = 0

    def run(self, chunk: Chunk) -> "Resolver":
        self._statements(chunk.body, self.root)
        return self

    # -- declarations and references ---------------------------------------- #

    def _declare(self, decl: Decl, scope: Scope) -> None:
        scope.names[decl.name] = decl
        if self.bind:
            decl.scope = scope
            decl.refs = []
            self.decls.append(decl)

    def _reference(self, name: Name, scope: Scope) -> None:
        printed = name.decl.name if name.decl else name.ident
        found = scope.lookup(printed)
        if not self.bind:
            if found is not name.decl:
                self.mismatches += 1
            return
        name.decl = found
        name.scope = scope
        if found is None:
            self.free_names.append(name)
            return
        found.refs.append(name)

    # -- statements --------------------------------------------------------- #

    def _statements(self, block: Block, scope: Scope) -> None:
        for statement in block.stmts:
            self._statement(statement, scope)

    def _child_block(self, block: Block, scope: Scope) -> None:
        self._statements(block, Scope(scope))

    def _statement(self, node: Node, scope: Scope) -> None:
        match node:
            case Local(decls=decls, values=values):
                self._expressions(values, scope)
                for decl in decls:
                    self._declare(decl, scope)
            case LocalFunction(decl=decl, func=func):
                self._declare(decl, scope)
                self._expression(func, scope)
            case FunctionStmt(target=target, func=func):
                self._expression(target, scope)
                self._expression(func, scope)
            case Assign(targets=targets, values=values):
                self._expressions([*targets, *values], scope)
            case CompoundAssign(target=target, value=value):
                self._expressions([target, value], scope)
            case CallStmt(call=call):
                self._expression(call, scope)
            case If(arms=arms, orelse=orelse):
                for condition, block in arms:
                    self._expression(condition, scope)
                    self._child_block(block, scope)
                if orelse is not None:
                    self._child_block(orelse, scope)
            case While(cond=cond, body=body):
                self._expression(cond, scope)
                self._child_block(body, scope)
            case Repeat(body=body, cond=cond):
                inner = Scope(scope)
                self._statements(body, inner)
                self._expression(cond, inner)
            case NumericFor(var=var, start=start, stop=stop, step=step, body=body):
                self._expressions([start, stop, *([step] if step else [])], scope)
                loop_scope = Scope(scope)
                self._declare(var, loop_scope)
                self._child_block(body, loop_scope)
            case GenericFor(vars=variables, exprs=exprs, body=body):
                self._expressions(exprs, scope)
                loop_scope = Scope(scope)
                for variable in variables:
                    self._declare(variable, loop_scope)
                self._child_block(body, loop_scope)
            case Do(body=body):
                self._child_block(body, scope)
            case Return(values=values):
                self._expressions(values, scope)

    # -- expressions -------------------------------------------------------- #

    def _expressions(self, nodes: list[Node], scope: Scope) -> None:
        for node in nodes:
            self._expression(node, scope)

    def _expression(self, node: Node, scope: Scope) -> None:
        match node:
            case Name():
                self._reference(node, scope)
            case FuncExpr():
                self._function(node, scope)
            case Field(obj=obj) | Paren(inner=obj) | Unary(operand=obj):
                self._expression(obj, scope)
            case Index(obj=obj, key=key):
                self._expressions([obj, key], scope)
            case Call(fn=fn, args=args):
                self._expressions([fn, *args], scope)
            case Method(obj=obj, args=args):
                self._expressions([obj, *args], scope)
            case Binary(left=left, right=right):
                self._expressions([left, right], scope)
            case TableExpr(items=items):
                for item in items:
                    if item.kind == "expr":
                        self._expression(item.key, scope)
                    self._expression(item.value, scope)
            case IfExpr(arms=arms, orelse=orelse):
                for condition, value in arms:
                    self._expressions([condition, value], scope)
                self._expression(orelse, scope)

    def _function(self, func: FuncExpr, scope: Scope) -> None:
        function_scope = Scope(scope)
        if func.self_decl is not None:
            self._declare(func.self_decl, function_scope)
        for param in func.params:
            self._declare(param, function_scope)
        self._child_block(func.body, function_scope)
