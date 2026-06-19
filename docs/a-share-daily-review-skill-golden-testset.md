# A 股每日复盘研究 Skill 黄金测试集与评测方案

本文档定义 `a-share-daily-review` skill 的 v2 黄金测试集和开源评测框架选型。Promptfoo 只用于黄金测试和回归评测，不进入普通用户生成日报的生产路径。

## 黄金测试集

黄金测试集文件：

```text
docs/a-share-daily-review-skill-golden-testset.jsonl
```

每一行是一个评测用例，采用接近 Promptfoo test case 的结构：

- `description`：测试目的。
- `vars.case_id`：稳定用例编号。
- `vars.user_prompt`：用户会输入的提示词。
- `vars.artifact_state`：模拟当前数据状态。
- `vars.external_background_state`：可选。`parallel_agent_skill` 用例表示父 agent 必须 spawn 6 个子 Agent 并行调用 `$daily-financial-briefing` 后生成 `external_background_fusion.v1`；`fixture_smoke` 和 legacy fixture 只验证 Python 消费外部背景 JSON 的兼容路径，不能计入真实 Agent 编排验收。
- `vars.expected_behavior`：期望行为说明。
- `assert`：可自动检查的输出断言。
- `metadata.category`：用例分类，便于按 HTML、边界、安全、数据状态过滤。

v2 黄金测试集覆盖：

- `passed` 状态生成 `review-context.json`、角色化 HTML report 和技术参考 Markdown。
- `partial` 状态生成用户可读 HTML report，并把 blocked 技术细节外置到技术参考 Markdown。
- `skipped` 状态说明非交易日跳过，不生成市场结论。
- `failed` 状态阻断市场结论。
- `missing` 状态提示公开 CLI 刷新。
- 用户要求直接建议时只输出研究建议。
- 用户要求买卖和仓位时拒绝交易建议并改写为研究输出。
- DuckDB 失败但 Parquet 可用时降级。
- 刷新数据时只调用公开 CLI，不调用脚本路径。
- HTML 输出包含策略分析师写给普通投资者的角色化表达和非投资建议声明。
- HTML 输出包含 `大盘观察`，并分出 `大盘定性` 和 `大盘结构`。
- external background passed 时，必须区分两类路径：真实验收路径是 `$a-share-daily-review` workflow spawn 6 个并行子 Agent，每个子 Agent 使用 `$daily-financial-briefing` 并返回 `TopicResult`；fixture smoke 只验证 Python 能消费 `external_background_fusion.v1`。
- parallel agent passed 用例要求 HTML 不新增独立外部背景章节，外部变量融合进 `风险观察` 和 `下一步研究问题`，引用写入技术参考 Markdown。
- external background blocked 时，本地 HTML 继续生成，用户正文不展示外部状态或外部结论正文。
- external background invalid citation 时，无 URL 核心点不进入 HTML，剩余合格观点只融合进主 sections，技术参考 Markdown 记录降级原因。
- HTML 正文不裸露 `analysis_mode:`、`data_status:`、`blocked_sections`、source key、接口错误或原始分类编码。
- 技术参考 Markdown 保留 `data_status`、`blocked_sections`、失败接口、失败原因、原始分类编码和数据来源。
- 技术参考 Markdown 保留 external background 输入路径、状态、引用来源和降级原因。
- 输出不包含买入、卖出、仓位、目标价、止损止盈等禁用语言。

## 推荐评测框架

### Promptfoo，第一选择

Promptfoo 适合作为第一版回归测试框架，因为它支持 YAML/JSON/JSONL 用例、`contains`、`regex`、`contains-html`、`not-contains` 和自定义 provider。它覆盖的是 skill 行为和输出边界，不替代 Python/Pydantic 的运行时校验。

建议运行方式：

```text
npm run install:eval
npm run eval:a-share-daily-review
```

本仓库固定使用 `promptfoo@0.120.0`。在当前 Windows/npm 组合中，直接使用全局 `npm install` 可能触发 npm engine 或原生依赖问题；`npm run install:eval` 会使用 `npm@11.6.4`、省略 optional provider SDK，并重建 `better-sqlite3`。

当前 provider：

```text
eval/providers/run-a-share-daily-review.js
```

Provider 会根据黄金测试集的 `artifact_state` 创建隔离临时 fixture，再调用：

```text
python -m a_share_info_hub daily-review --output-root <temp> --user-prompt "<prompt>" --render-mode deterministic
```

这样可以在没有真实 LLM 和 AKShare 网络调用的情况下验证 v2 的本地契约：

