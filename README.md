# A Share Info Hub

本仓库用于验证和落地每日 A 股免费数据采集链路。当前主入口是每日快照采集，不生成预测，也不提供交易建议。

## 每日快照采集

实施入口是仓库 CLI：

```text
python -m a_share_info_hub daily-update
```

需要指定日期时，使用参数传入，不要把日期写死到脚本或文档流程里：

```text
python -m a_share_info_hub daily-update --trade-date <YYYY-MM-DD>
```

`daily-update` 会在采集前验证目标日期是否为 A 股交易日。非交易日返回 `skipped`，只生成 `reports/daily-runs/YYYY-MM-DD/interface-status.json` 和 `daily-data-summary.md`，不调用行情接口，也不写入原始行情、标准化表或 DuckDB。

如果当前环境代理导致 AKShare 接口失败，可以显式忽略代理：

```text
python -m a_share_info_hub daily-update --ignore-proxy
```

交易日主要输出：

- `data/raw/YYYY-MM-DD/<source>/response.json`
- `data/raw/YYYY-MM-DD/<source>/metadata.json`
- `data/normalized/daily_stock_snapshot.parquet`
- `data/normalized/limit_pool_events.parquet`
- `data/normalized/lhb_events.parquet`
- `data/normalized/market_summary.parquet`
- `data/normalized/board_snapshot.parquet`
- `logs/external-interface-failures.jsonl`
- `reports/daily-runs/YYYY-MM-DD/interface-status.json`
- `reports/daily-runs/YYYY-MM-DD/daily-data-summary.md`
- `market.duckdb`

## 验证命令

```text
python -m py_compile a_share_info_hub/__main__.py a_share_info_hub/daily_review.py scripts/collect_daily_snapshot.py
python -m pytest tests
python -c "import akshare, pandas, duckdb, pyarrow, pydantic"
npm run install:eval
npm run eval:a-share-daily-review
```

真实接口验证需要指定日期运行每日采集脚本；单元测试只验证本地解析、状态和落盘逻辑。
Promptfoo 评测使用仓库固定版本；在 Windows/npm 11 环境下先运行 `npm run install:eval`，该命令会使用兼容的 npm 版本并构建 `better-sqlite3`。

## 每日复盘研究

已有每日快照后，先生成 research-only evidence packet：

```text
python -m a_share_info_hub daily-review --output-format context
```

指定日期生成 `review-context.json`：

```text
python -m a_share_info_hub daily-review --trade-date <YYYY-MM-DD> --output-format context
```

输出位置：

- `reports/daily-reviews/YYYY-MM-DD/review-context.json`
- `reports/daily-reviews/YYYY-MM-DD/a-share-daily-review.html`
- `reports/daily-reviews/YYYY-MM-DD/a-share-daily-review-data-notes.md`

然后让 agent/LLM 只基于 `review-context.json` 生成：

```text
reports/daily-reviews/YYYY-MM-DD/llm-review-sections.json
```

再由 Python 校验并渲染 HTML：

```text
python -m a_share_info_hub daily-review --trade-date <YYYY-MM-DD> --llm-output reports/daily-reviews/YYYY-MM-DD/llm-review-sections.json --output-format html
```

直接在终端返回研究建议或数据质量诊断时，也使用已校验的 sections：

```text
python -m a_share_info_hub daily-review --trade-date <YYYY-MM-DD> --llm-output reports/daily-reviews/YYYY-MM-DD/llm-review-sections.json --output-format inline
```

如需先刷新再复盘，只通过公开 CLI 子命令：

```text
python -m a_share_info_hub daily-review --trade-date <YYYY-MM-DD> --refresh-mode daily_update --output-format context
```

本地评测或 fixture 可使用 deterministic fallback：

```text
python -m a_share_info_hub daily-review --trade-date <YYYY-MM-DD> --render-mode deterministic --output-format html
```

正式用户报告应使用 `$a-share-daily-review` 的 evidence packet + LLM sections + Python/Pydantic validator 流程。该 skill 只输出研究复盘、风险观察和待验证问题；不提供买卖、仓位、目标价或止盈止损建议。

HTML 报告默认按“策略分析师写给普通投资者”的方式表达，只展示可读的市场观察和证据边界；接口失败、`data_status`、`blocked_sections`、source key、原始分类编码和排障建议写入同目录 `a-share-daily-review-data-notes.md`。

每日复盘正文固定包含 `1.1 大盘`，其中 `大盘定性` 解释当日全市场宽度，`大盘结构` 解释上涨/下跌覆盖面、极端样本和结构证据边界。
