# AI 原生 CRM — 产品需求文档（PRD）

| 属性 | 内容 |
|---|---|
| 产品代号 | MontoCRM（内部暂定名） |
| 文档版本 | v0.7 |
| 更新日期 | 2026-08-19 |
| 文档状态 | Draft — v0.7 补充第二期（P5–P9）需求 |
| 默认行业 | 工业软件 / 智能制造 ToB（大客户、项目型销售） |
| 产品语言 | 中文界面；对象/字段保留中英标识，便于 API 与扩展 |

---

## 1. 文档目的

本文档定义 AI 原生 CRM 第一期的产品范围、业务规则、功能需求与验收标准，供产品、研发、测试与真实销售团队对齐使用。

**读者**：产品负责人、后端/前端/Agent 研发、销售主管（业务验收人）。

**不在本文档范围**：详细接口字段定义（见《API 设计》）、数据库 DDL（见《数据模型》）、Agent 图结构（见《Agent 架构设计》）——PRD 完成后单独输出。

---

## 2. 产品愿景

### 2.1 一句话定义

**把 CRM 从「销售被要求填写的账本」，变成「会记忆、会提醒、会起草、关键动作等人拍板的 B2B 大客户作战系统」。**

### 2.2 我们要解决的核心痛点

| 痛点 | 现状 | 目标状态 |
|---|---|---|
| 录入负担 | 见完客户后补录，质量差或干脆不写 | 会议纪要/自然语言输入 → 系统自动理解并写回 |
| 信息碎片化 | 客户真实情况在人脑子里、在微信/邮件里 | 每次互动自动沉淀为可检索的客户记忆 |
| 经验难复制 | MEDDIC/决策链停在培训，新人靠猜 | 方法论内置为阶段检查点与健康度规则 |
| 事后诸葛亮 | 单子卡住、客户要流失时才发现 | 商机健康度实时预警，主管可干预 |

### 2.3 与「AI 增强型 CRM」的本质区别

| 维度 | AI 增强型 CRM | AI 原生 CRM（本产品） |
|---|---|---|
| 核心交互 | 菜单 + 表单，旁边挂聊天框 | 意图驱动；表单是结果工作台 |
| AI 角色 | 问答助手 | 一等公民 Agent：读、写、建议、待审批 |
| 数据模型 | 结构化字段为主 | 结构化 + 语义记忆双轨；写入即理解 |
| 流程 | 人配置工作流 | 业务规则 + Agent 编排 + HITL 审批 |
| 价值衡量 | 功能覆盖率 | 销售事务时间减少、预警提前量、写回采纳率 |

---

## 3. 目标用户与角色

### 3.1 用户画像

| 角色 | 代号 | 典型诉求 |
|---|---|---|
| 一线销售 | AE | 少填表；会前知道客户背景；会后自动生成纪要和待办 |
| 销售主管 | Sales Manager | 看团队 pipeline 风险；方法论被执行；不靠盯人 |
| 系统管理员 | Admin | 用户/角色/权限；审计；模型与阈值配置 |
| AI Agent | System Agent | 非人类用户；受 RBAC 与 HITL 约束 |

### 3.2 权限矩阵（MVP）

| 能力 | AE | Sales Manager | Admin |
|---|---|---|---|
| 查看本人客户/商机 | ✅ | ✅（团队） | ✅（全部） |
| 创建/编辑活动、纪要 | ✅ | ✅ | ✅ |
| 确认 Agent 写回建议 | ✅ | ✅ | ✅ |
| 推进商机阶段 | ✅（需确认） | ✅ | ✅ |
| 对外发送邮件 | ✅（需本人确认） | ✅ | ✅ |
| 修改商机金额 / 折扣 | ❌ | ✅（审批） | ✅ |
| 查看团队风险看板 | ❌ | ✅ | ✅ |
| 用户/角色/规则配置 | ❌ | ❌ | ✅ |
| **LLM Provider / 模型配置（Admin 设置页）** | ❌ | ❌ | ✅ |
| 查看 Agent 审计日志 | ❌ | ✅ | ✅ |

---

## 4. 产品原则（设计北极星）

以下原则来自 AI 原生 CRM 的核心思想，**所有功能设计必须对照检验**：

1. **Agent 是一等公民**：能读 CRM、写 CRM、调工具；不是页面插件。
2. **写入即理解**：非结构化输入（纪要、邮件摘要）进入后，必须完成实体抽取、关系映射、语义索引。
3. **意图驱动**：用户用自然语言表达目标；系统补全上下文（当前客户/商机/页面）。
4. **方法论内置**：阶段、决策链、健康度是系统规则，不是培训材料。
5. **分级信任（HITL）**：低风险自动，中风险确认，高风险审批；全程可审计。
6. **可测量进化**：关键 Agent 链路可追踪、可评测（架构预留 Langfuse + Ragas）。

---

## 5. 范围定义

### 5.1 MVP（第一期，必须交付）

**业务场景**：B2B 大客户 / 项目型销售（工业软件 / 智能制造 ToB）。

**三条闭环**（演示与验收最小集）：

| 闭环 | 名称 | 验证思想 |
|---|---|---|
| A | 会议纪要 → 智能写回 | 写入即理解 |
| B | 商机健康度与风险预警 | 方法论内置 |
| C | 自然语言查询 + 邮件草稿 + 发送审批 | Agent 协作 + HITL |

**MVP 功能清单**：

- 核心对象：Account（客户）、Contact（联系人）、Opportunity（商机）、Activity（活动/纪要）
- 决策链：5 类角色标注与健康度关联
- 商机 6 阶段 + 默认推进规则
- LangGraph Agent：**Orchestrator**（Planner + 并行专责 + 汇总）+ 混合检索 RAG
- 混合检索 RAG：向量 + 关键词 + Rerank（客户记忆检索）
- HITL：写回确认、阶段推进确认、对外发送确认
- **LLM Provider 可切换**：`.env` 白名单 + Admin「模型配置」三 Tab（对话 / 检索 / 护栏）（见 §10.5）
- 认证授权：JWT + RBAC
- 审计日志：Agent 与人工操作均可追溯
- 种子数据：接近真实业务体量的模拟数据
- Docker Compose 一键启动

### 5.2 第二期（本轮规划，见 §14）

从「能演示」升级为「能给真实销售团队试跑」：安全、可观测、检索质量、IM 通知、CI/CD。

| 阶段 | 内容 |
|---|---|
| P5 | 真实 LLM Guard（注入分类 + PII NER） |
| P6 | Langfuse SDK + Ragas 评估 + Grafana |
| P7 | 混合 RAG（BM25 + Vector）+ Rerank + Query Rewriting |
| P8 | 钉钉群自定义机器人 Webhook 通知 |
| P9 | GitHub Actions CI + Nginx SSL/限流 + E2E 稳定化 |

**明确推迟到第三期及以后**：多租户、企微/钉钉企业应用审批回调、真实 SMTP、会前简报、线索评分、赢单复盘、客户成功、MCP 外部系统、移动端。

### 5.3 明确不做（第一期；第二期仍不做）

- 营销自动化（MA）、广告投放、全渠道线索汇聚
- CPQ / 合同 / 电子签
- 电话录音实时接入、语音转写
- 移动端 App
- 多语言国际化
- **普通销售（AE）自行切换 LLM**（仅 Admin 可配）
- **在前端填写或修改 API Key**（密钥仅允许在服务端 `.env` 配置）
- **多租户 / 计费**（第三期）

---

## 6. 领域模型

### 6.1 核心对象

