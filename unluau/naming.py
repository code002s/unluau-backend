"""Replace decompiler-style names (`result2`, `Parent3`, `v1`, ...) with meaningful ones.

Names are only ever *suggested* from what a variable is initialised with
(`game:GetService("Players")` -> `Players`, `Instance.new("Frame")` -> `frame`)
or from the event it is a callback parameter of. A suggestion is applied only if
it cannot capture, shadow or be shadowed by any other name in the script.
Names that look intentional (recovered from debug info) are never touched.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Optional

from .scopes import Resolver, Scope, scope_within
from .syntax import (
    KEYWORDS, Assign, Binary, Call, Chunk, Decl, Field, FuncExpr, GenericFor,
    Index, Local, Method, Name, Node, Paren, Str, iter_nodes,
)

RESERVED_NAMES = KEYWORDS | frozenset("""
    game workspace script plugin shared self continue type typeof export
    Instance Vector2 Vector3 CFrame Color3 UDim UDim2 Enum Random Ray Rect Region3
    BrickColor TweenInfo NumberRange NumberSequence ColorSequence Font DateTime
    math string table task os coroutine buffer bit32 utf8 debug
    print warn error assert pcall xpcall select unpack next pairs ipairs
    tostring tonumber setmetatable getmetatable rawget rawset rawequal rawlen
    require tick time wait spawn delay _G _VERSION
