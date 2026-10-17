"""Add object-storage content reference columns to jobs

Revision ID: b99d953463d9
Revises: 28cba2a150b3
Create Date: 2026-10-17 16:00:00.000000

The API streams uploads into object storage and hands the Celery worker a
content reference (backend + bucket + key) instead of a local filesystem
path. These columns carry that reference; they stay NULL for stream and
cluster-ingest jobs, which pass log lines directly.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b99d953463d9'
down_revision: Union[str, Sequence[str], None] = '28cba2a150b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('storage_backend', sa.String(length=32), nullable=True))
    op.add_column('jobs', sa.Column('storage_bucket', sa.String(length=255), nullable=True))
    op.add_column('jobs', sa.Column('storage_key', sa.String(length=1024), nullable=True))


def downgrade() -> None:
    op.drop_column('jobs', 'storage_key')
    op.drop_column('jobs', 'storage_bucket')
    op.drop_column('jobs', 'storage_backend')
