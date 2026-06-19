# reports/daily-reviews 目录索引

本文件是 `reports/daily-reviews/` 的目录索引。新增、删除、改名或移动每日复盘报告结构时，必须同步更新这里的说明。

## 目录用途

- 按日期保存 `a-share-daily-review` 生成的 evidence packet、LLM sections、HTML 研究复盘报告和技术参考 Markdown。
- 报告只基于每日快照 artifacts，必须标记 `research_only` 和 `not_investment_advice: true`。
- `partial`、`failed`、`missing` 状态不能被写成完整市场结论。

## 文件和子目录索引

- `AGENTS.md`：本目录索引和维护规则。
- `claude.md`：Claude/Codex 入口引用文件，内容固定为 `@agents.md`。
- `YYYY-MM-DD/review-context.json`：指定交易日的可校验 evidence packet，由 `python -m a_share_info_hub daily-review --output-format context` 生成。
- `YYYY-MM-DD/external-background-local-topics.json`：外部背景流程从 `review-context.json` 抽取的固定 6 个本地 topic 审计产物；可能来自真实并行子 Agent 或本地 fixture helper。
- `YYYY-MM-DD/external-background-topic-results.json`：外部背景流程保存的 6 个 topic task 输入和结果审计产物；fixture helper 产物不代表真实外部抓取。
- `YYYY-MM-DD/external-background-fusion.json`：外部背景流程汇总出的 `external_background_fusion.v1`，可传给 `daily-review --external-background`。
- `YYYY-MM-DD/llm-review-sections.json`：LLM 基于 `review-context.json` 生成的 sections JSON，进入 HTML 前必须通过 Python/Pydantic 校验。
- `YYYY-MM-DD/a-share-daily-review.html`：指定交易日的本地 HTML 复盘报告，由已校验 sections 渲染生成，默认面向普通投资者，不裸露内部状态字段。
- `YYYY-MM-DD/a-share-daily-review-data-notes.md`：指定交易日的技术参考文件，记录 `data_status`、`blocked_sections`、接口失败、数据来源和排障建议。

## 当前报告索引

- `2026-06-18/review-context.json`：基于当前 `2026-06-18` daily run 生成的 evidence packet；状态为 `partial`，板块快照为 blocked section。
- `2026-06-18/external-background-local-topics.json`：基于当前 `review-context.json` 抽取的 6 个本地 topic。
- `2026-06-18/external-background-topic-results.json`：基于 fixture runner 生成的 6 个 topic task 输入和结果，用于验证 fusion helper 路径，不代表真实同日外部抓取或真实 `$daily-financial-briefing` 调用。
- `2026-06-18/external-background-fusion.json`：由 topic results 汇总出的 `external_background_fusion.v1`，当前样例 HTML 使用该文件作为 external background 输入。
- `2026-06-18/external-background-passed-simulated.json`：第一阶段用于验证 external background 融入主报告的 legacy 模拟输入；不再作为第二阶段编排验收样例。
- `2026-06-18/llm-review-sections.json`：基于 `review-context.json` 写入的 sections JSON，external background 字段已改为 fusion 语义，进入 HTML 前必须通过 Python/Pydantic 校验。
- `2026-06-18/a-share-daily-review.html`：基于当前 `2026-06-18` daily run、`external-background-fusion.json` 和已校验 sections 生成的真实复盘报告。
- `2026-06-18/a-share-daily-review-data-notes.md`：基于当前 `2026-06-18` daily run 和 `external-background-fusion.json` 生成的技术参考文件，记录 `partial` 状态、板块接口失败细节和 external background 引用。

## 更新要求

- 新增日期报告时，不需要在日期目录下创建 `AGENTS.md`。
- 修改 HTML 模板、输出字段或状态语义时，同步更新测试、README 和相关实施文档。
