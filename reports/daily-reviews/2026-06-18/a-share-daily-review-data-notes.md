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

- status: partial
- input_path: reports\daily-reviews\2026-06-18\external-background-fusion.json
- briefing_date: 2026-06-18
- source_skill: daily-financial-briefing

### 引用来源

- 华尔街见闻: https://wallstreetcn.com/livenews/3121487
- 每日经济新闻: http://www.nbd.com.cn/articles/2026-06-18/4430694.html
- 中国金融信息网: https://www.cnfin.com/zs-lb/detail/20260618/4428565_1.html
- 东方财富: https://finance.eastmoney.com/a/202606183776526341.html
- 天天基金网: https://fund.eastmoney.com/a/202606183776105172.html
- 东方财富: https://fund.eastmoney.com/a/202606183776106489.html
- 东北证券: https://www.nesc.cn/main/a/20260618/86321.shtml
- 财联社: https://www.cls.cn/detail/2403425
- 东方财富: https://finance.eastmoney.com/a/202606183776482959.html
- 证券时报: https://stcn.com/article/detail/3970021.html
- 东方财富: https://finance.eastmoney.com/a/202606183776193115.html
- 金融界: https://finance.jrj.com.cn/2026/06/18160157513529.shtml
- 新浪财经: https://finance.sina.cn/2026-06-18/detail-inicvmmr3316803.d.html
- 华夏时报: https://www.chinatimes.net.cn/article/153600.html
- 21世纪经济报道: http://www.21jingji.com/article/20260618/herald/a1d5686e49cdc2e76ef860561c3b78d5.html
- EdgeN技术分析: https://www.edgen.tech/zh/news/post/a-share-tech-crowding-at-92-percentile-as-style-rotation-nears-equilibrium

### 降级或拒绝原因

- 未记录 external_background 降级或拒绝原因。

### 信息缺口

- 本地板块快照维度缺失，外部板块数据（申万一级行业涨跌、资金流向）来自财经媒体转述，非交易所原始数据
- WebFetch工具对中国财经域名不可用，所有引用基于WebSearch返回的文章摘要，未经全文逐字核验
- 未找到高盛、摩根士丹利、摩根大通等国际顶级投行针对6月18日A股当日行情的直接公开报告原文，引用来自证券时报等媒体转述
- 光学光电、化学制品两个本地涨停集中行业在外部来源中缺乏独立板块专题覆盖
- 美联储鹰派转向对A股的具体传导强度缺乏可量化的当日公开数据支撑
- 端午节前最后一个交易日的节前效应在外部来源中仅有定性判断，缺乏可量化的节前效应指标

## 诊断问题

- stock_board_industry_name_em 状态为 failed：ConnectionError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
- stock_board_concept_name_em 状态为 failed：ConnectionError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))

## 修复建议

- 如需重跑数据采集，使用：`python -m a_share_info_hub daily-update --trade-date 2026-06-18`
- 修复或重跑后重新生成 `review-context.json`，再让 LLM 基于新的 context 生成 sections JSON。