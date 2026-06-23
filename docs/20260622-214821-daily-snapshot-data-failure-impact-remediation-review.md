# 每日数据采集失败影响与补救方案报告

## 报告用途

本文用于 review 每日 A 股快照采集失败后的数据影响、当前代码风险和补救优先级。结论来自 2026-06-22 对当前仓库代码的静态核对，范围包括：

- `scripts/collect_daily_snapshot.py`
- `a_share_info_hub/daily_review.py`
- `scripts/run_daily_report_job.py`
- `a_share_info_hub/__main__.py`

本文只讨论数据工程和研究报告证据边界，不提供任何投资建议。

## 核心结论

1. 主接口 `stock_zh_a_spot` 失败是最高风险场景。当前代码会在计算 `overall_status` 之前写 Parquet 和 DuckDB，因此空主表可能覆盖 `data/normalized/daily_stock_snapshot.parquet`，也可能替换 DuckDB 中同一 `trade_date` 的已有主表记录。
2. DuckDB 不是完全安全层。当前写入策略会保留其他交易日历史，但同一交易日重跑时先排除旧日期记录再拼接 incoming；如果 incoming 是空主表，同一交易日旧记录会被清掉。
3. Raw JSON 是审计和重放基础，但只对已经成功返回或 schema changed 的接口有 `response.json`。真正调用失败的接口只有 `metadata.json`，不能从 raw 还原缺失响应。
4. 交易日历验证失败比主接口失败更安全。当前实现只写 daily-run 状态报告，不写 Parquet，也不写 DuckDB；不会覆盖已有标准化文件。
5. Daily Review 当前主要从 Parquet 读取标准化表，只检查 DuckDB 是否可查询，不从 DuckDB 回填表数据。Parquet 为空或缺失时，DuckDB 历史数据不能被复盘自动利用。
6. 现有 watchdog 和告警可以发现任务失败、连续失败和 heartbeat 停滞，但它们发生在数据写入风险之后，不能替代写入前保护。

## 当前实现核对

| 主题 | 当前代码位置 | 已核对行为 | 影响 |
| --- | --- | --- | --- |
| 交易日门禁 | `scripts/collect_daily_snapshot.py:859-874` | 先调用交易日验证；失败或非交易日直接走 `build_no_collection_outputs()` | 不调用行情接口 |
| 交易日历失败输出 | `scripts/collect_daily_snapshot.py:958-993` | 只写 `interface-status.json` 和 `daily-data-summary.md`，表对象只用于行数统计 | 不覆盖 Parquet/DuckDB |
| 标准表构造 | `scripts/collect_daily_snapshot.py:905`、`1008-1049` | 每个表无片段时生成空 DataFrame | 主接口失败会得到空主表 |
| Parquet 写入 | `scripts/collect_daily_snapshot.py:906`、`1052-1057` | 每次把所有标准表写到固定文件名 | 空表会覆盖上一份 Parquet |
| DuckDB 写入 | `scripts/collect_daily_snapshot.py:907-909`、`1060-1092` | 每表按 `trade_date <> ?` 保留其他日期，再拼接 incoming 后 `CREATE OR REPLACE` | 保留其他日期，但同日空 incoming 会清掉同日旧记录 |
| 整体状态判定 | `scripts/collect_daily_snapshot.py:910`、`1105-1121` | 写完 Parquet/DuckDB 后才根据主表、增强表、DuckDB 计算状态 | 状态失败无法阻止前面写入 |
| CLI 退出码 | `a_share_info_hub/__main__.py:148-166` | `passed`、`partial`、`skipped` 返回 0；`failed` 返回 1 | 定时任务能识别失败，但已经完成写入动作 |
| Review 读表 | `a_share_info_hub/daily_review.py:832-864` | 只从 `data/normalized/*.parquet` 读取并按 `trade_date` 过滤 | 无 DuckDB 表数据回退 |
| Review DuckDB 检查 | `a_share_info_hub/daily_review.py:867-892` | 只执行 `COUNT(*)` 查询并标记可查询，没有检查 count 是否大于 0 | DuckDB 健康信号可能偏乐观 |
| Review 状态规则 | `a_share_info_hub/daily_review.py:895-941` | 主表失败或为空会 blocked；DuckDB 不可用会降级 partial | 复盘主体仍以 Parquet 主表为准 |
| 告警 SLA | `scripts/run_daily_report_job.py:215-226`、`504-604`、`924-944`、`1485-1492`、`1829-1860` | 有 hard timeout、heartbeat、连续失败和 watchdog 检查 | 负责发现失败，不负责写入保护 |