```
Account（客户/公司）
  ├── Contact（联系人）× N
  ├── Opportunity（商机）× N
  └── Activity（活动）× N
        └── 关联 Opportunity（可选）

Opportunity（商机）
  ├── 所属 Account
  ├── 关联 Contact（决策链成员）
  └── Activity × N
```

### 6.2 Account（客户）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | 主键 |
| name | string | 公司名称 |
| industry | enum | 行业（默认：工业软件、智能制造、能源、医疗…） |
| size | enum | 规模：SMB / Mid / Enterprise |
| region | string | 区域 |
| description | text | 公司简介 |
| created_at / updated_at | datetime | 审计 |

### 6.3 Contact（联系人）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | 主键 |
| account_id | FK | 所属客户 |
| name | string | 姓名 |
| title | string | 职位 |
| email / phone | string | 联系方式 |
| role_in_deal | enum | 决策链角色（见 6.5） |
| influence_level | enum | high / medium / low |
| last_contacted_at | datetime | 最近互动时间 |
| notes | text | 备注 |

### 6.4 Opportunity（商机）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | 主键 |
| account_id | FK | 所属客户 |
| name | string | 商机名称 |
| amount | decimal | 预计金额（CNY） |
| stage | enum | 阶段（见 7.1） |
| expected_close_date | date | 预计成交日 |
| owner_id | FK | 负责销售 |
| competitor | string | 主要竞对 |
| pain_points | text[] | 已识别痛点 |
| budget_status | enum | unknown / estimated / confirmed / approved |
| health_score | int | 0–100，系统计算 |
| health_status | enum | green / yellow / red |
| last_activity_at | datetime | 最近活动时间 |
| win_loss_reason | text | 赢单/丢单原因（结案时填写） |

### 6.5 决策链角色（role_in_deal）

| 枚举值 | 中文 | 说明 |
|---|---|---|
| economic_buyer | 经济买家 | 能批预算 |
| technical_buyer | 技术把关 | 能否决方案 |
| user_buyer | 使用者 | 日常使用者 |
| coach | 教练 | 内部推动者 |
| influencer | 影响者 | 能影响但不拍板 |
| unknown | 未识别 | 待 Agent/销售补充 |

### 6.6 Activity（活动）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | 主键 |
| account_id | FK | 所属客户 |
| opportunity_id | FK | 关联商机（可选） |
| type | enum | meeting / call / email / note / agent_action |
| subject | string | 主题 |
| content | text | 原始内容（纪要、邮件正文等） |
| structured_summary | jsonb | Agent 抽取的结构化摘要 |
| created_by | FK | 创建人（或 agent） |
| occurred_at | datetime | 实际发生时间 |

### 6.7 语义记忆（Memory Chunk）

与 Activity 关联，供 RAG 检索；写入 Activity 后异步生成。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | 主键 |
| source_type | enum | activity / agent_derived |
| source_id | FK | 来源 ID |
| account_id / opportunity_id | FK | 归属 |
| chunk_text | text | 分块文本 |
| embedding | vector | pgvector |
| metadata | jsonb | 实体、角色、情感、竞对等 tags |

---

## 7. 业务规则

> **说明**：以下为按 B2B 大客户销售市场惯例设定的默认规则。上线前由销售主管确认阈值；规则本质上是**业务流程节点上的判定条件**。

### 7.1 商机阶段定义

| 阶段代码 | 中文 | 含义 | 进入条件（摘要） |
|---|---|---|---|
| qualified | 线索确认 | 确认为真实机会 | 有明确需求或主动询价 |
| discovery | 需求澄清 | 痛点、预算、时间窗 | ≥1 次有效沟通 |
| proposal | 方案/POC | 方案、演示、试点 | 有技术/业务对接人 |
| negotiation | 商务谈判 | 价格、合同、采购 | 有明确报价意向 |
| closed_won | 赢单 | 签约 | 合同确认 |
| closed_lost | 丢单 | 失败 | 客户选竞对/暂停/无预算 |

**阶段推进规则**：

- Agent **不得自动推进阶段**；仅可「建议推进」并生成待确认任务。
- 销售确认推进时，系统校验当前阶段必填项（见 7.4）。
- 主管可强制修改阶段（需填写原因，记入审计）。

### 7.2 商机健康度规则

健康分基础分 100，按下列规则扣分，得分映射状态：

| 状态 | 分数区间 |
|---|---|
| green | 80–100 |
| yellow | 50–79 |
| red | 0–49 |

**扣分规则（默认）**：

| 规则 ID | 条件 | 扣分 | 严重级别 |
|---|---|---|---|
| H001 | 当前阶段停留 > 14 天且无 Activity | -15 | yellow |
| H002 | 当前阶段停留 > 30 天且无 Activity | -35 | red |
| H003 | 金额 ≥ 50 万且缺 economic_buyer | -25 | red |
| H004 | 阶段 ≥ proposal 且 budget_status = unknown | -15 | yellow |
| H005 | 提到竞对但 7 天内无应对 Activity | -10 | yellow |
| H006 | 任一 high influence 联系人 > 30 天未互动 | -10 | yellow |
| H007 | expected_close_date 已过且未结案 | -20 | red |
| H008 | discovery 阶段未记录 pain_points | -10 | yellow |

健康度**每日批量重算** + 关键 Activity 写入后**触发重算**。

### 7.3 HITL 动作分级

| 级别 | 动作示例 | 策略 |
|---|---|---|
| L0 自动 | 内部检索、生成摘要、创建内部待办草稿、更新非关键标签 | Agent 直接执行，记审计 |
| L1 确认 | 写回 Activity 结构化字段、创建/更新 Contact、建议阶段推进 | 销售点击「确认」后生效 |
| L2 审批 | 修改 amount、对外发送邮件、阶段推进至 negotiation+ | 销售确认；amount 变更需主管审批 |
| L3 禁止 | 删除 Account/Opportunity、覆盖 closed 商机 | 仅人工，Agent 不可触发 |

### 7.4 阶段必填项校验（推进时）

| 目标阶段 | 必填 |
|---|---|
| discovery | ≥1 Contact，≥1 pain_point |
| proposal | ≥1 technical_buyer 或 user_buyer |
| negotiation | economic_buyer 或 budget_status ≥ estimated |
| closed_won | amount，win_loss_reason |
| closed_lost | win_loss_reason |

### 7.5 Agent 行为边界

- Agent 工具调用受 RBAC 约束，不得越权访问其他销售私海（主管除外）。
- 任何 L1+ 动作生成 `PendingAction` 记录，48 小时未处理则过期提醒。
- Agent 输出必须附 `reasoning` 与 `evidence`（引用的 Activity/Memory 来源）。
- 对外内容（邮件）必须经过 LLM Guard 输出扫描（MVP 可先做关键词+长度规则，二期接 LLM Guard 完整能力）。

---

## 8. MVP 场景与用户故事

### 8.1 闭环 A — 会议纪要 → 智能写回

**用户故事**：作为 AE，我希望粘贴会议纪要让系统自动提取关键信息并更新客户/商机，以便我不必手工填表。

**主流程**：

1. AE 在商机详情页点击「录入纪要」，**粘贴文本或上传** txt / md / docx / pdf（录音见 RAG 预处理规范）。
2. 系统 **预处理**（Parse + Normalize）→ 得到 `canonical_text`。
3. 系统调用 **Orchestrator**（LangGraph）：
   - **Planner**：识别 Account/Opportunity/Contact，决定并行激活 A/B/C/D
   - **客户洞察** 决策链 · **商机研判** MEDDIC · **风险预警** H001–H008 · **行动规划** 待办（可选）
   - **汇总 Agent**：合并 → **WritebackProposal**（含各子 Agent evidence）
