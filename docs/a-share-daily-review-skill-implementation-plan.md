# A 股每日复盘研究 Skill v2 实施计划

本文档用于 review `a-share-daily-review` skill 的 v2 重构方案。当前仓库已有 `daily-review` CLI、源 skill、HTML 输出、用户指南、黄金测试集和 Promptfoo 配置；旧版 HTML 报告由 Python 直接拼接生成，机器元数据暴露在正文首屏，缺少 LLM 分析表达层。本次重构目标是把“确定性证据和运行时护栏”与“用户可读分析报告”拆开。当前仓库已按本文档完成 v2 实施，本文档同时保留目标、验收条件和已运行验证记录。

## 背景和问题

当前每日数据刷新入口是仓库公开 CLI：

```text
python -m a_share_info_hub daily-update
```

当前每日复盘入口是：

```text
python -m a_share_info_hub daily-review
```

现有 `daily-review` 实现可以读取本地 artifacts 并生成 HTML，但报告正文更像调试输出，典型问题包括：

- `analysis_mode`、`data_status`、`blocked_sections` 等机器契约字段以裸文本出现在用户报告顶部。
- Python 直接拼接 Markdown/HTML，LLM 没有参与报告的分析表达。
- 用户期待的“交易员视角复盘”没有被转化为自然语言分析，只是结构化统计映射。
- 测试主要验证固定字符串存在，无法评估报告是否真的尊重证据边界并具备可读性。

结论：Python 仍必须负责数据契约、状态判断、证据边界和最终校验；但最终用户可读报告应由 LLM 基于受控 evidence packet 生成，再由 Python 校验和封装。

## 目标

1. 保留仓库 CLI 作为每日更新和复盘的公开入口，不 hard code 脚本路径、交易日期或本机绝对路径。
2. Python 只生成可验证的 `review-context.json` evidence packet，不直接承担最终分析表达。
3. LLM 基于 `review-context.json` 和提示词生成结构化分析内容。
4. Python 使用 `pydantic>=2.0,<3` 校验 evidence packet、LLM 输出和最终报告元数据。
5. Python 负责最终 HTML 封装，避免裸露机器字段，同时保留可审计 metadata。
6. Promptfoo 只作为黄金测试和回归评测框架，不进入正常日报生成路径。
7. 所有输出保持 `research_only` 和 `not_investment_advice` 边界，不提供交易行动建议。

## 不做事项

- 不做买入、卖出、持有、加仓、减仓建议。
- 不做仓位、目标价、止盈止损或实盘时点建议。
- 不生成“明日必涨”“确定性主线”“强烈看多/看空并执行交易”等交易行动语言。
- 不在单日快照基础上生成历史趋势、胜率、回测收益或个股强势概率。
- 不让 LLM 自行读取未进入 evidence packet 的本地文件。
- 不让 LLM 推断 `blocked_sections` 对应的缺失维度。
- 不把 Promptfoo 当成生产运行时校验器。
- 不绕过仓库 CLI 直接调用 `scripts/collect_daily_snapshot.py` 作为日常数据刷新入口。

## 目标架构

```text
daily-update CLI
  -> reports/daily-runs/YYYY-MM-DD/
  -> data/normalized/*.parquet
  -> market.duckdb

daily-review context
  -> Python 读取 artifacts
  -> Pydantic 校验 ReviewContext
  -> reports/daily-reviews/YYYY-MM-DD/review-context.json

LLM analysis
  -> 输入 review-context.json 和 report prompt
  -> 输出结构化 JSON sections 或 Markdown sections
  -> Pydantic 校验 LlmReviewSections

daily-review render
  -> Python 校验禁用语言、blocked sections、必需声明
  -> 生成 reports/daily-reviews/YYYY-MM-DD/a-share-daily-review.html
```

核心原则：

- Python 决定“能不能分析”和“哪些事实可用”。
- LLM 只决定“如何把已允许事实写成可读研究报告”。
- Pydantic 只做 schema、字段、枚举、格式、必填项和结构边界校验。
- 业务接受规则由 Python 显式代码处理，例如 blocked section 禁止引用、交易建议禁用词、状态降级。
- Promptfoo 用于离线黄金测试，不阻塞正常用户调用路径。

## 输入契约

Skill 读取当前仓库 artifacts。默认不刷新数据，除非用户明确要求刷新。

