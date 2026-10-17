"""Unit tests for the chunked pipeline's pure helpers.

``src.workers.chunking`` is stdlib-only on purpose, so these tests run
without Celery, SQLAlchemy, or any infrastructure.
"""

import io

import pytest

from src.workers.chunking import compute_chunk_ranges, count_stream_lines


class TestComputeChunkRanges:
    """Line-range math for the fan-out."""

    def test_exact_multiple_has_no_trailing_empty_range(self):
        assert compute_chunk_ranges(20000, 10000) == [(0, 10000), (10000, 20000)]

    def test_partial_last_chunk(self):
        assert compute_chunk_ranges(25000, 10000) == [
            (0, 10000),
            (10000, 20000),
            (20000, 25000),
        ]

    def test_empty_file_yields_no_ranges(self):
        # The fan-out completes empty uploads directly instead of
        # dispatching a zero-task chord.
        assert compute_chunk_ranges(0, 10000) == []

    def test_file_smaller_than_one_chunk(self):
        assert compute_chunk_ranges(500, 10000) == [(0, 500)]

    def test_single_line_chunks(self):
        assert compute_chunk_ranges(3, 1) == [(0, 1), (1, 2), (2, 3)]

    def test_ranges_are_contiguous_and_cover_everything(self):
        ranges = compute_chunk_ranges(123456, 10000)
        assert ranges[0][0] == 0
        assert ranges[-1][1] == 123456
        for (s1, e1), (s2, e2) in zip(ranges, ranges[1:]):
            assert e1 == s2  # no gaps, no overlaps
            assert e1 - s1 <= 10000

    def test_invalid_chunk_lines_rejected(self):
        with pytest.raises(ValueError):
            compute_chunk_ranges(100, 0)
        with pytest.raises(ValueError):
            compute_chunk_ranges(100, -5)

    def test_negative_total_rejected(self):
        with pytest.raises(ValueError):
            compute_chunk_ranges(-1, 10000)


class TestCountStreamLines:
    """Streaming line counts agree with chunk slicing."""

    def test_counts_lines(self):
        data = b"\n".join(f"line {i}".encode() for i in range(1000)) + b"\n"
        assert count_stream_lines(io.BytesIO(data)) == 1000

    def test_empty_stream(self):
        assert count_stream_lines(io.BytesIO(b"")) == 0

    def test_no_trailing_newline(self):
        assert count_stream_lines(io.BytesIO(b"a\nb")) == 2

    def test_blank_lines_count(self):
        # Blank lines are skipped by matching but still occupy line
        # numbers, so the counter must include them.
        assert count_stream_lines(io.BytesIO(b"a\n\nb\n")) == 3

    def test_count_agrees_with_slice_enumeration(self):
        # The fan-out counts with count_stream_lines; chunks slice with
        # enumerate() over the same decoding. Both must number lines
        # identically or slices drift.
        data = ("x\n" * 25000).encode()
        total = count_stream_lines(io.BytesIO(data))
        ranges = compute_chunk_ranges(total, 10000)
        enumerated = sum(1 for _ in io.BytesIO(data).read().decode().splitlines())
        assert total == enumerated == 25000
        assert sum(e - s for s, e in ranges) == total
