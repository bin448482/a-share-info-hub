# 每日 A 股报告任务摘要

- trade_date: `2026-06-21`
- overall_status: `skipped`
- health_level: `info`
- send_status: `skipped`
- not_investment_advice: `true`

## 阶段状态

- `daily_update`: `passed` exit=`0` elapsed=`1.546` log=`reports/daily-jobs/2026-06-21/logs/daily_update.log`

## Artifacts

- `daily_data_summary`: `reports/daily-runs/2026-06-21/daily-data-summary.md`
- `data_notes`: `reports/daily-reviews/2026-06-21/a-share-daily-review-data-notes.md`
- `heartbeat`: `reports/daily-jobs/2026-06-21/heartbeat.json`
- `html_report`: `reports/daily-reviews/2026-06-21/a-share-daily-review.html`
- `interface_status`: `reports/daily-runs/2026-06-21/interface-status.json`
- `job_status`: `reports/daily-jobs/2026-06-21/job-status.json`
- `job_summary`: `reports/daily-jobs/2026-06-21/job-summary.md`
- `llm_sections`: `reports/daily-reviews/2026-06-21/llm-review-sections.json`
- `review_context`: `reports/daily-reviews/2026-06-21/review-context.json`

## Alerts

- `info` `job`: no alerts

## 边界

- 本任务只编排公开 CLI、Claude Code sections 生成、Python validator 和飞书通知。
- 本任务不直接调用采集实现，不生成交易建议、仓位建议、目标价或止盈止损指令。