4. AE 在 diff 视图中逐项确认/修改/拒绝。
5. 确认后写入业务表；异步对 **canonical_text** 按分块策略 chunk + embed 索引。
6. 触发商机健康度重算。

**验收标准**：

- [ ] 300–2000 字中文纪要，≤30s 返回抽取结果（不含 LLM 冷启动）
- [ ] 正确识别已存在 Contact；新联系人进入「待确认创建」
- [ ] 写回前不修改业务表；确认后才生效
- [ ] 每次写回有完整审计记录（谁确认、改了什么）
- [ ] 纪要入库后可被 NL 查询检索到

**异常场景**：

| 场景 | 系统行为 |
|---|---|
| 无法匹配客户 | 提示 AE 手动选择 Account/Opportunity |
| 纪要为空/过短 | 拒绝处理，提示最小长度 |
| 抽取置信度低 | 字段标黄，默认不勾选，需人工勾选 |
| AE 全部拒绝 | 仅保存原始 Activity，不更新其他对象 |

---

### 8.2 闭环 B — 商机健康度与风险预警

**用户故事**：作为 Sales Manager，我希望一眼看到团队哪些商机有风险、卡在哪，以便提前辅导而不是月底才救火。

**主流程**：

1. 系统按 7.2 规则计算 health_score / health_status。
2. AE 在商机列表看到健康度灯号与扣分原因。
3. Sales Manager 在「团队风险看板」看到：
   - 红灯商机列表（按金额排序）
   - 扣分原因分布
   - 停留阶段过久 Top N
4. 点击商机可查看 Agent 生成的「风险说明与建议动作」（只读建议，不自动执行）。

**验收标准**：

- [ ] 种子数据中至少 5 条商机可稳定触发 yellow/red
- [ ] 扣分原因可展开，对应规则 ID（H001–H008）
- [ ] Activity 写回后 1 分钟内健康度更新
- [ ] 主管只能看本团队数据

**异常场景**：

| 场景 | 系统行为 |
|---|---|
| 新商机无 Activity | 默认 100 分 green，或按创建天数轻微扣分（可配置） |
| 规则冲突 | 取最严重状态；扣分累加上限 100 |

---

### 8.3 闭环 C — 自然语言查询 + 邮件草稿 + 发送审批

**用户故事**：作为 AE，我希望用自然语言问客户情况并让系统起草邮件，但发送前必须由我确认。

**主流程 — 查询**：

1. AE 在客户/商机详情页打开 Copilot 面板（带 page context）。
2. 输入：「这个客户最担心什么？」「我们上次承诺了什么？」
3. **Orchestrator**（`copilot_query`）：Planner 激活 A∥B∥C（简单问句可降级单路）→ 混合检索 + Rerank → **汇总 Agent** 生成带 citation 的回答。
4. 回答必须标注引用来源（Activity 链接）。

**主流程 — 邮件**：

1. AE 输入：「帮张总写一封会后跟进邮件，强调交付周期优势。」
2. **Orchestrator**（`copilot_draft`）：Planner + A∥B∥D 并行 → **汇总 Agent** 生成邮件主题+正文。
3. 创建 `PendingAction`（type=send_email，级别 L2）。
4. AE 编辑 → 点击「确认发送」→ 调用邮件适配器（MVP：Mock 发送 + 记录；可配置 SMTP）。
5. 发送成功后创建 Activity（type=email）。

**验收标准**：

- [ ] 查询响应引用 ≥1 条来源；无来源时明确说「未找到记录」
- [ ] 邮件未确认前不会发送
- [ ] 邮件发送记录进 Activity 与审计
- [ ] Copilot 不带 page context 时，需澄清「您指的是哪个客户？」

---

## 9. Agent 设计概要

### 9.1 编排模型（MontoForce 风格 — Planner + 并行 + 汇总）

采用 **Harness → Primary → Planner → 专责 Agent 并行（fan-out）→ 汇总 Agent（fan-in）→ HITL** 架构，对齐 MontoForce「多 Agent 协作」与多子任务并行处理（详见 [agent-architecture.md](architecture/agent-architecture.md)）。

```text
Planner → [ 客户洞察 ∥ 商机研判 ∥ 风险预警 ∥ 行动规划(可选) ] → 汇总 Agent → HITL
```

| 层次 | Agent / 组件 | 职责 |
|---|---|---|
| Planner | 规划 | 意图分解；决定并行激活哪些专责 Agent |
| 客户洞察 | customer_insight | 联系人、决策链、关系变化 |
| 商机研判 | opportunity_judge | 阶段、痛点、预算、竞对 |
| 风险预警 | risk_sentinel | 规则 H001-H008 + 纪要/Copilot 风险信号 |
| 行动规划（可选） | action_planner | 待办、next best action |
| 汇总 Agent | 综合 | 合并并行结果 → WritebackProposal / Copilot 回答 / 邮件草稿 |
| Health 批算 | 规则 + C | 写回后或定时重算 health_score |

**不再使用**「5 条互不相干、纯串行流水线」作为目标设计；对外 API 不变，**内部统一 Orchestrator 图**。

### 9.2 Agent 清单与触发（对外能力映射）

| 对外场景 | Planner scene | 并行 Agent | 汇总输出 |
|---|---|---|---|
| 闭环 A 纪要写回 | `meeting_extract` | 客户洞察 ∥ 商机研判 ∥ 风险预警 ∥ 行动规划 | WritebackProposal → HITL L1 |
| 闭环 B 健康度 | `health_batch`（每日 Cron，默认凌晨 2 点）/ 写回后联动触发 | 风险预警 + 规则引擎 | health_score + 风险说明 |
| 闭环 C Copilot 查询 | `copilot_query` | 客户洞察 ∥ 商机研判 ∥ 风险预警（Planner 可降级单路） | 带 citation 的回答 |
| 闭环 C 邮件草稿 | `copilot_draft` | 客户洞察 ∥ 商机研判 ∥ 行动规划 | 邮件草稿 → HITL L2 |

### 9.3 编排原则

- 使用 **LangGraph** `Send` / join 实现 **fan-out / fan-in**；状态在 `CRMGraphState` 共享。
- 专责 Agent **只写 GraphState**，不改业务表；写库仅在 HITL confirm 之后。
- 某路 Agent 失败时 **部分降级**，汇总 Agent 标注缺失并继续。
- 工具层：Planner/A/B/C/D/Synth 共享 Tool Registry；RBAC 在 tool 层强制。
- 长对话 checkpoint 到 PostgreSQL；P4 可选 SSE 推送各 Agent 进度（War-room UI）。
- 二期 MCP：工具层抽象为 MCP Server。

### 9.4 记忆与 RAG

| 层级 | 实现 |
|---|---|
| 结构化记忆 | PostgreSQL 业务表 |
| 语义记忆 | pgvector + `pg_trgm` / ILIKE 关键词 |
| **写入预处理** | 文本/Word/PDF/Markdown/录音(ASR) → Parse + Normalize → `canonical_text`（[rag-pipeline §4](architecture/rag-pipeline.md)） |
| **分块策略** | fixed / recursive / semantic / structured；默认 `auto` 按格式路由 |
| **Query 改写** | **必做**；检索前改写 + 指代消解（[rag-pipeline §6](architecture/rag-pipeline.md)） |
| 检索策略 | 改写后混合检索 → RRF 融合 → Cross-Encoder Rerank |
| 写入时机 | Activity 确认写回后异步 preprocess → chunk → embed |

---

## 10. 非功能需求

