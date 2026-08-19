"""P9：限流 429、安全响应头、CORS 白名单。不依赖 Postgres。"""
from fastapi.testclient import TestClient

from app.core import ratelimit
from app.core.config import settings
from app.main import app


def test_security_headers_on_health():
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/health")
    assert r.status_code == 200
    assert r.headers.get("x-frame-options") == "DENY"
    assert r.headers.get("x-content-type-options") == "nosniff"


def test_auth_token_rate_limit_returns_429(monkeypatch):
    ratelimit.reset()
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_AUTH_PER_MIN", 3)
    with TestClient(app, raise_server_exceptions=False) as c:
        codes = []
        for _ in range(5):
            resp = c.post(
                "/auth/token",
                data={"username": "x@test.com", "password": "nope"},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            codes.append(resp.status_code)
    assert 429 in codes
    assert codes.count(429) >= 2


def test_cors_allow_list_from_settings():
    assert "http://localhost:3000" in settings.cors_origins
