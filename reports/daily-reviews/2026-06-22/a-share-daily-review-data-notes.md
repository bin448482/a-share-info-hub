# 2026-06-22 A 股每日复盘技术参考

本文档记录主报告隐藏的技术状态、接口失败和数据来源，供 review、排障和后续重跑使用。

## 运行状态

- trade_date: 2026-06-22
- data_status: partial
- analysis_mode: research_only
- not_investment_advice: true
- context_artifact: /mnt/tool/2-projects/a-share-info-hub/reports/daily-reviews/2026-06-22/review-context.json
- blocked_sections: ["board_snapshot", "lhb_events"]
- render_mode: llm

## 数据来源

- /mnt/tool/2-projects/a-share-info-hub/reports/daily-runs/2026-06-22/interface-status.json
- /mnt/tool/2-projects/a-share-info-hub/reports/daily-runs/2026-06-22/daily-data-summary.md
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
| stock_board_concept_name_em | board_snapshot | failed | 0 | ProxyError: HTTPSConnectionPool(host='79.push2.eastmoney.com', port=443): Max retries exceeded with url: /api/qt/clist/get?pn=1&pz=100&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f12&fs=m%3A90+t%3A3+f%3A%2150&fields=f2%2Cf3%2Cf4%2Cf8%2Cf12%2Cf14%2Cf15%2Cf16%2Cf17%2Cf18%2Cf20%2Cf21%2Cf24%2Cf25%2Cf22%2Cf33%2Cf11%2Cf62%2Cf128%2Cf124%2Cf107%2Cf104%2Cf105%2Cf136 (Caused by ProxyError('Unable to connect to proxy', RemoteDisconnected('Remote end closed connection without response'))) |
| stock_board_industry_name_em | board_snapshot | failed | 0 | ProxyError: HTTPSConnectionPool(host='17.push2.eastmoney.com', port=443): Max retries exceeded with url: /api/qt/clist/get?pn=1&pz=100&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f3&fs=m%3A90+t%3A2+f%3A%2150&fields=f1%2Cf2%2Cf3%2Cf4%2Cf5%2Cf6%2Cf7%2Cf8%2Cf9%2Cf10%2Cf12%2Cf13%2Cf14%2Cf15%2Cf16%2Cf17%2Cf18%2Cf20%2Cf21%2Cf23%2Cf24%2Cf25%2Cf26%2Cf22%2Cf33%2Cf11%2Cf62%2Cf128%2Cf136%2Cf115%2Cf152%2Cf124%2Cf107%2Cf104%2Cf105%2Cf140%2Cf141%2Cf207%2Cf208%2Cf209%2Cf222 (Caused by ProxyError('Unable to connect to proxy', RemoteDisconnected('Remote end closed connection without response'))) |
| stock_lhb_detail_daily_sina | lhb | failed | 0 | KeyError: '股票代码' |
| stock_lhb_detail_em | lhb | success | 105 |  |
| stock_lhb_jgmmtj_em | lhb | success | 63 |  |
| stock_sse_deal_daily | market_summary | success | 8 |  |
| stock_szse_summary | market_summary | success | 14 |  |
| stock_zh_a_spot | main | success | 5527 |  |
| stock_zt_pool_dtgc_em | limit_pool | success | 4 |  |
| stock_zt_pool_em | limit_pool | success | 134 |  |
| stock_zt_pool_previous_em | limit_pool | success | 91 |  |
| stock_zt_pool_strong_em | limit_pool | success | 383 |  |
| stock_zt_pool_sub_new_em | limit_pool | success | 133 |  |
| stock_zt_pool_zbgc_em | limit_pool | success | 26 |  |
| table:board_snapshot | normalized_table | readable | 0 |  |
| table:daily_stock_snapshot | normalized_table | readable | 5527 |  |
| table:lhb_events | normalized_table | readable | 168 |  |
| table:limit_pool_events | normalized_table | readable | 771 |  |
| table:market_summary | normalized_table | readable | 22 |  |
| trading_day_check | run_status | success |  | trade date is listed in AKShare trading calendar |

## 原始分类统计

### 涨跌停情绪池分类

- strong_limit_up: 383
- limit_up: 134
- sub_new_limit_up: 133
- previous_limit_up: 91
- broken_board: 26
- limit_down: 4

### 龙虎榜事件来源

- 无

## external_background

- status: partial
- input_path: /mnt/tool/2-projects/a-share-info-hub/reports/daily-reviews/2026-06-22/external-background-fusion.json
- briefing_date: 2026-06-22
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

