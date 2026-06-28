# 每日 A 股快照数据摘要

- 交易日期：`2026-06-24`
- 生成时间：`2026-06-24T16:01:08.303573+08:00`
- 当日整体状态：`partial`
- DuckDB 状态：`written`
- 交易日检查状态：`success`
- 是否交易日：`True`
- 交易日检查来源：`akshare.tool_trade_date_hist_sina`
- 交易日检查说明：`trade date is listed in AKShare trading calendar`

## 主表状态

- 主表接口：`stock_zh_a_spot`
- 主表状态：`success`
- 主表原始行数：`5528`
- 标准化主表行数：`5528`

## 增强接口状态

| 来源 | 类别 | 状态 | 原始行数 | 失败或说明 |
| --- | --- | --- | ---: | --- |
| `stock_zt_pool_em` | `limit_pool` | `success` | 98 |  |
| `stock_zt_pool_previous_em` | `limit_pool` | `success` | 96 |  |
| `stock_zt_pool_strong_em` | `limit_pool` | `success` | 259 |  |
| `stock_zt_pool_sub_new_em` | `limit_pool` | `success` | 134 |  |
| `stock_zt_pool_zbgc_em` | `limit_pool` | `success` | 23 |  |
| `stock_zt_pool_dtgc_em` | `limit_pool` | `success` | 12 |  |
| `stock_lhb_detail_daily_sina` | `lhb` | `failed` | 0 | KeyError: '股票代码' |
| `stock_lhb_detail_em` | `lhb` | `failed` | 0 | TypeError: 'NoneType' object is not subscriptable |
| `stock_lhb_jgmmtj_em` | `lhb` | `failed` | 0 | TypeError: 'NoneType' object is not subscriptable |
| `stock_sse_deal_daily` | `market_summary` | `failed` | 0 | ValueError: Length mismatch: Expected axis has 1 elements, new values have 6 elements |
| `stock_szse_summary` | `market_summary` | `failed` | 0 | AttributeError: 'float' object has no attribute 'replace' |
| `stock_board_industry_name_em` | `board_snapshot` | `ignored` | 0 | ProxyError: HTTPSConnectionPool(host='17.push2.eastmoney.com', port=443): Max retries exceeded with url: /api/qt/clist/get?pn=1&pz=100&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f3&fs=m%3A90+t%3A2+f%3A%2150&fields=f1%2Cf2%2Cf3%2Cf4%2Cf5%2Cf6%2Cf7%2Cf8%2Cf9%2Cf10%2Cf12%2Cf13%2Cf14%2Cf15%2Cf16%2Cf17%2Cf18%2Cf20%2Cf21%2Cf23%2Cf24%2Cf25%2Cf26%2Cf22%2Cf33%2Cf11%2Cf62%2Cf128%2Cf136%2Cf115%2Cf152%2Cf124%2Cf107%2Cf104%2Cf105%2Cf140%2Cf141%2Cf207%2Cf208%2Cf209%2Cf222 (Caused by ProxyError('Unable to connect to proxy', RemoteDisconnected('Remote end closed connection without response'))) |
| `stock_board_concept_name_em` | `board_snapshot` | `ignored` | 0 | ProxyError: HTTPSConnectionPool(host='79.push2.eastmoney.com', port=443): Max retries exceeded with url: /api/qt/clist/get?pn=1&pz=100&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f12&fs=m%3A90+t%3A3+f%3A%2150&fields=f2%2Cf3%2Cf4%2Cf8%2Cf12%2Cf14%2Cf15%2Cf16%2Cf17%2Cf18%2Cf20%2Cf21%2Cf24%2Cf25%2Cf22%2Cf33%2Cf11%2Cf62%2Cf128%2Cf124%2Cf107%2Cf104%2Cf105%2Cf136 (Caused by ProxyError('Unable to connect to proxy', RemoteDisconnected('Remote end closed connection without response'))) |

## 标准化表行数

| 表 | 行数 |
| --- | ---: |
| `daily_stock_snapshot` | 5528 |
| `limit_pool_events` | 622 |
| `lhb_events` | 0 |
| `market_summary` | 0 |
| `board_snapshot` | 0 |

## 边界

- 本运行不生成预测。
- 本运行不生成交易建议。
- 快照型主表只表达获取时点，不承诺历史回放。
- 事件型增强数据不会补齐成全股票字段。
