"""
文本分块策略
- structured：按 Markdown 标题分块
- recursive：递归按段落 → 句子分块
"""
from __future__ import annotations
import re


def extract_source_metadata(text: str) -> dict:
    """从纪要开头提取会议日期与参会人，写入 chunk metadata。"""
    head = (text or "")[:800]
    date = None
    m = re.search(r"20\d{2}-\d{2}-\d{2}", head)
    if m:
        date = m.group(0)
    attendees = None
    m2 = re.search(r"参会[人：:]\s*(.+)", head)
    if m2:
        attendees = m2.group(1).strip()[:240]
    title = None
    m3 = re.search(r"【([^】]+)】", head)
    if m3:
        title = m3.group(1).strip()[:80]
    return {"meeting_date": date, "attendees": attendees, "source_title": title}


def chunk_text(text: str, strategy: str = "auto", chunk_size: int = 512, overlap: int = 64) -> list[str]:
    if strategy == "auto":
        strategy = "structured" if text.strip().startswith("#") else "recursive"

    if strategy == "structured":
        return _chunk_by_headers(text)
    return _recursive_chunk(text, chunk_size, overlap)


def _chunk_by_headers(text: str) -> list[str]:
    """Split on Markdown headings (##, ###)."""
    parts = re.split(r"\n(?=#{1,3}\s)", text)
    return [p.strip() for p in parts if p.strip()]


def _recursive_chunk(text: str, size: int, overlap: int) -> list[str]:
    """Split by paragraphs; if too large, split by sentences."""
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    chunks: list[str] = []
    buf = ""
    for para in paragraphs:
        if len(buf) + len(para) > size and buf:
            chunks.append(buf.strip())
            buf = buf[-overlap:] + "\n" + para
        else:
            buf += ("\n" if buf else "") + para
    if buf.strip():
        chunks.append(buf.strip())
    return chunks or [text.strip()]