| 参数 | 默认值 | 含义 |
| --- | --- | --- |
| `trade_date` | 最近一次 daily run | 指定要分析的交易日期，格式为 `YYYY-MM-DD`。 |
| `refresh_mode` | `none` | `none` 只分析已有数据；`daily_update` 先调用仓库 CLI 刷新数据。 |
| `output_format` | `html` | `html` 生成可打开报告；`inline` 直接返回研究建议；`context` 只生成 evidence packet。 |
| `render_mode` | `llm` | `llm` 使用 LLM 分析层；`deterministic` 只生成诊断/调试报告。 |
| `output_root` | 仓库根目录 | 从当前工作区推导，不写死本机绝对路径。 |

可读取的数据：

- `market.duckdb`
- `data/normalized/daily_stock_snapshot.parquet`
- `data/normalized/limit_pool_events.parquet`
- `data/normalized/lhb_events.parquet`
- `data/normalized/market_summary.parquet`
- `data/normalized/board_snapshot.parquet`
- `reports/daily-runs/YYYY-MM-DD/interface-status.json`
- `reports/daily-runs/YYYY-MM-DD/daily-data-summary.md`
- `logs/external-interface-failures.jsonl`

## CLI 刷新契约

当用户明确要求刷新数据，或 `refresh_mode=daily_update` 时，skill 只能调用仓库公开 CLI：

```text
python -m a_share_info_hub daily-update --trade-date <YYYY-MM-DD>
```

实施要求：

- Python 可执行程序来自当前运行环境，不写死为 `python.exe` 绝对路径。
- 模块入口固定为公开契约 `-m a_share_info_hub daily-update`。
- `trade_date`、`ignore_proxy`、`output_root` 等参数来自用户输入或上层配置。
- 不直接调用 `scripts/collect_daily_snapshot.py`。
- 不在 skill、测试或 provider 中写死某个日期作为默认业务逻辑。

如果 CLI 返回非零退出码，skill 必须停止生成完整复盘，只输出刷新失败说明、可复查命令、退出码和可用日志路径。

## Evidence Packet 契约

Python 第一阶段输出：

```text
reports/daily-reviews/YYYY-MM-DD/review-context.json
```

`review-context.json` 是 LLM 唯一允许引用的事实来源。建议顶层字段：

```json
{
  "schema_version": "daily_review_context.v1",
  "analysis_mode": "research_only",
  "not_investment_advice": true,
  "trade_date": "2026-06-18",
  "data_status": "passed|partial|failed|missing",
  "data_sources_used": [],
  "blocked_sections": [],
  "source_health": {},
  "market_breadth": {},
  "limit_pool": {},
  "lhb": {},
  "market_summary": {},
  "board_snapshot": {},
  "issues": [],
  "allowed_sections": [],
  "forbidden_claims": []
}
```

要求：

- `review-context.json` 必须通过 Pydantic v2 模型校验后才可写入。
- 每个统计值必须来自当前交易日 artifacts，不能混入其他日期。
- 每个事实应能追溯到来源表或状态文件。
- `blocked_sections` 对应维度只能出现在“数据缺口/不可分析”说明中，不能出现在 LLM 结论中。
- `failed` 或 `missing` 状态下，context 只能允许数据诊断、阻断原因和修复建议。

## LLM 输出契约

LLM 输入：

- `review-context.json`
- skill reference 中的 report prompt
- 用户原始请求中与输出形态、关注点相关的约束

LLM 输出建议采用 JSON，而不是自由 Markdown。推荐字段：

```json
{
  "headline": "",
  "summary": [],
  "market_breadth_review": "",
  "sentiment_and_events_review": "",
  "board_and_structure_review": "",
  "risk_observations": [],
  "follow_up_questions": [],
  "data_boundary_note": "",
  "not_investment_advice_note": ""
}
```

要求：

- LLM 不允许输出买卖、仓位、目标价、止盈止损或实盘行动建议。
- LLM 不允许声称完整复盘，除非 `data_status=passed`。
- LLM 不允许分析 `blocked_sections` 中被阻断的维度。
- LLM 必须明确说明 `partial`、`failed`、`missing` 的数据限制。
- LLM 输出必须通过 Pydantic v2 模型校验后才进入 HTML 渲染。

如果 LLM 输出不合法，运行时应返回校验失败说明；可选择触发一次修复提示词重试，但不能静默生成不合格报告。

