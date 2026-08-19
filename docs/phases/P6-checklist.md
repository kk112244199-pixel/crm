# P6 核查清单 — Langfuse + Ragas + Grafana

| 属性 | 内容 |
|---|---|
| 阶段 | P6 |
| 目标 | 真实 LLM/Agent trace；golden 评估可复现；基础 Grafana 看板 |
| 预估 | 1 周 |
| **状态** | **✅ 已实现 — 2026-08-19**（`test_observability_p6.py` 3 passed） |

---

## 范围

**In**

- `trace_agent_run` / Orchestrator / `call_llm` 接入 Langfuse 适配层（无 Key → Mock）
- Orchestrator：planner ∥ 四专责 ∥ synthesizer span；trace 带 user_id / opportunity_id
- `tests/golden/extract_writeback.json`：10 条纪要 + 参考答案草稿
- `make eval` / `python -m app.eval.runner` → `tests/ragas_report.json`；阈值不足 **警告不阻断**
- docker-compose：Prometheus :9090 + Grafana :3001
- Celery Beat 周一 00:00 周评估（钉钉推送留 P8）

**Out**

- 自建评测 UI
- Ragas CI 硬门禁
- 自托管 Langfuse 全家桶（ClickHouse）；默认走 Cloud 或 Mock

---

## 核查清单

### Langfuse

- [x] `call_llm` 写 generation（model、latency、input/output hash）
- [x] Orchestrator fan-out/fan-in span
- [x] trace 携带 `user_id`、`opportunity_id`
- [x] `.env.example` Langfuse Host / Public / Secret

### Ragas / Golden

- [x] 10 条 golden 草稿（`status: draft_pending_review`）
- [x] Faithfulness / Answer Relevancy / Context Recall
- [x] `make eval` 可跑
- [x] 启发式自检：Faithfulness 1.0，Relevancy 0.84（P7 后对照模型输出再刷）

### Grafana

- [x] prometheus + grafana 服务
- [x] 看板：LLM 调用/延迟、HTTP 5xx、Guard 拦截

### 测试

- [x] Mock exporter 单测（无云账号）
- [x] golden JSON schema 校验

---

## 出口标准（进入 P7）

- [x] Langfuse Cloud 或 Mock 已文档化
- [x] golden 入库 `tests/golden/`
- [x] `make eval` 写入 README
