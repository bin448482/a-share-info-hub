# logs 目录索引

本文件是 `logs/` 的目录索引。新增、删除、改名或移动日志文件时，必须同步更新这里的说明。

## 目录用途

- 保存外部接口失败、空结果、字段变化和运行诊断日志。
- 日志必须使用可解析结构，优先 JSONL。
- 日志用于审计和排查，不作为有效市场数据来源。

## 文件索引

- `AGENTS.md`：本目录索引和维护规则。
- `claude.md`：Claude/Codex 入口引用文件，内容固定为 `@agents.md`。
- `external-interface-failures.jsonl`：每日采集过程中非 `success` 状态的接口记录，包括失败、空结果和 schema 变化；可能包含多次重跑记录。

## 更新要求

- 修改日志字段时，同步更新采集脚本、测试、README、实施文档和本索引。
- 日志可追加，不应把历史失败记录改写成成功。
- 判断某次运行的最终状态时，优先读取对应日期的 `reports/daily-runs/YYYY-MM-DD/interface-status.json`。
