"""Post-process decompiler output into clean, readable Luau.

    parse -> rename -> cache services -> flatten control flow -> verify -> print

The stage can never make the result worse: if the source uses syntax the parser
does not know, or any check below fails, the original text is returned as-is.
"""

from __future__ import annotations

from dataclasses import dataclass

from .flow import flatten_control_flow
from .naming import rename_generic_names
from .printer import print_chunk
from .scopes import Resolver
from .services import hoist_services
from .syntax import SyntaxProblem, parse

STRICT_HEADER = "--!strict\n"


@dataclass(frozen=True)
class CleanupOptions:
    rename: bool = True
    cache_services: bool = True
    flatten: bool = True
    strict_header: bool = False  # decompiled code has no type annotations; off by default


@dataclass(frozen=True)
class CleanupResult:
    source: str
    cleaned: bool
    note: str = ""


def clean_source(source: str, options: CleanupOptions = CleanupOptions()) -> CleanupResult:
    try:
        return _clean(source, options)
    except SyntaxProblem as problem:
        return CleanupResult(source, False, f"skipped: {problem}")
    except RecursionError:
        return CleanupResult(source, False, "skipped: script is nested too deeply")
    except Exception as error:  # noqa: BLE001 - cleanup must never break decompilation
        return CleanupResult(source, False, f"skipped: internal error {type(error).__name__}")


def _clean(source: str, options: CleanupOptions) -> CleanupResult:
    chunk = parse(source)
    resolver = Resolver(bind=True).run(chunk)
    if options.rename:
        rename_generic_names(chunk, resolver)
    if options.cache_services:
        hoist_services(chunk, resolver)
    if options.flatten:
        flatten_control_flow(chunk)

    if Resolver(bind=False).run(chunk).mismatches:
        return CleanupResult(source, False, "skipped: a name would change meaning")

    text = print_chunk(chunk)
    parse(text)  # the output must be valid input for our own parser
    if options.strict_header and not text.startswith("--!"):
        text = STRICT_HEADER + text
    return CleanupResult(text, True)
