"""Add chunk-tracking columns for the fan-out/fan-in pipeline

Revision ID: f3a2b1c4d5e6
Revises: b99d953463d9
Create Date: 2026-10-17 16:30:00.000000

The monolithic process_log_file task was decomposed into a chunked
Celery group + chord finalizer. These columns carry the bookkeeping:

- jobs.total_chunks / jobs.chunks_completed: progress aggregation across
  chunk workers (atomic increment, safe under concurrency). NULL for
  legacy monolithic jobs.
- incidents.chunk_index: retry safety — a retried chunk deletes its
  previous output via (job_id, chunk_index) before reprocessing, so a
  redelivery after a successful commit cannot duplicate incidents.
  NULL = legacy monolithic path; the delete predicate never matches NULL.

All columns are additive and nullable: existing rows are untouched and the
migration is safe to run against a live database.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a2b1c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'b99d953463d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('total_chunks', sa.Integer(), nullable=True))
    op.add_column('jobs', sa.Column('chunks_completed', sa.Integer(), nullable=True))
    op.add_column('incidents', sa.Column('chunk_index', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('incidents', 'chunk_index')
    op.drop_column('jobs', 'chunks_completed')
    op.drop_column('jobs', 'total_chunks')
