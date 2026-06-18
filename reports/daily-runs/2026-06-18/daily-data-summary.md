# 每日 A 股快照数据摘要

- 交易日期：`2026-06-18`
- 生成时间：`2026-06-18T22:28:39.486044+08:00`
- 当日整体状态：`partial`
- DuckDB 状态：`written`

## 主表状态

- 主表接口：`stock_zh_a_spot`
- 主表状态：`success`
- 主表原始行数：`5527`
- 标准化主表行数：`5527`

## 增强接口状态

| 来源 | 类别 | 状态 | 原始行数 | 失败或说明 |
| --- | --- | --- | ---: | --- |
| `stock_zt_pool_em` | `limit_pool` | `success` | 91 |  |
| `stock_zt_pool_previous_em` | `limit_pool` | `success` | 86 |  |
| `stock_zt_pool_strong_em` | `limit_pool` | `success` | 347 |  |
| `stock_zt_pool_sub_new_em` | `limit_pool` | `success` | 135 |  |
| `stock_zt_pool_zbgc_em` | `limit_pool` | `success` | 42 |  |
| `stock_zt_pool_dtgc_em` | `limit_pool` | `success` | 12 |  |
| `stock_lhb_detail_daily_sina` | `lhb` | `success` | 99 |  |
| `stock_lhb_detail_em` | `lhb` | `success` | 102 |  |
| `stock_lhb_jgmmtj_em` | `lhb` | `success` | 55 |  |
| `stock_sse_deal_daily` | `market_summary` | `success` | 8 |  |
| `stock_szse_summary` | `market_summary` | `success` | 14 |  |
| `stock_board_industry_name_em` | `board_snapshot` | `failed` | 0 | ConnectionError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) |
| `stock_board_concept_name_em` | `board_snapshot` | `failed` | 0 | ConnectionError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) |

## 标准化表行数

| 表 | 行数 |
| --- | ---: |
| `daily_stock_snapshot` | 5527 |
| `limit_pool_events` | 713 |
| `lhb_events` | 256 |
| `market_summary` | 22 |
| `board_snapshot` | 0 |

## 边界

- 本运行不生成预测。
- 本运行不生成交易建议。
- 快照型主表只表达获取时点，不承诺历史回放。
- 事件型增强数据不会补齐成全股票字段。
