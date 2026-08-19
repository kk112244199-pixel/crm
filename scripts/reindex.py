#!/usr/bin/env python
"""Repo-root wrapper. Prefer: cd apps/api && python -m app.services.rag.reindex --full"""
import sys
from pathlib import Path

api = Path(__file__).resolve().parent.parent / "apps" / "api"
sys.path.insert(0, str(api))
from app.services.rag.reindex import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
