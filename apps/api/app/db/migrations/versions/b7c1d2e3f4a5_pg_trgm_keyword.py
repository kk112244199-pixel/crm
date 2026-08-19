"""add pg_trgm for hybrid keyword search

Revision ID: b7c1d2e3f4a5
Revises: 4355016b51b3
Create Date: 2026-08-19 20:20:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "b7c1d2e3f4a5"
down_revision: Union[str, None] = "4355016b51b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_memory_chunks_content_trgm "
        "ON memory_chunks USING gin (content gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_memory_chunks_content_trgm")