### 10.1 性能

| 指标 | MVP 目标 |
|---|---|
| 纪要抽取 P95 | ≤ 30s（2000 字） |
| NL 查询 P95 | ≤ 10s |
| 列表页加载 | ≤ 2s（100 条商机） |
| 健康度重算 | ≤ 5s/商机 |

### 10.2 安全与合规

- 全站 HTTPS（生产）；JWT 过期与刷新。
- 敏感字段（金额、联系方式）按角色脱敏展示（二期）。
- 审计日志保留 ≥ 180 天（可配置）。
- Agent 输出对外内容前做安全扫描（MVP 规则引擎，二期 LLM Guard）。

### 10.3 可观测性（分期）

| 能力 | MVP | 二期 |
|---|---|---|
| 结构化日志 | ✅ | ✅ |
| Agent trace | 基础 JSON 日志 | Langfuse 全链路 |
| 质量评测 | 人工抽检 | Ragas 自动门禁 |
| 指标大盘 | 健康检查接口 | Prometheus + Grafana |

### 10.4 部署

- Docker Compose 一键启动：api、web、postgres、redis（缓存/队列）。
- LLM 与 Provider 配置通过环境变量或配置文件注入，详见 §10.5。

### 10.5 LLM Provider 可切换策略

> **产品要求**：系统不得绑定单一 LLM 厂商。切换 Provider 或模型时，三条 MVP 闭环（纪要写回、健康度、Copilot）必须仍可运行，且**无需修改业务代码**（仅改配置）。实现细节见《技术架构设计》LLM 抽象层章节。

#### 10.5.1 设计目标

| 目标 | 说明 |
|---|---|
| 厂商无关 | 业务与 Agent 逻辑不直接依赖某一 SDK 或固定 endpoint |
| 配置驱动 | 通过 `.env` 注册 Provider 白名单；**Admin 在前端选择**生效 Provider/模型（DB 覆盖 `.env` 默认） |
| 按 Agent 分模型 | 不同 Agent 可使用不同模型（成本与质量平衡） |
| 可降级 | 主模型失败时可切换备用模型（MVP 可选，架构必须预留） |
| 可观测 | 每次 LLM 调用记录 provider、model、latency（MVP 结构化日志；二期 Langfuse） |

#### 10.5.2 MVP 支持的 Provider 类型

| 类型 | 示例 | MVP 要求 |
|---|---|---|
| OpenAI 兼容 API | OpenAI、DeepSeek、Groq、本地 Ollama（OpenAI 兼容网关） | **必须支持** |
| 国内云 API | 通义千问（DashScope）、智谱、Moonshot 等（OpenAI 兼容或适配器） | **必须支持至少一种**（通过兼容层或 Provider 适配器） |
| 直连专有 SDK | 仅某厂商独有 SDK、无兼容 endpoint | **MVP 不做**；二期按需加 Adapter |

**统一约定**：后端通过 **LLM Provider 抽象层**（如 `LLMProvider` / `get_chat_model(agent_name)`）获取模型实例；Agent 代码只依赖抽象接口，不硬编码 `gpt-4o` 等模型名。

#### 10.5.3 配置项（MVP 最小集）

| 配置项 | 说明 | 示例 |
|---|---|---|
| `LLM_DEFAULT_PROVIDER` | 全局默认 Provider | `openai` / `deepseek` / `dashscope` |
| `LLM_DEFAULT_MODEL` | 全局默认模型 | `gpt-4o-mini` / `deepseek-chat` |
| `LLM_<AGENT>_PROVIDER` | 按 Agent 覆盖 Provider | `LLM_PLANNER_PROVIDER=deepseek` |
| `LLM_<AGENT>_MODEL` | 按 Agent 覆盖模型 | `LLM_SYNTH_MODEL=deepseek-chat` |
| `<PROVIDER>_API_KEY` | 各 Provider 密钥 | `OPENAI_API_KEY`、`DEEPSEEK_API_KEY` |
| `<PROVIDER>_BASE_URL` | 可选，自定义 endpoint | `https://api.deepseek.com/v1` |
| `LLM_FALLBACK_PROVIDER` | 备用 Provider（可选） | `openai` |
| `LLM_FALLBACK_MODEL` | 备用模型（可选） | `gpt-4o-mini` |
| `LLM_TIMEOUT_SECONDS` | 单次调用超时 | `60` |
| `LLM_MAX_RETRIES` | 失败重试次数 | `2` |
| `LLM_AVAILABLE_PROVIDERS` | **前端可选 Provider 白名单**（逗号分隔） | `deepseek,openai,dashscope` |
| `LLM_<PROVIDER>_MODELS` | 可选，该 Provider 在前端展示的模型列表 | `deepseek-chat,deepseek-reasoner` |

**配置优先级（生效顺序，后者覆盖前者）**：

1. `.env` / `config/llm.yaml` — 部署默认值、API Key、白名单  
2. **数据库 `llm_settings`（Admin 前端保存）** — 当前运行配置  
3. 单次请求级 override — **MVP 不做**

**Agent 名称与配置键对应（MVP）**：

| Agent | 配置前缀（建议） | 说明 |
|---|---|---|
| Planner | `LLM_PLANNER_*` | 意图与并行路由 |
| 客户洞察 | `LLM_CUSTOMER_INSIGHT_*` | 决策链、联系人 |
| 商机研判 | `LLM_OPPORTUNITY_JUDGE_*` | 阶段、痛点、竞对 |
| 风险预警 | `LLM_RISK_SENTINEL_*` | 规则 + 风险叙述 |
| 行动规划 | `LLM_ACTION_PLANNER_*` | 待办、next step |
| 汇总 Synth | `LLM_SYNTH_*` | 合并 Proposal / 回答 |
| Copilot 润色 | `LLM_QUERY_*` | 最终问答表达 |
| Draft 邮件润色（可选） | `LLM_DRAFT_*` | `copilot_draft` 最终润色；默认可跟随 `LLM_SYNTH_*` |

未配置时回退 `LLM_DEFAULT_*`。Extract/Writeback/Health/Query/Draft 旧键名可映射到上表（兼容 .env）。

#### 10.5.4 Admin 前端切换（MVP 必须）

> **模式**：运维在 `.env` 配好 **API Key + Provider 白名单**；**Admin 在设置页**选择当前使用的 Provider/模型，**无需改代码、无需重启**（热生效）。前端** never** 接触密钥。

**页面入口**：`设置 → 模型配置`（仅 Admin 可见）。MVP 采用 **三个 Tab**，与 Chat LLM 配置对齐：

| Tab | 内容 | 详见 |
|---|---|---|
| **对话模型** | 全局默认 + 按 Agent（Planner/客户洞察/商机研判/风险预警/行动规划/汇总/Copilot）+ Fallback + 连接测试 | §10.5.3 |
| **检索模型** | Embedding + Rerank（RAG 专用，与 Chat 独立） | §10.5.5 |
| **安全护栏** | Guard 开关与 Scanner 列表（MVP 规则模式） | §10.5.5 |

**对话模型 Tab 能力**：

| 区块 | 内容 |
|---|---|
| 全局默认 | 默认 Provider + Model（下拉，选项来自白名单） |
| 按 Agent 配置 | Planner / 客户洞察 / 商机研判 / 风险预警 / 行动规划 / 汇总 / Copilot；可勾选「跟随全局默认」 |
| Fallback | 可选备用 Provider + Model |
| 连接测试 | 对所选 Chat Provider 发最小请求，返回成功/失败与延迟 |
| 当前生效配置 | 只读：各 Agent 实际 provider/model（DB + `.env` 合并结果） |

