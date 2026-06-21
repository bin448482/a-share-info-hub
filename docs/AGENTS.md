# docs 目录索引

本文件是 `docs/` 的目录索引。新增、删除、改名或移动本目录下的文档时，必须同步更新这里的文件说明。

## 目录用途

- 保存项目设计、实施计划、数据契约和用户可 review 的说明文档。
- 文档必须区分“计划”“已实测结果”和“待验证假设”，不能把未运行的接口探测写成事实。

## 文件索引

- `AGENTS.md`：本目录索引和维护规则。
- `claude.md`：Claude/Codex 入口引用文件，内容固定为 `@agents.md`。
- `20260619-132232-daily-financial-briefing-html-integration-implementation-plan.md`：`$daily-financial-briefing` 融入每日复盘 HTML 的修正实施计划；已记录前两次设计偏差，当前第三阶段方案改为 `$a-share-daily-review` workflow 内 spawn 6 个并行子 Agent，每个子 Agent 使用 `$daily-financial-briefing`，Python runner 仅作为 fixture/validation helper。
- `20260621-094138-code-simplification-refactor-implementation-plan.md`：代码瘦身重构实施计划，定义本轮只删除死代码、收敛重复逻辑和少量 wrapper 的低风险范围、目标达成条件、DAG、跳过项和验证命令；当前用于 review，未代表改动已实施。
- `a-share-daily-review-skill-golden-testset.jsonl`：每日复盘研究 skill 的 v2 黄金测试集，用于覆盖 context、HTML 输出、external background 融合、无独立外部背景章节、数据状态降级、CLI 契约、HTML 机器字段边界和非交易建议边界。
- `a-share-daily-review-skill-golden-testset.md`：每日复盘研究 skill 的黄金测试集说明和开源评测框架选型，当前推荐 Promptfoo 作为回归评测层，DeepEval 作为后续 Python/LLM 组件评测方案；external background passed 真实验收需使用 `parallel_agent_skill` 审计语义，并与 fixture smoke / legacy compatibility 区分。
- `a-share-daily-review-skill-implementation-plan.md`：每日复盘研究 skill 的 v2 重构实施计划，定义 evidence packet、LLM 分析层、Pydantic 运行时校验、HTML 封装和 Promptfoo 回归评测边界；角色化报告细节以后续改造计划为准。
- `a-share-daily-review-role-based-report-plan.md`：每日复盘报告角色化改造计划，定义策略分析师到普通投资者的写作角色、HTML 正文与技术 Markdown 拆分、prompt/validator/eval 调整、目标达成条件和验收标准。
- `a-share-daily-review-skill-user-guide.md`：每日复盘研究 skill 的用户提示词说明，介绍 agent 调用 skill 的能力、context -> LLM sections -> validator -> HTML 流程、适用场景和直接研究建议提示词；与当前 CLI 用法对齐。
- `daily-financial-news-design.md`：当日财经信息总结 skill 设计稿，定义基于 US Macro 和主要投行观点的 LLM 阅读、总结、引用来源、每日复盘衔接和第一版明确不做事项。
- `daily-financial-news-feasibility-analysis.md`：当日财经信息采集数据源可行性分析报告，基于 AKShare 1.18.64 实测结果，确认 us_macro 数据源充足可用、investment_bank_views 需降级为 AKShare 内有限源，标注 DXY/金十新闻不可用及替代方案。
- `daily-financial-news-skill-golden-testset.jsonl`：当日财经信息总结 skill 的黄金测试集，覆盖默认范围、指定日期、事实/预期/推论分离、投行观点边界、来源缺口、冲突、付费来源、交易建议拒绝、每日复盘衔接、blocked 和引用不足场景。
- `daily-financial-news-skill-golden-testset.md`：当日财经信息总结 skill 的黄金测试说明，定义 Promptfoo provider、离线 fixture、审计行、运行命令和验收门槛。
- `daily-financial-news-skill-implementation-plan.md`：当日财经信息总结 skill 的实施计划，定义 `daily-financial-briefing` skill scaffold、reference 拆分、黄金测试集、Promptfoo/provider 验证、异常降级和目标达成条件。
- `daily-data-contract-implementation-plan.md`：可验证每日数据契约报告的实施计划，重点是 AKShare 今日能力探测、历史回溯和契约生成。
- `daily-snapshot-data-design.md`：每日 A 股快照数据设计，定义主表、增强数据、存储结构、去重关联和 v1 不做事项。
- `daily-snapshot-data-implementation-plan.md`：每日快照采集链路实施计划，定义脚本入口、异常处理、单元测试、验收标准和目标达成条件。
- `linkedin-article-cn.html`：LinkedIn 分享用的中文技术文章 HTML 版本，可直接复制到 LinkedIn 发布。
- `linkedin-article-en.html`：LinkedIn 分享用的英文技术文章 HTML 版本，可直接复制到 LinkedIn 发布。

## 更新要求

- 修改数据设计、采集入口、输出目录或验证标准时，同步检查 `daily-snapshot-data-design.md` 和 `daily-snapshot-data-implementation-plan.md` 是否仍一致。
- 新增实施计划文档时，文件名必须包含本地生成时间戳，格式为 `YYYYMMDD-HHMMSS-<topic>-implementation-plan.md`；历史未带时间戳的文档不因本规则自动改名。
- 新增面向 review 的文档时，在本索引写明文档用途和状态边界。
- 删除或归档文档时，在本索引移除或改写对应条目，避免未来误读旧计划为当前事实。