## Pydantic 运行时校验

新增依赖：

```text
pydantic>=2.0,<3
```

建议新增模型：

- `ReviewContext`：校验 evidence packet。
- `SourceHealth`：校验接口、表、DuckDB、文件状态。
- `ReviewFact`：校验可引用事实的来源、字段和值。
- `LlmReviewSections`：校验 LLM 分析结构。
- `ValidatedReviewReport`：校验进入 HTML 渲染的最终对象。

Pydantic 负责：

- 字段存在性。
- 枚举值，例如 `data_status`。
- 日期格式。
- 数值类型和可空性。
- section 名称合法性。
- LLM JSON 是否可解析并符合结构。

Pydantic 不负责：

- 判断市场强弱。
- 决定某个主题是否成立。
- 决定是否可以输出市场结论。
- 替代禁用交易建议规则。
- 替代 Promptfoo 的跨场景评测。

业务规则必须由 Python 显式代码处理：

- `failed` / `missing` 阻断市场结论。
- `partial` 降级分析范围。
- `blocked_sections` 禁止在结论段落中出现。
- 禁用交易建议词和句式。
- HTML 首屏不得裸露机器键值字段。

## HTML 报告交付

当用户要求“生成 HTML”“发我 HTML report”“给我一份可打开报告”时，skill 应生成本地 HTML 文件。

建议输出路径：

```text
reports/daily-reviews/YYYY-MM-DD/a-share-daily-review.html
```

HTML 报告要求：

- 第一屏显示交易日期、数据状态、`research_only` 和非投资建议声明，但不能裸露 `analysis_mode: ...` 这种机器映射文本。
- 顶部应有用户可读的数据状态卡片，例如 `数据状态：partial`、`本报告仅用于研究复盘`。
- 机器 metadata 可放入以下位置之一：
  - `<script type="application/json" id="review-metadata">...</script>`
  - HTML comment
  - “数据边界”折叠区
- 报告正文来自已校验的 LLM sections。
- `partial`、`failed`、`missing` 状态必须在 HTML 顶部显著展示。
- 所有数据来源和 blocked sections 必须可见，但应以用户可读方式展示。
- 不使用外链 JavaScript；第一版优先生成单文件静态 HTML。
- 生成完成后，agent 在对话中返回 HTML 路径、数据状态和一句边界说明。

如果用户要求“直接给建议”，默认不写 HTML，直接返回研究建议、风险观察或下一步验证问题；这里的建议不能是交易行动建议。

## 数据状态语义

- `passed`：每日采集整体通过，主表、标准化文件、DuckDB 和关键状态报告可读取。
- `partial`：主表可用，但一个或多个增强来源失败、为空或 schema 变化。
- `failed`：主表失败、主表为空、主表标准化不可读、DuckDB 必需查询失败，或状态报告显示当日失败。
- `missing`：找不到指定交易日 daily run，或缺少可判断状态的关键文件。

状态降级规则：

- `failed` 或 `missing` 时，不生成市场复盘结论，只输出阻断原因和下一步修复建议。
- `partial` 时，可以输出主表范围内的观察，但所有增强维度必须标注数据受限。
- 任一关键来源不可读取时，不能用旧文件或其他日期文件补推断。

## Promptfoo 评测边界

Promptfoo 用于黄金测试和回归评测，不放进正常日报生成路径。

适合 Promptfoo 覆盖的内容：

- 用户不同提示词是否触发正确输出模式。
- HTML 是否生成。
- HTML 是否不再裸露机器键值字段。
- `partial` / `failed` / `missing` 是否被正确表达。
- blocked section 是否被尊重。
- 禁用交易建议语言是否出现。
- provider 是否调用公开 CLI，而不是直接调用采集脚本。

不适合 Promptfoo 承担的内容：

- 生产运行时 schema 校验。
- 每次日报生成时的强制 gate。
- 代替 Python 判断数据状态。
- 代替 Pydantic 校验 LLM JSON。

Promptfoo 可以通过自定义 Python 或 JavaScript assertion 调用同一套 Pydantic validator，但这是 eval / CI 用法，不是用户生成报告时的必经步骤。

## 实施工作 DAG

