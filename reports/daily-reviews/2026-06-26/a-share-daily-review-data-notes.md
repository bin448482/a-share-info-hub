# 2026-06-26 A 股每日复盘技术参考

本文档记录主报告隐藏的技术状态、接口失败和数据来源，供 review、排障和后续重跑使用。

## 运行状态

- trade_date: 2026-06-26
- data_status: partial
- analysis_mode: research_only
- not_investment_advice: true
- context_artifact: /mnt/tool/2-projects/a-share-info-hub/reports/daily-reviews/2026-06-26/review-context.json
- blocked_sections: ["lhb_events", "market_summary"]
- render_mode: llm

## 数据来源

- /mnt/tool/2-projects/a-share-info-hub/reports/daily-runs/2026-06-26/interface-status.json
- /mnt/tool/2-projects/a-share-info-hub/reports/daily-runs/2026-06-26/daily-data-summary.md
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
| stock_board_concept_name_em | board_snapshot | ignored | 0 | ProxyError: HTTPSConnectionPool(host='79.push2.eastmoney.com', port=443): Max retries exceeded with url: /api/qt/clist/get?pn=1&pz=100&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f12&fs=m%3A90+t%3A3+f%3A%2150&fields=f2%2Cf3%2Cf4%2Cf8%2Cf12%2Cf14%2Cf15%2Cf16%2Cf17%2Cf18%2Cf20%2Cf21%2Cf24%2Cf25%2Cf22%2Cf33%2Cf11%2Cf62%2Cf128%2Cf124%2Cf107%2Cf104%2Cf105%2Cf136 (Caused by ProxyError('Unable to connect to proxy', RemoteDisconnected('Remote end closed connection without response'))) |
| stock_board_industry_name_em | board_snapshot | ignored | 0 | ProxyError: HTTPSConnectionPool(host='17.push2.eastmoney.com', port=443): Max retries exceeded with url: /api/qt/clist/get?pn=1&pz=100&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f3&fs=m%3A90+t%3A2+f%3A%2150&fields=f1%2Cf2%2Cf3%2Cf4%2Cf5%2Cf6%2Cf7%2Cf8%2Cf9%2Cf10%2Cf12%2Cf13%2Cf14%2Cf15%2Cf16%2Cf17%2Cf18%2Cf20%2Cf21%2Cf23%2Cf24%2Cf25%2Cf26%2Cf22%2Cf33%2Cf11%2Cf62%2Cf128%2Cf136%2Cf115%2Cf152%2Cf124%2Cf107%2Cf104%2Cf105%2Cf140%2Cf141%2Cf207%2Cf208%2Cf209%2Cf222 (Caused by ProxyError('Unable to connect to proxy', RemoteDisconnected('Remote end closed connection without response'))) |
| stock_lhb_detail_daily_sina | lhb | failed | 0 | KeyError: '股票代码' |
| stock_lhb_detail_em | lhb | failed | 0 | TypeError: 'NoneType' object is not subscriptable |
| stock_lhb_jgmmtj_em | lhb | failed | 0 | TypeError: 'NoneType' object is not subscriptable |
| stock_sse_deal_daily | market_summary | failed | 0 | ValueError: Length mismatch: Expected axis has 1 elements, new values have 6 elements |
| stock_szse_summary | market_summary | failed | 0 | AttributeError: 'float' object has no attribute 'replace' |
| stock_zh_a_spot | main | success | 5527 |  |
| stock_zt_pool_dtgc_em | limit_pool | success | 30 |  |
| stock_zt_pool_em | limit_pool | success | 60 |  |
| stock_zt_pool_previous_em | limit_pool | success | 86 |  |
| stock_zt_pool_strong_em | limit_pool | success | 281 |  |
| stock_zt_pool_sub_new_em | limit_pool | success | 135 |  |
| stock_zt_pool_zbgc_em | limit_pool | success | 35 |  |
| table:board_snapshot | normalized_table | readable | 0 |  |
| table:daily_stock_snapshot | normalized_table | readable | 5527 |  |
| table:lhb_events | normalized_table | readable | 0 |  |
| table:limit_pool_events | normalized_table | readable | 627 |  |
| table:market_summary | normalized_table | readable | 0 |  |
| trading_day_check | run_status | success |  | trade date is listed in AKShare trading calendar |

## 原始分类统计

### 涨跌停情绪池分类

- strong_limit_up: 281
- sub_new_limit_up: 135
- previous_limit_up: 86
- limit_up: 60
- broken_board: 35
- limit_down: 30

### 龙虎榜事件来源

- 无

## external_background

- status: invalid
- input_path: /mnt/tool/2-projects/a-share-info-hub/reports/daily-reviews/2026-06-26/external-background-fusion.json
- briefing_date: 无
- source_skill: 无

### 引用来源

- 无

### 降级或拒绝原因

- 外部背景融合包结构校验失败：7 validation errors for ExternalBackgroundFusionInput
issues.0
  Input should be a valid string [type=string_type, input_value={'severity': 'warning', '...-06-25 验证记录。'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/string_type
issues.1
  Input should be a valid string [type=string_type, input_value={'severity': 'warning', '...nal_findings 为空。'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/string_type
issues.2
  Input should be a valid string [type=string_type, input_value={'severity': 'info', 'des...何 US Macro 数据。'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/string_type
issues.3
  Input should be a valid string [type=string_type, input_value={'severity': 'info', 'des...投行情绪评论。'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/string_type
issues.4
  Input should be a valid string [type=string_type, input_value={'severity': 'info', 'des...构性背景叙事。'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/string_type
issues.5
  Input should be a valid string [type=string_type, input_value={'severity': 'info', 'des...数据值未确认。'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/string_type
issues.6
  Input should be a valid string [type=string_type, input_value={'severity': 'info', 'des...叉验证的能力。'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/string_type

### 信息缺口

- 无

## 诊断问题

- stock_lhb_detail_daily_sina 状态为 failed：KeyError: '股票代码'
- stock_lhb_detail_em 状态为 failed：TypeError: 'NoneType' object is not subscriptable
- stock_lhb_jgmmtj_em 状态为 failed：TypeError: 'NoneType' object is not subscriptable
- stock_sse_deal_daily 状态为 failed：ValueError: Length mismatch: Expected axis has 1 elements, new values have 6 elements
- stock_szse_summary 状态为 failed：AttributeError: 'float' object has no attribute 'replace'

## 修复建议

- 如需重跑数据采集，使用：`python -m a_share_info_hub daily-update --trade-date 2026-06-26`
- 修复或重跑后重新生成 `review-context.json`，再让 LLM 基于新的 context 生成 sections JSON。