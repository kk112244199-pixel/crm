"""共享 Redis 客户端。protocol=2 避免部分环境对 RESP3 HELLO 不兼容。"""
from __future__ import annotations

from app.core.config import settings
from app.core.redis_compat import apply_redis_resp2

apply_redis_resp2()


def get_redis(*, socket_timeout: float = 2.0):
    try:
        import redis
        return redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=socket_timeout,
            protocol=2,
        )
    except Exception:
        return None