1. 冻结 v2 契约
   - 输入：本文档、现有 `daily_review.py`、现有测试和黄金集。
   - 输出：确定 `ReviewContext`、`LlmReviewSections`、HTML metadata 边界。
   - 依赖：本文档 review 通过。
   - 触碰模块：`docs/`。
   - 风险：继续把机器契约混入用户正文。
   - 验证：review 通过后再改代码。

2. 引入 Pydantic 模型
   - 输入：evidence packet 和 LLM 输出契约。
   - 输出：Pydantic v2 models 和 validator。
   - 依赖：v2 契约冻结。
   - 触碰模块：`requirements.txt`、`a_share_info_hub/`、`tests/`。
   - 风险：把 Pydantic 误用成业务判断器。
   - 验证：schema-valid 与 business-invalid 场景分开测试。

3. 拆分 evidence packet 生成
   - 输入：daily run artifacts、Parquet、DuckDB。
   - 输出：`review-context.json` 和 `--emit-context` 或等价 CLI。
   - 依赖：Pydantic 模型完成。
   - 触碰模块：`daily_review.py`、`__main__.py`、测试。
   - 风险：context 中混入自然语言结论或旧日期数据。
   - 验证：fixture 断言 context 字段、来源、状态和 blocked sections。

4. 新增 LLM 报告提示词
   - 输入：`ReviewContext`、用户请求、禁用语言规则。
   - 输出：`skills/a-share-daily-review/references/report-prompt.md` 或等价 reference。
   - 依赖：context 契约完成。
   - 触碰模块：skill reference、目录索引。
   - 风险：提示词允许 LLM 越过 evidence packet。
   - 验证：提示词明确要求只引用 context，并输出 JSON sections。

5. 新增 LLM 输出接入和校验
   - 输入：LLM JSON sections。
   - 输出：`ValidatedReviewReport`。
   - 依赖：LLM 提示词和 Pydantic 模型完成。
   - 触碰模块：`daily_review.py`、测试。
   - 风险：LLM 返回 Markdown 或非法 JSON 后仍继续生成 HTML。
   - 验证：非法 JSON、缺字段、blocked section 引用、禁用词都被阻断。

6. 重做 HTML 封装
   - 输入：`ValidatedReviewReport`。
   - 输出：用户可读 HTML。
   - 依赖：LLM 输出校验完成。
   - 触碰模块：HTML renderer、测试、样例报告。
   - 风险：HTML 又退回机器字段堆砌。
   - 验证：首屏不出现裸露 `analysis_mode:`、`data_status:`、`blocked_sections:` 机器映射行。

7. 更新 skill 和用户指南
   - 输入：v2 运行流程。
   - 输出：`SKILL.md`、workflow reference、用户指南。
   - 依赖：context、LLM、HTML 流程完成。
   - 触碰模块：`skills/`、`docs/`、目录索引。
   - 风险：用户指南仍描述旧的确定性 Python 生成报告。
   - 验证：示例提示词覆盖 HTML、inline、context、数据诊断和拒绝交易建议。

8. 更新黄金测试和 Promptfoo provider
   - 输入：v2 输出形态和 HTML 要求。
   - 输出：更新后的 JSONL、Promptfoo config、provider。
   - 依赖：v2 CLI 和 HTML 完成。
   - 触碰模块：`docs/`、`eval/`。
   - 风险：黄金测试继续断言旧机器字段裸露存在。
   - 验证：Promptfoo 或等价本地 harness 能验证新断言。

9. 回归验证和索引同步
   - 输入：所有实现文件和文档。
   - 输出：测试记录、README 更新、`AGENTS.md` 索引更新。
   - 依赖：前八项完成。
   - 触碰模块：`README.md`、`AGENTS.md`、各子目录索引。
   - 风险：实现已变但文档仍指向旧链路。
   - 验证：单元测试、skill validator、黄金测试、文档索引检查通过。

## 异常处理

### 未找到 daily run

- 找不到 `reports/daily-runs/YYYY-MM-DD/` 时，状态为 `missing`。
- 不允许自动改用其他日期，除非用户没有指定 `trade_date`，且流程是“读取最近一次 daily run”。
- 输出必须提示公开刷新入口：`python -m a_share_info_hub daily-update --trade-date <YYYY-MM-DD>`。
- `review-context.json` 可生成诊断型 context，但 `allowed_sections` 只能包含数据诊断和修复建议。

### 状态文件不可用

