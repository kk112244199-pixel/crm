# P0 核查清单 — 文档与架构

| 属性 | 内容 |
|---|---|
| 阶段 | P0 |
| 目标 | 完成文档体系、架构图、API 契约 Draft，PRD 确认 |
| 预估 | 1 周 |
| **状态** | **✅ 已确认 — 2026-08-19** |

---

## 交付物

- [x] [PRD v0.6](../PRD.md)
- [x] [README.md](../../README.md)
- [x] [tech-architecture.md](../architecture/tech-architecture.md)
- [x] [agent-architecture.md](../architecture/agent-architecture.md)
- [x] [business-flow.md](../architecture/business-flow.md)
- [x] [data-model.md](../architecture/data-model.md)
- [x] [rag-pipeline.md](../architecture/rag-pipeline.md)
- [x] [code-map.md](../architecture/code-map.md)
- [x] [openapi.yaml v0.1](../api/openapi.yaml)
- [x] [docker-compose.md](../deployment/docker-compose.md)
- [x] [guardrails-hitl.md](../security/guardrails-hitl.md)
- [x] P0–P4 核查清单

---

## 核查项

### 产品

- [x] PRD 三条闭环与业务规则（§7）已阅读并认可
- [x] MVP / 二期 / 不做 边界清晰
- [x] Admin 前端 LLM 切换需求明确（§10.5.4）

### 架构

- [x] 技术架构图覆盖：Nginx、FastAPI、Next.js、Postgres、Redis、LangGraph
- [x] Agent 架构图覆盖：Orchestrator（Planner + 客户洞察∥商机研判∥风险预警∥行动规划 + Synth）+ HITL interrupt
- [x] 业务流程图覆盖：闭环 A/B/C + LLM 配置流
- [x] 数据模型 ER 图覆盖：核心业务表 + llm_settings + memory_chunks
- [x] RAG 管道图覆盖：混合检索 + Rerank

### 契约

- [x] OpenAPI 包含 CRUD + Writeback + Copilot + Admin LLM + PendingAction
- [x] 契约版本号 v0.1 已标注

### 安全

- [x] HITL L0–L3 分级与 PRD §7.3 一致
- [x] API Key 不出现在 API 响应的设计已文档化

---

## 出口标准（进入 P1）

- [x] 本清单全部勾选
- [x] OpenAPI v0.1 冻结为 P1 实现基准
- [x] code-map 目录结构确认为 P1 脚手架目标

---

## 开放问题（P0 结束前 → 已 deferred 至 P1 启动会）

- [ ] 默认主/备 LLM Provider（P1 启动前确认）
- [ ] Celery vs ARQ（P1 启动前确认）
- [ ] 默认 Embedding 模型（P1 启动前确认）

---

## 下一阶段输入

→ [P1-checklist.md](P1-checklist.md) 使用：
- `docs/api/openapi.yaml` v0.1
- `docs/architecture/code-map.md`
- `docs/architecture/data-model.md`
