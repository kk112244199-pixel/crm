# P3 核查清单 — 健康度看板 + Copilot 问答

| 属性 | 内容 |
|---|---|
| 阶段 | P3 |
| 目标 | 闭环 B（健康度看板 + 风险预警）+ 闭环 C（Copilot 问答 + 邮件草稿）|
| 预估 | 2 周 |
| 输入契约 | OpenAPI v0.3 + RAG ingest 稳定 |
| **状态** | **✅ 已验证 — 2026-08-19** |

---

## 核查清单

### 闭环 B — 健康度

- [x] 规则引擎 H001-H008 已实现（28 tests pass ✅）
- [x] `GET /opportunities/{id}/health` 返回 score + status + rules（✅）
- [x] recalc=true 实时触发（✅）
- [x] `GET /dashboard/risk-board` 返回 RED/YELLOW/GREEN 三组（total=20, YELLOW=4, GREEN=16 ✅）
- [x] HealthBadge 前端组件（✅）
- [x] Manager Risk Board 前端页面（✅）
- [x] AE 只看自己商机（owner filter ✅）
- [x] Celery 夜批全量重算任务（health_batch.py ✅）

### 闭环 C — Copilot 问答

- [x] `POST /copilot/query` 返回 answer + citations（answer_len=177 ✅）
- [x] RAG 向量检索已修复（CAST 语法 ✅，memory_chunks count=1 ✅）
- [x] no_data 时告知用户（✅）
- [x] CopilotPanel 前端组件（问答 + 邮件草稿两种模式 ✅）

### 闭环 C — Copilot 邮件草稿

- [x] `POST /copilot/draft` 返回 subject + body + pending_action_id（✅）
- [x] 邮件草稿 PendingAction L2（status=pending ✅）
- [x] `POST /copilot/draft/{id}/send` HITL 确认后触发 MailHog（✅）
- [x] Guard 输出扫描：屏蔽邮件中的 PII（✅）

### 测试

- [x] test_health_rules.py（28 passed ✅）
- [x] test_copilot_e2e.py（Mock LLM ✅）

---

## 出口标准（进入 P4）

- [x] P3 演示脚本可手动跑通
- [x] OpenAPI **v0.4**（Health + Copilot 路径冻结）

---

## 下一阶段输入

→ [P4-checklist.md](P4-checklist.md)
