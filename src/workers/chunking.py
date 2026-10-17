"""Pure, stdlib-only helpers for the chunked fan-out/fan-in pipeline.

Kept free of Celery/SQLAlchemy imports so the chunk-boundary math and the
streaming line counter are unit-testable without the application dependency
stack. The Celery tasks in :mod:`src.workers.log_processor` build on these.
"""

import io
from typing import BinaryIO, List, Tuple


def compute_chunk_ranges(
    total_lines: int, chunk_lines: int
) -> List[Tuple[int, int]]:
    """Split ``total_lines`` into half-open ``[start, end)`` line ranges.

    Each range holds at most ``chunk_lines`` lines. Returns an empty list
    for an empty file (the fan-out completes such jobs directly instead of
    dispatching a zero-task chord, whose semantics vary by result backend).
    A file smaller than one chunk yields a single range; an exact multiple
    yields no trailing empty range.

    Raises:
        ValueError: if ``chunk_lines`` < 1 or ``total_lines`` < 0.
    """
    if chunk_lines < 1:
        raise ValueError(f"chunk_lines must be >= 1, got {chunk_lines}")
    if total_lines < 0:
        raise ValueError(f"total_lines must be >= 0, got {total_lines}")
    return [
        (start, min(start + chunk_lines, total_lines))
        for start in range(0, total_lines, chunk_lines)
    ]


def count_stream_lines(stream: BinaryIO) -> int:
    """Count text lines in a binary stream in O(1) memory.

    Decodes as UTF-8 ignoring errors — the same decoding the worker uses —
    so the count agrees with the line numbers the chunk tasks observe when
    they re-stream their slices.
    """
    count = 0
    with io.TextIOWrapper(stream, encoding="utf-8", errors="ignore") as text:
        for _ in text:
            count += 1
    return count
