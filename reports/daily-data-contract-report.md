# 每日数据契约接口探测报告

本报告由 AKShare 接口实测生成，用于决定哪些数据可以进入每日数据契约。

## 执行摘要

- 探测日期：`2026-06-18`
- 报告生成时间：`2026-06-18T18:31:40.129747+08:00`
- AKShare 版本：`1.18.64`
- 候选接口数量：`26`
- 今日可调用且非空接口数量：`15`
- 历史每日契约纳入接口数量：`1`
- 推荐历史契约起始日：`2008-01-02`
- 契约验证状态：`passed`

## 今日最大可获取数据

| 接口 | 函数 | 行数 | 数据频率初判 | 今日状态 |
| --- | --- | ---: | --- | --- |
| `stock_zh_a_spot_em` | `stock_zh_a_spot_em` | 0 | `latest_snapshot` | 排除：call_failed |
| `stock_zh_a_spot_sina` | `stock_zh_a_spot` | 5527 | `latest_snapshot` | 可用 |
| `stock_zh_a_hist_000001_daily` | `stock_zh_a_hist` | 0 | `daily_range` | 排除：call_failed |
| `stock_zh_index_spot_em_important` | `stock_zh_index_spot_em` | 0 | `latest_snapshot` | 排除：call_failed |
| `stock_zh_index_daily_em_sh000001` | `stock_zh_index_daily_em` | 0 | `daily_range` | 排除：call_failed |
| `stock_zt_pool_em` | `stock_zt_pool_em` | 91 | `daily_range` | 可用 |
| `stock_zt_pool_previous_em` | `stock_zt_pool_previous_em` | 86 | `daily_range` | 可用 |
| `stock_zt_pool_strong_em` | `stock_zt_pool_strong_em` | 347 | `daily_range` | 可用 |
| `stock_zt_pool_sub_new_em` | `stock_zt_pool_sub_new_em` | 135 | `daily_range` | 可用 |
| `stock_zt_pool_zbgc_em` | `stock_zt_pool_zbgc_em` | 42 | `daily_range` | 可用 |
| `stock_zt_pool_dtgc_em` | `stock_zt_pool_dtgc_em` | 12 | `daily_range` | 可用 |
| `stock_lhb_detail_em` | `stock_lhb_detail_em` | 102 | `event_window` | 可用 |
| `stock_lhb_jgmmtj_em` | `stock_lhb_jgmmtj_em` | 55 | `event_window` | 可用 |
| `stock_lhb_stock_statistic_em_month` | `stock_lhb_stock_statistic_em` | 903 | `latest_snapshot` | 可用 |
| `stock_individual_fund_flow_rank_today` | `stock_individual_fund_flow_rank` | 0 | `latest_snapshot` | 排除：call_failed |
| `stock_sector_fund_flow_rank_industry_today` | `stock_sector_fund_flow_rank` | 0 | `latest_snapshot` | 排除：call_failed |
| `stock_sector_fund_flow_rank_concept_today` | `stock_sector_fund_flow_rank` | 0 | `latest_snapshot` | 排除：call_failed |
| `stock_individual_fund_flow_600094` | `stock_individual_fund_flow` | 0 | `embedded_history` | 排除：call_failed |
| `stock_concept_fund_flow_hist_data_element` | `stock_concept_fund_flow_hist` | 0 | `embedded_history` | 排除：call_failed |
| `stock_board_industry_name_em` | `stock_board_industry_name_em` | 0 | `latest_snapshot` | 排除：call_failed |
| `stock_board_concept_name_em` | `stock_board_concept_name_em` | 0 | `latest_snapshot` | 排除：call_failed |
| `stock_sse_summary` | `stock_sse_summary` | 8 | `latest_snapshot` | 可用 |
| `stock_szse_summary` | `stock_szse_summary` | 14 | `daily_range` | 可用 |
| `stock_info_a_code_name` | `stock_info_a_code_name` | 5528 | `latest_snapshot` | 可用 |
| `stock_zh_a_new` | `stock_zh_a_new` | 135 | `latest_snapshot` | 可用 |
| `stock_xgsr_ths` | `stock_xgsr_ths` | 3816 | `latest_snapshot` | 可用 |

## 历史最早可获取日

