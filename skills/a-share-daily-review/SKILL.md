---
name: a-share-daily-review
description: Generate research-only A-share daily review reports from this repository's daily snapshot artifacts with an evidence-packet + LLM-sections + validator workflow. Use when the user asks for A-share daily review, post-market review, HTML report, direct research suggestions, data quality diagnosis, or to analyze current collected A-share data; always enforce no trading advice, no position sizing, no price targets, and use the public CLI rather than hard-coded script paths.
---

# A Share Daily Review

## Overview

Use this skill to turn this repository's existing daily A-share snapshot artifacts into a research-only daily review, HTML report, direct research suggestions, or data-quality diagnosis.

Do not provide buy/sell calls, position sizing, price targets, stop-loss/take-profit levels, or real-time trading instructions.

## Workflow

1. Read the user's request and extract `trade_date`, `refresh_mode`, `output_format`, and focus.
2. If the user asks for trading action advice, refuse that part and offer research observations instead.
3. Generate the evidence packet with the repository CLI:

```text
python -m a_share_info_hub daily-review --trade-date <YYYY-MM-DD> --output-format context
```

4. Read `review-context.json`, then read [report-prompt.md](references/report-prompt.md) and produce `llm-review-sections.json` using only the evidence packet.
5. Validate and render HTML with:

```text
python -m a_share_info_hub daily-review --trade-date <YYYY-MM-DD> --llm-output reports/daily-reviews/<YYYY-MM-DD>/llm-review-sections.json --output-format html
```

6. If the user asked to refresh data first, include `--refresh-mode daily_update` when generating the context. Refreshing must still use the public `daily-update` module CLI.
7. Return the generated report path, data status, blocked sections, context path, and the research-only boundary.

## Output Modes

- Context: use `--output-format context` to produce `reports/daily-reviews/YYYY-MM-DD/review-context.json`.
- HTML report: use for user-reviewable reports after LLM sections are validated. Return `reports/daily-reviews/YYYY-MM-DD/a-share-daily-review.html`.
- Inline: use when the user asks for direct research suggestions or data-quality diagnosis.
- Markdown: use only for debugging or prompt/eval work after sections validation.

## Required Boundaries

CLI messages must include:

```text
analysis_mode: research_only
not_investment_advice: true
```

If data status is `failed` or `missing`, do not generate market conclusions. If status is `partial`, clearly label blocked sections and do not infer from missing data.

HTML reports must show those boundaries in user-readable language. Do not expose raw machine lines such as `analysis_mode:` or `data_status:` in the report body; keep machine metadata in the embedded JSON or data-boundary section.

## Reference

For exact commands, status semantics, HTML output, and validation rules, read [daily-review-workflow.md](references/daily-review-workflow.md). For the LLM sections format, read [report-prompt.md](references/report-prompt.md).
