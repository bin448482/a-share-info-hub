# 每日 A 股快照数据实施计划

本文档用于 review `daily-snapshot-data-design.md` 的落地方式。当前阶段只定义实施路径、输出文件、阻断条件和验收标准；接口真实可用性、字段稳定性和行数只能在实施运行后写入报告，不能在本文档中当作已验证事实。

## 背景和目标

`daily-snapshot-data-design.md` 已经冻结 v1 数据边界：每天以 `stock_zh_a_spot` 作为全 A 股主快照，再独立保存涨跌停、龙虎榜、市场背景、行业板块和概念板块增强数据。第一版不做预测、不做交易建议、不引入 PostgreSQL，也不把事件数据补齐成全股票字段。

实施目标是生成一条可重复运行的每日采集链路：

1. 保存外部接口原始返回，保留审计证据。
2. 将主表和增强数据标准化为独立表。
3. 将标准化表写入本地 Parquet/CSV 和 `market.duckdb`。
4. 记录成功、失败、空结果和字段变化。
5. 采集前验证目标日期是否为 A 股交易日，非交易日不调用行情接口。
6. 生成每日可读摘要，说明当天数据包是否满足 v1 验收标准。

## 核心假设

- 项目 Python 环境可安装并导入 `akshare`、`pandas`、`duckdb` 和 `pyarrow`。
- 每日运行日期默认使用本地日期；指定 `--trade-date` 时按指定日期验证是否为 A 股交易日。
- 交易日判断使用本地周末规则和 AKShare 交易日历接口；非交易日必须跳过行情采集。
- 交易日历不可用或字段异常时，当日整体状态为 `failed`，且不能继续调用行情接口。
- `stock_zh_a_spot` 是 v1 主表入口；若该接口失败或主表为空，当日快照状态必须标记为失败。
- 增强接口失败不阻断主表落盘，但必须进入接口状态报告和失败日志。
- 原始数据文件是审计依据，DuckDB 只是查询和分析层，不是唯一事实来源。

## 实施工作 DAG

1. 依赖和目录准备
   - 输入：`requirements.txt`、设计文档中的存储结构。
   - 输出：补齐运行依赖；创建真实承载数据的 `data/`、`logs/`、`reports/daily-runs/` 目录及目录规则文件。
   - 依赖：无。
   - 触碰模块：`requirements.txt`、新增目录的 `AGENTS.md` 和 `claude.md`。
   - 风险：只为规范创建空目录会违反仓库规则。
   - 验证：目录只在有真实输出或说明用途时创建；每个新增目录都有规则文件。

2. 交易日门禁
   - 输入：目标日期、AKShare 交易日历。
   - 输出：`trading_day_check` 状态，写入 `interface-status.json` 和 `daily-data-summary.md`。
   - 依赖：依赖安装完成。
   - 触碰模块：每日采集入口和状态报告。
   - 风险：把非交易日误当成接口失败，或在交易日历不可验证时继续采集。
   - 验证：周末或交易日历未列出的日期返回 `skipped`，不调用行情接口；交易日历异常返回 `failed`，不调用行情接口。

3. 外部接口调用和原始落盘
   - 输入：交易日期、v1 固定接口清单。
   - 输出：`data/raw/YYYY-MM-DD/<source>/response.*` 和 `metadata.json`。
   - 依赖：交易日门禁确认目标日期为交易日。
   - 触碰模块：新增每日采集脚本。
   - 风险：接口失败、空返回、网络超时、字段变化。
   - 验证：每个接口都有 `status`、`row_count`、`columns`、`failure_reason` 和 `fetched_at`；失败不静默吞掉。

4. 主表标准化
   - 输入：`stock_zh_a_spot` 原始返回和元数据。
   - 输出：`data/normalized/daily_stock_snapshot.parquet`。
   - 依赖：主表原始落盘成功且非空。
   - 触碰模块：标准化函数或脚本。
   - 风险：原始字段缺失、列名变化、数值类型不可解析。
   - 验证：标准字段包含 `trade_date`、`symbol`、`name`、价格、成交、`snapshot_time`、`fetched_at`、`source`；主表为空或关键字段缺失时阻断当日成功状态。

5. 增强表标准化
   - 输入：涨跌停池、龙虎榜、市场汇总、板块快照原始返回。
   - 输出：`limit_pool_events.parquet`、`lhb_events.parquet`、`market_summary.parquet`、`board_snapshot.parquet`。
   - 依赖：对应接口已尝试调用并写入状态。
   - 触碰模块：增强表解析和标准化逻辑。
   - 风险：事件型数据自然为空；不同来源字段不一致。
   - 验证：空事件集记录为 `success_empty` 或等价状态，不补齐到主表；每条增强记录保留 `trade_date`、来源和可关联键。