- parallel_agent_market_overview_structure: blocked=true，子Agent无法获取US Macro或Investment Bank Views的可引用公开来源
- parallel_agent_sentiment_and_events: blocked=true，子Agent无法获取US Macro或Investment Bank Views的可引用公开来源
- parallel_agent_risk_observations: blocked=true，子Agent无法获取US Macro或Investment Bank Views的可引用公开来源
- external_background_coverage: 3/6 topics blocked，fusion JSON中市场结构、情绪与事件、风险观察三个主题的外部背景覆盖不足，仅基于本地证据和从其他topic的交叉引用提供有限背景
- citation_freshness: 7条去重引用中，仅2条为2026-06-10之后发布（FOMC 2026-06-17，CPI 2026-06-10）；5条投行引用均为2025年末中期展望
- citation_verification: 所有URL在2026-06-22未经过实时可访问性验证，依赖forward test缓存记录和模型训练数据回忆
- board_snapshot_data_blocked: 本地 board_snapshot 表0行（东方财富推送服务器ProxyError），即使外部来源可用，board_and_structure主题的本地数据基础仍然缺失
- 第 7 条外部融合结论缺少正文、合法类型、来源名称或 URL。
- 第 14 条外部融合结论缺少正文、合法类型、来源名称或 URL。
- 第 21 条外部融合结论缺少正文、合法类型、来源名称或 URL。

### 信息缺口

- 无法获取2026-06-22当日美债收益率（2Y/5Y/10Y/30Y）及10Y-2Y利差数据——来源缺口：U.S. Treasury Daily Yield Curve页面在无网络权限下不可访问
- 引用的投行观点（高盛、花旗、瑞银）均为2025年末至2026年初发布的中期展望，非2026-06-22当日或近一周新发布的观点——信息时效性存在缺口，当日是否有投行发布针对A股或中国资产的更新观点无法确认
- 缺失Morgan Stanley和J.P. Morgan在2026-06-17至2026-06-22期间关于中国/亚洲市场或全球风险偏好的公开可引用观点——仅覆盖了高盛、花旗、瑞银三家投行的中期展望
- 所有外部来源URL基于2026-06-19 forward test的验证记录，未在2026-06-22通过实时网络请求逐条重新验证可访问性和内容一致性
- 未获取VIX指数或全球风险偏好量化指标，无法将A股大盘定性与全球权益市场风险偏好水平进行量化对照
- 未获取2026-06-22当周美国宏观数据发布日历，无法判断当日是否有US Macro关键数据发布对全球市场产生即时影响
- 无法从公开免费渠道获取NYSE/NASDAQ Advance-Decline涨跌比、52周新高新低比等结构化美国市场宽度数据——此类数据通常由交易所官方或付费终端（Bloomberg/FactSet）提供
- 无法获取全球半导体行业指数（SOX/费城半导体指数）或全球制造业PMI等海外行业景气度数据，无法将A股涨停池的行业分布与海外同行业表现进行跨境对比
- 无法获取2026-06-22当日US股票市场行业涨跌分布（S&P 500 sector performance）作为A股行业结构的对照基准
- 3个主题（market_overview_structure、sentiment_and_events、risk_observations）因子Agent未能获取外部来源而返回blocked——这些主题的外部背景覆盖存在缺口
- 板块快照本地数据持续阻塞（行业板块和概念板块均ProxyError），叠加外部行业观点缺失，board_and_structure主题虽有外部投行中期展望作为背景，但本地板块数据完全盲视

## 诊断问题

- stock_lhb_detail_daily_sina 状态为 failed：KeyError: '股票代码'
- stock_board_industry_name_em 状态为 failed：ProxyError: HTTPSConnectionPool(host='17.push2.eastmoney.com', port=443): Max retries exceeded with url: /api/qt/clist/get?pn=1&pz=100&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f3&fs=m%3A90+t%3A2+f%3A%2150&fields=f1%2Cf2%2Cf3%2Cf4%2Cf5%2Cf6%2Cf7%2Cf8%2Cf9%2Cf10%2Cf12%2Cf13%2Cf14%2Cf15%2Cf16%2Cf17%2Cf18%2Cf20%2Cf21%2Cf23%2Cf24%2Cf25%2Cf26%2Cf22%2Cf33%2Cf11%2Cf62%2Cf128%2Cf136%2Cf115%2Cf152%2Cf124%2Cf107%2Cf104%2Cf105%2Cf140%2Cf141%2Cf207%2Cf208%2Cf209%2Cf222 (Caused by ProxyError('Unable to connect to proxy', RemoteDisconnected('Remote end closed connection without response')))
- stock_board_concept_name_em 状态为 failed：ProxyError: HTTPSConnectionPool(host='79.push2.eastmoney.com', port=443): Max retries exceeded with url: /api/qt/clist/get?pn=1&pz=100&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f12&fs=m%3A90+t%3A3+f%3A%2150&fields=f2%2Cf3%2Cf4%2Cf8%2Cf12%2Cf14%2Cf15%2Cf16%2Cf17%2Cf18%2Cf20%2Cf21%2Cf24%2Cf25%2Cf22%2Cf33%2Cf11%2Cf62%2Cf128%2Cf124%2Cf107%2Cf104%2Cf105%2Cf136 (Caused by ProxyError('Unable to connect to proxy', RemoteDisconnected('Remote end closed connection without response')))

## 修复建议

- 如需重跑数据采集，使用：`python -m a_share_info_hub daily-update --trade-date 2026-06-22`
- 修复或重跑后重新生成 `review-context.json`，再让 LLM 基于新的 context 生成 sections JSON。