**检索模型 Tab 能力**：

| 区块 | 内容 |
|---|---|
| Embedding | Provider + Model + 维度（只读）；变更时 **强制提示 re-index** |
| Rerank | 开关、Provider + Model、TopK / ReturnN |
| 检索测试 | 输入样例 query，返回 **rewritten_query** + Top chunks（不调 Chat LLM） |

**安全护栏 Tab 能力（MVP）**：

| 区块 | 内容 |
|---|---|
| 总开关 | `GUARD_ENABLED` |
| 模式 | `rules`（MVP 固定）；二期可选 `llm-guard` |
| 输入规则 | 最大长度、敏感词组（展示 `.env` 预设；二期 Admin 可编辑） |
| 输出规则 | 邮件占位符检测、对外内容扫描开关 |

**下拉选项规则**：

- 仅展示 `LLM_AVAILABLE_PROVIDERS` 中且 **对应 API Key 已在 `.env` 配置** 的 Provider  
- 未配置 Key 的 Provider 显示为禁用，附文案「未在服务器配置密钥」  
- 模型列表来自 Provider 适配器内置列表 + 可选 `LLM_<PROVIDER>_MODELS` 环境变量  

**后端 API（MVP，写入 OpenAPI 契约）**：

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/api/v1/llm/options` | Admin | 返回可选 Provider/Model（无 Key） |
| GET | `/api/v1/admin/llm/settings` | Admin | 当前 DB 中保存的配置 |
| PUT | `/api/v1/admin/llm/settings` | Admin | 保存配置；写审计日志 |
| POST | `/api/v1/admin/llm/test` | Admin | 测试指定 Provider/Model 连通性 |

**持久化（`llm_settings` 表，单行或 key-value）**：

| 字段 | 说明 |
|---|---|
| default_provider / default_model | Chat 全局默认 |
| agent_overrides | JSON：`{ "planner": { "provider", "model" }, "customer": {...}, "synth": {...}, ... }`；旧键 `extract` 等可映射 |
| embedding_provider / embedding_model | RAG Embedding（§10.5.5） |
| rerank_enabled / rerank_provider / rerank_model | Rerank 配置（§10.5.5） |
| rerank_top_k / rerank_return_n | Rerank 候选数 / 返回数 |
| guard_enabled / guard_mode | 护栏总开关与模式（§10.5.5） |
| guard_config | JSON：输入/输出 scanner 列表（MVP subset） |
| fallback_provider / fallback_model | Chat 备用 |
| updated_by / updated_at | 审计 |

**安全与审计**：

- 仅 **Admin** 角色可访问上述 API 与页面  
- 每次保存记录：操作人、变更 diff（旧值→新值）、时间戳  
- API Key **不得**通过 API 读取或写入；PUT 请求体拒绝含 `api_key` 字段  

**与普通销售的关系**：

- AE / Sales Manager **不能**在前端切换 LLM（MVP）  
- Copilot 与 Orchestrator（纪要写回 / 查询 / 草稿）自动使用 Admin 已配置的模型，对用户透明  

#### 10.5.5 检索与安全模型配置

> **原则**：Embedding、Rerank、LLM Guard **不得与 Chat LLM 混为同一模型下拉**。三者与 Chat 一样：**`.env` 注册能力与 Key → Admin 前端选择生效模型/开关 → DB 覆盖 `.env` 默认 → 热生效**。API Key **never** 经前端或 API 读写。

##### 10.5.5.1 三类模型/服务的定位

| 类型 | 用途 | 是否 Chat LLM | 换模型是否 re-index |
|---|---|---|---|
| **Embedding** | Activity → 向量，供语义检索 | ❌ | **是**，必须全库 re-index |
| **Rerank** | 混合检索后对候选重排序 | ❌ | **否**，即时生效 |
| **LLM Guard** | 输入/输出安全扫描 | ❌（Scanner/规则服务） | 不适用 |

##### 10.5.5.2 Embedding 配置（MVP）

| 配置项 | 说明 | 示例 |
|---|---|---|
| `EMBEDDING_AVAILABLE_PROVIDERS` | Embedding 白名单 | `local,openai,dashscope` |
| `EMBEDDING_PROVIDER` | 默认 Provider | `local` / `openai` |
| `EMBEDDING_MODEL` | 模型名 | `bge-small-zh-v1.5` / `text-embedding-3-small` |
| `EMBEDDING_DIMENSION` | 向量维度（与 pgvector 列一致） | `512` / `1536` |
| `EMBEDDING_BASE_URL` | 可选 API endpoint | — |
| `<PROVIDER>_API_KEY` | 共用 Chat 的 Key 或独立 Key | `OPENAI_API_KEY` |

**抽象层**：`get_embedding_model()` — RAG ingest 与 query 统一调用；**禁止**在 Agent 内硬编码模型名。

**Admin 变更 Embedding 模型时**：

1. 保存配置前弹窗：**「变更 Embedding 模型需 re-index 全部 memory_chunks，是否继续？」**
2. 确认后：标记 `reindex_required=true`，触发异步 `scripts/reindex.py`（或 Admin「立即 re-index」按钮）
3. re-index 完成前，Copilot 查询可继续用旧向量或提示「索引重建中」（实现二选一，文档默认：**允许查询旧索引 + 后台重建**）

##### 10.5.5.3 Rerank 配置（MVP）

| 配置项 | 说明 | 示例 |
|---|---|---|
| `RERANK_ENABLED` | 是否启用重排 | `true` |
| `RERANK_AVAILABLE_PROVIDERS` | 白名单 | `local,cohere` |
| `RERANK_PROVIDER` | Provider | `local` / `cohere` |
| `RERANK_MODEL` | Cross-Encoder 或 API 模型 | `BAAI/bge-reranker-base` |
| `RERANK_TOP_K` | 参与 rerank 的 RRF 候选数 | `20` |
| `RERANK_RETURN_N` | 交给 LLM 的最终条数 | `5` |
| `RERANK_API_KEY` | API 型 reranker 密钥 | 可选 |

**抽象层**：`rerank(query, documents) -> ranked_docs`；`RERANK_ENABLED=false` 时跳过，直接取 RRF Top `RERANK_RETURN_N`。

**默认推荐（MVP）**：本地 `bge-reranker-base`，无额外 API 成本。

##### 10.5.5.4 LLM Guard 配置（MVP / 二期）

Guard **不是**第 6 个 Chat Agent，而是独立 **Guard Service / 规则引擎**。

| 配置项 | MVP | 说明 |
|---|---|---|
| `GUARD_ENABLED` | ✅ | 总开关 |
| `GUARD_MODE` | `rules` | MVP 固定；二期 `llm-guard` |
| `GUARD_MAX_INPUT_CHARS` | ✅ | 如 `10000` |
| `GUARD_MAX_OUTPUT_CHARS` | ✅ | 如 `8000` |
| `GUARD_BLOCK_PATTERNS` | ✅ | 敏感词/正则（env 或配置文件） |
| `GUARD_API_URL` | 二期 | 独立 llm-guard-api 服务地址 |
| `GUARD_INPUT_SCANNERS` | 二期 | 如 `prompt_injection,toxicity,secrets` |
| `GUARD_OUTPUT_SCANNERS` | 二期 | 如 `toxicity,secrets,relevance` |
| `GUARD_MODEL_PROVIDER` | 二期 | Guard 内置小模型（若有） |

**扫描挂载点**（见 [guardrails-hitl.md](security/guardrails-hitl.md)）：

- Copilot **输入**（用户问题、纪要文本）→ 输入 Guard  
- Agent **对外输出**（邮件草稿、即将发送正文）→ 输出 Guard  
- 拦截时：返回明确错误码 + 审计；**不调用** Chat LLM（输入拦截）或 **不进入** PendingAction 发送（输出拦截）

**Admin 安全护栏 Tab（MVP）**：可切换 `GUARD_ENABLED`、查看当前 rules 摘要；**二期**可编辑 Scanner 列表。

##### 10.5.5.5 配置优先级与 API 扩展

与 Chat 一致：**DB `llm_settings` > `.env` 默认**。

`PUT /api/v1/admin/llm/settings` 请求体扩展字段（与 Chat 同一次保存或分 Tab 保存均可）：

- `embedding_provider`, `embedding_model`
- `rerank_enabled`, `rerank_provider`, `rerank_model`, `rerank_top_k`, `rerank_return_n`
- `guard_enabled`, `guard_mode`, `guard_config`

新增（MVP 建议）：

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/admin/rag/test-retrieval` | Admin 测试检索（Embedding+Rerank，无 Chat） |
| POST | `/api/v1/admin/rag/reindex` | 触发全库 re-index |
| GET | `/api/v1/admin/rag/reindex-status` | re-index 进度 |

