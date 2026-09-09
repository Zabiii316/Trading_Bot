"""Mechanical enforcement of the purity invariant.

The architecture's parity guarantee rests entirely on ``core/`` being unable to
reach the outside world. That is an invariant a code reviewer will eventually
fail to enforce -- so it is enforced here, in CI, by walking the AST.

If someone adds ``import time`` to a core module, this test fails the build.
That is the whole point: the previous iteration of this codebase had the same
*intent* (two sizing formulas that were meant to agree) and drifted silently
across 377 commits because nothing checked.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

CORE_DIR = Path(__file__).resolve().parents[2] / "core"

#: Modules that would let core observe or affect the world outside its inputs.
FORBIDDEN_MODULES = {
    "time",
    "datetime",
    "random",
    "secrets",
    "os",
    "sys",
    "socket",
    "pathlib",
    "subprocess",
    "threading",
    "asyncio",
    "httpx",
    "requests",
    "aiohttp",
    "websockets",
    "sqlite3",
    "logging",
}

#: Callables that introduce non-determinism even without a fresh import.
FORBIDDEN_CALLS = {
    "print",
    "input",
    "open",
    "eval",
    "exec",
    "compile",
    "globals",
    "id",
}


def _core_modules() -> list[Path]:
    return sorted(p for p in CORE_DIR.rglob("*.py") if "__pycache__" not in p.parts)


def test_core_directory_exists() -> None:
    assert CORE_DIR.is_dir(), f"{CORE_DIR} missing"
    assert _core_modules(), "no modules found under core/"


@pytest.mark.parametrize("module_path", _core_modules(), ids=lambda p: p.name)
def test_core_module_imports_nothing_impure(module_path: Path) -> None:
    tree = ast.parse(module_path.read_text(), filename=str(module_path))
    offences: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in FORBIDDEN_MODULES:
                    offences.append(f"line {node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in FORBIDDEN_MODULES:
                offences.append(f"line {node.lineno}: from {node.module} import ...")

    assert not offences, (
        f"{module_path.relative_to(CORE_DIR.parent)} breaks core purity:\n  "
        + "\n  ".join(offences)
        + "\n\nTime, I/O and randomness must enter through core.ports only."
    )


@pytest.mark.parametrize("module_path", _core_modules(), ids=lambda p: p.name)
def test_core_module_makes_no_impure_calls(module_path: Path) -> None:
    tree = ast.parse(module_path.read_text(), filename=str(module_path))
    offences: list[str] = []

    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id in FORBIDDEN_CALLS:
            offences.append(f"line {node.lineno}: {node.func.id}(...)")
        # __import__("x") would otherwise sidestep the import check above.
        if node.func.id == "__import__":
            offences.append(f"line {node.lineno}: __import__(...) bypasses import checks")

    assert not offences, (
        f"{module_path.relative_to(CORE_DIR.parent)} makes impure calls:\n  "
        + "\n  ".join(offences)
    )


def test_core_never_imports_adapters() -> None:
    """The dependency arrow points one way: adapters -> core, never back."""
    offences: list[str] = []
    for module_path in _core_modules():
        tree = ast.parse(module_path.read_text(), filename=str(module_path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                root = name.split(".")[0]
                if root in {"adapters", "ops", "runtime", "services"}:
                    offences.append(f"{module_path.name}:{node.lineno} imports {name}")

    assert not offences, "core must not depend on outer layers:\n  " + "\n  ".join(offences)
