# 第二期总览 — Phase 2（P5–P9）

| 属性 | 内容 |
|---|---|
| 范围 | 第一期 MVP 之后的能力升级 |
| 文档 | [PRD §5.2 / §13 / §14](../PRD.md) |
| 预估 | 约 5 周 |
| **状态** | **✅ 第二期完成 — 2026-08-19** |

---

## 目标

把 MontoCRM 从「三条闭环可演示」升级到「真实销售团队可试跑」：护栏可量化、回答可评测、检索更准、关键事件能推到钉钉、合并请求有 CI。

## 已确认决策

| 议题 | 决策 |
|---|---|
| 多租户 | **第三期**；本期保持单租户 |
| IM 通知 | 钉钉**群自定义机器人 Webhook**（有测试群）；不做企业应用审批回调 |
| Ragas 标注 | 助手基于 10 条种子纪要生成 golden 草稿，业务过一遍确认 |
| 真实 SMTP / 企微企业应用 | 第三期 |

## 阶段顺序

| 阶段 | 目标 | 预估 | 清单 |
|---|---|---|---|
| P5 | LLM Guard 产品化 | 1 周 | [P5-checklist.md](P5-checklist.md) ✅ |
| P6 | Langfuse + Ragas + Grafana | 1 周 | [P6-checklist.md](P6-checklist.md) ✅ |
| P7 | 混合 RAG + Rerank | 1.5 周 | [P7-checklist.md](P7-checklist.md) ✅ |
| P8 | 钉钉 Webhook | 0.5 周 | [P8-checklist.md](P8-checklist.md) ✅ |
| P9 | CI/CD + SSL + E2E | 1 周 | [P9-checklist.md](P9-checklist.md) ✅ |

依赖：P6 的 Ragas 周报推钉钉依赖 P8 的发送层；可先 Mock Webhook，P8 再换成真机器人。P7 检索质量是 Ragas 分数的主要杠杆，P6 先搭评估架子、P7 后再跑对照。

## 明确不做（本期）

- 多租户 / RLS
- 钉钉/企微内点按钮确认 HITL
- 会前简报、线索评分、赢单复盘、客户成功
- 移动端、语音转写

## 出口标准（第二期结束）

- [x] P5–P9 清单全部勾选
- [x] Guard：注入检出 ≥90%，PII 召回 ≥85%，误判 ≤5%（见 P5 golden）
- [x] Ragas：启发式 runner 可跑；阈值警告不阻断（见 P6）
- [x] 钉钉：测试消息可送达（见 P8 冒烟）；CI 用 Mock
- [x] PR CI 绿；HTTPS + `/auth/token` 429
