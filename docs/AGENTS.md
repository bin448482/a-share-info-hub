# docs 目录索引

本文件是 `docs/` 的目录索引。新增、删除、改名或移动本目录下的文档时，必须同步更新这里的文件说明。

## 目录用途

- 保存项目设计、实施计划、数据契约和用户可 review 的说明文档。
- 文档必须区分“计划”“已实测结果”和“待验证假设”，不能把未运行的接口探测写成事实。

## 文件索引

- `AGENTS.md`：本目录索引和维护规则。
- `claude.md`：Claude/Codex 入口引用文件，内容固定为 `@agents.md`。
- `daily-data-contract-implementation-plan.md`：可验证每日数据契约报告的实施计划，重点是 AKShare 今日能力探测、历史回溯和契约生成。
- `daily-snapshot-data-design.md`：每日 A 股快照数据设计，定义主表、增强数据、存储结构、去重关联和 v1 不做事项。
- `daily-snapshot-data-implementation-plan.md`：每日快照采集链路实施计划，定义脚本入口、异常处理、单元测试、验收标准和目标达成条件。

## 更新要求

- 修改数据设计、采集入口、输出目录或验证标准时，同步检查 `daily-snapshot-data-design.md` 和 `daily-snapshot-data-implementation-plan.md` 是否仍一致。
- 新增面向 review 的文档时，在本索引写明文档用途和状态边界。
- 删除或归档文档时，在本索引移除或改写对应条目，避免未来误读旧计划为当前事实。
