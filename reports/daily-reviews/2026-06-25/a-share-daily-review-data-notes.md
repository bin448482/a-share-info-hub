# 2026-06-25 A 股每日复盘技术参考

本文档记录主报告隐藏的技术状态、接口失败和数据来源，供 review、排障和后续重跑使用。

## 运行状态

- trade_date: 2026-06-25
- data_status: partial
- analysis_mode: research_only
- not_investment_advice: true
- context_artifact: /mnt/tool/2-projects/a-share-info-hub/reports/daily-reviews/2026-06-25/review-context.json
- blocked_sections: ["lhb_events", "market_summary"]
- render_mode: llm

## 数据来源

- /mnt/tool/2-projects/a-share-info-hub/reports/daily-runs/2026-06-25/interface-status.json
- /mnt/tool/2-projects/a-share-info-hub/reports/daily-runs/2026-06-25/daily-data-summary.md
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
| stock_lhb_detail_em | lhb | success | 45 |  |
| stock_lhb_jgmmtj_em | lhb | failed | 0 | TypeError: 'NoneType' object is not subscriptable |
| stock_sse_deal_daily | market_summary | failed | 0 | ValueError: Length mismatch: Expected axis has 1 elements, new values have 6 elements |
| stock_szse_summary | market_summary | success | 1 |  |
| stock_zh_a_spot | main | success | 5528 |  |
| stock_zt_pool_dtgc_em | limit_pool | success | 17 |  |
| stock_zt_pool_em | limit_pool | success | 86 |  |
| stock_zt_pool_previous_em | limit_pool | success | 99 |  |
| stock_zt_pool_strong_em | limit_pool | success | 330 |  |
| stock_zt_pool_sub_new_em | limit_pool | success | 134 |  |
| stock_zt_pool_zbgc_em | limit_pool | success | 31 |  |
| table:board_snapshot | normalized_table | readable | 0 |  |
| table:daily_stock_snapshot | normalized_table | readable | 5528 |  |
| table:lhb_events | normalized_table | readable | 45 |  |
| table:limit_pool_events | normalized_table | readable | 697 |  |
| table:market_summary | normalized_table | readable | 1 |  |
| trading_day_check | run_status | success |  | trade date is listed in AKShare trading calendar |

## 原始分类统计

### 涨跌停情绪池分类

- strong_limit_up: 330
- sub_new_limit_up: 134
- previous_limit_up: 99
- limit_up: 86
- broken_board: 31
- limit_down: 17

### 龙虎榜事件来源

- 无

## external_background

- status: partial
- input_path: /mnt/tool/2-projects/a-share-info-hub/reports/daily-reviews/2026-06-25/external-background-fusion.json
- briefing_date: 2026-06-25
- source_skill: daily-financial-briefing

### 引用来源

- Federal Reserve: https://www.federalreserve.gov/newsevents/pressreleases/monetary20260617a.htm
- Bureau of Labor Statistics: https://www.bls.gov/news.release/cpi.nr0.htm
- CME Group: https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html
- Goldman Sachs: https://www.goldmansachs.com/insights/outlooks/2026-outlooks
- Goldman Sachs: https://www.goldmansachs.com/insights/articles/chinas-economy-is-forecast-to-grow-faster-than-expected-in-2026
- Citi: https://www.citigroup.com/global/insights/china-economics-2026-outlook-mind-the-gap
- UBS: https://www.ubs.com/global/en/investment-bank/insights-and-data/articles/china-outlook.html
- Federal Reserve: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
- Bureau of Labor Statistics: https://www.bls.gov/schedule/news_release/cpi.htm

### 降级或拒绝原因

- 并行子 Agent 产出不完整：6 个 topic 中仅 market_overview_structure（1/6）返回了外部 findings；其余 5 个 topic（market_overview_assessment、market_breadth、sentiment_and_events、board_and_structure、risk_observations）均因 WebSearch/WebFetch 工具权限未授予而 blocked
- 所有 topic_findings 仅来自 market_overview_structure 一个 topic，其他 5 个 topic 的外部信息缺口已记录在 information_gaps 中
- 市场宽度、情绪与事件、板块与结构、风险观察等本地维度缺乏对应的外部 US Macro 或 Investment Bank Views 背景参照，报告外部背景覆盖不完整
- 已引用的投行观点（Goldman Sachs、Citi、UBS）为中长期展望而非 2026-06-25 当日研判，时效性不足，在报告中应标注其发布日期以区分静态观点与当日增量信息

### 信息缺口

- 美债实时收益率：无法获取 2026-06-25 当日美国国债收益率（2Y/5Y/10Y/30Y）及 10Y-2Y 利差的具体数值
- CME FedWatch 快照：无法获取 2026-06-25 当日的 CME FedWatch 隐含概率快照，此前验证仅确认该页面在 2026-06-19 可访问
- 当日投行观点缺失：未找到 2026-06-25 当日发布的公开投行观点或中国市场评论；已引用的 Goldman Sachs、Citi、UBS 观点均为中期展望（2025-11 至 2025-12 发布），不代表 2026-06-25 当日观点
- 地缘政治事件盲区：无法搜索和验证 2026-06-19 至 2026-06-25 期间是否有影响全球风险偏好的突发地缘政治事件或贸易政策变化
- 全球风险偏好代理指标缺失：无法获取 VIX 波动率指数、美元流动性指标（TED spread、FRA-OIS）、信用利差变化、EPFR 资金流向等全球风险偏好参考数据
- 北向/南向资金流向：A 股本地数据未覆盖互联互通资金流向，外部来源同样无法在无网络环境下获取
- 2026-06-25 处于 FOMC 声明（6月17日）与下一次 CPI（7月14日）之间的宏观信息真空期，外部增量宏观数据偏少，外部背景贡献集中于静态利率和通胀环境描述

## 诊断问题

- stock_lhb_detail_daily_sina 状态为 failed：KeyError: '股票代码'
- stock_lhb_jgmmtj_em 状态为 failed：TypeError: 'NoneType' object is not subscriptable
- stock_sse_deal_daily 状态为 failed：ValueError: Length mismatch: Expected axis has 1 elements, new values have 6 elements

## 修复建议

- 如需重跑数据采集，使用：`python -m a_share_info_hub daily-update --trade-date 2026-06-25`
- 修复或重跑后重新生成 `review-context.json`，再让 LLM 基于新的 context 生成 sections JSON。