| 接口 | 历史类型 | 历史状态 | 最早非空交易日 | 字段一致性 | 是否纳入历史每日契约 |
| --- | --- | --- | --- | --- | --- |
| `stock_zh_a_spot_em` | `latest_snapshot` | `not_probed` | `无` | `not_checked` | 否 |
| `stock_zh_a_spot_sina` | `latest_snapshot` | `not_probed` | `无` | `not_checked` | 否 |
| `stock_zh_a_hist_000001_daily` | `daily_range` | `not_probed` | `无` | `not_checked` | 否 |
| `stock_zh_index_spot_em_important` | `latest_snapshot` | `not_probed` | `无` | `not_checked` | 否 |
| `stock_zh_index_daily_em_sh000001` | `daily_range` | `not_probed` | `无` | `not_checked` | 否 |
| `stock_zt_pool_em` | `daily_range` | `not_probed` | `无` | `not_checked` | 否 |
| `stock_zt_pool_previous_em` | `daily_range` | `not_probed` | `无` | `not_checked` | 否 |
| `stock_zt_pool_strong_em` | `daily_range` | `not_probed` | `无` | `not_checked` | 否 |
| `stock_zt_pool_sub_new_em` | `daily_range` | `not_probed` | `无` | `not_checked` | 否 |
| `stock_zt_pool_zbgc_em` | `daily_range` | `not_probed` | `无` | `not_checked` | 否 |
| `stock_zt_pool_dtgc_em` | `daily_range` | `not_probed` | `无` | `not_checked` | 否 |
| `stock_lhb_detail_em` | `event_window` | `not_probed` | `无` | `not_checked` | 否 |
| `stock_lhb_jgmmtj_em` | `event_window` | `not_probed` | `无` | `not_checked` | 否 |
| `stock_lhb_stock_statistic_em_month` | `latest_snapshot` | `not_probed` | `无` | `not_checked` | 否 |
| `stock_individual_fund_flow_rank_today` | `latest_snapshot` | `not_probed` | `无` | `not_checked` | 否 |
| `stock_sector_fund_flow_rank_industry_today` | `latest_snapshot` | `not_probed` | `无` | `not_checked` | 否 |
| `stock_sector_fund_flow_rank_concept_today` | `latest_snapshot` | `not_probed` | `无` | `not_checked` | 否 |
| `stock_individual_fund_flow_600094` | `embedded_history` | `not_probed` | `无` | `not_checked` | 否 |
| `stock_concept_fund_flow_hist_data_element` | `embedded_history` | `not_probed` | `无` | `not_checked` | 否 |
| `stock_board_industry_name_em` | `latest_snapshot` | `not_probed` | `无` | `not_checked` | 否 |
| `stock_board_concept_name_em` | `latest_snapshot` | `not_probed` | `无` | `not_checked` | 否 |
| `stock_sse_summary` | `latest_snapshot` | `not_probed` | `无` | `not_checked` | 否 |
| `stock_szse_summary` | `daily_range` | `success` | `2008-01-02` | `passed` | 是 |
| `stock_info_a_code_name` | `latest_snapshot` | `not_probed` | `无` | `not_checked` | 否 |
| `stock_zh_a_new` | `latest_snapshot` | `not_probed` | `无` | `not_checked` | 否 |
| `stock_xgsr_ths` | `latest_snapshot` | `not_probed` | `无` | `not_checked` | 否 |

## 推荐每日数据契约

- 契约版本：`daily_data_contract.v1`
- 起始交易日：`2008-01-02`
- 纳入接口：
  - `stock_szse_summary`：`stock_szse_summary`，最早 `2008-01-02`，字段数 `5`

## 排除清单

