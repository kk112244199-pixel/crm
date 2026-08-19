"""Re-index 状态（Redis，失败则进程内）。"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings

log = logging.getLogger("montocrm.reindex")
_KEY = "montocrm:rag:reindex"
_local: dict[str, Any] = {
    "status": "idle",
    "needs_reindex": False,
    "reason": None,
    "last_run": None,
    "chunks": 0,
    "error": None,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redis():
    from app.core.redis_client import get_redis
    return get_redis(socket_timeout=1)


def get_status() -> dict[str, Any]:
    r = _redis()
    if r is not None:
        try:
            raw = r.get(_KEY)
            if raw:
                data = json.loads(raw)
                return {**_local, **data}
        except Exception:
            pass
    return dict(_local)


def set_status(**kwargs: Any) -> dict[str, Any]:
    cur = get_status()
    cur.update(kwargs)
    _local.update(cur)
    r = _redis()
    if r is not None:
        try:
            r.set(_KEY, json.dumps(cur, ensure_ascii=False))
        except Exception as e:
            log.debug("reindex_status_redis: %s", e)
    return cur


def mark_needs_reindex(reason: str = "embedding_changed") -> None:
    set_status(needs_reindex=True, reason=reason)
