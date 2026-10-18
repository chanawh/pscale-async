"""Add jobs.celery_task_ids + CANCELLED job status

Revision ID: 552bbe04eacb
Revises: a1b2c3d4e5f6
Create Date: 2026-10-18 10:00:00.000000

Cancellation support (the last v2.0 gap):

* jobs.celery_task_ids (JSON, nullable): every Celery task id dispatched
  for the job, recorded at each stage -- the API handlers store the
  entrypoint task id, fanout_process_log appends its own id plus every
  chunk task id and the chord id. NULL for jobs created before task
  tracking; those are not revocable and the cancel endpoint answers 422
  honestly instead of pretending.
* 'CANCELLED' added to the native PostgreSQL jobstatus enum. SQLite
  stores the enum as VARCHAR and needs no change.

All additive and nullable: safe against a live database.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '552bbe04eacb'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # ALTER TYPE ... ADD VALUE cannot run inside a transaction block;
        # autocommit just this statement. Guarded so a re-run (or a DB
        # where the value was added manually) does not fail.
        already = bind.execute(
            sa.text(
                "SELECT 1 FROM pg_enum e "
                "JOIN pg_type t ON t.oid = e.enumtypid "
                "WHERE t.typname = 'jobstatus' AND e.enumlabel = 'CANCELLED'"
            )
        ).first()
        if not already:
            with op.get_context().autocommit_block():
                op.execute("ALTER TYPE jobstatus ADD VALUE 'CANCELLED'")
    op.add_column(
        'jobs', sa.Column('celery_task_ids', sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('jobs', 'celery_task_ids')
    # NOTE: the 'CANCELLED' enum value is intentionally left in place on
    # PostgreSQL -- removing a value requires recreating the type and
    # rewriting every row that references it. Documented, not automated.
