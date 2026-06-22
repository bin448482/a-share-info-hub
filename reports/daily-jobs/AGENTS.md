# reports/daily-jobs 目录索引

本文件是 `reports/daily-jobs/` 的目录索引。新增、删除、改名或移动本目录下的任务状态产物类型时，必须同步更新这里的说明。

## 目录用途

- 保存每日定时采集、复盘报告生成、飞书发送和 watchdog 检查的运行状态。
- 每个交易日期目录保存机器可读 `job-status.json`、`heartbeat.json`、人读 `job-summary.md` 和阶段日志。
- 状态产物不得包含飞书 webhook URL、secret、token 或收件人敏感信息。

## 文件和子目录索引

- `AGENTS.md`：本目录索引和维护规则。
- `claude.md`：Claude/Codex 入口引用文件，内容固定为 `@agents.md`。
- `YYYY-MM-DD/`：单个交易日期的定时任务状态目录，由 `scripts/run_daily_report_job.py` 生成；典型文件包括 `job-status.json`、`job-summary.md`、`heartbeat.json`、`watchdog-status.json` 和 `logs/` 阶段日志。

## 更新要求

- 修改任务状态字段、heartbeat 字段、日志路径或 watchdog 产物时，同步更新本索引、`reports/AGENTS.md` 和相关测试。
- 新增状态产物时，说明来源脚本、输入、输出和是否包含人工可读诊断。
- 任务状态只能表达运行质量和报告路径，不记录密钥或不可提交的本机敏感配置。