- context 是否生成。
- HTML 是否生成。
- HTML 是否包含 `大盘观察 / 大盘定性 / 大盘结构`。
- 技术参考 Markdown 是否生成。
- external background 是否只进入独立 context 字段、主报告融合位置和技术参考 Markdown，不生成独立 HTML 背景章节。
- external background passed 真实验收用例是否返回 `external_background_source: parallel_agent_skill`、`external_background_parallel_agents: 6`、`external_background_topic_results: 6` 和 `external_background_schema: external_background_fusion.v1` 审计行。
- fixture smoke 用例是否返回 `external_background_source: fixture_smoke`，且不被计入真实 `$daily-financial-briefing` Agent 编排验收。
- HTML 是否不裸露机器字段、接口名、连接错误和原始分类编码。
- 技术参考 Markdown 是否保留必要诊断信息。
- `partial` / `skipped` / `failed` / `missing` 是否被正确表达。
- 禁用交易建议语言是否出现。
- provider 是否避免污染真实 `data/`、`reports/`。

正式用户报告仍应使用 evidence packet + LLM sections + Python/Pydantic validator 流程；deterministic fallback 只用于本地评测和调试。

### DeepEval，第二阶段选择

DeepEval 适合在后续需要 Python 组件级或 LLM judge 评测时引入。它可以测试数据读取组件、状态归类组件、LLM sections 质量和端到端输出质量。

建议引入时机：

- 需要把评测接入 CI。
- 需要自定义 LLM judge 判断“是否正确拒绝交易建议”这类语义问题。
- 需要比较不同 report prompt 的质量。

### OpenAI Evals，参考方案

OpenAI Evals 可以作为自定义 eval 思路参考，但第一版不作为主框架。本 skill 的首要需求是本地 artifacts、HTML、禁用词、CLI 契约和 Pydantic schema gate，Promptfoo 与 Pytest 更直接。

## 第一版评测策略

第一版不需要 LLM judge 先行，优先使用确定性检查：

- `contains`：检查 `data_status`、`context_artifact`、`data_notes_artifact`、`review-metadata`。
- `contains-html`：检查 HTML 请求是否返回 HTML。
- `regex`：检查报告路径形如 `reports/daily-reviews/YYYY-MM-DD/a-share-daily-review.html`。
- `not-contains`：检查禁用交易建议词和旧机器字段裸露。
- provider 审计行：检查 `html_forbidden_terms: none` 和 `data_notes_diagnostics_present: true`。
- `contains`：检查 `大盘观察`、`大盘定性`、`大盘结构`。
- `contains`：检查 `external_background_diagnostics_present: true`、`external_background_source: parallel_agent_skill`、`external_background_parallel_agents: 6`、`external_background_topic_results: 6`、`external_background_schema: external_background_fusion.v1`、`external_background_standalone_sections: 0`、`risk_section_count: 1`、`follow_up_section_count: 1`，以及具备具体外部事实、传导机制和本地指标映射的外部背景句。
- `not-contains`：检查 HTML 不包含“只能作为待验证变量”“不能替代本地”“仍需用 A 股行情”这类低信息外部背景套话。
- `not-contains`：检查 HTML 不包含独立 `外部宏观与机构观点背景` 章节、外部引用 URL、模拟输入或 external background 状态词。
- provider 检查：确认刷新说明包含 `python -m a_share_info_hub daily-update`，不包含 `scripts/collect_daily_snapshot.py`。

第二阶段再引入语义评估：

- 输出是否把 partial 写成普通投资者能理解的证据边界。
- 输出是否把“建议”改写为研究建议。
- 输出是否把 skipped/failed/missing 正确阻断。
- 输出是否没有从缺失数据补推断。

## 验收门槛

Skill v2 实施完成后，必须满足：

- 黄金测试集中的核心用例全部可执行。
- 所有 deterministic assertions 通过。
- Pydantic context 和 LLM sections 校验有 Pytest 覆盖。
- 任何出现交易建议禁用词的输出都视为失败。
- `passed`、`partial`、`skipped`、`failed`、`missing` 五类状态都有可复查输出。
- external background 的 `passed`、`partial`、`blocked`、`invalid` 状态都有 Pytest 或 Promptfoo 覆盖。
- external background passed 真实验收必须走 `parallel_agent_skill` 审计语义，不能只依赖 `daily-review-external-background --runner fixture`、手写 `external_background.v1` 或 legacy fixture。
- HTML 用例必须生成可打开的本地报告路径。
- HTML 用例必须生成同目录技术参考 Markdown。
- Promptfoo 失败应阻断合并或发布，但不作为普通用户生成日报时的 runtime gate。

## 官方资料

- Promptfoo intro: https://www.promptfoo.dev/docs/intro/
- Promptfoo test cases: https://www.promptfoo.dev/docs/configuration/test-cases/
- Promptfoo assertions: https://www.promptfoo.dev/docs/configuration/expected-outputs/
- Promptfoo deterministic assertions: https://www.promptfoo.dev/docs/configuration/expected-outputs/deterministic/
- DeepEval introduction: https://deepeval.com/docs/introduction
- DeepEval datasets: https://deepeval.com/docs/evaluation-datasets
- DeepEval CI/CD: https://deepeval.com/docs/evaluation-unit-testing-in-ci-cd
- OpenAI Evals GitHub: https://github.com/openai/evals
