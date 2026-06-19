# docs 目录索引

本文件是 `docs/` 的目录索引。新增、删除、改名或移动本目录下的文档时，必须同步更新这里的文件说明。

## 目录用途

- 保存项目设计、实施计划、数据契约和用户可 review 的说明文档。
- 文档必须区分“计划”“已实测结果”和“待验证假设”，不能把未运行的接口探测写成事实。

## 文件索引

- `AGENTS.md`：本目录索引和维护规则。
- `claude.md`：Claude/Codex 入口引用文件，内容固定为 `@agents.md`。
- `a-share-daily-review-skill-golden-testset.jsonl`：每日复盘研究 skill 的 v2 黄金测试集，用于覆盖 context、HTML 输出、数据状态降级、CLI 契约、HTML 机器字段边界和非交易建议边界。
- `a-share-daily-review-skill-golden-testset.md`：每日复盘研究 skill 的黄金测试集说明和开源评测框架选型，当前推荐 Promptfoo 作为回归评测层，DeepEval 作为后续 Python/LLM 组件评测方案；已与 `eval/` 配置对齐。
- `a-share-daily-review-skill-implementation-plan.md`：每日复盘研究 skill 的 v2 重构实施计划，定义 evidence packet、LLM 分析层、Pydantic 运行时校验、HTML 封装和 Promptfoo 回归评测边界；角色化报告细节以后续改造计划为准。
- `a-share-daily-review-role-based-report-plan.md`：每日复盘报告角色化改造计划，定义策略分析师到普通投资者的写作角色、HTML 正文与技术 Markdown 拆分、prompt/validator/eval 调整、目标达成条件和验收标准。
- `a-share-daily-review-skill-user-guide.md`：每日复盘研究 skill 的用户提示词说明，介绍 agent 调用 skill 的能力、context -> LLM sections -> validator -> HTML 流程、适用场景和直接研究建议提示词；与当前 CLI 用法对齐。
- `daily-data-contract-implementation-plan.md`：可验证每日数据契约报告的实施计划，重点是 AKShare 今日能力探测、历史回溯和契约生成。
- `daily-snapshot-data-design.md`：每日 A 股快照数据设计，定义主表、增强数据、存储结构、去重关联和 v1 不做事项。
- `daily-snapshot-data-implementation-plan.md`：每日快照采集链路实施计划，定义脚本入口、异常处理、单元测试、验收标准和目标达成条件。

## 更新要求

- 修改数据设计、采集入口、输出目录或验证标准时，同步检查 `daily-snapshot-data-design.md` 和 `daily-snapshot-data-implementation-plan.md` 是否仍一致。
- 新增面向 review 的文档时，在本索引写明文档用途和状态边界。
- 删除或归档文档时，在本索引移除或改写对应条目，避免未来误读旧计划为当前事实。
