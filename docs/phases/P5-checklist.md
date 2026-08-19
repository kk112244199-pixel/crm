# P5 核查清单 — 真实 LLM Guard

| 属性 | 内容 |
|---|---|
| 阶段 | P5 |
| 目标 | 规则引擎升级为可配置的注入检测 + PII NER，可审计、可观测 |
| 预估 | 1 周 |
| 输入 | [PRD §14.1](../PRD.md)、[guardrails-hitl.md](../security/guardrails-hitl.md)、现有 Guard 模块 |
| **状态** | **✅ 已实现 — 2026-08-19**（golden 单测 12 passed） |

---

## 范围

**In**

- Prompt Injection 启发式评分 + Base64/中英变体；可选 `GUARD_API_URL` 分类器，不可用则规则降级
- PII NER（手机 / 18 位身份证校验 / 邮箱 / 带称谓中文名）+ 输出脱敏
- Admin `guard_config.sensitivity` 写入 `llm_settings`；`POST /admin/llm/guard/test`
- 拦截写入 `audit_log`（`guard.block`，snippet 已脱敏）；`montocrm_guard_blocked_total{reason}`
- `tests/test_guard_e2e.py`：10 注入 + 10 PII + 10 正常纪要

**Out**

- 自训分类模型、torch/`llm-guard` 重依赖
- 企业 DLP 产品对接

---

## 核查清单

### 检测能力

- [x] 输入扫描覆盖 `/activities/extract`、`/copilot/query`、`/copilot/draft`
- [x] 输出扫描覆盖 Copilot 回答与邮件草稿
- [x] Base64 / 中英混写覆盖 golden 攻击集
- [x] 姓名、手机、身份证、邮箱可识别并脱敏
- [x] 远程分类器不可用时规则降级

### 配置与审计

- [x] Admin 可调灵敏度 0–1；响应不含 API Key
- [x] 拦截 `guard.block`；snippet 脱敏
- [x] `guard_blocked_total` 定义于 metrics

### 测试

- [x] 注入检出率 ≥ 90%（10 条 golden）
- [x] PII 召回率 ≥ 85%（10 条）
- [x] 正常业务文本误判率 ≤ 5%

---

## 出口标准（进入 P6）

- [x] 本清单检测 + 测试项通过
- [x] `guardrails-hitl.md` 同步为 hybrid + NER
- [x] OpenAPI 标注 `guard_config` 与 `/admin/llm/guard/test`
