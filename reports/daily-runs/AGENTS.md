# reports/daily-runs 目录索引

本文件是 `reports/daily-runs/` 的目录索引。新增、删除、改名或移动每日运行报告结构时，必须同步更新这里的说明。

## 目录用途

- 按日期保存每日快照运行的 `interface-status.json` 和 `daily-data-summary.md`。
- 每份日报告必须说明主表、增强数据、失败项、空结果和整体状态。
- 不要在日报告中生成预测或交易建议。

## 文件和子目录索引

- `AGENTS.md`：本目录索引和维护规则。
- `claude.md`：Claude/Codex 入口引用文件，内容固定为 `@agents.md`。
- `YYYY-MM-DD/interface-status.json`：机器可读的每日接口状态、表行数、DuckDB 状态和每个来源状态。
- `YYYY-MM-DD/daily-data-summary.md`：面向 review 的每日摘要，说明主表、增强接口、标准化表行数和边界。

## 当前运行索引

- `2026-06-18/`：一次真实每日快照运行产物；状态为 `partial`，主表和多数增强数据成功，行业/概念板块接口上游断连并被记录为失败。

## 更新要求

- 新增日期运行目录时，不需要在日期目录内再创建 `AGENTS.md`；但如果该日期目录作为长期样例保留，应在“当前运行索引”增加一行说明。
- 修改日报告字段或状态语义时，同步更新采集脚本、测试、实施文档和本索引。
- 不要把 `partial` 或 `failed` 日报改写成 `passed`；应通过重跑生成新的状态。
