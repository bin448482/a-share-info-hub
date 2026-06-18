# 每日 A 股快照数据设计

本文档定义 `daily-free-a-share-prediction` 的每日数据获取设计。当前决策是：每天以 `stock_zh_a_spot` 作为全 A 股主快照，再按独立增强表补充涨跌停、龙虎榜、板块和市场背景数据。

## 设计目标

- 每天固定获取一份覆盖全 A 股的主数据。
- 主表不依赖历史回放能力，只表达“当天获取时刻”的股票截面。
- 增强数据独立保存，不强行补齐到每只股票。
- 能与股票代码关联的增强数据保留代码字段，后续分析时再按需 join。
- 接口失败、返回空、字段变化必须记录，不静默写入主契约。
- 第一版使用“原始文件 + 本地分析库”组合：原始返回先落文件，清洗数据、特征、标签、预测和评估进入本地 DuckDB/Parquet 分析层。

## 数据分层

### 1. 主表：每日全 A 股快照

v1 每天必取：

```text
stock_zh_a_spot()
```

该接口当前实测可返回约 5500 只股票，是每日数据的核心表。

主表字段：

- `代码`
- `名称`
- `最新价`
- `涨跌额`
- `涨跌幅`
- `买入`
- `卖出`
- `昨收`
- `今开`
- `最高`
- `最低`
- `成交量`
- `成交额`
- `时间戳`

建议标准化字段：

| 标准字段 | 原始字段 | 含义 |
| --- | --- | --- |
| `trade_date` | 运行日期 | 数据所属日期 |
| `symbol` | `代码` | 股票代码，保留交易所前缀或原始代码格式 |
| `name` | `名称` | 股票名称 |
| `last_price` | `最新价` | 获取时点最新价，收盘后近似收盘价 |
| `change_amount` | `涨跌额` | 相对昨收涨跌额 |
| `change_pct` | `涨跌幅` | 相对昨收涨跌幅 |
| `bid_price` | `买入` | 买一或接口定义的买入价 |
| `ask_price` | `卖出` | 卖一或接口定义的卖出价 |
| `prev_close` | `昨收` | 昨日收盘价 |
| `open` | `今开` | 当日开盘价 |
| `high` | `最高` | 当日最高价 |
| `low` | `最低` | 当日最低价 |
| `volume` | `成交量` | 当日成交量 |
| `amount` | `成交额` | 当日成交额 |
| `snapshot_time` | `时间戳` | 接口返回的行情时间 |
| `fetched_at` | 采集时间 | 本地实际获取时间 |
| `source` | 固定值 | `akshare.stock_zh_a_spot` |

主表约束：

- 主表必须非空。
- 主表行数明显低于正常全市场规模时，标记为异常。
- 主表不使用空值补齐未获取股票。
- 主表不承诺可回放历史日期；它是每日运行时快照。

### 2. 涨跌停和情绪池增强

v1 每天固定获取：

```text
stock_zt_pool_em(date)
stock_zt_pool_previous_em(date)
stock_zt_pool_strong_em(date)
stock_zt_pool_sub_new_em(date)
stock_zt_pool_zbgc_em(date)
stock_zt_pool_dtgc_em(date)
```

用途：

- 识别涨停、跌停、炸板、强势、次新等情绪状态。
- 通过股票代码与主表关联。
- 作为事件池保存，不要求覆盖所有股票。

设计约束：

- 这些接口自然可能只返回少量股票。
- 返回空时不能补主表字段。
- 每个池单独保存 `pool_type`，不要混成一个不带来源的表。

建议标准字段：

- `trade_date`
- `pool_type`
- `symbol`
- `name`
- `last_price`
- `change_pct`
- `amount`
- `turnover_pct`
- `first_limit_time`
- `last_limit_time`
- `open_count`
- `limit_up_stat`
- `streak_count`
- `industry`
- `fetched_at`
- `source`

### 3. 龙虎榜增强

v1 每天固定获取核心龙虎榜：

```text
stock_lhb_detail_daily_sina(date)
stock_lhb_detail_em(start_date=date, end_date=date)
stock_lhb_jgmmtj_em(start_date=date, end_date=date)
```