- `interface-status.json` 不存在、不可解析或缺少整体状态时，状态为 `missing` 或 `failed`。
- 可以读取 `daily-data-summary.md` 辅助解释，但不能只凭 Markdown 摘要生成完整复盘。
- Pydantic 校验失败时输出 schema 错误摘要和文件路径。

### 主表不可用

- 主表 Parquet 不存在、不可读取、指定日期无记录或关键字段缺失时，状态为 `failed`。
- 不能继续生成市场宽度、涨跌结构或个股分布结论。
- 如果接口状态显示主表成功但主表文件不可读，必须在 context `issues` 中列为数据一致性问题。

### 增强表部分失败

- 涨跌停、龙虎榜、市场汇总或板块表缺失时，不阻断主表观察，但状态最高只能是 `partial`。
- 对缺失维度对应章节标记为 blocked，不使用其他来源补写。
- 事件型数据为空时说明“当日未获取到该类事件或接口返回为空”，不写成市场没有事件。

### DuckDB 不可用

- DuckDB 不存在或查询失败时，可以尝试读取 Parquet 作为降级数据源。
- 若 Parquet 主表可用，状态为 `partial`，并在 `issues` 中说明 DuckDB 不可用。
- 若 DuckDB 和 Parquet 主表都不可用，状态为 `failed`。

### CLI 刷新失败

- `refresh_mode=daily_update` 且 CLI 返回非零退出码时，不生成完整复盘。
- 输出命令、退出码、stderr 摘要和可能的日志路径。
- 不在失败后自动改读旧日期报告，除非用户明确要求使用旧数据。

### LLM 输出非法

- JSON 不可解析、缺必填字段、字段类型错误或枚举值错误时，Pydantic 校验失败。
- 可允许一次修复提示词重试；重试仍失败则返回阻断结果。
- 不允许把非法 LLM 输出直接包成 HTML。

### Blocked section 被引用

- 如果 LLM 在结论段落中引用 `blocked_sections` 对应维度，视为业务校验失败。
- 失败后应要求 LLM 改写为数据缺口说明，不能继续保留相关结论。

### 禁用语言检查失败

- 如果生成内容包含买卖、仓位、目标价或实盘建议语言，视为输出失败。
- 失败后应改写为“研究问题”“风险观察”或“待验证线索”。
- 禁用词检查属于业务规则，不交给 Pydantic 独自承担。

## 单元测试计划

单元测试只验证本地逻辑，不依赖真实 AKShare 网络调用，也不强依赖真实 LLM 调用。

建议新增或扩展测试：

1. `ReviewContext` schema 通过
   - 输入：完整 fixture artifacts。
   - 断言：生成 `review-context.json`，并通过 Pydantic v2 校验。

2. `ReviewContext` schema 失败
   - 输入：缺少必填字段或非法 `data_status` 的 context。
   - 断言：Pydantic 返回明确错误，流程不进入 HTML 渲染。

3. `passed` 状态允许完整复盘 section
   - 输入：主表、增强表、DuckDB 和状态 JSON fixture 均可用。
   - 断言：`allowed_sections` 包含市场宽度、情绪事件、板块结构、风险和后续问题。

4. `partial` 状态限制增强维度
   - 输入：主表可用，某个增强接口失败或表缺失。
   - 断言：状态为 `partial`；缺失增强章节进入 `blocked_sections`。

5. `failed` 状态阻断市场结论
   - 输入：主表为空、主表不可读或状态 JSON 标记失败。
   - 断言：只允许数据诊断和修复建议，不允许市场判断 section。

6. `missing` 状态不读取其他日期
   - 输入：指定日期没有 daily run，但其他日期存在。
   - 断言：输出 `missing`，提示公开 CLI 刷新方式，不读取其他日期。

7. DuckDB 降级到 Parquet
   - 输入：DuckDB 查询失败但 Parquet 主表可用。
   - 断言：状态降级为 `partial`，context `issues` 说明 DuckDB 风险。

8. LLM 输出 schema 校验
   - 输入：合法和非法 LLM JSON fixtures。
   - 断言：合法 JSON 进入 `ValidatedReviewReport`；非法 JSON 被阻断。

9. Blocked section 校验
   - 输入：`board_snapshot` blocked，但 LLM 输出板块主线结论。
   - 断言：业务校验失败，不生成 HTML。

10. 禁用交易建议语言
   - 输入：LLM 输出含买入、卖出、仓位、目标价、止损止盈、实盘建议。
   - 断言：业务校验失败，并返回 research-only 改写要求。

