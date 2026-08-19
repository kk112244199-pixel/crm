# Golden dataset（P6）

`extract_writeback.json` v0.2：10 条种子纪要 + 参考答案。

- `canonical_text` 与 P2 `seed_crm_data.py` 的 `GOLDEN_MINUTES` 对齐，不重写场景。
- **事实字段**可为空；MEDDIC 角色必须有 `evidence` + `confidence`。
- `champion` / `economic_buyer` 仅在有行为或预算拍板证据时填写，否则 `null`。
- 相对日期以 **meeting_date** 为锚点（不要用评测当天）。
- `status: frozen` — 业务已确认，作为 RAG / Agent 评测冻结集。
- 评估：`make eval`。
