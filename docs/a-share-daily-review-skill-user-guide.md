# A 股每日复盘研究 Skill 用户提示词说明

本文档面向使用者，说明如何让 agent 调用 `a-share-daily-review` skill，基于本仓库已经采集的每日 A 股数据生成 HTML report 或直接返回研究建议。当前流程是：Python 生成 evidence packet，LLM 以“策略分析师写给普通投资者”的角色生成 sections JSON，Python/Pydantic 校验后渲染 HTML，并在同目录生成技术参考 Markdown。

## 这个 agent 能做什么

当用户提出每日复盘、盘后观察、数据诊断或 HTML report 请求时，agent 应调用 `a-share-daily-review` skill。Skill 的能力边界如下：

- 读取每日采集 artifacts，包括 `interface-status.json`、`daily-data-summary.md`、Parquet 标准化表和 `market.duckdb`。
- 生成 `reports/daily-reviews/YYYY-MM-DD/review-context.json`，作为 LLM 唯一事实输入。
- 判断数据状态是 `passed`、`partial`、`skipped`、`failed` 还是 `missing`。
- 让 LLM 只基于 `review-context.json` 生成 `llm-review-sections.json`。
- 使用 Python/Pydantic 校验 LLM 输出和业务边界。
- 在校验通过后生成本地 HTML report 和技术参考 Markdown，并返回两个路径。
- 在用户要求“直接给建议”时，返回研究建议、风险观察和待验证问题。
- 在数据缺失、接口失败或主表不可用时阻断市场结论，提示如何刷新或排查。

这个 agent 不能做：

- 不能给买入、卖出、持有、加仓、减仓建议。
- 不能给仓位、目标价、止损止盈或实盘执行时点。
- 不能把单日快照说成历史趋势、确定主线或预测结果。
- 不能让 LLM 引用 `review-context.json` 之外的事实。
- 不能在没有用户要求刷新时自动调用每日更新。

## 用户需要提供什么

最少只需要说明想要“HTML report”还是“直接建议”。更稳定的提示词建议包含：

- `trade_date`：要分析的交易日，例如 `2026-06-18`。
- `refresh_mode`：是否先刷新数据。默认只用已有数据。
- `output_format`：`html`、`inline` 或 `context`。
- `focus`：关注市场宽度、情绪、龙虎榜、板块、风险或数据质量。
- `external_background`：可选。`$daily-financial-briefing` 输出整理后的 `external_background.v1` 或 `external_background_fusion.v1` JSON 路径。

如果用户不提供日期，agent 默认读取最近一次 daily run。若找不到 daily run，agent 应提示使用公开 CLI：

```text
python -m a_share_info_hub daily-update --trade-date <YYYY-MM-DD>
```

## 标准 HTML report 场景

### 生成最近一次复盘 HTML

```text
调用 a-share-daily-review，读取最近一次 daily run，生成 HTML 复盘报告。
要求：先生成 review-context.json；LLM 只能基于这个 context 写 sections JSON；最后通过 Python 校验并生成 HTML。HTML 按策略分析师写给普通投资者的方式表达，技术状态写入同目录 Markdown，不要在正文裸露机器字段。
```

预期结果：

- 生成 `reports/daily-reviews/YYYY-MM-DD/review-context.json`。
- 生成 `reports/daily-reviews/YYYY-MM-DD/llm-review-sections.json`。
- 校验通过后生成 `reports/daily-reviews/YYYY-MM-DD/a-share-daily-review.html`。
- 同时生成 `reports/daily-reviews/YYYY-MM-DD/a-share-daily-review-data-notes.md`。
- HTML 正文包含 `大盘观察`，并分出 `大盘定性` 和 `大盘结构`。
- 对话中返回 HTML 路径、技术参考路径、交易日期和研究边界。
- 不输出交易建议。

### 指定日期并先刷新数据

```text
调用 a-share-daily-review，先通过仓库 CLI 更新 2026-06-18 的每日数据，然后生成 HTML report。
要求：不要直接调用 scripts/collect_daily_snapshot.py；如果刷新失败，只返回失败原因和可复查日志，不要生成完整复盘。
```

预期结果：

- agent 使用 `python -m a_share_info_hub daily-update --trade-date 2026-06-18` 这个公开入口。
- 刷新成功后生成 `review-context.json`。
- LLM 基于 context 生成 sections JSON。
- Python 校验后生成 HTML。
- 刷新失败时返回阻断说明。

### 只基于已有数据生成 HTML

```text
调用 a-share-daily-review，只使用当前仓库已有的 2026-06-18 数据，不刷新接口，生成 HTML 复盘报告。
重点看市场宽度、涨跌停情绪和龙虎榜异动；如果板块数据缺失，请用普通投资者能理解的语言说明证据不足，不要在 HTML 正文写接口名或 blocked 字段。
```

预期结果：

- 不调用每日更新 CLI。
- 使用指定日期已有 artifacts。
- HTML 主报告呈现可用市场事实、情绪线索、风险含义和后续验证问题。
- 如果板块证据不足，报告不能写板块主线或领涨板块结论。
- 技术参考 Markdown 记录 `data_status`、`blocked_sections`、失败接口和排障建议。

### 接入外部宏观与机构观点背景