6. DuckDB 分析库注册
   - 输入：标准化 Parquet/CSV 输出。
   - 输出：`market.duckdb` 中可查询的标准化表。
   - 依赖：标准化文件生成完成。
   - 触碰模块：DuckDB 写入或注册脚本。
   - 风险：重复运行导致重复行或旧数据覆盖不清晰。
   - 验证：同一 `trade_date` 重跑采用明确的替换策略；可查询主表和增强表行数。

7. 失败日志和接口状态报告
   - 输入：每个接口调用结果、解析结果和标准化结果。
   - 输出：`logs/external-interface-failures.jsonl`、`reports/daily-runs/YYYY-MM-DD/interface-status.json`。
   - 依赖：接口调用和标准化已完成。
   - 触碰模块：状态聚合逻辑。
   - 风险：把真实空结果、调用失败和解析失败混成一种状态。
   - 验证：状态至少区分 `success`、`success_empty`、`failed`、`schema_changed`；失败日志包含 `raw_path` 或明确说明无原始文件。

8. 每日摘要报告
   - 输入：接口状态、主表统计、增强表统计、失败日志摘要。
   - 输出：`reports/daily-runs/YYYY-MM-DD/daily-data-summary.md`。
   - 依赖：接口状态报告完成。
   - 触碰模块：报告生成逻辑。
   - 风险：报告把未获取数据写成可用，或隐藏增强接口失败。
   - 验证：摘要明确主表是否成功、每类增强是否成功/为空/失败、当日是否满足 v1 验收标准。

9. 端到端验证
   - 输入：一个指定 `trade_date` 的完整运行。
   - 输出：验证记录和可复查命令。
   - 依赖：前 7 项完成。
   - 触碰模块：测试或验证脚本。
   - 风险：只做语法检查，没有验证输出契约。
   - 验证：至少执行编译检查、一次 dry-run 或小范围真实运行、输出文件存在性检查、DuckDB 查询检查。

## 核心契约

实施前冻结以下契约，避免边写边改语义：

- 主表契约：`daily_stock_snapshot` 只来自 `stock_zh_a_spot`，不由增强数据补齐。
- 增强契约：涨跌停、龙虎榜、市场汇总、板块快照都是独立表。
- 关联键：个股增强用 `trade_date + symbol`，市场增强用 `trade_date`，板块增强用 `trade_date + board_code/board_name`。
- 状态契约：接口状态必须区分成功、空结果、失败和字段变化。
- 存储契约：原始返回先落盘，标准化数据再写入分析层。
- 交易日契约：只有交易日门禁确认目标日期为交易日，才允许调用行情接口。
- 运行契约：主表失败阻断当日快照成功；增强失败不阻断主表，但必须暴露。

## 建议文件结构

```text
data/
  AGENTS.md
  claude.md
  raw/
    AGENTS.md
    claude.md
    YYYY-MM-DD/
      <source-name>/
        response.json
        metadata.json
  normalized/
    AGENTS.md
    claude.md
    daily_stock_snapshot.parquet
    limit_pool_events.parquet
    lhb_events.parquet
    market_summary.parquet
    board_snapshot.parquet
logs/
  AGENTS.md
  claude.md
  external-interface-failures.jsonl
reports/
  AGENTS.md
  claude.md
  daily-runs/
    AGENTS.md
    claude.md
    YYYY-MM-DD/
      interface-status.json
      daily-data-summary.md
market.duckdb
```

`reports/` 当前在工作区中存在删除状态的旧探测产物；本实施不应恢复或覆盖这些旧文件，除非后续任务明确要求。

## 脚本入口建议

第一版保持日常入口少而清晰，统一通过仓库 CLI 调用：

```text
python -m a_share_info_hub daily-update
```

建议参数：

