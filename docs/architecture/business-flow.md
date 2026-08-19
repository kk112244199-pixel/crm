# 业务流程设计

| 属性 | 内容 |
|---|---|
| 版本 | v0.2 |
| 关联 | [PRD §8](../PRD.md) |

---

## 1. 业务域总览

```mermaid
flowchart TB
    subgraph Marketing["营销（二期）"]
        LEAD[线索]
    end

    subgraph Sales["销售 MVP"]
        ACC[Account 客户]
        CON[Contact 联系人]
        OPP[Opportunity 商机]
        ACT[Activity 活动]
    end

    subgraph Service["服务（二期）"]
        TKT[工单]
    end

    LEAD -.-> OPP
    ACC --> CON
    ACC --> OPP
    OPP --> ACT
    ACC --> ACT
```

MVP 聚焦 **Sales** 域三条闭环。

---

## 2. 角色协作流程

```mermaid
sequenceDiagram
    participant AE as 一线销售
    participant SYS as MontoCRM
    participant AGT as Agent
    participant MGR as 销售主管

    AE->>SYS: 录入会议纪要
    SYS->>AGT: Orchestrator（Planner → A∥B∥C∥D → 汇总）
    AGT-->>AE: 写回建议（HITL L1）
    AE->>SYS: 确认写回
    SYS->>AGT: 索引记忆 + 重算健康度

    MGR->>SYS: 打开团队风险看板
    SYS-->>MGR: 红灯商机 + 扣分原因

    AE->>SYS: Copilot「客户最担心什么？」
    SYS->>AGT: Orchestrator（copilot_query）
    AGT-->>AE: 带引用的回答

    AE->>SYS: 「写跟进邮件」
    SYS->>AGT: Orchestrator（copilot_draft）
    AGT-->>AE: 草稿 + PendingAction L2
    AE->>SYS: 确认发送
```

---

## 3. 闭环 A — 会议纪要 → 智能写回（Orchestrator）

<a id="闭环-a"></a>

```mermaid
flowchart TB
    A1[AE 粘贴/上传纪要] --> A2[预处理 canonical_text]
    A2 --> PL[Planner]
    PL --> PA[客户洞察]
    PL --> PB[商机研判]
    PL --> PC[风险预警]
    PL --> PD[行动规划]
    PA --> SYN[汇总 Agent]
    PB --> SYN
    PC --> SYN
    PD --> SYN
    SYN --> A6[AE Diff 确认 HITL L1]
    A6 -->|确认| A7[写库 + RAG + Health]
    A6 -->|拒绝| A8[仅保存原始 Activity]
```

**业务价值**：录入负担 → 说话即录入；Multi-Agent 并行分析 → 汇总写回。

**验收**：见 [P2-checklist](../phases/P2-checklist.md)。

---

## 4. 闭环 B — 商机健康度与风险预警

<a id="闭环-b"></a>

**两类触发**：① Activity 写回后立即触发单条重算；② Cron 每日凌晨 2 点全量批算（默认，可 Admin 配置间隔）。

```mermaid
flowchart TD
    B1[Cron 每日 02:00 / Activity 写回后] --> B2[加载商机+联系人+活动]
    B2 --> B3[规则引擎 H001-H008 扣分]
    B3 --> B4[计算 score + green/yellow/red]
    B4 --> B5[风险预警（risk_sentinel）+ 规则引擎 风险说明]
    B5 --> B6[更新 Opportunity 展示]

    B6 --> B7{用户角色?}
    B7 -->|AE| B8[商机列表看灯号+原因]
    B7 -->|Manager| B9[团队风险看板 Top 红灯]
```

**业务规则示例**：

| 规则 | 业务含义 |
|---|---|
| H001/H002 | 单子卡住太久 |
| H003 | 大单缺经济买家 |
| H005 | 有竞对但没应对 |
| H007 | 过了预计成交日还没结 |

**验收**：见 [P3-checklist](../phases/P3-checklist.md)。

---

## 5. 闭环 C — Copilot 查询 + 邮件 + 审批

<a id="闭环-c"></a>

### 5.1 查询分支（Orchestrator）

```mermaid
flowchart TB
    C1[AE Copilot + page context] --> PL[Planner]
    PL --> PA[客户洞察]
    PL --> PB[商机研判]
    PL --> PC[风险预警]
    PA --> SYN[汇总 Agent + citations]
    PB --> SYN
    PC --> SYN
    SYN --> C5[返回答案]
```

简单问句时 Planner **降级为单路**（仍经 Planner，非 API 硬编码）。

### 5.2 邮件分支（Orchestrator）

```mermaid
flowchart TB
    D1[AE: 写跟进邮件] --> PL[Planner<br/>scene=copilot_draft]
    PL --> PA[客户洞察]
    PL --> PB[商机研判]
    PL --> PD[行动规划]
    PA --> SYN[汇总 Agent 生成邮件]
    PB --> SYN
    PD --> SYN
    SYN --> D3[Guard 输出扫描]
    D3 --> D4[PendingAction L2]
    D4 --> D5[AE 编辑草稿]
    D5 --> D6{确认发送?}
    D6 -->|是| D7[Email Adapter 发送]
    D6 -->|否| D8[取消/保存草稿]
    D7 --> D9[Activity + Audit]
```

**业务价值**：Agent 协作 + HITL；零误发邮件。

---

## 6. Admin LLM 配置流程

```mermaid
flowchart LR
    ADM[Admin 登录] --> PAGE[设置 → LLM 配置]
    PAGE --> OPT[GET /llm/options<br/>白名单内 Provider]
    OPT --> SEL[选择 Provider/Model<br/>按 Agent 配置]
    SEL --> TEST[测试连接]
    TEST --> SAVE[PUT /admin/llm/settings]
    SAVE --> AUDIT[审计日志]
    SAVE --> HOT[下一条 Agent 请求热生效]
```

---

## 7. 商机阶段推进流程（业务规则节点）

```mermaid
stateDiagram-v2
    [*] --> qualified: 确认真实机会
    qualified --> discovery: ≥1 次有效沟通
    discovery --> proposal: 有对接人 + pain_points
    proposal --> negotiation: 有 technical/user buyer
    negotiation --> closed_won: 合同确认 + amount
    negotiation --> closed_lost: 明确失败

    note right of discovery: Agent 仅建议推进\n销售确认 + 必填校验
    note right of negotiation: 需 economic_buyer\n或 budget ≥ estimated
```

---

## 8. 二期场景清单（PRD §5.2）

| 场景 | 说明 |
|---|---|
| 会前简报 | 拜访前自动汇总客户背景 |
| 线索分配 | SDR → AE 评分与路由 |
| 赢单复盘 | 沉淀打法到 Memory/规则 |
| 客成流失预警 | 健康分 + 续费时机 |
| 团队 Pipeline 看板 | 金额分布、阶段漏斗 |

---

## 9. 与 API 契约的对应

| 流程 | 主要 API |
|---|---|
| 闭环 A | `POST /activities/extract`, `POST /writeback/{id}/confirm` |
| 闭环 B | `GET /opportunities?health_status=`, `GET /manager/risk-board` |
| 闭环 C | `POST /copilot/query`, `POST /copilot/draft`, `POST /pending-actions/{id}/confirm` |
| LLM 配置 | `GET/PUT /admin/llm/settings` |

详见 [openapi.yaml](../api/openapi.yaml)。
