"""P8 钉钉：加签、模板、Mock HTTP、静默期、URL 脱敏。不访问真 Webhook。"""
from __future__ import annotations
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.services.dingtalk import (
    in_quiet_hours,
    mask_webhook_url,
    post_markdown,
    render_markdown,
    send_event,
    sign_webhook,
)


def test_sign_hmac_sha256_stable():
    url = "https://oapi.dingtalk.com/robot/send?access_token=tok"
    signed, ts = sign_webhook(url, "SEC123", timestamp_ms=1710000000000)
    assert ts == "1710000000000"
    assert "timestamp=1710000000000" in signed
    assert "sign=" in signed
    assert signed.startswith(url + "&")
    # 同一输入签名不变
    signed2, _ = sign_webhook(url, "SEC123", timestamp_ms=1710000000000)
    assert signed == signed2


def test_refuse_without_secret():
    r = post_markdown("https://oapi.dingtalk.com/robot/send?access_token=x", "", "t", "b")
    assert r["ok"] is False
    assert r["error"] == "missing_secret"


def test_templates_distinguish_four_events():
    red, t1 = render_markdown("opp_red", {"opp_name": "MES", "score": 20, "opportunity_id": "u1", "rules": "H001", "suggestion": "跟进"})
    l2, t2 = render_markdown("pending_l2", {"opp_name": "MES", "old_amount": 1, "new_amount": 2, "pending_action_id": "p", "opportunity_id": "u1"})
    dr, t3 = render_markdown("email_draft", {"opp_name": "MES", "subject": "POC", "pending_action_id": "p", "opportunity_id": "u1"})
    ra, t4 = render_markdown("ragas_weekly", {"faithfulness": 1, "answer_relevancy": 0.8, "context_recall": 0.9, "n_items": 10, "retrieval_mrr": 1, "warnings": "无"})
    assert "红灯" in red and "红灯" in t1
    assert "L2" in l2 and "待审批" in t2
    assert "草稿" in dr and "POC" in t3
    assert "Ragas" in ra and "Faithfulness" in t4
    assert len({t1[:20], t2[:20], t3[:20], t4[:20]}) == 4


class _Resp:
    status_code = 200
    text = '{"errcode":0}'

    def json(self):
        return {"errcode": 0, "errmsg": "ok"}


def test_mock_http_200():
    with patch("httpx.post", return_value=_Resp()) as mocked:
        r = post_markdown(
            "https://oapi.dingtalk.com/robot/send?access_token=abc",
            "SECxxx",
            "标题",
            "正文",
        )
    assert r["ok"] is True
    mocked.assert_called_once()
    args, kwargs = mocked.call_args
    assert "timestamp=" in args[0]
    assert "sign=" in args[0]
    assert kwargs["json"]["msgtype"] == "markdown"


def test_quiet_hours_overnight():
    tz = ZoneInfo("Asia/Shanghai")
    night = datetime(2026, 8, 19, 23, 30, tzinfo=tz)
    morning = datetime(2026, 8, 20, 10, 0, tzinfo=tz)
    assert in_quiet_hours(night, start="22:00", end="08:00") is True
    assert in_quiet_hours(morning, start="22:00", end="08:00") is False


def test_quiet_hours_defers(monkeypatch):
    deferred = []
    monkeypatch.setattr("app.services.dingtalk.in_quiet_hours", lambda **k: True)
    monkeypatch.setattr("app.services.dingtalk.defer_message", lambda e, c: deferred.append((e, c)))
    r = send_event(
        "opp_red",
        {"opp_name": "x"},
        notify_config={
            "enabled": True,
            "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=abc",
            "secret": "SEC",
        },
    )
    assert r.get("deferred") is True
    assert deferred and deferred[0][0] == "opp_red"


def test_mask_webhook_hides_token():
    url = "https://oapi.dingtalk.com/robot/send?access_token=abcdefghijklmnop"
    masked = mask_webhook_url(url)
    assert "abcdefghijklmnop" not in masked
    assert "access_token=" in masked
    assert "***" in masked
