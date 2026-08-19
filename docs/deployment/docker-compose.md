# Docker Compose 部署手册

| 属性 | 内容 |
|---|---|
| 版本 | v0.1 |
| 状态 | P0 设计（P1 实现 docker-compose.yml） |

---

## 1. 服务拓扑

```mermaid
flowchart TB
    subgraph compose["docker-compose.yml"]
        NG[nginx:alpine<br/>:80 / :443]
        WEB[montocrm-web<br/>Next.js :3000]
        API[montocrm-api<br/>FastAPI :8000]
        PG[postgres:16-pgvector<br/>:5432]
        RD[redis:7-alpine<br/>:6379]
    end

    User((Browser)) --> NG
    NG --> WEB
    NG -->|/api/*| API
    API --> PG
    API --> RD
```

**二期服务（P6 已接入）**：prometheus:9090、grafana:3001。Langfuse 默认 SaaS/Mock，不在 compose 中自托管。

---

## 2. 预期目录（P1）

```
montocrm/
├── docker-compose.yml
├── docker/
│   ├── nginx/nginx.conf
│   ├── api/Dockerfile
│   └── web/Dockerfile
├── .env.example
└── apps/
    ├── api/
    └── web/
```

---

## 3. Nginx 路由与 TLS

**Nginx 路由规则**

| 路径 | 上游 |
|---|---|
| `/` | web:3000 |
| `/api/` | api:8000 |
| `/api/auth/token` | api + `limit_req` 5r/m |
| `/api/activities/extract` | api + `limit_req` 10r/m |

**TLS（P9）**

- 监听 `80`（301 → HTTPS）与 `443`（可用 `NGINX_HTTP_PORT` / `NGINX_HTTPS_PORT` 改映射）
- 本机 **Apache httpd 占用 443** 时，`.env` 设 `NGINX_HTTPS_PORT=18443`，HTTP 301 会跳到 `https://host:18443`
- 容器启动时若 volume `nginx_certs` 中没有 `fullchain.pem`，`docker/nginx/start.sh` 生成 **自签** 证书（仅内网/本机）
- 公网：把 Let's Encrypt 的 `fullchain.pem` / `privkey.pem` 写入该 volume 后重启 nginx
- API 另有进程内限流与安全头；开发默认 `RATE_LIMIT_*_PER_MIN=120`，生产改为 5/10

---

## 4. 环境变量（`.env.example` 摘要）

### 4.1 基础

```bash
POSTGRES_USER=montocrm
POSTGRES_PASSWORD=changeme
POSTGRES_DB=montocrm
DATABASE_URL=postgresql+asyncpg://montocrm:changeme@postgres:5432/montocrm
REDIS_URL=redis://redis:6379/0
JWT_SECRET=change-me-in-production
```

### 4.2 LLM — Provider 白名单（Key 仅服务端）

```bash
# 白名单：Admin 前端仅能选择以下 Provider
LLM_AVAILABLE_PROVIDERS=deepseek,openai,dashscope,mock

# 全局默认（可被 Admin DB 覆盖）
LLM_DEFAULT_PROVIDER=dashscope
LLM_DEFAULT_MODEL=qwen3.7-flash-2026-07-15

# 按 Agent 默认（可被 Admin DB 覆盖，见 PRD §10.5.3）
LLM_PLANNER_PROVIDER=dashscope
LLM_PLANNER_MODEL=qwen3.7-flash-2026-07-15
LLM_SYNTH_PROVIDER=dashscope
LLM_SYNTH_MODEL=qwen3.7-flash-2026-07-15
LLM_CUSTOMER_INSIGHT_PROVIDER=dashscope
LLM_CUSTOMER_INSIGHT_MODEL=qwen3.7-flash-2026-07-15
LLM_OPPORTUNITY_JUDGE_PROVIDER=dashscope
LLM_OPPORTUNITY_JUDGE_MODEL=qwen3.7-flash-2026-07-15
LLM_RISK_SENTINEL_PROVIDER=dashscope
LLM_RISK_SENTINEL_MODEL=qwen3.7-flash-2026-07-15
LLM_ACTION_PLANNER_PROVIDER=dashscope
LLM_ACTION_PLANNER_MODEL=qwen3.7-flash-2026-07-15

# Provider Keys（never 暴露给前端）
DASHSCOPE_API_KEY=
DEEPSEEK_API_KEY=
OPENAI_API_KEY=

# Base URL（可选）
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
OPENAI_BASE_URL=https://api.openai.com/v1

# Fallback（主挂时自动降级）
LLM_FALLBACK_PROVIDER=deepseek
LLM_FALLBACK_MODEL=deepseek-v4-flash

# Embedding（RAG 专用，与 Chat 独立）
EMBEDDING_AVAILABLE_PROVIDERS=local,openai
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIMENSION=1024

# Rerank（RAG 检索重排）
RERANK_ENABLED=true
RERANK_AVAILABLE_PROVIDERS=local
RERANK_PROVIDER=local
RERANK_MODEL=BAAI/bge-reranker-v2-m3
RERANK_TOP_K=20
RERANK_RETURN_N=5

# LLM Guard（安全护栏，非 Chat 模型）
GUARD_ENABLED=true
GUARD_MODE=rules
GUARD_MAX_INPUT_CHARS=10000
GUARD_MAX_OUTPUT_CHARS=8000
# GUARD_API_URL=http://llm-guard:8001  # 二期
```

