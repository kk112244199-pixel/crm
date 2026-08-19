"""
RAG Ingest Pipeline
Activity confirm 后异步触发：canonical_text → 分块 → embed → pgvector 写入
"""
from __future__ import annotations
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete

from app.models.memory import MemoryChunk
from app.services.rag.chunker import chunk_text, extract_source_metadata
from app.services.rag.embedder import embed_texts


async def ingest_activity(
    db: AsyncSession,
    *,
    opportunity_id: uuid.UUID,
    activity_id: uuid.UUID,
    canonical_text: str,
    metadata: dict | None = None,
) -> int:
    """
    将 Activity 纪要分块、向量化，写入 memory_chunks。
    先删除该 activity 的旧 chunks（幂等）。
    返回写入的 chunk 数量。
    """
    if not canonical_text.strip():
        return 0

    # 删除旧 chunks
    await db.execute(
        delete(MemoryChunk).where(MemoryChunk.activity_id == activity_id)
    )

    src_meta = extract_source_metadata(canonical_text)
    header_bits = [src_meta.get("meeting_date") or "", src_meta.get("attendees") or ""]
    header = " | ".join(b for b in header_bits if b)

    # 分块
    chunks = chunk_text(canonical_text)
    if not chunks:
        return 0

    stored = [f"{header}\n{c}" if header and header not in c[:120] else c for c in chunks]

    # Embed
    embeddings = await embed_texts(stored)

    # 写入
    for idx, (content, embedding) in enumerate(zip(stored, embeddings)):
        chunk = MemoryChunk(
            opportunity_id=opportunity_id,
            activity_id=activity_id,
            chunk_index=idx,
            content=content,
            embedding=embedding,
            metadata_={
                **(metadata or {}),
                **src_meta,
                "chunk_index": idx,
                "total_chunks": len(chunks),
            },
        )
        db.add(chunk)

    await db.commit()
    return len(chunks)