##### 10.5.5.6 RAG 预处理与分块（MVP）

| 要求 | 说明 |
|---|---|
| 预处理在组装前 | 上传/粘贴须经 Parse + Normalize，索引使用 `canonical_text` |
| 支持格式 MVP | txt、md、docx、pdf（基础抽文本）；录音 ASR 可配置，未配置则拒绝 |
| 分块策略 | 支持 fixed / recursive / semantic / structured；默认 `auto` |
| Query 改写 | **必做**；`search_memory` 无跳过路径 |

Admin「检索模型」Tab 可增加：`CHUNK_STRATEGY`、`CHUNK_SIZE`、`CHUNK_OVERLAP`（变更仅影响新索引，见 rag-pipeline §5.3）。

##### 10.5.5.7 检索与安全模型验收标准

- [ ] Embedding 与 Chat 使用**独立**配置项；切换 Chat **不**影响已入库向量
- [ ] Admin 变更 Embedding 后，系统提示 re-index；re-index 脚本可完成全库重建
- [ ] `RERANK_ENABLED=false` 时 Copilot 仍可用（降级为 RRF TopN）
- [ ] Admin 可切换 Rerank Provider/Model，下一条检索即生效（无需 re-index）
- [ ] `GUARD_ENABLED=false` 时仅记录告警（开发环境）；生产默认 `true`
- [ ] 输入 Guard 拦截恶意超长文本；输出 Guard 拦截含 `{TODO}` 的待发送邮件
- [ ] 日志含 `embedding_provider/model`、`rerank_provider/model`、`guard_mode`、拦截原因
- [ ] 上传 docx/md 经预处理后索引；Copilot 可检索到正文内容
- [ ] Query 改写必做：检索 meta 含 `raw_query` 与 `rewritten_query`
- [ ] 分块策略 `auto`：md 走 structured，纯文本走 recursive

#### 10.5.6 Fallback 与降级（MVP 范围）

| 能力 | MVP | 说明 |
|---|---|---|
| 单 Provider 内重试 | **必须** | 超时、429、5xx 指数退避重试 |
| 跨 Provider Fallback | **建议** | 主 Provider 连续失败后切换 `LLM_FALLBACK_*` |
| 离线 Mock Provider | **必须（开发/测试）** | 无 API Key 时可跑通 UI 与 HITL 流程（固定 JSON 响应） |
| **Admin 前端切换 Provider/模型** | **必须** | 见 §10.5.4；DB 配置热生效 |
| Admin 前端连通性测试 | **必须** | `POST /admin/llm/test` |

#### 10.5.7 切换验收标准

- [ ] 仅修改 `.env`（或 `config/llm.yaml`），不修改 Python/TS 业务代码，即可从 Provider A 切换到 Provider B
- [ ] **Admin 在设置页切换 Provider/Model 并保存后，下一条 Agent 请求即使用新配置（无需重启服务）**
- [ ] **AE 无法访问 LLM 设置页与相关 API（403）**
- [ ] **前端下拉仅展示白名单内且已配置 Key 的 Provider；响应中不包含任何 API Key**
- [ ] 切换后闭环 A（纪要写回）可完成一次端到端演示
- [ ] 切换后闭环 C（Copilot 查询 + 邮件草稿）可完成一次端到端演示
- [ ] 日志与审计中可见 `provider`、`model`、`agent_name`、耗时；**Admin 改配置有独立审计记录**
- [ ] 文档提供至少 **2 套** 开箱配置示例（如 OpenAI + DeepSeek，或 DeepSeek + 通义）
- [ ] §10.5.5 检索与安全模型验收项全部通过

#### 10.5.8 分期扩展

| 能力 | 阶段 |
|---|---|
| 环境变量 / YAML 默认值与白名单 | MVP |
| **Admin 前端选择 Provider/Model（热生效）** | **MVP** |
| Mock Provider（CI 与本地无 Key） | MVP |
| 跨 Provider Fallback | MVP 建议 / P4 必验 |
| Langfuse 记录 model/provider/cost | 二期 |
| **AE 个人偏好模型（可选，Admin 开关）** | 二期 |
| **在线新增 Provider（仍不写 Key 到前端，仅增模型映射）** | 二期 |
| 按租户/用户不同模型 | 二期 |
| Embedding / Rerank Admin 可配 + re-index | **MVP**（§10.5.5） |
| Guard `llm-guard` 模式 + Scanner Admin 编辑 | 二期 |
| Cohere / API Rerank Adapter | MVP 可选 / 二期扩展 |
| GraphRAG | 二期评估 |

---

## 11. 种子数据要求

**目标**：演示时像真实销售团队用了 3–6 个月的 CRM，而非 3 条假数据。

| 实体 | 数量（建议） |
|---|---|
| Account | 12–15 家 |
| Contact | 40–60 人（含完整决策链） |
| Opportunity | 20–25 条（覆盖 6 阶段） |
| Activity | 80–120 条（会议/电话/邮件/笔记） |
| 红灯商机 | ≥ 5 |
| 黄灯商机 | ≥ 8 |
| 赢单/丢单案例 | 各 ≥ 2 |

**命名与内容**：使用虚构但 realistic 的工业软件客户名；纪要含竞对、预算、交付周期、POC 等真实话术。

---

## 12. 成功指标（North Star Metrics）

| 指标 | 定义 | MVP 验证方式 |
|---|---|---|
| 写回采纳率 | AE 确认的抽取字段 / Agent 建议字段 | ≥ 60%（种子数据演示测算） |
| 事务时间节省 | 录入纪要 vs 手工填表耗时对比 | 演示计时 ≥ 50% 节省 |
| 预警有效感 | 主管认为红灯商机「确实有风险」 | 定性访谈 ≥ 80% 认可 |
| 发送零误发 | 未经确认的对外邮件 | = 0 |

---

## 13. 里程碑

### 第一期（MVP）— ✅ 已完成（2026-08-19）

| 阶段 | 交付物 | 预估 |
|---|---|---|
| M0 | PRD 确认 + 数据模型 + Agent 架构文档 | 1 周 |
| M1 | 项目骨架、Docker、认证、核心 CRUD、**Admin LLM 设置 API + 设置页骨架** | 1–2 周 |
| M2 | 种子数据 + 闭环 A（纪要写回） | 2 周 |
| M3 | 闭环 B（健康度）+ 闭环 C（Copilot） | 2 周 |
| M4 | 审计、HITL 完善、**LLM 切换 E2E 验收**、演示脚本、部署文档 | 1 周 |