- `--trade-date YYYY-MM-DD`：指定数据所属日期；不传时默认使用运行当天。
- `--output-root .`：指定项目根目录，默认当前工作区。
- `--request-timeout 12`：外部请求超时。
- `--max-retries 2`：接口调用重试次数。
- `--skip-duckdb`：仅用于定位 DuckDB 写入问题；默认不跳过。
- `--ignore-proxy`：忽略 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY` 等环境代理；仅在代理导致 AKShare 接口失败时使用，并需在最终验证说明中注明。

CLI 的 `daily-update` 子命令负责一次完整每日运行。内部可以复用脚本模块，但 README 和日常调度不应 hard code `scripts/collect_daily_snapshot.py`。

## 数据状态语义

接口级状态：

- `success`：调用成功，返回非空且字段可解析。
- `success_empty`：调用成功但自然无事件或返回空。
- `ignored`：增强接口命中已知临时忽略规则；当前仅用于 Eastmoney `push2.eastmoney.com` 代理断连问题。
- `failed`：接口调用失败、网络失败或上游错误。
- `schema_changed`：调用成功但缺少必需字段或字段无法映射。

当日整体状态：

- `passed`：主表成功非空，标准化和 DuckDB 写入成功，增强接口状态全部可解释；`ignored` 不降低整体状态。
- `partial`：主表成功，但一个或多个增强接口失败或字段变化。
- `skipped`：目标日期已验证为非交易日；未调用行情接口，未写入原始行情、标准化表或 DuckDB。
- `failed`：主表失败、主表为空、主表关键字段缺失，或标准化主表无法写入。

## 异常处理

异常处理的目标不是让脚本“尽量成功”，而是让每种失败都可复查、可定位、不会被误写成有效数据。

### 外部接口异常

- 接口调用超时、连接失败、上游返回异常或 AKShare 抛错时，接口状态记为 `failed`。
- 失败接口必须记录 `function_name`、`params`、异常类型、异常摘要、重试次数和 `fetched_at`。
- 如果调用前已经创建了原始目录但没有有效响应文件，`metadata.json` 必须写明 `raw_path: null` 或等价字段。
- 主表接口失败时，当日整体状态为 `failed`；增强接口失败时，当日整体状态最高只能是 `partial`。
- 增强接口命中 Eastmoney `push2.eastmoney.com` 代理断连时，接口状态记为 `ignored`，不写入外部接口失败日志，也不把整体状态降级；主表接口即使命中同类错误也不能忽略。

### 交易日验证异常

- `daily-update` 必须先验证目标日期是否为 A 股交易日，再调用主表或增强接口。
- 周末日期直接视为非交易日；工作日需通过 AKShare 交易日历确认。
- 目标日期不是交易日时，当日整体状态为 `skipped`，退出码为 0，只生成 `interface-status.json` 和 `daily-data-summary.md`。
- `skipped` 状态下不得创建目标日期的原始行情目录，不得写入标准化表或 DuckDB。
- 交易日历接口失败、缺少 `trade_date` 字段或无法解析日期时，当日整体状态为 `failed`，退出码为 1，且不得继续调用行情接口。
- `interface-status.json` 必须包含 `trading_day_check`，说明检查状态、是否交易日、来源和原因。

### 空结果异常

- 主表返回空结果时，当日整体状态为 `failed`。
- 事件型增强接口返回空结果时，状态为 `success_empty`，不是失败，也不能补齐到主表。
- 市场汇总或板块快照返回空结果时，先按 `success_empty` 记录，再在每日摘要中列为需要复查的数据缺口。
- 空结果必须保留元数据，不能只跳过输出。

### 字段和 schema 异常

- 原始字段缺少主表必需字段时，接口状态记为 `schema_changed`，当日整体状态为 `failed`。
- 增强表字段缺失但仍可保留部分原始数据时，原始文件继续保存，标准化表可以跳过该来源，当日整体状态为 `partial`。
- 字段映射失败必须记录缺失字段、实际字段列表和目标标准字段。
- 不允许用空列、默认值或猜测字段名来伪造标准化通过。

### 文件和落盘异常

- 原始文件写入失败时，不能继续把该接口当作可审计数据。
- 标准化主表写入失败时，当日整体状态为 `failed`。
- 增强标准化表写入失败时，当日整体状态最高只能是 `partial`。
- 每次写入关键 JSON、Parquet 或 Markdown 后，应做一次文件存在性和可读取性检查。

### DuckDB 异常

- DuckDB 写入失败时，默认当日整体状态为 `failed`。
- 只有显式使用 `--skip-duckdb` 时，脚本才允许跳过 DuckDB 写入；每日摘要必须标记 `duckdb_status: skipped`，不能标记为完整通过。
- 重跑同一 `trade_date` 时必须先删除或替换该日期旧记录，避免重复行。

### 报告生成异常

- `interface-status.json` 生成失败时，当日整体状态为 `failed`。
- `daily-data-summary.md` 生成失败时，当日整体状态为 `failed`，因为 review 无法确认当日边界。
- 报告生成失败不能删除已经落盘的原始数据和标准化数据；应保留它们用于排查。

## 验收标准

v1 实施完成后必须同时满足：

- 能用一个脚本执行指定日期的每日采集。
- 非交易日运行应返回 `skipped`，并确认没有调用行情接口。
- `stock_zh_a_spot` 原始返回和元数据保存到 `data/raw/YYYY-MM-DD/stock_zh_a_spot/`。
- 主表标准化结果写入 `data/normalized/daily_stock_snapshot.parquet`。
- 涨跌停池、龙虎榜、市场汇总、板块快照分别写入独立标准化表。
- `market.duckdb` 可查询主表和增强表。
- `reports/daily-runs/YYYY-MM-DD/interface-status.json` 记录每个接口状态。
- `reports/daily-runs/YYYY-MM-DD/daily-data-summary.md` 明确说明主表、增强表、失败项和当日整体状态。
- 接口失败、空返回和字段变化写入可复查状态；失败项追加到 `logs/external-interface-failures.jsonl`。
- 任一增强接口失败不影响主表落盘，但报告必须标记当日为 `partial`。
- 不生成预测、交易建议或历史回放承诺。

## 目标达成条件

本实施只有在以下条件全部满足后，才能声明“目标达成”：

1. 实现完成
   - 存在一个可执行 CLI 入口 `python -m a_share_info_hub daily-update`。
   - 入口支持默认当天运行，也支持通过 `--trade-date` 指定日期。
   - 交易日能完成采集、原始落盘、标准化、DuckDB 写入和日报告生成。
   - 非交易日能生成 `skipped` 状态报告，并且不调用行情接口。
   - 新增真实承载输出的目录时，同步添加对应 `AGENTS.md` 和 `claude.md`。

2. 契约满足
   - 主表只由 `stock_zh_a_spot` 生成。
   - 增强数据保持独立表，不覆盖主表字段。
   - 接口状态清楚区分 `success`、`success_empty`、`failed` 和 `schema_changed`。
   - 当日整体状态清楚区分 `passed`、`partial`、`skipped` 和 `failed`。
   - 原始数据、标准化数据、DuckDB、失败日志和每日摘要之间可以互相追溯。

3. 测试满足
   - 单元测试覆盖主表标准化、增强表标准化、状态归类、失败日志和报告摘要生成。
   - 单元测试不依赖真实 AKShare 网络调用。
   - 至少有一个 mock 或 fixture 场景覆盖主表失败，并确认当日状态为 `failed`。
   - 至少有一个 mock 或 fixture 场景覆盖增强接口为空，并确认当日状态不是 `failed`。
   - 至少有一个 mock 或 fixture 场景覆盖非交易日，并确认状态为 `skipped` 且行情接口未被调用。
   - 至少有一个 mock 或 fixture 场景覆盖交易日历不可用，并确认状态为 `failed` 且行情接口未被调用。

4. 验证满足
   - `python -m py_compile a_share_info_hub/__main__.py scripts/collect_daily_snapshot.py` 通过。
   - 单元测试命令通过。
   - 依赖导入检查通过。
   - 指定日期运行后，输出文件路径、JSON 可解析性、Parquet 可读取性和 DuckDB 查询检查通过。

5. 文档满足
   - `docs/daily-snapshot-data-design.md` 和本文档没有互相冲突的状态语义。
   - 如实施新增脚本、目录或运行命令，对应 README、`AGENTS.md` 或目录说明已同步更新。
   - 最终说明必须列出已运行的验证命令和未运行的验证项。

## 单元测试计划

单元测试验证本地逻辑，不验证 AKShare 当天真实可用性。真实接口调用属于集成验证或验收验证，不能用单元测试结果替代。

建议测试目录：

```text
tests/
  AGENTS.md
  claude.md
  fixtures/
    AGENTS.md
    claude.md
    stock_zh_a_spot_success.json
    stock_zh_a_spot_empty.json
    limit_pool_empty.json
    lhb_schema_changed.json
  test_daily_snapshot_normalization.py
  test_daily_snapshot_status.py
  test_daily_snapshot_outputs.py
