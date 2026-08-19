"""Force redis-py RESP2. Some brokers/proxies reject RESP3 HELLO."""
from __future__ import annotations

_applied = False


def apply_redis_resp2() -> None:
    global _applied
    if _applied:
        return
    try:
        import redis
        import redis.connection
        import redis.utils

        redis.utils.DEFAULT_RESP_VERSION = 2
        redis.connection.DEFAULT_RESP_VERSION = 2
        try:
            import redis.asyncio.connection as aio_conn
            aio_conn.DEFAULT_RESP_VERSION = 2
        except Exception:
            pass

        orig_from_url = redis.Redis.from_url
        orig_init = redis.Redis.__init__

        def from_url(*args, **kwargs):  # type: ignore[no-untyped-def]
            kwargs.setdefault("protocol", 2)
            return orig_from_url(*args, **kwargs)

        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            kwargs.setdefault("protocol", 2)
            orig_init(self, *args, **kwargs)

        redis.Redis.from_url = from_url  # type: ignore[method-assign]
        redis.Redis.__init__ = __init__  # type: ignore[method-assign]
        _applied = True
    except Exception:
        pass
