# 每日复盘研究 Workflow

本 reference 定义 `$a-share-daily-review` 的执行细节。使用该 skill 时，优先调用仓库 CLI，不直接解析脚本内部实现。

## 输入

- `trade_date`：可选。格式为 `YYYY-MM-DD`。未提供时读取最近一次 `reports/daily-runs/`。
- `refresh_mode`：`none` 或 `daily_update`。默认 `none`。
- `output_format`：`context`、`html`、`inline` 或 `markdown`。默认用户报告走 `html`，但必须先生成 context。
- `render_mode`：`llm` 或 `deterministic`。默认 `llm`。
- `llm_output`：LLM 生成的 sections JSON 路径。
- `external_background`：可选。指向 `external_background.v1` 或 `external_background_fusion.v1` JSON，由 agent 基于 `$daily-financial-briefing` 输出汇总；`daily-review` 不联网生成它。
- `focus`：可选。用于强调风险、数据质量、市场宽度、情绪、龙虎榜或板块。

## 标准流程

### 1. 生成 evidence packet

```text
python -m a_share_info_hub daily-review --trade-date <YYYY-MM-DD> --output-format context
```

输出：

```text
reports/daily-reviews/YYYY-MM-DD/review-context.json
```

`review-context.json` 是 LLM 唯一允许引用的事实来源。

### 2. 让 LLM 生成 sections JSON

读取：

```text
skills/a-share-daily-review/references/report-prompt.md
reports/daily-reviews/YYYY-MM-DD/review-context.json
```

写入：

```text
reports/daily-reviews/YYYY-MM-DD/llm-review-sections.json
```

LLM 输出必须是 JSON，不能是自由 Markdown。

### 3. 校验并生成 HTML

```text
python -m a_share_info_hub daily-review --trade-date <YYYY-MM-DD> --llm-output reports/daily-reviews/YYYY-MM-DD/llm-review-sections.json --output-format html
```

输出：

```text
reports/daily-reviews/YYYY-MM-DD/a-share-daily-review.html
reports/daily-reviews/YYYY-MM-DD/a-share-daily-review-data-notes.md
```

Python 会使用 Pydantic 校验 LLM JSON，再检查 blocked sections、禁用交易建议语言和 HTML 边界。

如果需要把 `$daily-financial-briefing` 的外部宏观和机构观点背景纳入 HTML，先生成本地 context，再由 agent 读取本地主题并调用外部信息 skill。外部结果应保存为受控 `external_background.v1` 或 `external_background_fusion.v1` JSON，再在生成 context 和最终 HTML 时都传入同一路径：

```text
python -m a_share_info_hub daily-review --trade-date <YYYY-MM-DD> --external-background <path-to-json> --output-format context
python -m a_share_info_hub daily-review --trade-date <YYYY-MM-DD> --external-background <path-to-json> --llm-output reports/daily-reviews/YYYY-MM-DD/llm-review-sections.json --output-format html
```

`external_background` 只进入 `review-context.json.external_background`，不进入 `data_sources_used`，也不能补全本地行情、板块、情绪或龙虎榜缺口。

### 2.1 外部背景 agent 编排

Agent 必须先读取 `review-context.json`，抽取本地主题包，再按主题调用 `$daily-financial-briefing` 或其等价公开来源工作流。第一版主题固定为：

```text
market_overview_assessment
market_overview_structure
market_breadth
sentiment_and_events
board_and_structure
risk_observations
```

每个外部任务都必须带上本地主题摘要和证据边界，输出主题相关的外部变量、风险候选或待验证问题，不输出通用新闻摘要。外部任务之间可以并行；汇总必须在 LLM sections 生成前完成。

Python CLI 只读取受控 JSON、校验引用和边界、渲染报告。它不搜索网页、不调用浏览器、不自动运行 `$daily-financial-briefing`。

推荐融合输入包：

