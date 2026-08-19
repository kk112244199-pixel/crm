# P9 核查清单 — CI/CD + Nginx 加固 + E2E

| 属性 | 内容 |
|---|---|
| 阶段 | P9 |
| 目标 | PR 可自动测；HTTPS 与限流；E2E 不再 flaky |
| 预估 | 1 周 |
| 输入 | [PRD §14.5](../PRD.md)、P4 遗留 asyncio fixture |
| **状态** | **✅ 完成 — 2026-08-19** |

---

## 范围

**In**

- GitHub Actions：pytest、compose build smoke；tag `v*` 推 GHCR
- `make eval` 周一定时（警告不阻断）
- Nginx：自签 SSL（可替换 Let's Encrypt）、HTTP→HTTPS、rate limit、安全头、CORS 白名单
- 修复 pytest-asyncio session loop；seed 用户 get-or-create
- writeback / guard / dingtalk E2E（Mock）

**Out**

- Kubernetes / 多环境 GitOps
- 多租户流水线

---

## 核查清单

### CI

- [x] `push` / `PR` 跑 API 单测（无 PG）+ 集成测（pgvector service）
- [x] compose build smoke（api + web）
- [x] 无 Langfuse/Dashscope Key 时 CI 仍绿（Mock）
- [x] README 指向 `.github/workflows/ci.yml`（仓库推到 GitHub 后可换官方 badge）

### Nginx / 安全

- [x] HTTPS 可访问；HTTP 301（本机 Apache 占 443 时宿主映射 `18443`，跳转 `https://host:18443`）
- [x] `/auth/token` 超频 429（Nginx 5r/m；API 生产建议 `RATE_LIMIT_AUTH_PER_MIN=5`）
- [x] `/activities/extract` 按 Authorization 前缀限流（Nginx 10r/m）
- [x] `X-Frame-Options`、`nosniff`、HSTS（生产 `APP_ENV=production` 或 Nginx always）
- [x] CORS 仅 `ALLOWED_ORIGINS`

### E2E

- [x] pytest-asyncio：function 作用域 loop + NullPool，去掉自定义 `event_loop`（避免 asyncpg 跨 loop）
- [x] writeback 3 条 golden parametrize
- [x] guard / dingtalk Mock 测试纳入 CI unit job
- [x] 限流/安全头单测不依赖 Postgres

---

## 出口标准（第二期结束）

- [x] 本清单全部勾选
- [x] [phase-2-overview.md](phase-2-overview.md) 出口标准同步勾选
- [x] OpenAPI **v2.0.0**
- [x] README 当前阶段 **P9 / 第二期完成**
