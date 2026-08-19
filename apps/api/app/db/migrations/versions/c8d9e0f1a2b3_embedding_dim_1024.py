"""bge-m3 vector dim 1024; drop old 1536 embeddings (must reindex)

Revision ID: c8d9e0f1a2b3
Revises: b7c1d2e3f4a5
Create Date: 2026-08-19 20:40:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "c8d9e0f1a2b3"
down_revision: Union[str, None] = "b7c1d2e3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_memory_chunks_embedding_hnsw")
    op.execute("TRUNCATE TABLE memory_chunks")
    op.execute("ALTER TABLE memory_chunks DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE memory_chunks ADD COLUMN embedding vector(1024) NOT NULL")
    op.execute(
        "CREATE INDEX ix_memory_chunks_embedding_hnsw "
        "ON memory_chunks USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_memory_chunks_embedding_hnsw")
    op.execute("ALTER TABLE memory_chunks DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE memory_chunks ADD COLUMN embedding vector(1536)")
    op.execute(
        "CREATE INDEX ix_memory_chunks_embedding_hnsw "
        "ON memory_chunks USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )
