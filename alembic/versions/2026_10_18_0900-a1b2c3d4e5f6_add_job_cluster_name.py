"""Add jobs.cluster_name for multi-cluster support

Revision ID: a1b2c3d4e5f6
Revises: 538e0aef385a
Create Date: 2026-10-18 09:00:00.000000

Adds jobs.cluster_name: the configured OneFS target name this job belongs
to (matches a "name" from ONEFS_TARGETS / ONEFS_TARGETS_FILE). Nullable
with an index. NULL means "not cluster-scoped" (upload/stream jobs) or
"created before multi-cluster support" -- both are treated as the default
cluster everywhere the name is consumed.

All additive and nullable: safe against a live database.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '538e0aef385a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('cluster_name', sa.String(255), nullable=True))
    op.create_index('ix_jobs_cluster_name', 'jobs', ['cluster_name'])


def downgrade() -> None:
    op.drop_index('ix_jobs_cluster_name', table_name='jobs')
    op.drop_column('jobs', 'cluster_name')
