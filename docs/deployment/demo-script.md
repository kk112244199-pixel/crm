# MontoCRM MVP 演示脚本

> 目标：15 分钟内走通三条闭环，适合向客户/评审演示。
> 前提：`docker compose up -d` 已运行，所有服务 healthy。

---

## 准备工作（2 min）

```bash
# 确认服务状态
docker compose ps

# 快速健康检查
curl http://localhost:8000/health
# → {"status":"ok","app":"MontoCRM","version":"1.0.0"}

# 获取 AE Token（后续所有请求都用这个）
TOKEN=$(curl -s -X POST http://localhost:8000/auth/token \
  -d "username=ae@montocrm.local&password=AE@123!" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "Token: ${TOKEN:0:20}..."
```

---

## 闭环 A — 会议纪要智能写回（5 min）

> 演示场景：AE 开完客户会议，粘贴纪要，AI 自动提取联系人/商机字段/风险/任务，AE 逐项确认写回。

### Step 1：查看种子商机列表

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/opportunities \
  | python3 -m json.tool | head -60
```

取第一个 `id` 存为变量：

```bash
OPP_ID="<复制上面的 id>"
```

### Step 2：触发 AI 分析（Orchestrator）

```bash
curl -s -X POST http://localhost:8000/activities/extract \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "opportunity_id": "'"$OPP_ID"'",
    "canonical_text": "【会议纪要】2026-08-19 与亿联智造\n王总确认 MES 采购预算 380 万，Q3 决策。竞对：用友 U9 已做演示。\n技术负责人张工支持我方方案。下一步：李明 8月25日前发 POC 方案。"
  }' | python3 -m json.tool
```

**期望结果：**
- `agents_activated`：含 `opportunity_judge`、`risk_sentinel`、`action_planner`
- `proposal.opportunity_updates.competitor`：`"用友 U9"`
- `proposal.tasks[0].title`：`"发送 POC 方案"`
- `proposal.risk_flags`：含 H003（竞对进入）

取 `pending_action_id`：

```bash
PENDING_ID="<复制上面的 pending_action_id>"
```

### Step 3：AE 确认写回（HITL）

```bash
curl -s -X POST "http://localhost:8000/pending-actions/$PENDING_ID/confirm" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"items": []}' | python3 -m json.tool
```

**期望结果：** `"status": "approved"`

### Step 4：验证商机字段已更新

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/opportunities/$OPP_ID" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('competitor:', d.get('competitor'), '| pain_points:', d.get('pain_points')[:30] if d.get('pain_points') else None)"
```

---

## 闭环 B — 健康度看板（3 min）

> 演示场景：Manager 查看团队风险看板，找到红灯商机，钻取扣分原因。

### Step 1：Manager Token

```bash
MGR_TOKEN=$(curl -s -X POST http://localhost:8000/auth/token \
  -d "username=manager@montocrm.local&password=Manager@123!" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

### Step 2：风险看板

```bash
curl -s -H "Authorization: Bearer $MGR_TOKEN" \
  http://localhost:8000/dashboard/risk-board \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'RED={len(d[\"red\"])}  YELLOW={len(d[\"yellow\"])}  GREEN={len(d[\"green\"])}  TOTAL={d[\"total\"]}')
for r in d['red'][:3]:
    print(f'  ⚠ {r[\"opportunity_name\"]} ({r[\"account_name\"]}) score={r[\"health_score\"]} rules={r[\"top_rules\"]}')
"
```

### Step 3：商机健康度明细（实时重算）

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/opportunities/$OPP_ID/health?recalc=true" \
  | python3 -m json.tool
```

**期望结果：** 含 `score`、`status`（GREEN/YELLOW/RED）、`rules` 扣分明细。

---

## 闭环 C — Copilot 问答 + 邮件（5 min）

> 演示场景：AE 在商机页面侧边栏问 Copilot，再让 AI 起草跟进邮件。

### Step 1：RAG 问答

```bash
curl -s -X POST http://localhost:8000/copilot/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "这个客户的预算情况和主要顾虑是什么？",
    "opportunity_id": "'"$OPP_ID"'"
  }' | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('Answer:', d['answer'][:200])
print('Citations:', len(d.get('citations', [])))
print('Chunks retrieved:', d['retrieved_chunks'])
"
```

### Step 2：起草跟进邮件

```bash
curl -s -X POST http://localhost:8000/copilot/draft \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "opportunity_id": "'"$OPP_ID"'",
    "instruction": "写一封跟进邮件，确认 POC 方案发送时间，顺带消除对方对 SAP 接口改造成本的顾虑",
    "recipient_name": "王总",
    "recipient_title": "VP 工程"
  }' | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('Subject:', d['subject'])
print()
print(d['body'][:400])
print()
print('CTA:', d['cta'])
print('Pending ID:', d['pending_action_id'])
"
```

### Step 3：发送前审核（HITL L2）

```bash
DRAFT_ID="<复制上面的 pending_action_id>"

# 确认发送（MailHog MVP）
curl -s -X POST "http://localhost:8000/copilot/draft/$DRAFT_ID/send" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"to_email": "wang.vp@yilian.com"}'
```

---

## 验收 Checklist

| 验收项 | 期望结果 | 状态 |
|---|---|---|
| Extract → Proposal 字段非空 | `competitor`、`tasks`、`risk_flags` 均有内容 | ☐ |
| HITL confirm → 商机写入 | `opp.competitor` 更新 | ☐ |
| Confirm 后 RAG ingest | memory_chunks 有新记录 | ☐ |
| 健康度看板 RED ≥1 | `risk_board.red` 非空 | ☐ |
| Copilot 回答带 citation | `citations` 长度 ≥0 | ☐ |
| 邮件草稿 → L2 PendingAction | `status=pending` | ☐ |
| AE 无法访问 /admin/llm | HTTP 403 | ☐ |
| /metrics 可访问 | Prometheus 格式文本 | ☐ |

---

## 常见问题

**LLM 调用失败（API Key 未填）**
```bash
# 临时切换 mock provider
docker compose exec api bash -c "
  sed -i 's/LLM_DEFAULT_PROVIDER=.*/LLM_DEFAULT_PROVIDER=mock/' .env
"
docker compose restart api
```

**重置种子数据**
```bash
docker compose exec api python seed_users.py
docker compose exec api python seed_crm_data.py
```

**查看结构化日志**
```bash
docker compose logs api --tail=50 | python3 -m json.tool 2>/dev/null | head -100
```
