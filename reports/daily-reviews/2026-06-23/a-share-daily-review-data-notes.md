# 2026-06-23 A 股每日复盘技术参考

本文档记录主报告隐藏的技术状态、接口失败和数据来源，供 review、排障和后续重跑使用。

## 运行状态

- trade_date: 2026-06-23
- data_status: partial
- analysis_mode: research_only
- not_investment_advice: true
- context_artifact: /mnt/tool/2-projects/a-share-info-hub/reports/daily-reviews/2026-06-23/review-context.json
- blocked_sections: ["board_snapshot", "lhb_events", "market_summary"]
- render_mode: llm

## 数据来源

- /mnt/tool/2-projects/a-share-info-hub/reports/daily-runs/2026-06-23/interface-status.json
- /mnt/tool/2-projects/a-share-info-hub/reports/daily-runs/2026-06-23/daily-data-summary.md
- /mnt/tool/2-projects/a-share-info-hub/data/normalized/daily_stock_snapshot.parquet
- /mnt/tool/2-projects/a-share-info-hub/data/normalized/limit_pool_events.parquet
- /mnt/tool/2-projects/a-share-info-hub/data/normalized/lhb_events.parquet
- /mnt/tool/2-projects/a-share-info-hub/data/normalized/market_summary.parquet
- /mnt/tool/2-projects/a-share-info-hub/data/normalized/board_snapshot.parquet
- /mnt/tool/2-projects/a-share-info-hub/market.duckdb

## 接口和表状态

| 名称 | 分类 | 状态 | 行数 | 问题 |
| --- | --- | --- | --- | --- |
| daily_data_summary | run_summary | readable |  |  |
| duckdb | storage | passed |  |  |
| interface_status | run_status | readable |  |  |
| stock_board_concept_name_em | board_snapshot | failed | 0 | ConnectionError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) |
| stock_board_industry_name_em | board_snapshot | failed | 0 | ConnectionError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) |
| stock_lhb_detail_daily_sina | lhb | failed | 0 | KeyError: '股票代码' |
| stock_lhb_detail_em | lhb | success | 48 |  |
| stock_lhb_jgmmtj_em | lhb | success | 40 |  |
| stock_sse_deal_daily | market_summary | failed | 0 | ValueError: Length mismatch: Expected axis has 1 elements, new values have 6 elements |
| stock_szse_summary | market_summary | success | 14 |  |
| stock_zh_a_spot | main | success | 5527 |  |
| stock_zt_pool_dtgc_em | limit_pool | success | 39 |  |
| stock_zt_pool_em | limit_pool | success | 96 |  |
| stock_zt_pool_previous_em | limit_pool | success | 134 |  |
| stock_zt_pool_strong_em | limit_pool | success | 324 |  |
| stock_zt_pool_sub_new_em | limit_pool | success | 133 |  |
| stock_zt_pool_zbgc_em | limit_pool | success | 50 |  |
| table:board_snapshot | normalized_table | readable | 0 |  |
| table:daily_stock_snapshot | normalized_table | readable | 5527 |  |
| table:lhb_events | normalized_table | readable | 88 |  |
| table:limit_pool_events | normalized_table | readable | 776 |  |
| table:market_summary | normalized_table | readable | 14 |  |
| trading_day_check | run_status | success |  | trade date is listed in AKShare trading calendar |

## 原始分类统计

### 涨跌停情绪池分类

- strong_limit_up: 324
- previous_limit_up: 134
- sub_new_limit_up: 133
- limit_up: 96
- broken_board: 50
- limit_down: 39

### 龙虎榜事件来源

- 无

## external_background

- status: invalid
- input_path: reports/daily-reviews/2026-06-23/external-background-fusion.json
- briefing_date: 无
- source_skill: 无

### 引用来源

- 无

### 降级或拒绝原因

- 外部背景融合包结构校验失败：7 validation errors for ExternalBackgroundFusionInput
issues.0
  Input should be a valid string [type=string_type, input_value={'severity': 'blocked', '...引用公开来源。'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/string_type
issues.1
  Input should be a valid string [type=string_type, input_value={'severity': 'blocked', '...k Views公开来源。'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/string_type
issues.2
  Input should be a valid string [type=string_type, input_value={'severity': 'blocked', '...败，双重阻塞。'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/string_type
issues.3
  Input should be a valid string [type=string_type, input_value={'severity': 'warning', '...存在显著缺口。'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/string_type
issues.4
  Input should be a valid string [type=string_type, input_value={'severity': 'warning', '...的多视角复用。'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/string_type
issues.5
  Input should be a valid string [type=string_type, input_value={'severity': 'warning', '...结构性风险）。'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/string_type
issues.6
  Input should be a valid string [type=string_type, input_value={'severity': 'info', 'top...新增覆盖topic。'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/string_type

### 信息缺口

- 无

## 诊断问题

- stock_lhb_detail_daily_sina 状态为 failed：KeyError: '股票代码'
- stock_sse_deal_daily 状态为 failed：ValueError: Length mismatch: Expected axis has 1 elements, new values have 6 elements
- stock_board_industry_name_em 状态为 failed：ConnectionError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
- stock_board_concept_name_em 状态为 failed：ConnectionError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))

## 修复建议

- 如需重跑数据采集，使用：`python -m a_share_info_hub daily-update --trade-date 2026-06-23`
- 修复或重跑后重新生成 `review-context.json`，再让 LLM 基于新的 context 生成 sections JSON。