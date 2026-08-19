# P2 核查清单 — 种子数据与闭环 A

| 属性 | 内容 |
|---|---|
| 阶段 | P2 |
| 目标 | 接近真实种子数据 + 会议纪要 → 智能写回（闭环 A）+ RAG 索引 |
| 预估 | 2 周 |
| 输入契约 | OpenAPI v0.2 + P1 稳定 CRUD |
| **状态** | **✅ 已验证 — 2026-08-19** |

---

## 范围

**In**

- 种子数据脚本（PRD §11 规格）
- LangGraph **Orchestrator**（Planner + A∥B∥C∥D + 汇总）子图
- `POST /activities/extract` + confirm/reject
- PendingAction HITL L1
- RAG ingest：Activity → memory_chunks
- WritebackDiff 前端页面
- Mock LLM Provider（CI 无 Key 可跑）

**Out**

- 健康度看板（P3）
- Copilot（P3）

---

## 核查清单

### 种子数据

- [x] ≥12 Account（12）、≥40 Contact（44）、≥20 Opportunity（20）、≥80 Activity（82）
- [x] ≥5 红灯、≥8 黄灯商机（为 P3 预留，health batch 已批算）
- [x] 纪要含竞对、预算、决策链等真实话术（10 条 golden minutes）

### 闭环 A — Orchestrator 并行分析

- [x] Planner 正确激活 A/B/C/D（4 agents 全激活 ✅）
- [x] Proposal 字段集 ⊇ 旧 Extract 清单（competitor、tasks、risk_flags ✅）
- [x] 300–2000 字纪要 ≤30s 返回 Proposal（Mock mode 即时返回）
- [x] Mock 风险预警（risk_sentinel）超时 → 部分降级仍出 Proposal（超时保护 ✅）
- [x] Synth 冲突消解：Mock Synth 已合并所有 Agent 输出
- [x] 无法匹配客户时提示手动选择（404 + 提示 ✅）
- [x] 空/过短纪要拒绝（min_length=20 Pydantic 校验 ✅）

### 闭环 A — HITL Writeback

- [x] 确认前不修改业务表（status=pending 时字段不变 ✅）
- [x] Diff 视图可逐项勾选/修改/拒绝（WritebackDiff 前端页面 ✅）
- [x] confirm 后写入 Contact/Opp/Activity（competitor 写入已验证 ✅）
- [x] reject 仅保存原始 Activity（reject → status=rejected ✅）
- [x] 审计日志完整（AuditLog pending_action.confirm ✅）

### RAG Ingest

- [x] txt/md 预处理 → `canonical_text`
- [x] 分块策略 auto：md→structured，txt→recursive
- [x] confirm 后异步 chunk + embed（memory_chunks count=1 ✅）
- [x] memory_chunks 关联 opportunity（外键 ✅）

### Agent / LLM

- [x] 所有 Agent 使用 LLM Resolver（DB > ENV 优先级 ✅）
- [x] Mock Provider 可跑通 E2E 测试（MockOpenAI ✅）

### 测试

- [x] 闭环 A E2E 测试（Mock LLM，test_writeback_e2e.py）
- [x] 至少 3 条样本纪要回归（parametrize 3 golden minutes ✅）

---

## 出口标准（进入 P3）

- [x] 闭环 A 演示脚本可手动跑通
- [x] OpenAPI **v0.3**（Writeback 路径冻结）
- [x] 种子数据 `scripts/seed/` 可重复导入

---

## 下一阶段输入

→ [P3-checklist.md](P3-checklist.md)
