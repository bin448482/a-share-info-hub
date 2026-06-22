# 每日 A 股报告任务摘要

- trade_date: `2026-06-22`
- overall_status: `partial`
- health_level: `warning`
- send_status: `skipped`
- not_investment_advice: `true`

## 阶段状态

- `daily_update`: `passed` exit=`0` elapsed=`45.461` log=`reports/daily-jobs/2026-06-22/logs/daily_update.log`
- `daily_review_context`: `passed` exit=`0` elapsed=`1.666` log=`reports/daily-jobs/2026-06-22/logs/daily_review_context.log`
- `external_background_fusion`: `passed` exit=`0` elapsed=`611.779` log=`reports/daily-jobs/2026-06-22/logs/external_background_fusion.log`
- `daily_review_context_with_external`: `passed` exit=`0` elapsed=`1.628` log=`reports/daily-jobs/2026-06-22/logs/daily_review_context_with_external.log`
- `claude_code_sections`: `passed` exit=`0` elapsed=`201.639` log=`reports/daily-jobs/2026-06-22/logs/claude_code_sections.log`
- `daily_review_html`: `passed` exit=`0` elapsed=`1.658` log=`reports/daily-jobs/2026-06-22/logs/daily_review_html.log`

## Artifacts

- `daily_data_summary`: `reports/daily-runs/2026-06-22/daily-data-summary.md`
- `data_notes`: `reports/daily-reviews/2026-06-22/a-share-daily-review-data-notes.md`
- `external_background`: `reports/daily-reviews/2026-06-22/external-background-fusion.json`
- `heartbeat`: `reports/daily-jobs/2026-06-22/heartbeat.json`
- `html_report`: `reports/daily-reviews/2026-06-22/a-share-daily-review.html`
- `interface_status`: `reports/daily-runs/2026-06-22/interface-status.json`
- `job_status`: `reports/daily-jobs/2026-06-22/job-status.json`
- `job_summary`: `reports/daily-jobs/2026-06-22/job-summary.md`
- `llm_sections`: `reports/daily-reviews/2026-06-22/llm-review-sections.json`
- `review_context`: `reports/daily-reviews/2026-06-22/review-context.json`

## Alerts

- `warning` `external_background_fusion`: external_background_fusion exceeded soft warning threshold.
- `warning` `daily_update`: daily-update returned partial data.
- `warning` `data_quality`: one or more enhanced sources failed.
- `warning` `daily_review_context`: review context contains blocked sections.

## 边界

- 本任务只编排公开 CLI、Claude Code external background/sections 生成、Python validator 和飞书通知。
- 本任务不直接调用采集实现，不生成交易建议、仓位建议、目标价或止盈止损指令。