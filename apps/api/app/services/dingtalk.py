"""钉钉群自定义机器人：加签、模板、静默期。Secret 不回显。"""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import logging
import time
import urllib.parse
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config import settings

log = logging.getLogger("montocrm.dingtalk")

EVENTS = ("opp_red", "pending_l2", "email_draft", "ragas_weekly", "test")
_TEMPLATES = Path(__file__).resolve().parents[1] / "templates" / "dingtalk"
_DELAYED_KEY = "montocrm:dingtalk:delayed"
_TITLES = {
    "opp_red": "商机红灯",
    "pending_l2": "L2 待审批",
    "email_draft": "邮件草稿待确认",
    "ragas_weekly": "Ragas 周报",
    "test": "MontoCRM 测试消息",
}


def mask_webhook_url(url: str) -> str:
    if not url:
        return ""
    if "access_token=" in url:
        pre, _, rest = url.partition("access_token=")
        token = rest.split("&", 1)[0]
        tail = rest[len(token) :]
        if len(token) <= 8:
            shown = "***"
        else:
            shown = token[:4] + "***" + token[-4:]
        return f"{pre}access_token={shown}{tail}"
    if len(url) > 20:
        return url[:16] + "***" + url[-4:]
    return "***"


def sign_webhook(webhook_url: str, secret: str, timestamp_ms: int | None = None) -> tuple[str, str]:
    """返回 (signed_url, timestamp)。与钉钉官方 HMAC-SHA256 一致。"""
    ts = str(timestamp_ms if timestamp_ms is not None else round(time.time() * 1000))
    string_to_sign = f"{ts}\n{secret}"
    digest = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(digest))
    joiner = "&" if "?" in webhook_url else "?"
    signed = f"{webhook_url}{joiner}timestamp={ts}&sign={sign}"
    return signed, ts


def render_markdown(event: str, context: dict[str, Any]) -> tuple[str, str]:
    name = event if event in EVENTS else "test"
    path = _TEMPLATES / f"{name}.md.j2"
    raw = path.read_text(encoding="utf-8") if path.exists() else "{{ text }}"
    ctx = {"base_url": settings.APP_PUBLIC_BASE_URL.rstrip("/"), **context}
    try:
        from jinja2 import Template
        text = Template(raw).render(**ctx)
    except Exception:
        text = raw
        for k, v in ctx.items():
            text = text.replace("{{ " + k + " }}", str(v if v is not None else ""))
            text = text.replace("{{" + k + "}}", str(v if v is not None else ""))
    title = _TITLES.get(name, "MontoCRM")
    return title, text.strip()


def _parse_hhmm(value: str) -> dt_time:
    parts = (value or "22:00").strip().split(":")
    return dt_time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)


def in_quiet_hours(now: datetime | None = None, start: str | None = None, end: str | None = None) -> bool:
    tz = ZoneInfo(settings.DINGTALK_TZ)
    now = now or datetime.now(tz)
    if now.tzinfo is None:
        now = now.replace(tzinfo=tz)
    else:
        now = now.astimezone(tz)
    t = now.timetz().replace(tzinfo=None)
    s = _parse_hhmm(start or settings.DINGTALK_QUIET_START)
    e = _parse_hhmm(end or settings.DINGTALK_QUIET_END)
    if s <= e:
        return s <= t < e
    return t >= s or t < e


def _redis():
    from app.core.redis_client import get_redis
    return get_redis(socket_timeout=2)


def defer_message(event: str, context: dict[str, Any]) -> None:
    r = _redis()
    payload = json.dumps({"event": event, "context": context}, ensure_ascii=False)
    if r is None:
        log.warning("dingtalk_defer_no_redis event=%s", event)
        return
    r.rpush(_DELAYED_KEY, payload)


def pop_delayed(limit: int = 50) -> list[dict[str, Any]]:
    r = _redis()
    if r is None:
        return []
    out = []
    for _ in range(limit):
        raw = r.lpop(_DELAYED_KEY)
        if not raw:
            break
        try:
            out.append(json.loads(raw))
        except Exception:
            continue
    return out


def resolve_runtime_config(notify_config: dict | None = None) -> dict[str, Any]:
    cfg = notify_config or {}
    url = (cfg.get("webhook_url") or settings.DINGTALK_WEBHOOK_URL or "").strip()
    secret = (cfg.get("secret") or settings.DINGTALK_SECRET or "").strip()
    enabled = cfg.get("enabled")
    if enabled is None:
        enabled = settings.DINGTALK_ENABLED
    return {
        "enabled": bool(enabled) and bool(url),
        "webhook_url": url,
        "secret": secret,
        "quiet_start": cfg.get("quiet_start") or settings.DINGTALK_QUIET_START,
        "quiet_end": cfg.get("quiet_end") or settings.DINGTALK_QUIET_END,
    }


def post_markdown(webhook_url: str, secret: str, title: str, text: str) -> dict[str, Any]:
    if not secret:
        log.warning("dingtalk_refused_no_secret")
        return {"ok": False, "error": "missing_secret"}
    if not webhook_url:
        return {"ok": False, "error": "missing_webhook"}
    signed, ts = sign_webhook(webhook_url, secret)
    import httpx
    payload = {"msgtype": "markdown", "markdown": {"title": title, "text": text}}
    resp = httpx.post(signed, json=payload, timeout=10.0)
    data = {}
    try:
        data = resp.json()
    except Exception:
        data = {"raw": resp.text[:300]}
    ok = resp.status_code == 200 and int(data.get("errcode", 1)) == 0
    if not ok:
        log.warning("dingtalk_http_fail status=%s body=%s ts=%s", resp.status_code, data, ts)
    return {"ok": ok, "status": resp.status_code, "body": data, "timestamp": ts}


def _load_notify_config_sync() -> dict:
    import asyncio

    async def _inner() -> dict:
        try:
            from sqlalchemy import select
            from app.db.session import AsyncSessionLocal
            from app.models.llm_settings import LLMSettings
            async with AsyncSessionLocal() as db:
                row = (await db.execute(select(LLMSettings).limit(1))).scalar_one_or_none()
                return dict(row.notify_config or {}) if row else {}
        except Exception:
            return {}

    try:
        return asyncio.run(_inner())
    except RuntimeError:
        return {}


def send_event(event: str, context: dict[str, Any], *, notify_config: dict | None = None, force: bool = False) -> dict[str, Any]:
    if notify_config is None:
        notify_config = _load_notify_config_sync()
    cfg = resolve_runtime_config(notify_config)
    if not cfg["enabled"] and not force:
        return {"ok": False, "skipped": True, "error": "disabled"}
    if not cfg["secret"]:
        log.warning("dingtalk_refused_no_secret event=%s", event)
        return {"ok": False, "error": "missing_secret"}
    if not force and in_quiet_hours(start=cfg["quiet_start"], end=cfg["quiet_end"]):
        defer_message(event, context)
        return {"ok": True, "deferred": True}
    title, text = render_markdown(event, context)
    return post_markdown(cfg["webhook_url"], cfg["secret"], title, text)


def enqueue_dingtalk(event: str, context: dict[str, Any]) -> None:
    try:
        from app.tasks.dingtalk_notify import send_dingtalk_event
        send_dingtalk_event.delay(event, context)
    except Exception as e:
        log.warning("dingtalk_enqueue_failed: %s", e)