可选：

```text
stock_lhb_hyyyb_em(start_date=date, end_date=date)
stock_lhb_stock_statistic_em(symbol="近一月")
```

用途：

- 识别上榜个股、机构买卖、活跃席位。
- 给股票增加资金博弈事件标签。

设计约束：

- 龙虎榜是事件数据，不是每日全股票字段。
- 当日无上榜数据时，应记录为空事件集或接口状态，而不是补到主表。
- 同一股票可能有多条上榜原因，需要保留明细，不要提前聚合丢失原因。

### 4. 市场背景增强

v1 每天固定获取：

```text
stock_sse_deal_daily(date)
stock_szse_summary(date)
```

用途：

- 获取上交所、深交所市场成交概况。
- 作为当天市场背景，不与每只股票逐行合并。

设计约束：

- 这是市场级数据，不是个股字段。
- 报告或模型使用时按 `trade_date` 引用。

### 5. 板块和概念增强

v1 每天固定获取：

```text
stock_board_industry_name_em()
stock_board_concept_name_em()
```

用途：

- 记录当天行业板块、概念板块表现。
- 后续可用于判断市场热点和板块强弱。

设计约束：

- 板块快照不直接等于个股所属行业或概念映射。
- 不要在没有映射依据时把板块涨跌强行写入每只股票。

v2 可考虑：

```text
stock_board_industry_hist_em(...)
stock_board_concept_hist_em(...)
```

### 6. 当前排除：资金流和融资融券

当前设计不纳入资金流和融资融券接口。

排除依据：

- 移除代理变量后，`stock_individual_fund_flow_rank`、`stock_sector_fund_flow_rank`、`stock_main_fund_flow`、`stock_sector_fund_flow_summary` 等资金流接口仍然连接失败。
- 融资融券接口只在部分已知历史日期可取；当前日期接口存在失败、空结果或交易所差异，不能作为每日稳定增强层。
- 这些接口如果未来重新评估，必须先生成新的接口可用性审计报告，再进入设计文档。

## 每日运行策略

v1 每日流程：

1. 验证目标日期是否为 A 股交易日。
2. 非交易日生成 `skipped` 状态报告，不调用行情接口。
3. 交易日获取主表 `stock_zh_a_spot`。
4. 校验主表非空、字段完整、行数达到最低阈值。
5. 获取涨跌停和情绪池增强。
6. 获取龙虎榜核心增强。
7. 获取上交所、深交所市场汇总。
8. 获取行业、概念板块快照。
9. 输出当天数据包和接口状态报告。

## 存储设计

第一版不直接上复杂数据库，也不把原始接口返回只写进数据库。采用：

```text
raw JSON/CSV/HTML 文件
+ normalized Parquet/CSV
+ DuckDB 本地分析库
+ JSONL 失败日志
```

目标是同时满足审计、重跑、查询、训练和回测。

建议输出结构：

```text
data/
  raw/
    YYYY-MM-DD/
      stock_zh_a_spot/
        response.json
        metadata.json
      stock_zt_pool_em/
        response.json
        metadata.json
      stock_lhb_detail_daily_sina/
        response.json
        metadata.json
  normalized/
    daily_stock_snapshot.parquet
    limit_pool_events.parquet
    lhb_events.parquet
    market_summary.parquet
    board_snapshot.parquet
  features/
    daily_features.parquet
  labels/
    forward_returns.parquet
  predictions/
    daily_predictions.parquet
  eval/
    backtest_metrics.parquet
logs/
  external-interface-failures.jsonl
market.duckdb
reports/
  daily-runs/
    YYYY-MM-DD/
      interface-status.json
      daily-data-summary.md
```

### 原始数据层

所有外部接口返回先保存到 `data/raw/YYYY-MM-DD/source-name/`，不改写、不清洗、不覆盖。

每个源至少保存：

- `response.json`、`response.csv` 或 `response.html`
- `metadata.json`

`metadata.json` 建议包含：

- `source`
- `function_name`
- `params`
- `fetched_at`
- `row_count`
- `columns`
- `status`
- `failure_reason`

原因：