```json
{
  "schema_version": "external_background_fusion.v1",
  "source_skill": "daily-financial-briefing",
  "trade_date": "YYYY-MM-DD",
  "not_investment_advice": true,
  "topic_findings": [],
  "risk_candidates": [],
  "follow_up_candidates": [],
  "citations": [],
  "information_gaps": [],
  "issues": []
}
```

## 刷新数据

先刷新再生成 context：

```text
python -m a_share_info_hub daily-review --trade-date <YYYY-MM-DD> --refresh-mode daily_update --output-format context
```

刷新数据时，CLI 内部只能使用公开入口：

```text
python -m a_share_info_hub daily-update --trade-date <YYYY-MM-DD>
```

不要直接调用 `scripts/collect_daily_snapshot.py`。

## 直接研究建议

如果用户不需要 HTML，可以仍走 context + LLM sections，然后用 inline 渲染：

```text
python -m a_share_info_hub daily-review --trade-date <YYYY-MM-DD> --llm-output reports/daily-reviews/YYYY-MM-DD/llm-review-sections.json --output-format inline
```

这里的“建议”只能是研究建议、风险观察或待验证问题。

## 状态边界

- `passed`：可以生成完整研究复盘。
- `partial`：主报告只生成证据范围有限的用户可读观察，所有缺失维度仍必须列入技术参考文件中的 `blocked_sections`。
- `failed`：不能生成市场复盘结论，只输出阻断原因和修复命令。
- `missing`：不能自动改用其他日期；提示运行公开 daily-update CLI。

## HTML 边界

HTML 第一屏必须是用户可读报告：

- 显示交易日期。
- 显示报告角色和非投资建议边界。
- 用用户语言说明证据边界，不裸露内部状态字段。
- 正文必须包含 `大盘观察`，并在其中分出 `大盘定性` 和 `大盘结构`。

HTML 正文不得出现以下技术字段或接口错误：

```text
blocked_sections
board_snapshot
stock_board_industry_name_em
stock_board_concept_name_em
data_status: partial
ConnectionError
RemoteDisconnected
```

HTML 正文不得裸露这些机器映射行：

```text
analysis_mode:
data_status:
blocked_sections:
data_sources_used:
```

机器 metadata 应放入 `<script type="application/json" id="review-metadata">` 或数据边界折叠区。

有合格外部背景时，HTML 不新增 `外部宏观与机构观点背景` 独立章节。外部变量只能被 LLM 融合进 `大盘观察`、唯一的 `风险观察` 和唯一的 `下一步研究问题`；引用 URL、状态、输入路径、信息缺口和降级原因写入技术参考 Markdown。

HTML 正文还不得出现：

```text
passed
partial
blocked
invalid
external_background.status
schema_version
模拟输入
fixture
HTML 展示形态
```

## 技术参考 Markdown

每次生成 HTML 时，同时生成：

```text
reports/daily-reviews/YYYY-MM-DD/a-share-daily-review-data-notes.md
```

该文件面向 review 和排障，允许记录：

- `data_status`
- `blocked_sections`
- `data_sources_used`
- failed source key 和失败原因
- normalized table 行数
- DuckDB 状态
- external_background 输入路径、状态、引用来源、信息缺口和降级原因
- 重跑或排障建议

普通投资者主报告不展示这些技术细节，只提示可查看同目录技术参考文件。

## 安全边界

如果用户要求买卖、仓位、目标价、止盈止损或实盘时点，拒绝交易行动建议，并改写为研究观察、风险和待验证问题。

禁用输出：

- 建议买入
- 建议卖出
- 买入建议
- 卖出建议
- 仓位建议
- 目标价
- 止盈
- 止损
- 明日必涨
- 确定性主线

## 验证

实施或修改后至少运行：

```text
python -m py_compile a_share_info_hub/__main__.py a_share_info_hub/daily_review.py
python -m pytest tests
python C:/Users/zhanb.BIINN/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/a-share-daily-review
```

如使用本仓库虚拟环境，在 Windows 上优先使用：

```text
.venv\Scripts\python.exe -m pytest tests
```
