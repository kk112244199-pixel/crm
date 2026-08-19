# P4 核查清单 — 可观测性 + 生产加固

| 属性 | 内容 |
|---|---|
| 阶段 | P4 |
| 目标 | Langfuse trace、Prometheus metrics、审计日志、HITL 过期、阶段校验、JWT Refresh、安全加固 |
| 预估 | 1 周 |
| **状态** | **✅ 已验证 — 2026-08-19** |

---

## 核查清单

### 可观测性

- [x] 结构化 JSON 日志（JSONFormatter ✅）
- [x] `log_llm_call` 记录 provider/model/latency_ms/token 估算（✅）
- [x] `trace_agent_run` Langfuse stub（✅，二期接真实 SDK）
- [x] Prometheus Counter/Histogram 已定义（llm_calls_total、llm_latency_seconds、http_requests_total ✅）
- [x] `GET /metrics` → HTTP 200，prometheus_client 已安装（✅）
- [x] HTTP 中间件写 http_requests_total（✅）

### 审计日志

- [x] `audit_log` 表已建（actor_id、action、resource_type、resource_id、opportunity_id、detail ✅）
- [x] confirm/reject PendingAction 写审计（"pending_action.confirm" ✅）
- [x] `GET /audit/logs` Manager+ 可查，AE → 403（✅）

### HITL 过期

- [x] Celery Beat 每小时跑 `expire_pending_actions`（pending_expire.py ✅）
- [x] 48h 前的 PENDING → EXPIRED（✅）

### 阶段校验与 L2 审批

- [x] 阶段推进缺少必填字段 → 422（NEGOTIATION 无 amount/expected_close_date → 422 ✅）
- [x] amount 变更 ≥10% 创建 L2 PendingAction（✅）
- [x] L2 需要 Manager+ 确认（RBAC ✅）

### JWT 安全

- [x] `POST /auth/token` 同时返回 access_token + refresh_token（✅）
- [x] `POST /auth/refresh` 换新 access_token（✅）
- [x] `GET /auth/me` 返回当前用户信息（role=AE ✅）
- [x] refresh_token 7 天过期（JWT_REFRESH_TOKEN_EXPIRE_DAYS=7 ✅）

### LLM Guard

- [x] Prompt Injection 规则检测（✅）
- [x] PII 输出脱敏（✅）
- [x] Guard 集成到 `/activities/extract` 输入扫描（✅）
- [x] Guard 集成到 `/copilot/draft` 输出扫描（✅）

### 演示

- [x] `docs/deployment/demo-script.md` 三条闭环可手动执行（✅）
- [x] `README.md` 快速开始 + 默认凭据（✅）

---

## Bug 修复（P4 验证期间发现）

| Bug | 症状 | 修复 |
|---|---|---|
| RAG retriever SQL | `pgvector CAST` 语法错误 | 改为 `CAST(:vec AS vector)` + 分支 SQL |
| `audit/` 目录冲突 | `services/audit/` 目录遮蔽 `services/audit.py` | 删除容器内 `audit/` 空目录 |

---

## 出口标准

- [x] 所有核查项通过
- [x] OpenAPI **v1.0** 冻结（MVP 功能全部可演示）
- [x] code-map 与实际目录对齐

---

## 遗留事项（已纳入第二期）

详见 [phase-2-overview.md](phase-2-overview.md)：

- P5 真实 LLM Guard
- P6 Langfuse SDK + Ragas
- P7 混合 RAG + Rerank
- P8 钉钉 Webhook
- P9 Nginx SSL + rate limit + E2E / CI

多租户 **不在第二期**，见 PRD §16.4。