### 第二期（AI 能力升级 + 企业集成）— 🚧 规划中

| 阶段 | 交付物 | 预估 |
|---|---|---|
| M5 | 真实 LLM Guard 产品化（Prompt Injection + PII 实体识别） | 1 周 |
| M6 | Langfuse SDK 接入 + Ragas 准确率评估 + Grafana 看板 | 1 周 |
| M7 | 混合 RAG（BM25 + Vector）+ BGE Reranker + Query Expansion | 1.5 周 |
| M8 | 钉钉群 Webhook 通知（风险预警 + HITL 审批提醒） | 0.5 周 |
| M9 | CI/CD GitHub Actions + Nginx SSL/Rate-limit + E2E 稳定化 | 1 周 |

---

---

## 14. 第二期需求详述

> 本章为 Phase 2（M5–M9）的产品需求补充，与第一期 §5–§10 并列，不替代。

### 14.1 P5 — 真实 LLM Guard 产品化

#### 背景

第一期 LLM Guard 为规则引擎 MVP（正则匹配注入模式、PII 脱敏），存在以下局限：
- 绕过率高：变体注入（如 Base64 编码、多语言混写）无法检测
- PII 识别依赖正则，漏召回率 >30%（姓名、职位等非结构化 PII 完全缺失）
- 没有可配置的风险阈值，Admin 无法调整灵敏度

#### 需求

| 功能 | 描述 | 优先级 |
|---|---|---|
| **Prompt Injection 分类器** | 调用 AliCloud 内容安全 API 或本地小模型（deberta-v3-base-injection），对 LLM 输入做二分类；置信度 > 0.85 时拦截 | P0 |
| **NER PII 识别** | 使用 `presidio-analyzer`（支持中文扩展）识别姓名/手机/身份证/邮箱；输出层脱敏后返回 | P0 |
| **Admin 阈值配置** | Admin 页面可调整 Guard 各项灵敏度（0–1.0），保存到 `llm_settings` | P1 |
| **Guard 审计** | 每次拦截写入 `audit_log`，Manager 可查询被拦截内容（脱敏后） | P1 |
| **误报率监控** | Prometheus Counter `guard_blocked_total{reason}` + Grafana 面板 | P2 |

#### 验收标准

- Prompt Injection 检出率 ≥ 90%（基于 10 条 golden 攻击样本）
- PII 召回率 ≥ 85%（基于 10 条含 PII 的种子纪要）
- 正常业务文本误判率 ≤ 5%

---

### 14.2 P6 — Langfuse SDK + Ragas 准确率评估

#### 背景

第一期 Langfuse 为 stub（`trace_agent_run` 空函数），没有真实 trace 数据；Ragas 评估完全缺失，无法量化 Copilot 回答质量。

#### 需求

**Langfuse 接入**

| 功能 | 描述 |
|---|---|
| LLM 调用 trace | 每次 `call_llm` 写 Langfuse span（model、latency、token_usage、input/output hash） |
| Agent 图 trace | 每次 Orchestrator 运行写一条 Langfuse trace，子 Agent 各占一个 span |
| 用户会话关联 | trace 携带 `user_id`、`opportunity_id`、`session_id` |
| Langfuse Dashboard | 直接使用 Langfuse 自带 UI，不自建 |

**Ragas 评估 Pipeline**

| 功能 | 描述 |
|---|---|
| Golden Dataset | 10 条种子纪要 × 标准答案（由助手生成草稿，业务确认），存放于 `tests/golden/` |
| 评估指标 | Faithfulness、Answer Relevancy、Context Recall（Ragas 默认套件） |
| CI 集成 | `make eval` 触发评估，结果写入 `tests/ragas_report.json`；Faithfulness < 0.75 时 CI 警告（不阻断） |
| 定期评估 | Celery Beat 每周一 00:00 跑一次全量评估，结果推送钉钉群 |

#### 验收标准

- Langfuse UI 可看到完整的 Agent trace（Planner → 4 子 Agent → Synth 各 span）
- Ragas Faithfulness ≥ 0.75，Answer Relevancy ≥ 0.70
- `make eval` 在 CI 中可复现运行

---

### 14.3 P7 — 混合 RAG + BGE Reranker

#### 背景

第一期 RAG 仅有 pgvector 向量检索，存在以下问题：
- 关键词精确匹配（如客户名、产品型号）召回率差
- 没有 Rerank，top-K 结果与 query 相关性未经二次排序
- Query Rewriting 为 placeholder，未实际调用 LLM

#### 需求

| 功能 | 描述 | 优先级 |
|---|---|---|
| **BM25 关键词检索** | 使用 `pg_trgm` 扩展做全文检索，与向量检索结果 RRF 融合 | P0 |
| **BGE Reranker** | 接入 `BAAI/bge-reranker-v2-m3`（Dashscope API 或本地推理）；对 top-20 结果重排，取 top-5 | P0 |
| **Query Rewriting** | 真实调用 LLM（轻量模型）改写用户 query 为更适合检索的形式，替换 placeholder | P0 |
| **Query Expansion** | 同义词扩展（可选）：从 query 生成 2–3 个变体并行检索，融合去重 | P1 |
| **Chunk 策略优化** | 会议纪要按段落 + 时间戳切分（P1 为 auto 策略），保留元数据（日期、参与人） | P1 |
| **Embedding 重建** | 提供 `scripts/reindex.py` 脚本，Embedding 模型变更时可重建全量 memory_chunks | P1 |

#### 验收标准

- Copilot query 检索命中率（MRR@5）相较 P4 随机向量基线提升 ≥ 20%（golden；`make eval` → `retrieval`）
- 无远程模型时 P95 混合检索（含 lexical Rerank）≤ 500ms；含 Dashscope 改写/Rerank 以网络为准
- `scripts/reindex.py --full`：local/hash 路径 1000 chunks 可在 5 分钟内完成

---

### 14.4 P8 — 钉钉群 Webhook 通知

#### 背景

销售主管和 AE 不会持续盯着 CRM 页面，需要关键事件主动推送到沟通工具。

#### 需求

**通知触发场景**

| 事件 | 接收人 | 消息类型 |
|---|---|---|
| 商机变红灯 | 负责 AE + 主管群 | Markdown 卡片（商机名、触发规则、建议行动） |
| PendingAction L2 待审批（金额变更） | 主管群 | 操作提醒卡片（金额变化幅度、商机名、审批链接） |
| Copilot 邮件草稿待确认 | 负责 AE | 简单文字提醒 |
| Ragas 周报评估完成 | 主管群 | 评分摘要（Faithfulness / Relevancy） |

**技术设计**

| 功能 | 描述 |
|---|---|
| Webhook 配置 | Admin 页面配置 Webhook URL + 加签 Secret，存入 `llm_settings`（扩展字段） |
| 加签安全 | timestamp + HMAC-SHA256，符合钉钉官方规范 |
| 消息模板 | Jinja2 模板，Admin 可自定义（P2 阶段提供 4 个默认模板） |
| 失败重试 | Celery task 重试 3 次（指数退避），失败写 audit_log |
| 静默时段 | Admin 可配置免打扰时间（如 22:00–08:00），静默期消息延迟到次日推送 |

#### 验收标准

- 商机变红灯后 30s 内钉钉群收到通知
- Webhook 加签验证正确（伪造请求被拒）
- 静默时段消息不丢失、次日正常推送

---

### 14.5 P9 — CI/CD + Nginx SSL + E2E 稳定化

