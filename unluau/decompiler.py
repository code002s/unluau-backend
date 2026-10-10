"""Run the unluac-rs CLI on Luau bytecode and clean up its output."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from . import descramble
from .cleanup import CleanupOptions, CleanupResult, clean_source

COMPILE_ERROR_MARKER = 0  # first byte of a Luau "compile error" blob
_NO_RETRY_STATUSES = (400, 504)


class Failure(Exception):
    """A decompile problem that maps directly onto an HTTP status."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass(frozen=True)
class DecompileConfig:
    binary: str = "/usr/local/bin/unluac-cli"
    timeout_seconds: int = 25
    cleanup: CleanupOptions = CleanupOptions()

    @property
    def cli_args(self) -> list[str]:
        return [
            self.binary, "-D", "luau",
            "-i", "-",
            "-n", "heuristic",     # readable fallback names
            "-g", "permissive",    # pseudo-code for control flow it cannot structure
            "--comment", "false",
            "--luau-vector-library", "Vector3",   # Roblox's Vector3 constants
            "--luau-vector-constructor", "new",
            "--luau-vector-size", "3",
        ]


@dataclass(frozen=True)
class Decompiled:
    source: str
    cleanup: CleanupResult | None  # None when cleanup was not requested


def decompile(data: bytes, config: DecompileConfig, clean: bool = True) -> Decompiled:
    if not data:
        raise Failure(400, "Empty request body")
    if data[0] == COMPILE_ERROR_MARKER:
        detail = data[1:200].decode("utf-8", "replace")
        raise Failure(422, f"Luau compile error blob, not bytecode: {detail}")

    raw = _run_with_descramble_retry(data, config)
    if not clean:
        return Decompiled(raw, None)
    result = clean_source(raw, config.cleanup)
    return Decompiled(result.source, result)


def _run_with_descramble_retry(data: bytes, config: DecompileConfig) -> str:
    try:
        return _run_cli(data, config)
    except Failure as first:
        # Roblox client/executor dumps scramble opcodes: undo that and retry once.
        plain = _descrambled(data, first)
        try:
            return _run_cli(plain, config)
        except Failure:
            raise first from None


def _descrambled(data: bytes, first: Failure) -> bytes:
    if first.status in _NO_RETRY_STATUSES:
        raise first
    try:
        plain = descramble.decode_roblox(data)
    except ValueError:
        raise first from None
    if plain == data:
        raise first
    return plain


def _run_cli(data: bytes, config: DecompileConfig) -> str:
    try:
        process = subprocess.run(
            config.cli_args, input=data, capture_output=True, timeout=config.timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        raise Failure(504, "decompiler timed out") from None
    except OSError as error:
        raise Failure(500, f"decompiler binary cannot run: {error.strerror}") from None

    if process.returncode == 0:
        return process.stdout.decode("utf-8", "replace")
    raise Failure(422 if process.returncode == 1 else 500, _error_message(process.stderr))


def _error_message(stderr: bytes) -> str:
    lines = stderr.decode("utf-8", "replace").strip().splitlines()
    if not lines:
        return "decompiler failed"
    message = next((line for line in lines if line.startswith("error")), lines[0])
    return message.replace("error: ", "", 1)
