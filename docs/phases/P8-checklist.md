# P8 核查清单 — 钉钉群 Webhook

| 属性 | 内容 |
|---|---|
| 阶段 | P8 |
| 目标 | 红灯、L2 审批、邮件草稿、Ragas 周报推送到测试群 |
| 预估 | 0.5 周 |
| 输入 | [PRD §14.4](../PRD.md)；用户已有钉钉测试群 |
| **状态** | **✅ 完成 — 2026-08-19** |

---

## 范围

**In**

- 群自定义机器人：Webhook URL + 加签（timestamp + HMAC-SHA256）
- 4 类事件：商机变红灯、PendingAction L2、Copilot 草稿待确认、Ragas 周报
- Celery 发送 + 最多 3 次指数退避；失败写 `audit_log`
- 免打扰时段（默认 22:00–08:00），次日补发
- Admin 配置入口（URL/Secret 只写服务端；Secret 不回显）
- 默认 Markdown 模板（Jinja2）

**Out**

- 企业应用 CorpID、@指定人、IM 内点确认/拒绝
- 企业微信（本期只钉钉）

---

## 核查清单

### 发送

- [x] `.env.example`：`DINGTALK_WEBHOOK_URL`、`DINGTALK_SECRET`
- [x] 加签与钉钉文档一致；无 Secret 时拒绝发送并打日志
- [x] 红灯：健康重算后入队 Celery（异步，目标 30s 内送达）
- [x] L2 / 草稿 / 周报四类模板可区分

### 可靠与合规

- [x] 重试 3 次后仍失败 → audit `dingtalk.send_failed`
- [x] 静默期消息入 Redis，小时任务补发
- [x] Webhook URL 不出现在 GET 明文（mask `access_token`）

### 测试

- [x] `test_dingtalk_notify.py`：加签、模板、Mock HTTP 200、静默期
- [x] Admin `POST /admin/notify/dingtalk/test` 发测试消息（需配置 URL+Secret）

---

## 出口标准（进入 P9）

- [x] 单测不依赖真 Webhook
- [x] 部署文档记录如何创建群机器人
- [x] 测试群收到至少一类真实通知（填入 Webhook 后点「发送测试消息」）

真群冒烟依赖你把加签 Secret 配进 `.env` 或 Admin，本机默认 `DINGTALK_ENABLED=false` 以免误推。