- 免费接口经常变字段。
- 接口可能返回空、限流、网络失败或网页结构变化。
- 原始文件是审计、重跑和修复解析逻辑的依据。

### 标准化数据层

清洗后的标准表写入 `data/normalized/`，优先使用 Parquet；需要人工查看时可额外导出 CSV。

v1 标准表：

- `daily_stock_snapshot.parquet`
- `limit_pool_events.parquet`
- `lhb_events.parquet`
- `market_summary.parquet`
- `board_snapshot.parquet`

这些表也同步注册或写入 `market.duckdb`，用于查询、训练和回测。

### 特征、标签、预测和评估层

后续建模时新增：

- `data/features/`：每日特征表。
- `data/labels/`：未来 1/3/5 日真实结果。
- `data/predictions/`：每天模型预测结果。
- `data/eval/`：回测、命中率和分组收益统计。

预测结果必须落库，最低字段：

| 字段 | 含义 |
| --- | --- |
| `prediction_date` | 预测生成日期 |
| `target_date` | 被预测日期或目标窗口结束日期 |
| `symbol` | 股票代码 |
| `prediction_score` | 模型分数 |
| `prediction_rank` | 当日排序 |
| `model_version` | 模型版本 |
| `feature_version` | 特征版本 |

真实收益出来后，再写入 label 和评估结果。否则无法判断模型是否有效。

### DuckDB 分析库

第一版使用本地 `market.duckdb`，不引入 PostgreSQL。

DuckDB 用途：

- 查询历史行情和增强数据。
- join 特征、标签、预测。
- 生成训练集。
- 运行回测和命中率统计。
- 导出审计或分析结果。

DuckDB 不是原始数据唯一来源；原始文件仍然是外部接口审计依据。

### 失败日志

接口失败、空返回、fallback、字段变化统一写入：

```text
logs/external-interface-failures.jsonl
```

失败日志不塞进主行情表。

每行建议包含：

- `logged_at`
- `trade_date`
- `source`
- `function_name`
- `params`
- `failure_type`
- `failure_reason`
- `fallback_used`
- `raw_path`

## 去重和关联策略

主表和增强表不直接互相覆盖。

关联键：

- 个股类增强：`trade_date + symbol`
- 市场类增强：`trade_date`
- 板块类增强：`trade_date + board_code/board_name`
- 龙虎榜明细：`trade_date + symbol + reason/source`

去重规则：

- `daily_stock_snapshot` 是股票主记录。
- 涨跌停、龙虎榜、市场汇总和板块快照都是增强记录。
- 如果增强表和主表都有价格字段，主表价格优先。
- 增强表保留自己的原始价格字段，用于追溯来源，不覆盖主表。

## 验收标准

v1 完成标准：

- 每日主表 `stock_zh_a_spot` 获取成功且非空。
- 非交易日运行应明确标记为 `skipped`，不调用行情接口，不写入原始行情、标准化表或 DuckDB。
- 主表字段标准化完成。
- 增强接口状态完整记录：成功、失败、空结果必须可区分。
- 涨跌停池、龙虎榜、市场汇总、板块快照都有独立输出。
- 原始接口返回保存到 `data/raw/YYYY-MM-DD/source-name/`。
- 标准化结果保存到 `data/normalized/`。
- 本地 `market.duckdb` 可查询标准化行情和增强表。
- 预测结果表设计包含 `prediction_date`、`target_date`、`symbol`、`prediction_score`、`prediction_rank`、`model_version`、`feature_version`。
- 接口失败、空返回和字段变化写入 `logs/external-interface-failures.jsonl`。
- 任一增强接口失败不影响主表落盘，但必须记录失败原因。
- 每日生成 `daily-data-summary.md`，说明当日获取了哪些数据、哪些失败、哪些为空。

## 明确不做

- v1 不做预测。
- v1 不做交易建议。
- v1 不上 PostgreSQL 或复杂数据库服务。
- v1 不把原始接口返回只存进 DuckDB。
- v1 不把事件数据补齐成全股票字段。
- v1 不强行历史回放 `stock_zh_a_spot`。
- v1 不在没有映射依据时把板块数据合并到每只股票。
- v1 不获取资金流数据。
- v1 不获取融资融券数据。