### 4.3 示例套配置

**套 A：DeepSeek 主 + OpenAI 备**

```bash
LLM_AVAILABLE_PROVIDERS=deepseek,openai,mock
LLM_DEFAULT_PROVIDER=deepseek
LLM_DEFAULT_MODEL=deepseek-chat
LLM_FALLBACK_PROVIDER=openai
LLM_FALLBACK_MODEL=gpt-4o-mini
DEEPSEEK_API_KEY=sk-...
OPENAI_API_KEY=sk-...
```

**套 B：通义主 + DeepSeek 备**

```bash
LLM_AVAILABLE_PROVIDERS=dashscope,deepseek,mock
LLM_DEFAULT_PROVIDER=dashscope
LLM_DEFAULT_MODEL=qwen-plus
LLM_FALLBACK_PROVIDER=deepseek
LLM_FALLBACK_MODEL=deepseek-chat
DASHSCOPE_API_KEY=sk-...
DEEPSEEK_API_KEY=sk-...
```

---

## 5. 启动命令（P1 就绪后）

```bash
cp .env.example .env
# 编辑 .env 填入 API Key

docker compose up -d --build
docker compose exec api alembic upgrade head
docker compose exec api python -m scripts.seed  # P2

# 验证
curl http://localhost/api/health
curl http://localhost/api/health/ready
```

| 入口 | URL |
|---|---|
| Web | http://localhost |
| API Docs | http://localhost/api/docs |
| Admin LLM 设置 | http://localhost/settings/llm |

---

## 6. Redis 用途

| 用途 | MVP |
|---|---|
| JWT/session 黑名单 | 可选 |
| Rate limiting | 是 |
| RAG 检索短缓存 | 是 |
| Celery broker | 是（异步 index、健康度重算） |

---

## 7. RabbitMQ（二期）

MVP 使用 Redis + Celery。当出现以下情况再引入 RabbitMQ：

- 异步任务量大、需持久化队列
- 多 worker 横向扩展
- 死信队列需求

---

## 8. 监控（分期）

| 组件 | MVP | 命令/URL |
|---|---|---|
| 健康检查 | ✅ | GET /health, /health/ready |
| Prometheus metrics | ✅ P6 | GET /metrics ；compose 服务 :9090 |
| Grafana | ✅ P6 | http://localhost:3001 admin/admin |
| Langfuse | ✅ P6 适配层 | `.env` Key → Cloud；空 Key → Mock |
| 钉钉群机器人 | ✅ P8 | `.env` `DINGTALK_*` 或 Admin「LLM 设置」页；Secret 不回显 |

---

## 8.1 创建钉钉自定义机器人

1. 打开测试群 → 群设置 → 智能群助手 → 添加机器人 → **自定义**
2. 安全设置选择 **加签**（不要只用关键词）
3. 复制 Webhook URL 与 SEC 开头的 Secret 到 `.env`：

```
DINGTALK_ENABLED=true
DINGTALK_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=...
DINGTALK_SECRET=SECxxxxxxxx
```

4. `docker compose exec api alembic upgrade head`
5. 重启 `api` / `celery_worker` / `celery_beat`
6. Admin 登录 → LLM 设置页 → **发送测试消息**

无 Secret 时系统拒绝发送并打日志。22:00–08:00（上海）消息进 Redis，由 Beat 小时任务在静默期外补发。

---

## 9. 生产注意事项

- [ ] 修改默认 JWT_SECRET、数据库密码
- [x] Nginx TLS：compose 已开 443 + HTTP 301；公网替换自签证书
- [ ] `ALLOWED_ORIGINS` 仅生产域名；`RATE_LIMIT_AUTH_PER_MIN=5`、`RATE_LIMIT_EXTRACT_PER_MIN=10`
- [ ] API Key 使用 secrets 管理，不入 git
- [ ] 审计日志备份策略
- [ ] Postgres volume 持久化

---

## 10. 故障排查

| 现象 | 检查 |
|---|---|
| LLM 调用失败 | `/health/ready` 中 llm 状态；Key 是否配置 |
| Admin 看不到 Provider | `LLM_AVAILABLE_PROVIDERS` 与 Key 是否匹配 |
| pgvector 错误 | `CREATE EXTENSION vector` migration |
| 前端 502 | nginx → api/web 容器日志 |