""".split())

_GENERIC_NAME = re.compile(r"""^(?:
    [A-Za-z]
  | [A-Za-z]\d+
  | (?:result|value|val|var|upval|num|str|fn|func|tmp|temp|obj|inst|tbl|Parent|new|arg|param|ret|res)_?\d*
  | (?:v|l|L|r|u|p|a|var|upval)_\d+(?:_\d+)?
)$""", re.VERBOSE)

EVENT_PARAMETERS: dict[str, list[str]] = {
    "OnClientEvent": ["data"],
    "OnServerEvent": ["player", "data"],
    "OnClientInvoke": ["data"],
    "OnServerInvoke": ["player", "data"],
    "Heartbeat": ["deltaTime"],
    "RenderStepped": ["deltaTime"],
    "PreRender": ["deltaTime"],
    "PreAnimation": ["deltaTime"],
    "PreSimulation": ["deltaTime"],
    "PostSimulation": ["deltaTime"],
    "Stepped": ["time", "deltaTime"],
    "PlayerAdded": ["player"],
    "PlayerRemoving": ["player"],
    "CharacterAdded": ["character"],
    "CharacterRemoving": ["character"],
    "ChildAdded": ["child"],
    "ChildRemoved": ["child"],
    "DescendantAdded": ["descendant"],
    "DescendantRemoving": ["descendant"],
    "Touched": ["otherPart"],
    "TouchEnded": ["otherPart"],
    "InputBegan": ["input", "gameProcessedEvent"],
    "InputEnded": ["input", "gameProcessedEvent"],
    "InputChanged": ["input", "gameProcessedEvent"],
    "Triggered": ["player"],
    "HealthChanged": ["health"],
    "AncestryChanged": ["child", "parent"],
}
_CONNECT_METHODS = frozenset({"Connect", "Once", "ConnectParallel"})
_EVENT_ASSIGNMENTS = frozenset({"OnClientInvoke", "OnServerInvoke"})

_LOOKUP_BY_NAME = frozenset({
    "WaitForChild", "FindFirstChild", "FindFirstAncestor", "FindFirstDescendant",
    "GetAttribute",
})
_LOOKUP_BY_CLASS = frozenset({
    "FindFirstChildOfClass", "FindFirstChildWhichIsA", "FindFirstAncestorOfClass",
    "FindFirstAncestorWhichIsA",
})
_METHOD_RESULTS = {
    "GetPlayers": "players", "GetChildren": "children", "GetDescendants": "descendants",
    "GetPlayerFromCharacter": "player", "GetMouse": "mouse", "Clone": "clone",
    "Connect": "connection",
}
_FIELD_RESULTS = {"LocalPlayer": "localPlayer", "CurrentCamera": "camera"}
_LOOP_ELEMENTS = {"GetPlayers": "player", "GetChildren": "child", "GetDescendants": "descendant"}
_WRAPPERS = frozenset({"tonumber", "tostring", "require"})
_MAX_SUFFIX = 50


def is_generic_name(name: str) -> bool:
    return bool(_GENERIC_NAME.match(name))


# --------------------------------------------------------------------------- #
# Name suggestions
# --------------------------------------------------------------------------- #

def lower_camel(text: str) -> Optional[str]:
    """`Data Ping` -> `dataPing`, `serverFPS` -> `serverFps`, `UIScale` -> `uiScale`."""
    words = re.findall(r"[A-Za-z0-9]+", text)
    if not words:
        return None
    joined = words[0] + "".join(word[:1].upper() + word[1:] for word in words[1:])
    joined = _lower_leading_acronym(joined)
    joined = re.sub(
        r"(?<=[A-Za-z0-9])([A-Z])([A-Z]+)(?=[A-Z][a-z]|[^A-Za-z]|$)",
        lambda match: match.group(1) + match.group(2).lower(),
        joined,
    )
    if not joined[0].isalpha() or joined in RESERVED_NAMES:
        return None
    return joined


def _lower_leading_acronym(text: str) -> str:
    match = re.match(r"[A-Z]+", text)
    if not match:
        return text
    run = match.group()
    rest = text[len(run):]
    if len(run) == 1:
        return run.lower() + rest
    if rest[:1].islower():
        return run[:-1].lower() + run[-1] + rest
    return run.lower() + rest


def _string_value(node: Node) -> Optional[str]:
    if not isinstance(node, Str) or node.text[:1] not in "\"'" or "\\" in node.text:
        return None
    return node.text[1:-1]


def suggest_name(expression: Node, allow_alias: bool = False) -> Optional[str]:
    """A descriptive variable name for the value of `expression`, if one is obvious."""
    match expression:
        case Method(obj=Name(ident="game", decl=None), name="GetService", args=[service, *_]):
            value = _string_value(service)
            return value if value and value.isidentifier() else None
        case Call(fn=Field(obj=Name(ident="Instance"), name="new"), args=[class_name, *_]):
            return lower_camel(_string_value(class_name) or "")
        case Method(name=name, args=[argument, *_]) if name in _LOOKUP_BY_NAME | _LOOKUP_BY_CLASS:
            return lower_camel(_string_value(argument) or "")
        case Method(name=name):
            return _METHOD_RESULTS.get(name)
        case Field(name=name):
            return _FIELD_RESULTS.get(name) or lower_camel(name)
        case Index(key=key):
            return lower_camel(_string_value(key) or "")
        case Binary(op="or", left=left):
            return suggest_name(left, allow_alias)
        case Call(fn=Name(ident=name), args=[first, *_]) if name in _WRAPPERS:
            return suggest_name(first, allow_alias)
        case Paren(inner=inner):
            return suggest_name(inner, allow_alias)
        case Name(decl=Decl(name=name)) if allow_alias and not is_generic_name(name):
            return name
    return None


def _singular(word: Optional[str]) -> Optional[str]:
    if not word:
        return None
    if word == "children":
        return "child"
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return None


def _loop_hints(loop: GenericFor) -> tuple[Optional[str], Optional[str]]:
    """(key name, value name) suggestions for a generic `for` loop."""
    match loop.exprs:
        case [Method(name=method)] if method in _LOOP_ELEMENTS:
            return None, _LOOP_ELEMENTS[method]
        case [Call(fn=Name(ident="ipairs"), args=[collection])]:
            return "index", _singular(suggest_name(collection, allow_alias=True))
        case [Call(fn=Name(ident="pairs"), args=[collection])] | [Name(ident="next"), collection, *_]:
            return "key", _singular(suggest_name(collection, allow_alias=True))
    return None, None


# --------------------------------------------------------------------------- #
# Hints
# --------------------------------------------------------------------------- #

def _attach_hints(chunk: Chunk) -> None:
    for node in iter_nodes(chunk):
        match node:
            case Local(decls=decls, values=values):
                _hint_initialisers(decls, values)
            case GenericFor():
                _hint_loop(node)
            case Method(name=name, obj=Field(name=event), args=args) if name in _CONNECT_METHODS:
                _hint_callbacks(event, args)
            case Assign(targets=[Field(name=event)], values=[callback]) if event in _EVENT_ASSIGNMENTS:
                _hint_callbacks(event, [callback])


def _hint_initialisers(decls: list[Decl], values: list[Node]) -> None:
    for decl, value in zip(decls, values):
        decl.hint = lambda value=value: suggest_name(value)


def _hint_loop(loop: GenericFor) -> None:
    key_name, value_name = _loop_hints(loop)
    first, *rest = loop.vars
    if rest and not first.refs:
        first.hint = lambda: "_"
    elif key_name:
        first.hint = lambda: key_name
    if rest and value_name:
        rest[0].hint = lambda: value_name
    elif not rest and value_name:
        first.hint = lambda: value_name


def _hint_callbacks(event: str, callbacks: list[Node]) -> None:
    names = EVENT_PARAMETERS.get(event)
    if not names:
        return
    for callback in callbacks:
        if not isinstance(callback, FuncExpr):
            continue
        for param, name in zip(callback.params, names):
            param.hint = lambda name=name: name


# --------------------------------------------------------------------------- #
# Conflict checking
# --------------------------------------------------------------------------- #

class NameTable:
    """Tracks every current variable name so renames stay collision-free."""

    def __init__(self, resolver: Resolver) -> None:
        self.by_name: dict[str, list[Decl]] = defaultdict(list)
        self.free_scopes: dict[str, list[Optional[Scope]]] = defaultdict(list)
        for decl in resolver.decls:
            self.by_name[decl.name].append(decl)
        for reference in resolver.free_names:
            self.free_scopes[reference.ident].append(reference.scope)

    def rename(self, decl: Decl, new_name: str) -> None:
        self.by_name[decl.name].remove(decl)
        decl.name = new_name
        self.by_name[new_name].append(decl)

    def pick(self, decl: Decl, base: str) -> Optional[str]:
        for attempt in range(1, _MAX_SUFFIX):
            candidate = base if attempt == 1 else f"{base}{attempt}"
            if not self.conflicts(decl, candidate):
                return candidate
        return None

    def conflicts(self, decl: Decl, name: str) -> bool:
        if name in RESERVED_NAMES and name != "_":
            return True
        if any(scope_within(scope, decl.scope) for scope in self.free_scopes.get(name, ())):
            return True  # a global with this name is used inside the declaration's scope
        others = (other for other in self.by_name.get(name, ()) if other is not decl)
        if name == "_":
            return any(self._captures(other, decl) for other in others)
        return any(self._related(other, decl) for other in others)

    @staticmethod
    def _related(other: Decl, decl: Decl) -> bool:
        """Visible from, or visible inside, the declaration: avoid shadowing either way."""
        return scope_within(decl.scope, other.scope) or scope_within(other.scope, decl.scope)

    @staticmethod
    def _captures(other: Decl, decl: Decl) -> bool:
        """Would `decl` steal references that currently resolve to `other`?"""
        return any(scope_within(reference.scope, decl.scope) for reference in other.refs)


def rename_generic_names(chunk: Chunk, resolver: Resolver) -> int:
    """Rename decompiler-style variables in place. Returns how many were renamed."""
    _attach_hints(chunk)
    table = NameTable(resolver)
    renamed = 0
    for decl in resolver.decls:
        suggestion = _suggestion_for(decl)
        if suggestion is None or suggestion == decl.name:
            continue
        chosen = table.pick(decl, suggestion)
        if chosen is None or chosen == decl.name:
            continue
        table.rename(decl, chosen)
        renamed += 1
    return renamed


def _suggestion_for(decl: Decl) -> Optional[str]:
    if decl.kind == "self" or decl.hint is None:
        return None
    suggestion = decl.hint()
    if suggestion is None:
        return None
    if suggestion == "_" or is_generic_name(decl.name):
        return suggestion
    return None