```

建议测试用例：

1. 主表标准化成功
   - 输入：包含设计文档必需字段的 `stock_zh_a_spot` fixture。
   - 断言：输出包含标准字段；`trade_date`、`symbol`、`source` 和 `fetched_at` 存在；状态为 `success`。

2. 主表为空
   - 输入：空列表或空 DataFrame fixture。
   - 断言：主表状态为 `success_empty` 或等价接口状态；当日整体状态为 `failed`；不生成有效主表标准化记录。

3. 主表字段变化
   - 输入：缺少 `代码`、`名称` 或价格关键字段的 fixture。
   - 断言：状态为 `schema_changed`；记录缺失字段；当日整体状态为 `failed`。

4. 增强接口为空
   - 输入：涨跌停或龙虎榜空 fixture。
   - 断言：接口状态为 `success_empty`；当日整体状态不因该接口变成 `failed`；摘要中能看到空事件说明。

5. 增强字段变化
   - 输入：缺少可关联字段的增强 fixture。
   - 断言：该增强来源状态为 `schema_changed`；主表成功时当日整体状态为 `partial`。

6. 非交易日跳过
   - 输入：周末日期，或工作日但交易日历不包含该日期。
   - 断言：当日整体状态为 `skipped`；`trading_day_check.is_trading_day` 为 `false`；主表和增强接口均未调用；不写原始行情目录。

7. 交易日历不可用
   - 输入：交易日历接口抛错、缺少 `trade_date` 字段或日期不可解析。
   - 断言：当日整体状态为 `failed`；主表和增强接口均未调用；摘要写明交易日历验证失败。

8. 失败日志写入
   - 输入：模拟接口异常。
   - 断言：`external-interface-failures.jsonl` 追加一行 JSON；包含 `trade_date`、`function_name`、`failure_type`、`failure_reason` 和 `raw_path`。

9. 原始文件和元数据落盘
   - 输入：成功 fixture 和失败 fixture。
   - 断言：成功接口写入响应文件和 `metadata.json`；失败接口写入失败元数据；关键 JSON 可解析。

10. DuckDB 重跑替换
   - 输入：同一 `trade_date` 两次写入不同 fixture。
   - 断言：第二次运行后指定日期没有重复行，查询结果与第二次 fixture 一致。

11. 每日摘要生成
   - 输入：混合状态的 `interface-status.json` fixture。
   - 断言：摘要包含主表状态、增强失败项、空事件项、整体状态和“不做预测/交易建议”边界。

建议命令：

```text
python -m pytest tests
```

如果第一版暂不引入 `pytest`，则至少提供一个标准库 `unittest` 测试入口，并在实施时把实际命令写入最终验证记录。

## 验证顺序

1. 静态检查
   - 命令：`python -m py_compile a_share_info_hub/__main__.py scripts/collect_daily_snapshot.py`
   - 通过标准：CLI 和采集实现可编译。

2. 单元测试
   - 命令：`python -m pytest tests` 或实施时选定的等价命令。
   - 通过标准：本地 fixture/mock 测试全部通过；不依赖真实网络。

3. 依赖检查
   - 命令：`python -c "import akshare, pandas, duckdb, pyarrow"`
   - 通过标准：所有运行依赖可导入。

4. 单日运行
   - 命令：`python -m a_share_info_hub daily-update --trade-date <YYYY-MM-DD>`
   - 通过标准：交易日脚本退出码为 0；非交易日脚本退出码为 0 且状态为 `skipped`；若主表失败或交易日历无法验证，必须生成失败状态报告并以明确错误结束。

5. 输出文件检查
   - 检查：原始文件、元数据、标准化文件、失败日志、接口状态和每日摘要是否存在。
   - 通过标准：文件路径与设计文档一致；没有只打印不落盘的关键结果。

6. DuckDB 查询检查
   - 检查：查询 `daily_stock_snapshot`、`limit_pool_events`、`lhb_events`、`market_summary`、`board_snapshot` 的指定日期行数。
   - 通过标准：主表行数大于 0；增强表可以为空但状态必须可解释。

## 阻断条件

遇到以下情况应停止声明当日运行成功：

- 主表接口调用失败。
- 交易日历无法验证目标日期是否为交易日。
- 主表返回空结果。
- 主表关键字段缺失或无法标准化。
- 主表标准化文件无法写入。
- DuckDB 写入失败且未显式使用 `--skip-duckdb`。
- 接口状态报告无法生成。

遇到以下情况不阻断主表落盘，但必须标记为 `partial`：

- 任一增强接口调用失败。
- 任一增强接口字段变化导致无法标准化。
- 事件型增强接口返回空。
- 板块或市场背景接口失败。

遇到以下情况不进入行情采集，也不视为失败：

- 目标日期是周末。
- 目标日期不在 AKShare 交易日历中。

## 不做事项

- 不做预测。
- 不做交易建议。
- 不做资金流和融资融券数据采集。
- 不做 `stock_zh_a_spot` 历史回放。
- 不把事件数据补齐成全股票字段。
- 不在没有映射依据时把板块数据写入每只股票。
- 不把接口实测尚未发生的结果写成事实。
- 不为未来模型训练提前设计复杂抽象层。
