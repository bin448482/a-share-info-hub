# reports 目录索引

本文件是 `reports/` 的目录索引。新增、删除、改名或移动报告类型时，必须同步更新这里的说明。

## 目录用途

- 保存每日运行摘要、接口状态报告和可 review 的验证产物。
- 报告必须区分已实测结果、失败状态、空结果和待验证假设。
- 不允许把未运行的接口探测写成事实。

## 文件和子目录索引

- `AGENTS.md`：本目录索引和维护规则。
- `claude.md`：Claude/Codex 入口引用文件，内容固定为 `@agents.md`。
- `daily-financial-briefings/`：当日财经信息总结 skill 的 forward test 和可 review 简报产物，按运行日期和场景保存公开来源、缺口和非投资建议边界。
- `daily-reviews/`：每日复盘研究报告目录，按日期保存 `a-share-daily-review` 的 HTML 主报告、技术参考 Markdown、context 和 LLM sections。
- `daily-runs/`：每日快照运行报告目录，按日期保存接口状态和人读摘要。

## 当前缺失的旧报告说明

工作区当前显示多个旧探测报告处于删除状态，例如 `daily-data-contract-report.md`、`today-capability-report.json`、`history-floor-report.json` 等。它们不是本次每日快照实施的当前产物；除非任务明确要求恢复旧契约探测报告，否则不要为了补索引而恢复这些文件。

## 更新要求

- 新增报告类型时，写明报告来源脚本、输入、输出和是否代表实测结果。
- 删除或归档报告时，同步更新本索引，避免未来把不存在的文件当作当前报告。
- 报告索引只描述当前存在或明确保留的报告类型，不列已删除的旧产物为当前文件。
