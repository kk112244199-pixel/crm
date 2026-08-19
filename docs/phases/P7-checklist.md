# P7 核查清单 — 混合 RAG + Rerank

| 属性 | 内容 |
|---|---|
| 阶段 | P7 |
| 目标 | BM25/关键词 + 向量 RRF 融合、Rerank、真实 Query Rewriting；检索质量可测 |
| 预估 | 1.5 周 |
| 输入 | [PRD §14.3](../PRD.md)、[rag-pipeline.md](../architecture/rag-pipeline.md)、`apps/api/app/services/rag/` |
| **状态** | **✅ 完成 — 2026-08-19** |

---

## 范围

**In**

- `pg_trgm`（或等价）关键词检索 + pgvector，RRF 融合
- Rerank：Dashscope 或本地 lexical / `gte-rerank`；top-20 → top-5
- Query Rewriting 替换 placeholder，走 LLM Resolver 轻量模型
- Query Expansion（可选，`RAG_EXPAND_ENABLED`）
- 纪要 chunk 保留日期/参与人 metadata
- `scripts/reindex.py` 全量重建 embedding

**Out**

- 更换主 Embedding 模型（仍 BGE-M3，除非评估证明必须换）
- 跨租户检索（无多租户）

---

## 核查清单

### 检索

- [x] 客户名、型号等关键词可命中（纯向量弱项）
- [x] RRF 融合参数可配置（k、权重）
- [x] Rerank 失败时降级为融合结果，不 500
- [x] Query Rewriting 超时降级为原 query
- [x] Copilot `citations` / `retrieved_chunks` 在有 ingest 的商机上可 > 0（关键词 + hash 向量；需先 ingest/reindex）

### 运维

- [x] `scripts/reindex.py`：local/hash 1000 chunks 远小于 5 分钟（文档记录）；Dashscope 取决于 QPS
- [x] Embedding 变更后 Admin `needs_reindex` + `GET/POST /admin/rag/reindex*`

### 质量与性能

- [x] 相对 P4：golden 上 MRR@5 相对随机向量基线提升 ≥ 20%（`make eval` → `retrieval`）
- [x] P95 检索（含 lexical Rerank，内存）≤ 500ms

### 文档

- [x] `rag-pipeline.md` v0.4 更新为混合检索 + Rerank 实装

---

## 出口标准（进入 P8）

- [x] 本清单检索 + 降级路径通过
- [x] 用 P6 `make eval` 跑一轮对照，报告含 `retrieval`
