# 代码瘦身重构实施计划

本文档用于 review 本次只读扫描后发现的代码瘦身重构改动。当前阶段只定义实施范围、目标达成条件、工作 DAG、风险和验证方式；不把尚未执行的测试结果写成事实。

## 背景和目标

仓库当前主要实现已经可运行，但存在少量低风险重复逻辑、死代码、无用参数和一次性 wrapper。第一版重构目标不是重写架构，而是用最小改动降低维护成本。

实施目标：

1. 删除确认无调用点的死代码和无效参数。
2. 收敛 `daily_review.py` 内部重复的日期校验和 citation 清洗逻辑。
3. 删除少量只包一层、没有业务含义的一次性 helper。
4. 保持 CLI、报告结构、数据状态语义和 skill 镜像规则不变。
5. 用现有测试验证行为未变。

## 非目标

- 不重写每日采集链路。
- 不改报告内容语义、HTML 结构或 JSON schema。
- 不新增依赖。
- 不新增共享模块来抽两个脚本之间的小重复；两处重复还没大到值得引入新层。
- 不改 `.claude/skills/`、`.agents/skills/` 和 `skills/` 的镜像结构。
- 不删除暂时无法确认用途的 fixture 或文档。

## 目标达成条件

完成后必须同时满足：

1. `python -m pytest` 通过。
2. CLI 帮助命令仍可执行：
   - `python -m a_share_info_hub daily-update --help`
   - `python -m a_share_info_hub daily-review --help`
3. 被删除的函数、参数或 fixture 名称经搜索确认无有效调用点。
4. `daily_review.py` 的日期校验错误文案保持原字段名语义，例如 `trade_date must be formatted as YYYY-MM-DD`。
5. external background citation 的过滤条件保持不变：缺少 `source_name` 或 `url` 的引用仍被跳过。
6. 不产生新的顶层文件或目录；若新增、删除、改名、移动文件，必须同步更新对应目录 `AGENTS.md`。
7. `git diff` 中每一行改动都能对应本计划中的工作项。

## 核心契约

实施前冻结以下契约：

- CLI 契约：继续通过 `python -m a_share_info_hub daily-update` 和 `python -m a_share_info_hub daily-review` 调用。
- 数据契约：不改变 Parquet、DuckDB、`review-context.json`、`llm-review-sections.json`、HTML 和技术 Markdown 的字段含义。
- 状态契约：不改变 `passed`、`partial`、`skipped`、`failed`、`missing`、`blocked`、`invalid` 等状态语义。
- external background 契约：仍只接受带来源和 URL 的引用；外部背景不得变成独立报告章节。
- 目录规则契约：新增本实施文档后，只同步 `docs/AGENTS.md` 索引。

## 实施工作 DAG

### A. 删除确定无用代码和无用参数

- 输入：全仓库搜索结果。
- 输出：删除确认无调用点的函数，删除无用参数。
- 依赖：无。
- 触碰文件：
  - `a_share_info_hub/daily_review.py`
  - `scripts/generate_daily_data_contract_report.py`
- 风险：函数存在动态调用或文档引用。
- 验证：
  - 搜索函数名或参数名确认无有效调用点。
  - 运行相关测试和全量测试。

计划改动：

1. 删除 `a_share_info_hub/daily_review.py` 中未使用的 `merge_paragraphs()`。
2. 删除 `a_share_info_hub/daily_review.py` 中未使用的 `format_counts()`。
3. 保留 `scripts/generate_daily_data_contract_report.py` 中 `build_candidate_interfaces(probe_date)`：实施前复核确认 `probe_date` 用于构造候选接口的日期参数，不是无用参数。

### B. 收敛 `daily_review.py` 内部重复逻辑

- 输入：当前 Pydantic validator 和 external background citation 清洗函数。
- 输出：减少重复代码，保持行为不变。
- 依赖：A 可独立，但建议 A 后执行，便于审阅 diff。
- 触碰文件：
  - `a_share_info_hub/daily_review.py`
- 风险：错误文案变化导致测试或调用方误读。
- 验证：
  - `tests/test_daily_review.py` 通过。
  - 全量 `python -m pytest` 通过。

计划改动：

1. 新增一个文件内私有 helper，例如 `_validate_report_date(value: str, field_name: str) -> str`，替代三处重复的 `REPORT_DATE_RE.fullmatch` 校验。
2. 新增一个文件内私有 helper，例如 `_coerce_external_citation(citation: ExternalBackgroundRawCitation) -> ExternalBackgroundCitation | None`，替代两处重复的 citation strip 和构造逻辑。

边界：只抽文件内 helper，不新增模块。

### C. 删除一次性 wrapper

- 输入：只包一层且没有业务语义的 helper。
- 输出：减少跳转和维护面。
- 依赖：A、B 完成后执行。
- 触碰文件：
  - `scripts/collect_daily_snapshot.py`
  - `scripts/generate_daily_data_contract_report.py`
- 风险：为了少量行数制造更难读的内联代码。
- 验证：
  - `tests/test_daily_snapshot_*.py` 通过。
  - 全量 `python -m pytest` 通过。

计划改动：

1. 删除 `scripts/generate_daily_data_contract_report.py` 中只等于 `asdict(spec)` 的 `spec_to_dict()`，调用点直接用 `asdict(spec)`。
2. 检查 `scripts/collect_daily_snapshot.py` 中 `dataframe_to_records()`、`build_empty_standard_tables()`、`table_name_for_category()` 的调用点；只有在确认单调用且内联后更清楚时才删除。

边界：若内联让代码更长或更难读，则跳过该项。

### D. 暂不删除测试 fixture

- 输入：`tests/fixtures/stock_zh_a_spot_empty.json` 和 `tests/fixtures/limit_pool_empty.json` 当前引用情况。
- 输出：本轮默认不删除。
- 依赖：无。
- 触碰文件：无。
- 风险：误删未来计划覆盖的空数据场景。
- 验证：无改动，无需验证。

理由：这两个 fixture 虽未被当前测试引用，但空结果场景是数据采集边界中的有效场景。删除收益很小，误删成本更高。

### E. 暂不处理 eval provider 去重

- 输入：`eval/providers/run-a-share-daily-review.js` 中 legacy/fusion fixture 重复 payload。
- 输出：本轮默认不改。
- 依赖：无。
- 触碰文件：无。
- 风险：改动本地黄金测试 fixture 生成逻辑，导致评测语义漂移。
- 验证：无改动，无需验证。

理由：provider 重复代码有一点维护成本，但本轮目标是低风险 Python 瘦身；eval fixture 行为更接近测试契约，先不碰。

## 实施复核记录

- `build_candidate_interfaces(probe_date)` 的 `probe_date` 已复核为有效输入：候选接口中的 `today_params` 会使用它生成当日探测参数，因此不删除该参数。

## 建议执行顺序

```text
1. A 删除死代码和无用参数 -> 验证：搜索无调用点
2. B 收敛 daily_review.py 重复逻辑 -> 验证：tests/test_daily_review.py
3. C 删除确认值得删的一次性 wrapper -> 验证：tests/test_daily_snapshot_*.py
4. 全量验证 -> python -m pytest + 两个 CLI --help
```

## 最小可交付范围

若 review 后希望进一步降低风险，只执行 A + B。

C 是可选瘦身项：只有在调用点确认简单、diff 更短且可读性不下降时才实施。

D 和 E 本轮明确跳过。

## 回滚方式

本次应是小 diff。若任一测试失败且不能用同等小改动修复，则回滚对应工作项，不扩大重构范围。
