"""Add incident fingerprint for idempotent bulk inserts

Revision ID: 538e0aef385a
Revises: f3a2b1c4d5e6
Create Date: 2026-10-17 17:00:00.000000

Adds incidents.fingerprint: sha256(pattern_id, node_id, stripped log line)
as 64 hex chars (see src/workers/fingerprint.py for the composition and the
scope rationale), with a UNIQUE constraint. The effective dedup scope is
(pattern, node, line), global across jobs: re-ingesting the same file as a
new job inserts zero new incidents, while the same line on a different
node/cluster still creates a distinct incident.

The column is nullable and existing rows keep NULL fingerprints — NULLs
never participate in dedup (NULL != NULL under unique indexes on both
PostgreSQL and SQLite), and no backfill is attempted: recomputing
fingerprints for historical rows is a data migration this project does
not need, and new code always sets the column.

Two dedup layers now exist, deliberately, and the ordering matters:

1. delete-then-recreate on (job_id, chunk_index) runs FIRST. It guards the
   at-least-once retry window and the changed-output case: if the pattern
   library was edited between attempts, the same line may match a different
   pattern (different fingerprint), and only the delete wipes the stale
   output. Fingerprint dedup alone could not do this.
2. The fingerprint SELECT-filter then handles cross-job idempotency, which
   the delete (scoped to one job) cannot.

All additive and nullable: safe against a live database.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '538e0aef385a'
down_revision: Union[str, Sequence[str], None] = 'f3a2b1c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The unique constraint carries its own index; no separate index needed.
    op.add_column('incidents', sa.Column('fingerprint', sa.String(64), nullable=True))
    op.create_unique_constraint('uq_incidents_fingerprint', 'incidents', ['fingerprint'])


def downgrade() -> None:
    op.drop_constraint('uq_incidents_fingerprint', 'incidents', type_='unique')
    op.drop_column('incidents', 'fingerprint')
