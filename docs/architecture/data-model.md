# 数据模型设计

| 属性 | 内容 |
|---|---|
| 版本 | v0.2 |
| 关联 | [PRD §6](../PRD.md) |

---

## 1. ER 图（核心实体）

```mermaid
erDiagram
    USER ||--o{ OPPORTUNITY : owns
    USER ||--o{ ACTIVITY : creates
    USER ||--o{ AUDIT_LOG : performs

    ACCOUNT ||--o{ CONTACT : has
    ACCOUNT ||--o{ OPPORTUNITY : has
    ACCOUNT ||--o{ ACTIVITY : has
    ACCOUNT ||--o{ MEMORY_CHUNK : has

    OPPORTUNITY ||--o{ ACTIVITY : has
    OPPORTUNITY ||--o{ MEMORY_CHUNK : has
    OPPORTUNITY ||--o{ PENDING_ACTION : has

    ACTIVITY ||--o{ MEMORY_CHUNK : generates

    USER {
        uuid id PK
        string email
        string name
        enum role
        datetime created_at
    }

    ACCOUNT {
        uuid id PK
        string name
        enum industry
        enum size
        string region
        text description
    }

    CONTACT {
        uuid id PK
        uuid account_id FK
        string name
        string title
        string email
        string phone
        enum role_in_deal
        enum influence_level
        datetime last_contacted_at
        text notes
    }

    OPPORTUNITY {
        uuid id PK
        uuid account_id FK
        uuid owner_id FK
        string name
        decimal amount
        enum stage
        date expected_close_date
        string competitor
        jsonb pain_points
        enum budget_status
        int health_score
        enum health_status
        datetime last_activity_at
    }

    ACTIVITY {
        uuid id PK
        uuid account_id FK
        uuid opportunity_id FK
        enum type
        string subject
        text content
        jsonb structured_summary
        uuid created_by FK
        datetime occurred_at
    }

    MEMORY_CHUNK {
        uuid id PK
        uuid account_id FK
        uuid opportunity_id FK
        enum source_type
        uuid source_id
        text chunk_text
        vector embedding
        enum chunk_strategy
        enum source_format
        string parent_heading
        jsonb metadata
        tsvector fts
    }

    PENDING_ACTION {
        uuid id PK
        enum type
        enum hitl_level
        jsonb payload
        enum status
        uuid created_by FK
        uuid confirmed_by FK
        datetime expires_at
    }

    LLM_SETTINGS {
        uuid id PK
        string default_provider
        string default_model
        jsonb agent_overrides
        string embedding_provider
        string embedding_model
        int embedding_dimension
        bool rerank_enabled
        string rerank_provider
        string rerank_model
        int rerank_top_k
        int rerank_return_n
        bool guard_enabled
        string guard_mode
        jsonb guard_config
        string fallback_provider
        string fallback_model
        uuid updated_by FK
        datetime updated_at
    }

    AUDIT_LOG {
        uuid id PK
        uuid user_id FK
        string action
        string resource_type
        uuid resource_id
        jsonb diff
        datetime created_at
    }
```

---

## 2. 枚举定义

### 2.1 opportunity.stage

`qualified` | `discovery` | `proposal` | `negotiation` | `closed_won` | `closed_lost`

### 2.2 contact.role_in_deal

`economic_buyer` | `technical_buyer` | `user_buyer` | `coach` | `influencer` | `unknown`

### 2.3 opportunity.health_status

`green` | `yellow` | `red`

### 2.4 activity.type

`meeting` | `call` | `email` | `note` | `agent_action`

### 2.5 pending_action.status

`pending` | `confirmed` | `rejected` | `expired`

---

## 3. Memory 与业务表关系

```mermaid
flowchart LR
    ACT[Activity 确认写回] --> CHUNK[Chunk 分割]
    CHUNK --> EMB[Embedding]
    EMB --> MC[(memory_chunks)]
    MC --> VEC[pgvector 索引]
    MC --> FTS[tsvector 全文索引]

    QUERY[Copilot 查询] --> HY[混合检索]
    HY --> VEC
    HY --> FTS
    HY --> RR[Rerank]
    RR --> CTX[Context]
```

**原则**：

- 结构化字段写回 `opportunities` / `contacts`
- 原始与摘要进 `activities.structured_summary`
- 可检索文本进 `memory_chunks`
- 禁止只更新 Memory 不更新业务表

---

## 4. LangGraph Checkpoint 表（概要）

| 表 | 用途 |
|---|---|
| `checkpoints` | LangGraph 官方 PostgresSaver 表 |
| `checkpoint_writes` | 写入记录 |

与 `thread_id` 关联，支持 HITL interrupt/resume。

---

## 5. 索引策略（MVP）

| 表 | 索引 |
|---|---|
| opportunities | `(owner_id, stage)`, `(health_status, amount DESC)` |
| activities | `(account_id, occurred_at DESC)`, `(opportunity_id)` |
| memory_chunks | `ivfflat (embedding vector_cosine_ops)`, `GIN (fts)` |
| pending_actions | `(status, created_by)`, `(expires_at)` |

---

## 6. 种子数据规格

见 [PRD §11](../PRD.md)。种子脚本路径（P2）：`scripts/seed/`.

---

## 7. 迁移策略

- Alembic 管理所有 DDL
- pgvector extension 在首次 migration 启用
- 变更 embedding 维度需 re-index 脚本

---

## 8. 数据隔离

| 级别 | MVP |
|---|---|
| 租户 | 单租户 |
| 用户 | AE 仅看本人 owner 商机；Manager 看团队；Admin 全部 |
| Agent | 工具层强制 RBAC filter |