## 存储层风险矩阵

| 存储层 | 当前定位 | 写入策略 | 当前风险 | 建议定位 |
| --- | --- | --- | --- | --- |
| Parquet | `data/normalized/*.parquet`，复盘优先读取 | 固定文件全量覆盖 | 主表失败、schema changed 或指定日期无数据时可能把上一份可用 Parquet 覆盖为空 | 作为“最新可用标准化缓存”，写入前必须要求主表有效 |
| DuckDB | `market.duckdb`，保留多日历史 | 按表重建，保留 `trade_date <> 当前日期` 后拼接 incoming | 其他日期相对安全；同一日期失败重跑可能删除旧记录；失败日也可能留下增强表数据 | 作为历史查询层，但写入前同样要拒绝空主表 |
| Raw JSON | `data/raw/YYYY-MM-DD/<source>/` | 按日期和接口保存响应及 metadata | 调用失败无 `response.json`，只能诊断不能重放 | 作为审计和重放来源；重放只适用于已有 raw response 的接口 |
| Daily run 报告 | `reports/daily-runs/YYYY-MM-DD/` | 每次运行写状态和摘要 | 状态能说明失败，但不保护数据文件 | 作为恢复入口和自动告警依据 |

## 失败场景分析

### 场景 1：主接口 `stock_zh_a_spot` 失败

当前实际链路：

```text
stock_zh_a_spot failed
  -> normalized_by_table["daily_stock_snapshot"] 无片段
  -> daily_stock_snapshot 标准表为空
  -> write_normalized_tables() 写出空 Parquet
  -> write_duckdb_tables() 尝试把空主表写入 DuckDB
  -> build_overall_status() 返回 failed
  -> daily-update CLI 返回 1
```

影响：

- `daily_stock_snapshot.parquet` 会被空表覆盖，上一份 Parquet 不再可用。
- DuckDB 会保留其他交易日，但同一 `trade_date` 的旧主表记录可能被空 incoming 替换掉。
- 如果增强接口成功，DuckDB/Parquet 可能留下“整体 failed 但增强表有数据”的不完整当日数据包。
- Daily Review 会把 `data_status` 判为 `failed`，并阻断 `market_width`、`limit_pool_events`、`lhb_events`、`board_snapshot` 等依赖主表的章节。

补救：

1. 立即补采同一交易日。如果 AKShare 恢复，成功重跑会重新写入 Parquet 和 DuckDB。

```bash
python -m a_share_info_hub daily-update --trade-date 2026-06-20
```

2. 增加重试和超时适合临时网络波动，但不能解决接口持续不可用。

```bash
python -m a_share_info_hub daily-update \
  --trade-date 2026-06-20 \
  --max-retries 5 \
  --retry-sleep 5.0 \
  --request-timeout 30.0
```

3. 如果已经有同日成功数据，不建议在主接口仍不稳定时反复用当前实现重跑；失败重跑可能覆盖同日旧数据。应先实施写入前保护，或在隔离 output root 中验证接口恢复后再写回主库。

### 场景 2：增强接口部分失败

当前实际链路：

```text
stock_zh_a_spot success
增强接口 failed/schema_changed
  -> 主表正常写 Parquet 和 DuckDB
  -> 失败增强表无片段或为空
  -> build_overall_status() 返回 partial
  -> daily-update CLI 返回 0
```

影响：

- 主表可用，大盘观察和市场宽度可产出。
- 对应增强章节会 blocked。例如龙虎榜接口失败时，`lhb_events` 不应生成完整结论。
- `partial` 是可 review 状态，但报告必须显式说明证据缺口，不能把缺失增强数据当成“无事件”。

补救：

