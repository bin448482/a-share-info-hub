# 2026-06-18 A 股每日复盘技术参考

本文档记录主报告隐藏的技术状态、接口失败和数据来源，供 review、排障和后续重跑使用。

## 运行状态

- trade_date: 2026-06-18
- data_status: partial
- analysis_mode: research_only
- not_investment_advice: true
- context_artifact: reports\daily-reviews\2026-06-18\review-context.json
- blocked_sections: ["board_snapshot"]
- render_mode: llm

## 数据来源

- reports\daily-runs\2026-06-18\interface-status.json
- reports\daily-runs\2026-06-18\daily-data-summary.md
- data\normalized\daily_stock_snapshot.parquet
- data\normalized\limit_pool_events.parquet
- data\normalized\lhb_events.parquet
- data\normalized\market_summary.parquet
- data\normalized\board_snapshot.parquet
- market.duckdb

## 接口和表状态

| 名称 | 分类 | 状态 | 行数 | 问题 |
| --- | --- | --- | --- | --- |
| daily_data_summary | run_summary | readable |  |  |
| duckdb | storage | passed |  |  |
| interface_status | run_status | readable |  |  |
| stock_board_concept_name_em | board_snapshot | failed | 0 | ConnectionError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) |
| stock_board_industry_name_em | board_snapshot | failed | 0 | ConnectionError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) |
| stock_lhb_detail_daily_sina | lhb | success | 99 |  |
| stock_lhb_detail_em | lhb | success | 102 |  |
| stock_lhb_jgmmtj_em | lhb | success | 55 |  |
| stock_sse_deal_daily | market_summary | success | 8 |  |
| stock_szse_summary | market_summary | success | 14 |  |
| stock_zh_a_spot | main | success | 5527 |  |
| stock_zt_pool_dtgc_em | limit_pool | success | 12 |  |
| stock_zt_pool_em | limit_pool | success | 91 |  |
| stock_zt_pool_previous_em | limit_pool | success | 86 |  |
| stock_zt_pool_strong_em | limit_pool | success | 347 |  |
| stock_zt_pool_sub_new_em | limit_pool | success | 135 |  |
| stock_zt_pool_zbgc_em | limit_pool | success | 42 |  |
| table:board_snapshot | normalized_table | readable | 0 |  |
| table:daily_stock_snapshot | normalized_table | readable | 5527 |  |
| table:lhb_events | normalized_table | readable | 256 |  |
| table:limit_pool_events | normalized_table | readable | 713 |  |
| table:market_summary | normalized_table | readable | 22 |  |

## 原始分类统计

### 涨跌停情绪池分类

- strong_limit_up: 347
- sub_new_limit_up: 135
- limit_up: 91
- previous_limit_up: 86
- broken_board: 42
- limit_down: 12

### 龙虎榜事件来源

- stock_lhb_detail_em: 102
- stock_lhb_detail_daily_sina: 99
- stock_lhb_jgmmtj_em: 55

## external_background

- status: passed
- input_path: reports\daily-reviews\2026-06-18\external-background-fusion.json
- briefing_date: 2026-06-18
- source_skill: daily-financial-briefing

### 引用来源

- Federal Reserve: https://www.federalreserve.gov/example

### 降级或拒绝原因

- 未记录 external_background 降级或拒绝原因。

### 信息缺口

- 无

## 诊断问题

- stock_board_industry_name_em 状态为 failed：ConnectionError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
- stock_board_concept_name_em 状态为 failed：ConnectionError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))

## 修复建议

- 如需重跑数据采集，使用：`python -m a_share_info_hub daily-update --trade-date 2026-06-18`
- 修复或重跑后重新生成 `review-context.json`，再让 LLM 基于新的 context 生成 sections JSON。