# data 目录索引

本文件是 `data/` 的目录索引。新增、删除、改名或移动本目录下的数据分层时，必须同步更新这里的说明。

## 目录用途

- 保存每日 A 股快照的原始返回、标准化表和后续分析层数据。
- 原始外部接口返回必须保留，不允许只保存清洗后的结果。
- 标准化表必须能追溯到原始来源和采集时间。
- 本目录不保存交易建议或预测解释文档。

## 文件和子目录索引

- `AGENTS.md`：本目录索引和维护规则。
- `claude.md`：Claude/Codex 入口引用文件，内容固定为 `@agents.md`。
- `raw/`：按日期和接口保存 AKShare 原始响应与 `metadata.json`。
- `normalized/`：保存标准化 Parquet 表，供 DuckDB 和后续分析读取。

## 更新要求

- 新增 `features/`、`labels/`、`predictions/` 或 `eval/` 等后续数据层时，必须先有真实输出需求，再创建目录并补目录索引。
- 修改标准化表名或数据分层时，同步更新 `README.md`、`docs/daily-snapshot-data-design.md`、`docs/daily-snapshot-data-implementation-plan.md` 和本索引。
- 不要为单次临时文件创建长期索引目录；临时验证输出应明确可删除边界。