- 优先重跑当日采集，因为 DuckDB 同日替换可以消除重复数据。
- 若只有某个增强接口返回 raw 成功但标准化失败，可以通过 raw replay 恢复该表；当前仓库还没有独立 raw replay CLI，需要补实现。
- 如果增强接口是上游自然空结果，应保持 `success_empty`，不要把空结果误报为失败。

### 场景 3：交易日历验证失败

当前实际链路：

```text
tool_trade_date_hist_sina failed
  -> build_no_collection_outputs()
  -> 不调用任何行情接口
  -> 不写 data/normalized/*.parquet
  -> 不写 market.duckdb
  -> daily-update CLI 返回 1
```

影响：

- 已有 Parquet 和 DuckDB 不会被覆盖。
- 状态报告会标记 `overall_status=failed`，Daily Review 会阻断复盘结论。
- 这是当前已有的数据保护机制，风险低于主接口失败。

补救：

- 恢复交易日历接口或确认目标日期后重跑公开 CLI。
- 不建议绕过交易日门禁直接采行情，否则会破坏“未确认交易日不采集”的保护边界。

### 场景 4：DuckDB 写入失败

当前实际链路：

```text
主表和 Parquet 写入成功
DuckDB 写入失败
  -> build_overall_status() 返回 failed
  -> daily-update CLI 返回 1
  -> Daily Review 可从 Parquet 读取主表，但 DuckDB section blocked
```

影响：

- `interface-status.json` 的 daily-run 整体状态是 `failed`。
- Daily Review 当前规则在主表 Parquet 可用时可以降级为 `partial`，但会记录 DuckDB 不可用。
- DuckDB 写入函数没有显式事务边界；如果未来出现中途失败，建议不要假设所有表都保持一致。

补救：

- 修复 DuckDB 文件锁、磁盘、schema 或权限问题后重跑。
- 如果 Parquet 已经可用，短期可以生成 partial 复盘，但技术参考必须保留 DuckDB blocked。

## 推荐改进方案

### P0：写入前保护主表

目标：主表无效时，不覆盖 Parquet，不替换 DuckDB。

最小规则：

```text
只有 main_record.status == success 且 daily_stock_snapshot 非空时，才允许写 Parquet 和 DuckDB。
否则只写 raw、metadata、failure log、daily-run 状态报告。
```

实现要点：

- 在 `build_standard_tables()` 后、`write_normalized_tables()` 前判定主表有效性。
- 主表无效时，跳过 `write_normalized_tables()` 和 `write_duckdb_tables()`，`overall_status` 仍为 `failed`。
- `interface-status.json` 保留本次空表行数和失败原因，但不要让空表落入持久标准化层。
- 增加测试：先写一份非空 Parquet/DuckDB，再模拟主接口失败，断言旧 Parquet 和同日 DuckDB 记录仍保留。

### P0：DuckDB 拒绝空主表替换

目标：即使调用方遗漏保护，DuckDB 写入层也不应接受空主表作为同日替换数据。

最小规则：

```text
write_duckdb_tables() 或其调用方发现 daily_stock_snapshot.empty 时，直接返回 failed/skipped，不执行 CREATE OR REPLACE。
```

建议优先放在调用方做业务判断；DuckDB 函数可以再加防御性校验，避免未来新入口误用。

### P1：Daily Review 增加 DuckDB 同日回退

目标：Parquet 缺失、不可读或指定日期为空时，尝试从 DuckDB 读取同一 `trade_date` 的标准表。

注意边界：

- 不建议把 DuckDB 中“最新可用日期”静默当作目标日期使用。复盘报告必须对应用户请求的交易日。
- 如果目标日期无数据，可以在技术参考中列出 DuckDB 最新可用日期，但正文不能生成目标日期市场结论。
- DuckDB fallback 应写入 `data_sources_used`，并在技术参考中说明是降级读取。

验收标准：

- Parquet 缺失但 DuckDB 有同日主表时，`market_width` 可用。
- Parquet 为空且 DuckDB 同日无主表时，仍 blocked。
- DuckDB 查询成功但 count 为 0 时，不应标记为 passed。

### P1：Raw replay CLI

目标：当接口 raw response 已存在但标准化或写库失败时，不再调用 AKShare，直接重放本地 raw。

