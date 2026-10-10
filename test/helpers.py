"""Shared test helpers: fixture loading and the optional real-Luau runner."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def find_luau(tool: str = "luau") -> str | None:
    """Real Luau binaries make the tests stronger; they are optional (LUAU_DIR or PATH)."""
    directory = os.environ.get("LUAU_DIR")
    if directory and (Path(directory) / tool).exists():
        return str(Path(directory) / tool)
    return shutil.which(tool)


def run_luau(source: str, tool: str = "luau") -> subprocess.CompletedProcess:
    import tempfile
    binary = find_luau(tool)
    with tempfile.NamedTemporaryFile("w", suffix=".luau", delete=False) as handle:
        handle.write(source)
    try:
        return subprocess.run([binary, handle.name], capture_output=True, text=True, timeout=30)
    finally:
        os.unlink(handle.name)


def parses_as_luau(source: str) -> tuple[bool, str]:
    """True when the real Luau compiler accepts `source`."""
    import tempfile
    binary = find_luau("luau-compile")
    with tempfile.NamedTemporaryFile("w", suffix=".luau", delete=False) as handle:
        handle.write(source)
    try:
        result = subprocess.run([binary, "--null", handle.name], capture_output=True, text=True, timeout=30)
    finally:
        os.unlink(handle.name)
    return result.returncode == 0, result.stderr.strip()
