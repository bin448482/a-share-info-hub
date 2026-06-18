# 每日复盘研究 Workflow

本 reference 定义 `$a-share-daily-review` 的执行细节。使用该 skill 时，优先调用仓库 CLI，不直接解析脚本内部实现。

## 输入

- `trade_date`：可选。格式为 `YYYY-MM-DD`。未提供时读取最近一次 `reports/daily-runs/`。
- `refresh_mode`：`none` 或 `daily_update`。默认 `none`。
- `output_format`：`context`、`html`、`inline` 或 `markdown`。默认用户报告走 `html`，但必须先生成 context。
- `render_mode`：`llm` 或 `deterministic`。默认 `llm`。
- `llm_output`：LLM 生成的 sections JSON 路径。
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
```

Python 会使用 Pydantic 校验 LLM JSON，再检查 blocked sections、禁用交易建议语言和 HTML 边界。

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
- `partial`：只生成数据受限观察，所有缺失维度必须列入 `blocked_sections`。
- `failed`：不能生成市场复盘结论，只输出阻断原因和修复命令。
- `missing`：不能自动改用其他日期；提示运行公开 daily-update CLI。

## HTML 边界

HTML 第一屏必须是用户可读报告：

- 显示交易日期。
- 显示数据状态。
- 显示 research-only 和非投资建议边界。
- 显示 blocked sections 或“无”。

HTML 正文不得裸露这些机器映射行：

```text
analysis_mode:
data_status:
blocked_sections:
data_sources_used:
```

机器 metadata 应放入 `<script type="application/json" id="review-metadata">` 或数据边界折叠区。

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
