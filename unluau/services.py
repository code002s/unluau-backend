"""Cache Roblox services once at the top of the script.

`game:GetService("Players")` repeated inside functions (or re-bound to a local in
every function) becomes a single `local Players = game:GetService("Players")`
at the top. Only well-known service names are hoisted, so the moved call can
never raise; a service is skipped when its name is already taken by anything else.
"""

from __future__ import annotations

from dataclasses import fields
from typing import Callable, Optional

from .scopes import Resolver
from .syntax import (
    Assign, Block, Chunk, CompoundAssign, Decl, FunctionStmt, Local, Method, Name,
    Node, Str, iter_blocks, iter_nodes,
)

KNOWN_SERVICES = frozenset("""
    AnalyticsService AssetService BadgeService Chat CollectionService ContentProvider
    ContextActionService DataStoreService Debris GuiService HttpService
    InsertService LocalizationService Lighting MarketplaceService MessagingService
    PathfindingService PhysicsService Players PolicyService ProximityPromptService
    ReplicatedFirst ReplicatedStorage RunService ScriptContext ServerScriptService
    ServerStorage SocialService SoundService StarterGui StarterPack StarterPlayer
    Stats TeleportService TextChatService TextService TweenService UserInputService
    UserService VRService VoiceChatService Workspace
""".split())


def hoist_services(chunk: Chunk, resolver: Resolver) -> int:
    """Hoist service lookups. Returns how many services were hoisted."""
    assigned = _assigned_decls(chunk)
    aliases = _alias_statements(chunk, assigned)
    inline_calls = _service_calls(chunk)
    hoisted: dict[str, Decl] = {}

    for service in sorted({service for _, service in aliases} | set(inline_calls)):
        alias_decls = {statement.decls[0] for statement, name in aliases if name == service}
        if service not in inline_calls and not any(decl.refs for decl in alias_decls):
            continue  # only bound to unused locals: nothing worth caching
        if _name_is_taken(service, resolver, alias_decls):
            continue
        hoisted[service] = Decl(service, "local")

    if not hoisted:
        return 0
    _redirect_aliases(chunk, aliases, hoisted)
    _replace_inline_calls(chunk, hoisted)
    _insert_declarations(chunk, hoisted)
    return len(hoisted)


# -- discovery ------------------------------------------------------------------ #

def _service_name(node: Node) -> Optional[str]:
    match node:
        case Method(obj=Name(ident="game", decl=None), name="GetService", args=[Str(text=text)]):
            name = text[1:-1] if text[:1] in "\"'" else ""
            return name if name in KNOWN_SERVICES else None
    return None


def _assigned_decls(chunk: Chunk) -> set[Decl]:
    assigned: set[Decl] = set()
    for node in iter_nodes(chunk):
        match node:
            case Assign(targets=targets):
                assigned.update(t.decl for t in targets if isinstance(t, Name) and t.decl)
            case CompoundAssign(target=Name(decl=Decl() as decl)):
                assigned.add(decl)
            case FunctionStmt(target=Name(decl=Decl() as decl)):
                assigned.add(decl)
    return assigned


def _alias_statements(chunk: Chunk, assigned: set[Decl]) -> list[tuple[Local, str]]:
    aliases = []
    for node in iter_nodes(chunk):
        match node:
            case Local(decls=[decl], values=[value]) if decl not in assigned:
                service = _service_name(value)
                if service:
                    aliases.append((node, service))
    return aliases


def _service_calls(chunk: Chunk) -> dict[str, int]:
    counts: dict[str, int] = {}
    for node in iter_nodes(chunk):
        service = _service_name(node)
        if service:
            counts[service] = counts.get(service, 0) + 1
    return counts


def _name_is_taken(name: str, resolver: Resolver, allowed: set[Decl]) -> bool:
    if any(decl.name == name and decl not in allowed for decl in resolver.decls):
        return True
    return any(reference.ident == name for reference in resolver.free_names)


# -- rewriting ------------------------------------------------------------------ #

def _redirect_aliases(chunk: Chunk, aliases: list[tuple[Local, str]], hoisted: dict[str, Decl]) -> None:
    removed = set()
    for statement, service in aliases:
        target = hoisted.get(service)
        if target is None:
            continue
        for reference in statement.decls[0].refs:
            reference.decl = target
        removed.add(statement)
    for block in iter_blocks(chunk):
        _remove_statements(block, removed)


def _remove_statements(block: Block, removed: set) -> None:
    kept: list[Node] = []
    carried: list[str] = []
    for statement in block.stmts:
        if statement in removed:
            carried.extend(statement.comments)
            continue
        if carried:
            statement.comments = [*carried, *statement.comments]
            carried = []
        kept.append(statement)
    block.stmts = kept
    block.trailing = [*carried, *block.trailing]


def _replace_inline_calls(chunk: Chunk, hoisted: dict[str, Decl]) -> None:
    def replace(node: Node) -> Node:
        service = _service_name(node)
        if service in hoisted:
            return Name(service, decl=hoisted[service])
        return node

    rewrite_expressions(chunk, replace)


def _insert_declarations(chunk: Chunk, hoisted: dict[str, Decl]) -> None:
    declarations: list[Node] = []
    for service, decl in sorted(hoisted.items()):
        call = Method(Name("game"), "GetService", [Str(f'"{service}"')])
        declarations.append(Local([decl], [call]))
    stmts = chunk.body.stmts
    if stmts and stmts[0].comments:
        declarations[0].comments = stmts[0].comments
        stmts[0].comments = []
    chunk.body.stmts = declarations + stmts


def rewrite_expressions(node: Node, replace: Callable[[Node], Node]) -> Node:
    """Post-order, in-place rewrite of every expression below `node`."""
    for field in fields(node):
        setattr(node, field.name, _rewrite_value(getattr(node, field.name), replace))
    return replace(node)


def _rewrite_value(value, replace):
    if isinstance(value, Node):
        return rewrite_expressions(value, replace)
    if isinstance(value, list):
        return [_rewrite_value(item, replace) for item in value]
    if isinstance(value, tuple):
        return tuple(_rewrite_value(item, replace) for item in value)
    return value