11. HTML 首屏可读性
   - 输入：已校验 `ValidatedReviewReport`。
   - 断言：HTML 顶部展示用户可读状态，不包含裸露 `analysis_mode:`、`data_status:`、`blocked_sections:` 机器行。

12. CLI 刷新契约
   - 输入：`refresh_mode=daily_update`。
   - 断言：构造公开 CLI 模块入口，不调用 `scripts/collect_daily_snapshot.py`，不 hard code 日期。

13. Promptfoo provider 契约
   - 输入：黄金测试 fixture。
   - 断言：provider 调用公开 CLI 或 v2 harness，不污染真实 `data/` 和 `reports/`。

建议验证命令：

```text
python -m pytest tests
```

如果本地安装 Promptfoo，再运行：

```text
npx promptfoo@latest eval -c eval/promptfooconfig.yaml
```

未安装 Promptfoo 时，应保留本地 harness 或 JSONL 解析测试，确保黄金测试集可读且核心断言可执行。

## 集成验证

实施完成后建议按以下顺序验证：

1. 依赖和静态校验
   - `requirements.txt` 包含 `pydantic>=2.0,<3`。
   - `python -m py_compile a_share_info_hub/__main__.py a_share_info_hub/daily_review.py` 通过。

2. Skill 结构校验
   - 验证 `SKILL.md` frontmatter、名称、description 和资源引用。

3. Context 生成
   - 使用已有 `reports/daily-runs/YYYY-MM-DD/` 和 `data/normalized/`。
   - 生成 `review-context.json`。
   - 确认 context 通过 Pydantic 校验。

4. LLM 输出校验
   - 使用 fixture LLM JSON 先做本地校验。
   - 再用真实或模拟 LLM 输出验证正常路径和失败路径。

5. HTML 生成
   - 使用通过校验的 report sections 生成 HTML。
   - 确认首屏是用户可读报告，不是机器字段堆砌。

6. 指定日期刷新后分析
   - 运行公开 CLI：

```text
python -m a_share_info_hub daily-update --trade-date <YYYY-MM-DD>
```

   - 再运行 skill 分析同一日期。
   - 确认报告引用的日期、状态和数据源一致。

7. 失败场景验证
   - 使用缺失状态文件、空主表、增强失败、DuckDB 不可用、非法 LLM JSON 和交易建议输出 fixture。
   - 确认输出降级或阻断，不生成越界报告。

8. Promptfoo 回归评测
   - 使用黄金测试集验证 HTML、禁用词、状态、blocked section 和 CLI 契约。
   - Promptfoo 失败不应影响普通用户本地生成流程，但必须阻断合并或发布。

9. 文档同步验证
   - README 包含 v2 使用说明。
   - 用户指南、黄金测试说明、Promptfoo 配置和相关 `AGENTS.md` 索引已同步。

## 目标达成条件

只有以下条件全部满足，v2 实施才能声明完成：

1. Skill 可被发现和触发
   - 存在 `skills/a-share-daily-review/SKILL.md`。
   - skill validator 通过。
   - skill 文档描述的是 v2 evidence packet + LLM + validator 流程。

2. Evidence packet 契约满足
   - 能读取指定交易日或最近一次 daily run。
   - 先读取并解释 `interface-status.json`，再生成 context。
   - `review-context.json` 存在，并通过 Pydantic v2 校验。
   - 主表失败、缺失或为空时阻断市场结论。
   - 增强数据失败时降级为 `partial`，并列入 `blocked_sections`。

3. LLM 分析层满足
   - LLM 只接收 `review-context.json` 和提示词，不直接读取额外数据文件。
   - LLM 输出结构化 JSON sections 或可等价校验的结构。
   - LLM 输出通过 Pydantic v2 校验后才进入 HTML 渲染。
   - 非法 JSON、缺字段、blocked section 引用和禁用交易语言都会阻断。

4. CLI 刷新契约满足
   - 需要刷新时只调用 `python -m a_share_info_hub daily-update` 这个公开入口。
   - 日期、代理选项和输出根目录来自参数或上下文，不 hard code。
   - 不直接调用 `scripts/collect_daily_snapshot.py` 作为日常入口。

