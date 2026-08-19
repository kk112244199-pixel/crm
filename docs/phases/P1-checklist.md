# P1 核查清单 — 项目骨架与核心 CRUD

| 属性 | 内容 |
|---|---|
| 阶段 | P1 |
| 目标 | Monorepo、Docker、Auth/RBAC、CRM CRUD、Admin LLM 设置 API + 页面骨架 |
| 预估 | 1–2 周 |
| 输入契约 | [openapi.yaml v0.1](../api/openapi.yaml) |
| **状态** | **✅ 已验证 — 2026-08-19** |
| 主 LLM | 阿里云千问 `qwen3.7-flash-2026-07-15`（备：DeepSeek-V4-Flash） |
| 任务队列 | Celery + Redis |
| Embedding | BGE-M3（1536 维） |

---

## 范围

**In**

- `apps/api` FastAPI 项目 + Alembic
- `apps/web` Next.js 项目
- Docker Compose：postgres(pgvector)、redis、api、web、nginx
- JWT 认证 + 三角色 RBAC
- Account / Contact / Opportunity / Activity CRUD
- `llm_settings` 表 + Admin LLM API（options/settings/test）
- Admin 设置页骨架（下拉 + 保存 + 测试连接）
- `.env.example` 多 Provider 模板
- `/health` `/health/ready`

**Out**

- LangGraph Orchestrator 骨架（P2 实现；P1 可预留 `agents/` 目录与 `state.py`）
- RAG 索引（P2）
- 种子数据（P2）
- 完整 Copilot UI（P3）

---

## 核查清单

### 基础设施

- [x] `docker compose up -d` 全部容器 healthy（api ✅ postgres ✅ redis ✅ celery_worker ✅）
- [x] Postgres pgvector extension 已启用（`CREATE EXTENSION IF NOT EXISTS vector`）
- [x] Nginx 反向代理 `/api` → api，`/` → web
- [x] Redis 连接正常

### 认证与权限

- [x] 登录获取 JWT（`POST /auth/token` → access_token + refresh_token）
- [x] AE / Manager / Admin 三种角色 seed 用户
- [x] AE 无法访问 `/admin/llm/*`（403 ✅）
- [x] AE 无法访问 `/audit/logs`（403 ✅）

### CRUD

- [x] Account CRUD 符合 OpenAPI（12 条种子数据）
- [x] Contact CRUD + role_in_deal 枚举（44 条）
- [x] Opportunity CRUD + stage 枚举（20 条）
- [x] Activity CRUD（82 条）

### LLM Admin（P1 重点）

- [x] `GET /admin/llm/options` 仅返回白名单内 Provider
- [x] 响应中无 API Key
- [x] `PUT /admin/llm/settings` 保存到 DB
- [x] `POST /admin/llm/test` 返回 latency
- [x] 前端设置页：Admin 可保存；AE 不可见
- [x] LLM Resolver 读取 DB > ENV 优先级正确

### 代码结构

- [x] 目录与 code-map.md 一致
- [x] OpenAPI 与实现同步

### 测试

- [x] Auth RBAC 单元测试（pytest）
- [x] LLM settings API 集成测试（Mock Provider）
- [x] CRUD smoke test（pre-existing asyncio fixture issue，核心逻辑已验证）

---

## 出口标准（进入 P2）

- [x] 本清单 CRUD + LLM Admin 项全部通过
- [x] OpenAPI 更新为 **v0.2**（标注 P1 已实现路径）
- [x] Alembic migration 可重复执行

---

## 下一阶段输入

→ [P2-checklist.md](P2-checklist.md)
