"""进程内滑动窗口限流。生产 Nginx 另有一层；开发默认较松，避免 E2E 误伤。"""
from __future__ import annotations
import time
from collections import defaultdict, deque

_hits: dict[str, deque[float]] = defaultdict(deque)


def reset() -> None:
    _hits.clear()


def too_many(key: str, limit_per_min: int) -> bool:
    if limit_per_min <= 0:
        return False
    now = time.monotonic()
    window = 60.0
    q = _hits[key]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit_per_min:
        return True
    q.append(now)
    return False