5. HTML 输出边界满足
   - 用户请求 HTML 时，生成可打开 HTML 文件并返回路径。
   - HTML 首屏是用户可读摘要，不裸露机器字段映射行。
   - HTML 包含交易日期、数据状态、研究用途声明、非投资建议声明和数据边界。
   - 机器 metadata 保留在隐藏 JSON、HTML comment 或“数据边界”区域。
   - 数据不足时输出观察限制，不补推断。

6. 研究边界满足
   - 输出包含 `research_only` 语义。
   - 输出包含 `not_investment_advice` 语义。
   - 不包含买卖、仓位、目标价、止盈止损或实盘行动建议。
   - 用户请求“建议”时，只返回研究建议、风险观察或待验证问题。

7. 测试满足
   - `passed`、`partial`、`failed`、`missing` 四类状态都有测试。
   - Pydantic context 和 LLM output 校验有测试。
   - CLI 调用契约有测试。
   - 禁用交易建议语言有测试。
   - HTML 首屏不裸露机器字段有测试。
   - Promptfoo 或等价 harness 覆盖黄金测试集。
   - 所有新增测试通过。

8. 文档满足
   - README 写明 v2 使用方式和每日刷新入口。
   - `docs/a-share-daily-review-skill-user-guide.md` 写明用户提示词、agent 调用 skill 的能力和不同场景输出方式。
   - `docs/a-share-daily-review-skill-golden-testset.jsonl` 更新为 v2 断言，不再要求裸露机器字段。
   - Promptfoo 文档说明它是 eval / CI 工具，不是生产运行时 gate。
   - 相关 `AGENTS.md` 目录索引已同步。
   - 最终实施说明列出已运行验证命令和未运行项。

## Review 关注点

请重点 review 以下决策：

- 是否接受 hybrid 架构：Python 证据包和校验，LLM 写分析表达。
- `review-context.json` 是否作为 LLM 唯一事实输入。
- LLM 输出是否必须用 JSON sections，而不是自由 Markdown。
- `pydantic>=2.0,<3` 是否作为生产运行时 schema 校验依赖。
- Promptfoo 是否只用于黄金测试和 CI，不进入正常日报生成路径。
- HTML 首屏是否禁止裸露机器键值字段。
- `deterministic` 模式是否保留为诊断 fallback，还是完全移除旧 Python 报告生成。
- LLM 输出失败时是否允许一次自动修复重试。
- 禁用交易建议语言是否需要更严格的词表或句式检测。

## 当前实施状态

截至 2026-06-19，v2 已在当前工作区落地：

- `requirements.txt` 已加入 `pydantic>=2.0,<3`。
- `a_share_info_hub/daily_review.py` 已拆分为 context 生成、LLM sections 校验、业务规则校验和 HTML 渲染。
- `python -m a_share_info_hub daily-review --output-format context` 可生成 `review-context.json`。
- `python -m a_share_info_hub daily-review --llm-output <path> --output-format html` 可校验 LLM sections 并生成 HTML。
- `--render-mode deterministic` 保留为本地 fixture 和 Promptfoo provider 使用的 fallback，不作为正式用户报告路径。
- `skills/a-share-daily-review/references/report-prompt.md` 已定义 LLM sections JSON 输出规则。
- 黄金测试集和 Promptfoo provider 已改为 v2 断言：context、HTML、不裸露机器字段、blocked section、禁用交易建议和公开 CLI 契约。
- `reports/daily-reviews/2026-06-18/review-context.json`、`llm-review-sections.json` 和 `a-share-daily-review.html` 已生成；HTML 的 `render_mode` 为 `llm`。

## 已运行验证

已在当前工作区运行：

```text
.venv\Scripts\python.exe -m pytest tests
.venv\Scripts\python.exe -m a_share_info_hub daily-review --trade-date 2026-06-18 --output-format context
.venv\Scripts\python.exe -m a_share_info_hub daily-review --trade-date 2026-06-18 --llm-output reports\daily-reviews\2026-06-18\llm-review-sections.json --output-format html
node --check eval\providers\run-a-share-daily-review.js
python C:/Users/zhanb.BIINN/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/a-share-daily-review
git diff --check
```

黄金测试集已用本地 Node harness 执行 `contains`、`not-contains`、`regex` 和 `contains-html` 断言，结果为：

```text
Golden assertions OK: 10 cases
```

`git diff --check` 仅输出 Windows 换行提示，没有 whitespace error。
