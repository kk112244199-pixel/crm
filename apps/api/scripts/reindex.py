"""
Rebuild RAG embeddings from Activity.canonical_text.

Usage (from apps/api):
  python -m app.services.rag.reindex --full
  python scripts/reindex.py --full

Expect ~1000 hash/local chunks well under 5 minutes; Dashscope BGE depends on API QPS.
"""
from app.services.rag.reindex import main

if __name__ == "__main__":
    raise SystemExit(main())