| 接口 | 函数 | 今日状态 | 今日行数 | 历史状态 | 排除原因 |
| --- | --- | --- | ---: | --- | --- |
| `stock_zh_a_spot_em` | `stock_zh_a_spot_em` | `failed` | 0 | `not_probed` | No date parameter; cannot prove arbitrary historical daily access. |
| `stock_zh_a_spot_sina` | `stock_zh_a_spot` | `success` | 5527 | `not_probed` | No date parameter; cannot prove arbitrary historical daily access. |
| `stock_zh_a_hist_000001_daily` | `stock_zh_a_hist` | `failed` | 0 | `not_probed` | not_today_contract_candidate |
| `stock_zh_index_spot_em_important` | `stock_zh_index_spot_em` | `failed` | 0 | `not_probed` | No date parameter; cannot prove arbitrary historical daily access. |
| `stock_zh_index_daily_em_sh000001` | `stock_zh_index_daily_em` | `failed` | 0 | `not_probed` | not_today_contract_candidate |
| `stock_zt_pool_em` | `stock_zt_pool_em` | `success` | 91 | `not_probed` | Pool data can be naturally empty and is not a required daily contract field. |
| `stock_zt_pool_previous_em` | `stock_zt_pool_previous_em` | `success` | 86 | `not_probed` | Pool data can be naturally empty and is not a required daily contract field. |
| `stock_zt_pool_strong_em` | `stock_zt_pool_strong_em` | `success` | 347 | `not_probed` | Pool data can be naturally empty and is not a required daily contract field. |
| `stock_zt_pool_sub_new_em` | `stock_zt_pool_sub_new_em` | `success` | 135 | `not_probed` | Pool data can be naturally empty and is not a required daily contract field. |
| `stock_zt_pool_zbgc_em` | `stock_zt_pool_zbgc_em` | `success` | 42 | `not_probed` | Pool data can be naturally empty and is not a required daily contract field. |
| `stock_zt_pool_dtgc_em` | `stock_zt_pool_dtgc_em` | `success` | 12 | `not_probed` | Pool data can be naturally empty and is not a required daily contract field. |
| `stock_lhb_detail_em` | `stock_lhb_detail_em` | `success` | 102 | `not_probed` | Event data is not expected to be non-empty every trading day. |
| `stock_lhb_jgmmtj_em` | `stock_lhb_jgmmtj_em` | `success` | 55 | `not_probed` | Event data is not expected to be non-empty every trading day. |
| `stock_lhb_stock_statistic_em_month` | `stock_lhb_stock_statistic_em` | `success` | 903 | `not_probed` | Relative-window endpoint; not an arbitrary historical daily source. |
| `stock_individual_fund_flow_rank_today` | `stock_individual_fund_flow_rank` | `failed` | 0 | `not_probed` | Indicator is a current short-window ranking, not arbitrary historical daily data. |
| `stock_sector_fund_flow_rank_industry_today` | `stock_sector_fund_flow_rank` | `failed` | 0 | `not_probed` | Indicator is a current short-window ranking, not arbitrary historical daily data. |
| `stock_sector_fund_flow_rank_concept_today` | `stock_sector_fund_flow_rank` | `failed` | 0 | `not_probed` | Indicator is a current short-window ranking, not arbitrary historical daily data. |
| `stock_individual_fund_flow_600094` | `stock_individual_fund_flow` | `failed` | 0 | `not_probed` | No date-range parameters; earliest date can be observed but not requested directly. |
| `stock_concept_fund_flow_hist_data_element` | `stock_concept_fund_flow_hist` | `failed` | 0 | `not_probed` | No date-range parameters; earliest date can be observed but not requested directly. |
| `stock_board_industry_name_em` | `stock_board_industry_name_em` | `failed` | 0 | `not_probed` | No date parameter; cannot prove arbitrary historical daily access. |
| `stock_board_concept_name_em` | `stock_board_concept_name_em` | `failed` | 0 | `not_probed` | No date parameter; cannot prove arbitrary historical daily access. |
| `stock_sse_summary` | `stock_sse_summary` | `success` | 8 | `not_probed` | No date parameter; cannot prove arbitrary historical daily access. |
| `stock_info_a_code_name` | `stock_info_a_code_name` | `success` | 5528 | `not_probed` | Reference snapshot; not historical daily market data. |
| `stock_zh_a_new` | `stock_zh_a_new` | `success` | 135 | `not_probed` | Reference snapshot; not historical daily market data. |
| `stock_xgsr_ths` | `stock_xgsr_ths` | `success` | 3816 | `not_probed` | Calendar snapshot; not arbitrary historical daily data. |

## 验证证据

- `candidate_interfaces.json`：候选接口、签名、参数和频率初判。
- `today-capability-report.json`：今日接口调用状态、行数、字段和失败原因。
- `today-contract-candidates.json`：今日可用且非空的候选接口。
- `history-floor-report.json`：历史回溯结果、最早非空日期和字段一致性。
- `daily-data-contract.v1.json`：最终每日数据契约 JSON。
- `contract-validation-report.json`：契约纳入接口的复验结果。

## 重要边界

- 本报告只证明当前环境、当前 AKShare 版本和当前网络条件下的接口可用性。
- 今日可用不等于可历史回放；快照型接口不会进入历史每日契约。
- 事件型接口即使今日非空，也不代表每天必有数据。
- 接口异常、代理失败和真实空数据分别记录，不互相替代。
