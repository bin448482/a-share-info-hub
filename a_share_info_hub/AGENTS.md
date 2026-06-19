# a_share_info_hub 目录索引

本文件是 `a_share_info_hub/` 的目录索引。新增、删除、改名或移动 CLI 包文件时，必须同步更新这里的说明。

## 目录用途

- 保存仓库级 Python CLI 包入口。
- 对外命令以 `python -m a_share_info_hub <subcommand>` 形式调用，不在文档中 hard code 具体脚本路径作为日常入口。

## 文件索引

- `AGENTS.md`：本目录索引和维护规则。
- `claude.md`：Claude/Codex 入口引用文件，内容固定为 `@agents.md`。
- `__init__.py`：Python 包初始化文件。
- `daily_review.py`：每日复盘研究模块，读取已有 daily run、Parquet、DuckDB 和可选 external background JSON，生成 `review-context.json`，校验 LLM sections，并输出 research-only HTML、技术参考 Markdown 或 inline 报告。
- `external_background.py`：每日复盘外部背景 fixture/validation helper，从 `review-context.json` 抽取固定 6 个本地 topic，派发可注入 runner，并汇总为 `external_background_fusion.v1` 及审计中间产物；不代表生产 `$daily-financial-briefing` skill 调用。
- `__main__.py`：顶层 CLI 入口；当前提供 `daily-update`、`daily-review` 和 `daily-review-external-background` 子命令，分别负责每日采集、每日复盘研究和外部背景 fixture/validation helper，`daily-review` 支持可选 `--external-background`。

## 更新要求

- 新增 CLI 子命令时，同步更新 `README.md`、相关实施文档、测试和本索引。
- 日常运行命令应通过 CLI 子命令表达，脚本路径只作为内部实现或兼容入口说明。