#### 背景

第一期无 CI/CD，E2E 测试存在 asyncio fixture 冲突，Nginx 无 SSL，生产就绪度不足。

#### 需求

**GitHub Actions CI**

| 步骤 | 触发条件 |
|---|---|
| `apps/api` 单元测试（pytest -x）| push / PR |
| `docker compose build` smoke | push / PR |
| `make eval` Ragas 评估 | 每周一定时 |
| docker image push 到 GHCR | tag `v*` |

**Nginx 生产加固**

| 功能 | 描述 |
|---|---|
| SSL 终止 | Let's Encrypt（公网）或自签（内网），HTTP → HTTPS 301 |
| Rate Limiting | `/auth/token` 限 5 req/min/IP；`/activities/extract` 限 10 req/min/user |
| CORS 收紧 | 仅允许 `ALLOWED_ORIGINS` 白名单域名 |
| 安全响应头 | `X-Frame-Options: DENY`、`X-Content-Type-Options: nosniff`、`Strict-Transport-Security` |

**E2E 测试稳定化**

- 修复 `pytest-asyncio` session-scoped fixture 冲突（`test_crud_smoke.py`、`test_auth_rbac.py`）
- 补充 `test_writeback_e2e.py`（Mock LLM，3 条 golden 纪要 parametrize）
- 补充 `test_guard_e2e.py`（10 条注入样本 + 10 条 PII 样本）
- 补充 `test_dingtalk_notify.py`（Mock Webhook，验证加签逻辑）

#### 验收标准

- PR CI 全绿（pytest + build smoke）
- HTTPS 访问正常，HTTP 自动跳转
- `/auth/token` 超频返回 429
- E2E 测试套件在 CI 中稳定通过（无 flaky）

---

## 15. 默认假设与待确认项

### 15.1 默认假设（已按此编写）

- 单租户部署；一个销售团队 5–20 人。
- 中文界面；工业软件 / 智能制造 ToB 行业。
- LLM：`.env` 注册 Provider 白名单与 Key；**Admin 在前端设置页选择**生效模型（见 §10.5.4）；默认至少 2 套 Provider 示例配置。
- 邮件 MVP 为 Mock 或 MailHog，不对真实客户发信。
- 第二期 IM：**钉钉群自定义机器人**（Webhook + 加签），非企业应用。
- 金额默认 CNY「万元」展示。

### 15.2 待业务确认（不阻塞开发）

**第一期遗留（多数已决策）**

- [x] MVP 默认主 Provider：阿里云千问；备用 DeepSeek-V4-Flash
- [x] 任务队列：Celery + Redis
- [x] Embedding：BGE-M3（1024 维；API 默认同维 hash，真模型走 sidecar）
- [x] 钉钉通知：Phase 2 接群自定义机器人 Webhook（有测试群）
- [x] 多租户：推迟到第三期
- [ ] 阶段停留阈值：14/30 天是否合适？
- [ ] 金额审批线：50 万是否需要调整？
- [ ] 各 Agent 是否接受「Planner/汇总 用大模型、风险预警 用小模型」的默认成本策略？

**第二期待确认**

- [ ] Guard 后端：AliCloud 内容安全 API vs 开源 `llm-guard` vs 本地 classifier（默认优先开源库 + 规则兜底）
- [ ] Langfuse：自托管 Docker 还是 Langfuse Cloud
- [ ] Rerank：Dashscope Rerank API vs 本地 `bge-reranker-v2-m3`
- [x] 钉钉 Webhook URL / 加签 Secret（`.env` 或 Admin `notify_config`；GET 只回 masked URL，Secret 不回显）
- [ ] golden dataset 草稿确认（助手生成，业务过一遍）

---

## 16. 附录

### 16.1 术语表

| 术语 | 说明 |
|---|---|
| HITL | Human-in-the-Loop，人工介入 |
| MEDDIC | Metrics, Economic buyer, Decision criteria, Decision process, Identify pain, Champion |
| WritebackProposal | Agent 生成的待确认写回建议包 |
| PendingAction | 待人工确认/审批的动作 |
| Memory Chunk | 用于 RAG 的语义分块 |
| llm_settings | Admin 保存的 Chat + Embedding + Rerank + Guard 运行配置（不含 API Key） |
| LLM 白名单 | `LLM_AVAILABLE_PROVIDERS`；Chat Provider 可选列表 |
| Embedding / Rerank | RAG 专用模型，与 Chat 独立配置（§10.5.5） |
| re-index | Embedding 模型变更后重建 memory_chunks 向量 |
| Golden Dataset | 种子纪要 + 参考答案，用于 Ragas 评估 |
| RRF | Reciprocal Rank Fusion，混合检索结果融合 |
| 钉钉群机器人 | 自定义 Webhook + 加签，仅推送、不做审批回调 |

### 16.2 与前期产品思想对照

| 思想 | PRD 落点 |
|---|---|
| Agent 是一等公民 | §9 Orchestrator；并行专责 + 汇总 |
| 写入即理解 | §8.1 闭环 A；§6.7 Memory |
| 意图驱动 | §8.3 Copilot + page context |
| 方法论内置 | §7 业务规则；§8.2 健康度 |
| HITL | §7.3 分级；§8.1/8.3 确认流 |
| 可测量进化 | §10.3 可观测性分期 |
| 企业级可落地 | §3 权限；§10 安全；§11 种子数据 |
| LLM 可切换、不绑厂商 | §10.5；§5.1 MVP 清单；§10.5.4 Admin 前端 |
| Embedding / Rerank / Guard 独立配置 | §10.5.5；rag-pipeline；guardrails-hitl |

### 16.3 文档清单

| 文档 | 路径 | 状态 |
|---|---|---|
| 产品需求文档 PRD | [PRD.md](PRD.md) | ✅ v0.7 |
| 技术架构 | [architecture/tech-architecture.md](architecture/tech-architecture.md) | ✅ v0.2 |
| Agent 架构 | [architecture/agent-architecture.md](architecture/agent-architecture.md) | ✅ v0.3 |
| 业务流程 | [architecture/business-flow.md](architecture/business-flow.md) | ✅ v0.2 |
| 数据模型与 ER 图 | [architecture/data-model.md](architecture/data-model.md) | ✅ v0.2 |
| RAG 管道设计 | [architecture/rag-pipeline.md](architecture/rag-pipeline.md) | ✅ v0.4（P7 混合检索实装） |
| 代码结构对照 | [architecture/code-map.md](architecture/code-map.md) | ✅ v0.2 |
| API 契约 OpenAPI | [api/openapi.yaml](api/openapi.yaml) | ✅ v2.0.0 |
| 部署与运维 | [deployment/docker-compose.md](deployment/docker-compose.md) | ✅ P9 TLS/限流 |
| 安全与 HITL | [security/guardrails-hitl.md](security/guardrails-hitl.md) | ✅ P0（P5 升级 Guard） |
| 阶段核查 P0–P4 | [phases/](phases/) | ✅ 第一期已验证 |
| 阶段核查 P5–P9 | [phases/](phases/) | ✅ 第二期完成 |
| 演示脚本 | [deployment/demo-script.md](deployment/demo-script.md) | ✅ P4 |

### 16.4 第三期（预告，不在本期范围）

- 多租户（`tenant_id` + Postgres RLS，或 schema-per-tenant）
- 企业微信/钉钉企业应用（CorpID + 审批回调，HITL 可在 IM 内确认）
- 真实 SMTP 对外发信（替换 MailHog）
- 语音/视频转写进 Activity
- 移动端

---

*文档结束 — v0.7 Draft*
