"""Unit tests for the job-cancel feature (the last v2.0 gap).

Two layers, both runnable without Docker, Redis, or a database:

* Functional: ``emit_job_cancelled`` publishes a well-formed
  ``job.cancelled`` event on the job's channel (``src.core.events`` is
  stdlib-only at import on purpose).
* Structural (AST): the endpoint, the worker guards, and the dispatch-
  site task-id tracking exist with the semantics the design requires.
  These fail loudly if anyone re-breaks cancellation the way the old
  naive endpoint did (revoking the job id instead of task ids, marking
  FAILED instead of CANCELLED, no finalizer guard).

The end-to-end behavior (real HTTP + SQLite + mocked broker) is
exercised by the standalone harness and by the integration tests in
``tests/integration/test_ingestion.py``.
"""

import ast
import os
from pathlib import Path

import pytest

os.environ.setdefault("EVENT_BUS", "memory")

from src.core.events import (  # noqa: E402
    emit_job_cancelled,
    get_event_bus,
    job_channel,
    reset_event_bus,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _fresh_bus():
    reset_event_bus()
    yield
    reset_event_bus()


def _read(relpath: str) -> str:
    return (REPO_ROOT / relpath).read_text()


def _function_src(relpath: str, name: str) -> str:
    """Source text of one function (for literal-string checks that
    ``ast.dump`` mangles, e.g. ``JobStatus.CANCELLED``)."""
    src = _read(relpath)
    return ast.get_source_segment(src, _function(relpath, name)) or ""


def _function(relpath: str, name: str) -> ast.FunctionDef:
    tree = ast.parse(_read(relpath))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in {relpath}")


def _ordered_call_lines(fn: ast.FunctionDef) -> list:
    """(lineno, name) for every call in the function, in source order."""
    out = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute):
                out.append((node.lineno, f.attr))
            elif isinstance(f, ast.Name):
                out.append((node.lineno, f.id))
    return sorted(out)


# ---------------------------------------------------------------------------
# Functional: the job.cancelled domain event
# ---------------------------------------------------------------------------


def test_emit_job_cancelled_publishes_on_job_channel():
    sub = get_event_bus().subscribe([job_channel("job-1")])
    assert emit_job_cancelled(job_id="job-1") is True
    channel, event = sub.get(timeout=5)
    assert channel == "job:job-1"
    assert event["type"] == "job.cancelled"
    assert event["job_id"] == "job-1"
    sub.close()


def test_emit_job_cancelled_uses_cluster_channel():
    sub = get_event_bus().subscribe([job_channel("job-2", "east")])
    assert emit_job_cancelled(job_id="job-2", cluster_name="east") is True
    channel, event = sub.get(timeout=5)
    assert channel == "job:east:job-2"
    assert event["type"] == "job.cancelled"
    sub.close()


# ---------------------------------------------------------------------------
# Structural: the cancel endpoint
# ---------------------------------------------------------------------------


def test_cancel_endpoint_status_branches():
    """404 missing / 409 terminal / 422 no task ids / 503 broker down."""
    src = _read("src/api/routers/jobs.py")
    fn = _function("src/api/routers/jobs.py", "cancel_job")
    body = ast.dump(fn)
    for code in ("404", "409", "422", "503"):
        assert f"status_code={code}" in src, f"cancel endpoint missing {code}"
    assert "TERMINAL_JOB_STATUSES" in body


def test_cancel_revokes_with_terminate_and_publishes_after_commit():
    """revoke(task_ids, terminate=True); order is revoke -> commit -> publish."""
    fn = _function("src/api/routers/jobs.py", "cancel_job")
    src = ast.dump(fn)
    assert "terminate=True" in src
    calls = _ordered_call_lines(fn)
    pos = {}
    for lineno, name in calls:
        pos.setdefault(name, lineno)
    assert pos["revoke"] < pos["commit"] < pos["emit_job_cancelled"], (
        "cancel must revoke, then commit CANCELLED, then publish "
        f"(got {pos})"
    )


def test_cancel_sets_cancelled_not_failed():
    assert "JobStatus.CANCELLED" in _function_src(
        "src/api/routers/jobs.py", "cancel_job"
    )


def test_cancelled_is_terminal_for_sse_and_delete():
    src = _read("src/api/routers/jobs.py")
    assert (
        "TERMINAL_JOB_STATUSES = (JobStatus.COMPLETED, JobStatus.FAILED, "
        "JobStatus.CANCELLED)" in src
    )
    assert "terminal = job.status in TERMINAL_JOB_STATUSES" in src
    assert '"job.cancelled"' in src  # SSE forwards it as a terminal event


# ---------------------------------------------------------------------------
# Structural: worker safety
# ---------------------------------------------------------------------------


def test_finalize_job_guards_cancelled_before_summary_write():
    """The chord finalizer must never resurrect a cancelled job."""
    src = _read("src/workers/log_processor.py")
    fn = _function("src/workers/log_processor.py", "finalize_job")
    lines = src.splitlines()
    start = fn.lineno
    guard = next(
        i
        for i, line in enumerate(lines[start:], start)
        if "leaving CANCELLED state untouched" in line
    )
    write = next(
        i
        for i, line in enumerate(lines[start:], start)
        if "job.result_summary = json.dumps(summary)" in line
    )
    assert guard < write


def test_fanout_refuses_cancelled_job_before_chord():
    src = _read("src/workers/log_processor.py")
    fn = _function("src/workers/log_processor.py", "fanout_process_log")
    lines = src.splitlines()
    start = fn.lineno
    guard = next(
        i
        for i, line in enumerate(lines[start:], start)
        if "fan-out skipped, job already cancelled" in line
    )
    chord = next(
        i
        for i, line in enumerate(lines[start:], start)
        if "chord_result = chord(" in line
    )
    assert guard < chord
    assert "chord_result.parent" in _function_src(
        "src/workers/log_processor.py", "fanout_process_log"
    ), "fan-out must record chunk/chord task ids for cancellation"


def test_process_chunk_skips_cancelled_job():
    fn = _function("src/workers/log_processor.py", "process_chunk")
    assert "job cancelled; skipping" in ast.dump(fn)


# ---------------------------------------------------------------------------
# Structural: task-id tracking at dispatch
# ---------------------------------------------------------------------------


def test_dispatch_sites_record_task_ids():
    """Upload, stream, and cluster handlers all store the entrypoint id."""
    src = _read("src/api/routers/ingest.py")
    assert (
        src.count("job.celery_task_ids = (job.celery_task_ids or []) + [task.id]")
        == 3
    ), "all three dispatch sites must append (never overwrite) the task id"


def test_job_status_has_cancelled():
    tree = ast.parse(_read("src/models/job.py"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "JobStatus":
            names = [t.targets[0].id for t in node.body if isinstance(t, ast.Assign)]
            assert "CANCELLED" in names
            return
    raise AssertionError("JobStatus not found")


def test_migration_chain_intact():
    """The cancel-support migration follows the cluster-name migration."""
    tree = ast.parse(
        _read(
            "alembic/versions/2026_10_18_1000-552bbe04eacb_add_job_cancel_support.py"
        )
    )
    assigns = {}
    for node in ast.walk(tree):
        target, value = None, None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            target, value = node.target, node.value
        if (
            isinstance(target, ast.Name)
            and isinstance(value, ast.Constant)
            and target.id in ("revision", "down_revision")
        ):
            assigns[target.id] = value.value
    assert assigns.get("revision") == "552bbe04eacb"
    assert assigns.get("down_revision") == "a1b2c3d4e5f6"
