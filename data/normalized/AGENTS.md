# data/normalized 目录索引

本文件是 `data/normalized/` 的目录索引。新增、删除、改名或移动标准化表时，必须同步更新这里的说明。

## 目录用途

- 保存从原始接口返回生成的标准化 Parquet 或 CSV 表。
- 标准化表必须保留 `trade_date`、`fetched_at` 和 `source` 等追溯字段。
- 不允许用空值、默认值或猜测字段伪造标准化成功。

## 文件索引

- `AGENTS.md`：本目录索引和维护规则。
- `claude.md`：Claude/Codex 入口引用文件，内容固定为 `@agents.md`。
- `daily_stock_snapshot.parquet`：每日全 A 股主快照标准表，只来自 `stock_zh_a_spot`。
- `limit_pool_events.parquet`：涨跌停、强势、次新、炸板、跌停等情绪池事件表。
- `lhb_events.parquet`：龙虎榜事件明细表，保留来源和原因，不提前聚合。
- `market_summary.parquet`：上交所、深交所市场级成交概况。
- `board_snapshot.parquet`：行业和概念板块快照；接口失败时可能为空表。

## 更新要求

- 新增或重命名标准化表时，同步更新采集脚本、DuckDB 写入逻辑、测试、README、设计文档和本索引。
- 标准化表为空不等于接口成功；必须结合 `reports/daily-runs/YYYY-MM-DD/interface-status.json` 判断状态。
- 不要手工编辑 Parquet 产物；应通过脚本重跑生成。
