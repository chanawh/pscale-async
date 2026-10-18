"""Guard against decorative async creeping back into the codebase.

The API stack is sync throughout (sync SQLAlchemy sessions, sync Celery
tasks, sync boto3/paramiko/Redis clients). FastAPI runs sync endpoints in a
threadpool, which is correct and honest here. These tests fail if anyone
reintroduces ``async def`` without a genuine ``await`` on real async I/O.

AST-based and stdlib-only (apart from pytest itself), so they run anywhere.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"


def _iter_py_files():
    return sorted(SRC_ROOT.rglob("*.py"))


def test_no_async_def_in_src():
    """No ``async def`` anywhere under src/ — sync throughout."""
    offenders = []
    for path in _iter_py_files():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno} {node.name}")
    assert not offenders, (
        "decorative async found — convert to sync def or await real async I/O:\n"
        + "\n".join(offenders)
    )


def test_no_await_in_src():
    """No ``await`` expressions — nothing left to await."""
    offenders = []
    for path in _iter_py_files():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Await):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")
    assert not offenders, "await without async def:\n" + "\n".join(offenders)


def test_no_asyncio_import_in_src():
    """No ``asyncio`` bridges — the event loop is not in play."""
    offenders = []
    for path in _iter_py_files():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(a.name.split(".")[0] == "asyncio" for a in node.names):
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")
            elif isinstance(node, ast.ImportFrom):
                if (node.module or "").split(".")[0] == "asyncio":
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")
    assert not offenders, "asyncio import found:\n" + "\n".join(offenders)
