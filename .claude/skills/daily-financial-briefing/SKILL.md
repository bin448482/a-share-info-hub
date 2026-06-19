---
name: daily-financial-briefing
description: Generate research-only daily financial briefings from public sources for US Macro and major investment bank views, with source citations and A-share research implications. Use when the user asks to summarize today's or a specified date's macro data, Fed/rates context, Treasury yield changes, public investment-bank views, or external background for A-share daily review, and when outputs must distinguish facts, expectations, institution views, inferences, information gaps, and non-investment-advice boundaries.
---

# Daily Financial Briefing

Use this skill to produce a cited Markdown briefing from public information. Keep the output as research background for A-share analysis; do not produce trading actions.

## Workflow

1. Confirm date and scope.
   - Use the user's explicit date when provided.
   - If no date is provided, use the current date and write it as `YYYY-MM-DD`.
   - Default scope is `US Macro` and `Investment Bank Views`; include additional user-specified themes only if they can be sourced.

2. Load the required references.
   - Read `references/source-routing.md` before collecting information.
   - Read `references/output-schema.md` before drafting the briefing.
   - Read `references/citation-rules.md` before finalizing claims.
   - Read `references/evaluation-rules.md` when checking edge cases, blocked states, or eval fixtures.

3. Collect only public, citable information.
   - Prefer official or quasi-official sources for macro facts.
   - Prefer public investment-bank pages, public report summaries, or reputable financial media summaries for bank views.
   - Exclude login-only, paywalled, source-less, unverifiable, social-media, and user-unrequested influencer content.
   - Do not bypass access controls, subscription walls, CAPTCHAs, robots blocks, or anti-scraping mechanisms.

4. Classify and deduplicate.
   - Separate `US Macro`, `Investment Bank Views`, and user-requested extra themes.
   - Merge duplicate descriptions of the same event into one fact.
   - Keep facts, market expectations, institution views, inferences, and open questions distinct.
   - Do not rewrite an investment-bank opinion as a macro fact.

5. Form conclusions only from cited material.
   - Each core conclusion needs at least one source citation.
   - If a conclusion combines macro facts and bank views, cite both source types.
   - State A-share relevance only as a candidate theme, risk observation, or question to verify with A-share evidence.
   - Put unverifiable, title-only, inaccessible, or conflicting material in the gap/boundary section unless enough sourced context exists.

6. Self-check before answering.
   - Required sections must match `references/output-schema.md`.
   - Every core conclusion must have source name, URL, and publication date or access date.
   - The output must not contain buy/sell/position/target-price/stop-loss/take-profit instructions.
   - If no citable public source is available, stop at the blocked boundary and say which source evidence is missing.

## Required Boundaries

- Output `research_only` background and include a non-investment-advice statement.
- Do not create or update data pipelines, DuckDB tables, Parquet files, or daily snapshot artifacts.
- Do not run `daily-update` or `daily-review` unless the user separately asks for that workflow.
- If the user wants this briefing connected to daily review, state that it is external background only and does not change the daily-review data contract.
- If no citable public investment-bank view is found for the date, write `未找到可引用的当日公开投行观点` and do not invent bank views.

## Blocked Output

When external information cannot be accessed or cited, return a short blocked response instead of a full briefing:

```text
blocked: 缺少可引用公开来源，无法生成当日财经信息简报。
日期：YYYY-MM-DD
范围：US Macro / Investment Bank Views
缺口：[具体缺少的信息或来源类型]
下一步：[需要联网、指定来源、提供材料或改为离线 fixture]
```
