# 2026-06-24 A 股每日复盘技术参考

本文档记录主报告隐藏的技术状态、接口失败和数据来源，供 review、排障和后续重跑使用。

## 运行状态

- trade_date: 2026-06-24
- data_status: partial
- analysis_mode: research_only
- not_investment_advice: true
- context_artifact: /mnt/tool/2-projects/a-share-info-hub/reports/daily-reviews/2026-06-24/review-context.json
- blocked_sections: ["lhb_events", "market_summary"]
- render_mode: llm

## 数据来源

- /mnt/tool/2-projects/a-share-info-hub/reports/daily-runs/2026-06-24/interface-status.json
- /mnt/tool/2-projects/a-share-info-hub/reports/daily-runs/2026-06-24/daily-data-summary.md
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
| stock_zh_a_spot | main | success | 5528 |  |
| stock_zt_pool_dtgc_em | limit_pool | success | 12 |  |
| stock_zt_pool_em | limit_pool | success | 98 |  |
| stock_zt_pool_previous_em | limit_pool | success | 96 |  |
| stock_zt_pool_strong_em | limit_pool | success | 259 |  |
| stock_zt_pool_sub_new_em | limit_pool | success | 134 |  |
| stock_zt_pool_zbgc_em | limit_pool | success | 23 |  |
| table:board_snapshot | normalized_table | readable | 0 |  |
| table:daily_stock_snapshot | normalized_table | readable | 5528 |  |
| table:lhb_events | normalized_table | readable | 0 |  |
| table:limit_pool_events | normalized_table | readable | 622 |  |
| table:market_summary | normalized_table | readable | 0 |  |
| trading_day_check | run_status | success |  | trade date is listed in AKShare trading calendar |

## 原始分类统计

### 涨跌停情绪池分类

- strong_limit_up: 259
- sub_new_limit_up: 134
- limit_up: 98
- previous_limit_up: 96
- broken_board: 23
- limit_down: 12

### 龙虎榜事件来源

- 无

## external_background

- status: partial
- input_path: /mnt/tool/2-projects/a-share-info-hub/reports/daily-reviews/2026-06-24/external-background-fusion.json
- briefing_date: 2026-06-24
- source_skill: daily-financial-briefing

### 引用来源

- Federal Reserve: https://www.federalreserve.gov/newsevents/pressreleases/monetary20260617a.htm
- Bureau of Labor Statistics: https://www.bls.gov/news.release/cpi.nr0.htm
- CME Group: https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html
- Goldman Sachs: https://www.goldmansachs.com/insights/articles/chinas-economy-is-forecast-to-grow-faster-than-expected-in-2026
- Goldman Sachs: https://www.goldmansachs.com/insights/outlooks/2026-outlooks
- Citigroup: https://www.citigroup.com/global/insights/china-economics-2026-outlook-mind-the-gap
- UBS: https://www.ubs.com/global/en/investment-bank/insights-and-data/articles/china-outlook.html

### 降级或拒绝原因

- 5 of 6 parallel agents returned blocked results due to WebSearch/WebFetch tool unavailability in current session — only sentiment_and_events produced usable external findings
- All Investment Bank View citations are from year-end 2025 outlooks, not 2026-06-24 same-day views — external background has a 6-month staleness risk
- CME FedWatch citation is from 2026-06-19 snapshot, 5 days before trade date — probability distribution may have shifted
- No real-time US Treasury yield, equity index, or VIX data available — cross-market correlation context missing
- 3 of 5 information gaps from the sentiment_and_events agent note WebSearch/WebFetch limitations rather than genuine source unavailability — external background coverage is severely constrained by tool permissions
- 第 1 条外部融合结论缺少正文、合法类型、来源名称或 URL。
- 第 2 条外部融合结论缺少正文、合法类型、来源名称或 URL。
- 第 3 条外部融合结论缺少正文、合法类型、来源名称或 URL。
- 第 4 条外部融合结论缺少正文、合法类型、来源名称或 URL。
- 第 5 条外部融合结论缺少正文、合法类型、来源名称或 URL。
- 第 6 条外部融合结论缺少正文、合法类型、来源名称或 URL。

### 信息缺口

- 无法获取2026-06-24当日的美国国债收益率数据（2Y/5Y/10Y/30Y）及10Y-2Y利差——WebSearch/WebFetch工具不可用
- 无法获取2026-06-24当日的美国主要股指表现（S&P 500/Dow/Nasdaq）和VIX指数——WebSearch/WebFetch工具不可用
- 无法获取2026-06-24当日任何投行发布的公开研报、市场评论或策略更新——Goldman Sachs/Citigroup/UBS引用均为年度展望（2025年底发布），非当日观点
- 无法获取2026-06-24当日CME FedWatch最新隐含概率数据——引用依赖2026-06-19快照，可能存在概率分布变化
- 无法获取高盛/摩根士丹利/摩根大通/花旗以外的投行（如摩根大通、巴克莱、汇丰等）公开观点——WebSearch工具不可用
- 5个外部主题（market_overview_assessment / market_overview_structure / market_breadth / board_and_structure / risk_observations）因网络工具不可用而完全blocked，缺乏对应维度的外部宏观与投行背景信息
- 本地龙虎榜数据完全缺失（三个接口均失败），外部投行观点无法弥补A股机构/游资资金流向的本地信息缺口
- 本地板块快照数据缺失（行业/概念板块接口ProxyError），外部投行的行业判断无法替代A股板块层级的实际涨跌和资金流向数据

## 诊断问题

- stock_lhb_detail_daily_sina 状态为 failed：KeyError: '股票代码'
- stock_lhb_detail_em 状态为 failed：TypeError: 'NoneType' object is not subscriptable
- stock_lhb_jgmmtj_em 状态为 failed：TypeError: 'NoneType' object is not subscriptable
- stock_sse_deal_daily 状态为 failed：ValueError: Length mismatch: Expected axis has 1 elements, new values have 6 elements
- stock_szse_summary 状态为 failed：AttributeError: 'float' object has no attribute 'replace'

## 修复建议

- 如需重跑数据采集，使用：`python -m a_share_info_hub daily-update --trade-date 2026-06-24`
- 修复或重跑后重新生成 `review-context.json`，再让 LLM 基于新的 context 生成 sections JSON。