```text
调用 a-share-daily-review，使用 2026-06-18 已有 A 股数据生成 HTML report。
同时接入 external_background JSON：<path-to-external-background.json>。
要求：外部背景只作为宏观和机构观点背景，不能覆盖本地 A 股快照结论；HTML 只能把它融入大盘观察、风险观察和待验证问题，参考来源写入技术参考 Markdown。
```

预期结果：

- agent 先用 `--external-background <path>` 生成 `review-context.json`。
- `review-context.json.external_background` 独立记录状态、核心点、引用、信息缺口和降级原因。
- LLM sections 可以使用兼容的外部背景字段，但最终只能合并进主报告已有 sections，不渲染独立外部背景章节。
- Python 校验通过后，HTML 只保留一个 `风险观察` 和一个 `下一步研究问题`，外部风险和待验证问题合并表达。
- 技术参考 Markdown 记录 external background 输入路径、状态、引用来源和降级原因。
- 若外部背景 blocked、invalid 或引用缺 URL，本地 A 股复盘仍可用，HTML 不展示外部状态、工程说明或无来源外部结论。

## 直接获取研究建议

这里的“建议”只指研究建议，不是交易建议。

### 获取盘后研究建议

```text
调用 a-share-daily-review，基于最近一次 daily run 直接给我研究建议，不用生成 HTML。
请输出：今天值得继续验证的市场问题、风险观察、需要补充的数据；不要给买卖、仓位和目标价。
```

预期结果：

- 生成并使用 `review-context.json`。
- LLM 输出 sections JSON 后，Python 校验。
- 直接在对话中返回结构化研究建议。
- 包含数据状态和限制。
- 不生成 HTML 文件。

### 获取风险优先的复盘

```text
调用 a-share-daily-review，基于 2026-06-18 已有数据直接给我风险观察。
请优先指出哪些结论不能下、哪些数据缺口会影响判断、下一步应该验证什么。
```

预期结果：

- 输出数据限制、不可下结论项和待验证问题。
- 不把风险观察转化为交易动作。

### 用户提出交易化问题时

```text
调用 a-share-daily-review，看看今天哪些股票可以买，给我仓位建议。
```

预期行为：

- agent 必须拒绝买入和仓位建议。
- 可以改写为研究输出：哪些数据维度可用于后续人工研究、哪些异动需要验证、哪些风险需要排查。
- 输出必须包含 `not_investment_advice: true`。

## 数据质量诊断场景

### 检查为什么不能生成完整报告

```text
调用 a-share-daily-review，检查 2026-06-18 为什么不能生成完整复盘。
只做数据质量诊断：读取 interface-status.json、daily-data-summary.md、DuckDB 和标准化表，列出阻断项和修复建议。
```

预期结果：

- 输出每个关键 artifact 的存在性和可读性。
- 说明整体状态是 `missing`、`failed`、`skipped` 还是 `partial`。
- 给出下一步修复命令或需要人工检查的文件。

### 解释 partial 数据

```text
调用 a-share-daily-review，解释最近一次 daily run 的 partial 状态。
请列出哪些接口成功、哪些接口失败、哪些复盘章节仍可生成、哪些章节必须 blocked。
```

预期结果：

- 不把 partial 写成完整市场复盘。
- 主表可用时可以输出主表范围内观察。
- 增强数据失败的章节必须明确 blocked。

## 输出选择

- 需要给普通读者 review：要求 `output_format=html`，按 context -> LLM sections -> validator -> HTML + 技术 Markdown 流程。
- 自己快速看结论：要求“直接给研究建议”或 `output_format=inline`。
- 只准备证据包：要求 `output_format=context`。
- 本地 fixture 或评测：可以用 `--render-mode deterministic`。
- 数据不确定：先要求“只做数据质量诊断”。

## 好提示词的模板

```text
调用 a-share-daily-review。
trade_date: <YYYY-MM-DD 或 最近一次>
refresh_mode: none|daily_update
output_format: html|inline|context
external_background: <可选 external_background.v1 或 external_background_fusion.v1 JSON 路径>
focus: <市场宽度/情绪/龙虎榜/板块/风险/数据质量>

要求：
1. 先生成 review-context.json。
2. LLM 只能引用 review-context.json。
3. HTML 按策略分析师写给普通投资者的口吻输出，技术状态写入同目录 Markdown。
4. 不要输出买卖、仓位、目标价或实盘建议。
5. HTML report 和技术参考 Markdown 都需要返回本地文件路径。
```

## 常见误区

- “直接给建议”不是“给交易建议”；agent 只能给研究建议和待验证问题。
- 单日数据不能支持历史趋势和胜率结论。
- 增强接口失败时，不能用主表数据补写龙虎榜、涨跌停或板块结论。
- 普通 HTML 报告不应出现 `blocked_sections`、接口名、连接错误或 `strong_limit_up` 这类原始分类编码；这些内容属于技术参考 Markdown。
- 如果用户指定日期，不应自动改用其他日期。
- 如果需要刷新数据，必须通过 `python -m a_share_info_hub daily-update`，不要 hard code 脚本路径。
- Promptfoo 是黄金测试和回归评测工具，不是普通用户生成日报时的必经步骤。
- 外部宏观和机构观点只能作为背景，不是本地 A 股行情证据；无 `source_name` 或 `url` 的外部观点不会进入 HTML 核心正文，引用和状态进入技术参考 Markdown。
