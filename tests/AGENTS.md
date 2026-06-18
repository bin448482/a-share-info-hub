# tests 目录索引

本文件是 `tests/` 的目录索引。新增、删除、改名或移动测试文件时，必须同步更新这里的说明。

## 目录用途

- 保存本地单元测试和 fixture。
- 单元测试应使用 fixture 或 mock，不依赖真实 AKShare 网络调用。
- 测试必须区分结构逻辑验证和真实接口验证。

## 文件和子目录索引

- `AGENTS.md`：本目录索引和维护规则。
- `claude.md`：Claude/Codex 入口引用文件，内容固定为 `@agents.md`。
- `fixtures/`：单元测试使用的最小 JSON fixture，不代表真实市场数据验证。
- `test_daily_snapshot_normalization.py`：覆盖主表、涨跌停和龙虎榜标准化逻辑，以及 schema 变化暴露。
- `test_daily_snapshot_status.py`：覆盖主表失败、增强空结果、增强 schema 变化和整体状态归类。
- `test_daily_snapshot_outputs.py`：覆盖失败日志、原始落盘、状态报告、每日摘要、DuckDB 重跑替换和 mock 端到端成功路径。
- `test_cli.py`：覆盖仓库级 CLI 的 `daily-update` 子命令、参数化日期和调用采集函数的参数传递。

## 更新要求

- 新增脚本功能或状态语义时，优先补对应单元测试，再更新本索引。
- 新增测试文件时，说明它覆盖的业务契约，不只写文件名。
- 单元测试不能宣称 AKShare 当前真实可用；真实接口验证结果应写入 `reports/daily-runs/`。