建议入口：

```bash
python -m a_share_info_hub daily-update --trade-date 2026-06-20 --from-raw
```

第一版范围应保持小：

- 只读取 `data/raw/<trade_date>/<source>/response.json` 和 `metadata.json`。
- 复用现有 normalize 函数和标准表写入函数。
- 缺少 raw response 的接口保持 failed，不伪造数据。
- raw replay 仍必须遵守主表写入前保护。

### P2：按日期保存标准化 Parquet

目标：减少固定文件覆盖带来的历史回看风险。

可选结构：

```text
data/normalized/latest/*.parquet
data/normalized/by_trade_date/YYYY-MM-DD/*.parquet
```

这是结构性改造，不建议作为第一步。P0 写入前保护更小、更直接。

### P2：告警增强

当前 watchdog 可以发现 job 层失败，但建议增加数据质量专项告警：

- 主表行数为 0：critical。
- 主表行数低于 `min_main_rows`：critical。
- `overall_status=failed` 且存在 Parquet/DuckDB 写入动作：critical，提示可能需要恢复。
- DuckDB 同日 count 为 0 但状态可查询：warning 或 failed。

## 补救优先级

| 优先级 | 操作 | 适用场景 | 风险 |
| --- | --- | --- | --- |
| 立即 | 成功重跑 `daily-update` | AKShare 临时失败、网络抖动、DuckDB 临时故障 | 当前实现下，失败重跑仍可能覆盖已有同日数据 |
| 立即 | 隔离 output root 验证接口恢复 | 已有同日成功数据需要保护 | 需要手工比对再写回 |
| P0 | 主表无效时跳过 Parquet/DuckDB 写入 | 主接口失败、主表 schema changed、主表行数过低 | 最小代码改动，收益最高 |
| P0 | DuckDB 空主表防御 | 防止新入口误用写库函数 | 需要明确返回状态语义 |
| P1 | Daily Review DuckDB 同日回退 | Parquet 被误删、固定 Parquet 只保留最新日 | 必须避免跨日期误用 |
| P1 | Raw replay CLI | raw 成功但标准化/写库失败 | 对真实接口失败无效 |
| P2 | 日期分区 Parquet | 需要长期可回看标准化文件 | 结构改动更大 |

## 建议测试清单

1. 主接口失败不覆盖已有 Parquet。
2. 主接口失败不替换 DuckDB 同日已有记录。
3. 主接口失败但增强接口成功时，不把增强表写入持久层，或至少不让 failed 数据包污染同日历史。
4. 交易日历失败只写状态报告，不写 raw、Parquet、DuckDB。
5. DuckDB 写入失败时，Parquet 可用，Daily Review 降级为 partial，并记录 `duckdb` blocked。
6. Parquet 缺失但 DuckDB 有同日数据时，Daily Review fallback 可生成同日 evidence packet。
7. DuckDB 查询 count 为 0 时，DuckDB health 不应标记为 passed。
8. Raw replay 只使用已有 `response.json`，缺失 raw 的接口保持 failed。

## Review 需要确认的问题

1. `data/normalized/*.parquet` 是否只定位为“最新可用缓存”？如果是，应明确禁止空主表覆盖；如果不是，应改为按日期分区。
2. 主表失败时，是否允许增强表继续落 DuckDB？建议不允许，因为没有主表基准时增强数据无法构成完整当日数据包。
3. Daily Review 是否可以在用户请求某交易日时自动使用“最新可用日期”？建议不可以，只能作为技术参考提示。
4. Raw replay 第一版是否只覆盖“raw response 已存在”的重放？建议是，避免引入对外部接口的第二套调用路径。

## 推荐结论

先做 P0：把主表有效性作为 Parquet 和 DuckDB 的共同写入门禁，并为 DuckDB 增加空主表防御。这是最小且收益最高的改动，可以直接消除主接口失败覆盖标准化层的核心风险。

随后做 P1：给 Daily Review 增加 DuckDB 同日 fallback，并补 raw replay CLI。这样即使 Parquet 缓存被误清或标准化写入失败，仍可从历史库或 raw 审计数据恢复研究 evidence packet。
