# scripts 目录索引

本文件是 `scripts/` 的目录索引。新增、删除、改名或移动脚本时，必须同步更新这里的文件说明。

## 目录用途

- 保存可执行脚本和脚本说明。
- 脚本输出必须写入可复查文件；关键结果不能只打印到控制台。
- 外部接口失败必须记录原因，不能静默降级为有效数据。

## 文件索引

- `AGENTS.md`：本目录索引和维护规则。
- `claude.md`：Claude/Codex 入口引用文件，内容固定为 `@agents.md`。
- `collect_daily_snapshot.py`：每日 A 股快照采集实现和兼容脚本入口；采集前验证交易日，非交易日输出 `skipped` 状态并跳过行情接口；日常每日更新应通过 `python -m a_share_info_hub daily-update` 调用。
- `generate_daily_data_contract_report.py`：AKShare 每日数据契约探测报告生成脚本；用于候选接口探测、历史边界探测、契约 JSON 和 Markdown 报告生成。
- `run_daily_report_job.py`：每日定时采集和报告发送的薄编排入口；按阶段调用 `.venv/bin/python -m a_share_info_hub daily-update`、`daily-review` 和 Claude Code 非交互命令，默认生成 `external-background-fusion.json` 后再生成 `llm-review-sections.json`，并写入 `reports/daily-jobs/YYYY-MM-DD/` 状态、heartbeat、摘要和可选 OpenClaw `feishu` channel 通知，不直接实现采集或 HTML 渲染。

## 更新要求

- 新增脚本时，写明脚本用途、主要输入、主要输出和验证命令。
- 修改脚本输出路径、命令行参数或状态语义时，同步更新 `README.md`、相关 `docs/` 实施文档和本索引。
- 删除脚本时，先确认没有 README、文档或测试仍引用它，再更新本索引。
