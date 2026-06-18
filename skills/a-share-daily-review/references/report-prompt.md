# 每日复盘 LLM Sections Prompt

本 prompt 用于把 `review-context.json` 转换为可校验的每日复盘 sections JSON。只能使用 context 中的事实，不要读取或推断其他文件。

## 输入

你会收到一个 `review-context.json`，其顶层字段包括：

- `trade_date`
- `data_status`
- `data_sources_used`
- `blocked_sections`
- `market_breadth`
- `limit_pool`
- `lhb`
- `market_summary`
- `board_snapshot`
- `issues`
- `allowed_sections`
- `forbidden_claims`
- `facts`

## 输出格式

只输出 JSON，不要包 Markdown，不要加解释文字。

```json
{
  "schema_version": "daily_review_sections.v1",
  "headline": "",
  "summary": [],
  "market_breadth_review": "",
  "sentiment_and_events_review": "",
  "board_and_structure_review": "",
  "risk_observations": [],
  "follow_up_questions": [],
  "data_boundary_note": "",
  "not_investment_advice_note": ""
}
```

## 写作规则

- 使用中文。
- 保持研究复盘口吻，不输出交易动作。
- `summary` 写 2-4 条，先说数据状态和证据边界，再说可观察事实。
- `market_breadth_review` 只能基于 `market_breadth`。
- `sentiment_and_events_review` 只能基于 `limit_pool`、`lhb` 和 `market_summary` 中可用的部分。
- `board_and_structure_review` 只能基于 `board_snapshot`。如果 `board_snapshot` 在 `blocked_sections` 中，只能说明板块数据受限，不能写板块主线、领涨板块或结构确认。
- `risk_observations` 必须包含数据缺口、`partial` 限制或单日快照限制。
- `follow_up_questions` 只能是研究问题或后续验证问题，不能是交易指令。
- `data_boundary_note` 必须说明只引用 `review-context.json`，缺失或 blocked 维度不补推断。
- `not_investment_advice_note` 必须说明不构成投资建议。

## 禁止输出

不要输出以下内容或同义表达：

- 建议买入
- 建议卖出
- 买入建议
- 卖出建议
- 仓位建议
- 目标价
- 止盈
- 止损
- 加仓
- 减仓
- 明日必涨
- 确定性主线
- 强烈看多
- 强烈看空

## 状态规则

- `data_status=passed`：可以写完整研究复盘，但仍只限单日快照。
- `data_status=partial`：必须写成数据受限观察，不能说“完整复盘”。
- `data_status=failed` 或 `missing`：只输出阻断原因、修复建议和数据诊断，不输出市场判断。

## Blocked Section 规则

如果某个 section 在 `blocked_sections` 中：

- 不要对该 section 做正向结论。
- 不要用其他字段补推断。
- 只能写“该维度数据受限/缺失/不可用，因此不能生成对应观察”。
