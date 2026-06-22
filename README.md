# A Share Info Hub

每日 A 股公开数据采集与复盘研究工具链。

A daily A-share public data collection and research review pipeline.

---

## 中文

### 项目概述

`a-share-info-hub` 是一个每日 A 股公开行情数据采集、标准化和复盘研究工具。它从 AKShare 获取当日全市场快照、涨跌停池、龙虎榜、交易所概况和板块快照，将数据标准化为 Parquet 表并写入本地 DuckDB 分析库，在此基础上生成研究用途的每日复盘报告。

**边界声明**：本项目仅用于数据采集和研究复盘，不提供任何形式的交易建议、买卖信号、仓位配置、目标价或止盈止损指令。

### 核心能力

- **每日快照采集** — 从 AKShare 获取当日 14 个公开接口的行情数据，经交易日验证后归一化为 5 张标准表
- **多源数据汇聚** — 覆盖个股快照、涨跌停池（涨停/曾涨停/炸板/跌停）、龙虎榜明细（新浪/东方财富/机构买卖）、沪深交易所概况、行业和概念板块快照
- **标准化存储** — 统一字段映射和类型转换，产出 Parquet 表并维护本地 DuckDB 按日替换的查询层
- **状态可追溯** — 每次运行生成 `interface-status.json`、人读摘要和外部接口失败日志，失败和空结果分开记录
- **研究复盘报告** — 通过 `review-context.json` evidence packet → LLM sections → 校验器 → HTML 报告的工作流，生成面向普通投资者的策略分析师报告，包含大盘观察、市场宽度、情绪事件、板块结构、风险观察和下一步研究问题
- **外部背景融合** — 可选接入 `daily-financial-briefing` 产出的 US Macro 和投行观点摘要，在本地 A 股证据边界内作为风险观察和待验证问题
- **安全输出边界** — 多层校验阻断交易行动语言、内部诊断泄漏和 blocked section 的越界结论

### 项目结构

```text
a_share_info_hub/    CLI 包入口和复盘研究模块
scripts/             采集脚本和契约探测脚本
skills/              可复用的 agent skill（采集复盘、财经简报）
data/
  raw/               按日期和接口保存的 AKShare 原始响应
  normalized/        标准化 Parquet 表
reports/
  daily-jobs/        定时报告任务状态、heartbeat、摘要和阶段日志
  daily-runs/        每次采集运行的状态报告和摘要
  daily-reviews/     每日复盘 HTML、技术参考和 context
logs/                外部接口失败 JSONL 日志
tests/               单元测试和 fixture
docs/                设计和实施文档
```

### 快速开始

**环境要求**：Python 3.11+，依赖见 `requirements.txt`。

```bash
# 安装依赖
pip install -r requirements.txt

# 执行每日数据采集（T 日快照）
python -m a_share_info_hub daily-update --trade-date 2026-06-20

# 生成研究复盘 context（evidence packet）
python -m a_share_info_hub daily-review --trade-date 2026-06-20 --output-format context

# 基于 LLM sections 生成 HTML 复盘报告
python -m a_share_info_hub daily-review \
  --trade-date 2026-06-20 \
  --llm-output reports/daily-reviews/2026-06-20/llm-review-sections.json \
  --output-format html

# 本机定时任务编排入口（由 OpenClaw prompt 调用）
.venv/bin/python scripts/run_daily_report_job.py --trade-date 2026-06-20 --send --delivery-provider openclaw_message

# 预期运行后 watchdog 检查
.venv/bin/python scripts/run_daily_report_job.py --check-latest --trade-date 2026-06-20 --send --delivery-provider openclaw_message
```

**可选参数**：

| 参数 | 说明 |
| --- | --- |
| `--trade-date` | 交易日，格式 `YYYY-MM-DD`，默认当天 |
| `--output-root` | 项目根，控制 data/logs/reports 输出位置 |
| `--ignore-proxy` | 跳过系统 HTTP 代理，适合直连环境 |
| `--skip-duckdb` | 跳过 DuckDB 写入，用于诊断 |
| `--refresh-mode daily_update` | 复盘前先执行数据刷新 |
| `--render-mode deterministic` | 使用确定性 fallback，适合本地测试 |
| `--external-background` | 指定外部财经背景 JSON |
| `--skip-external-background` | 定时任务跳过默认外部背景生成，仅使用本地 A 股 context |
| `--delivery-provider openclaw_message` | 定时任务通过 OpenClaw `feishu` channel 发送消息 |
| `--openclaw-report-targets` | 报告消息的 OpenClaw Feishu channel routes，格式 `account:chatId`，默认发 main 和 candy 两个 channel |
| `--openclaw-alert-targets` | 告警和 watchdog 消息的 OpenClaw Feishu channel routes，格式 `account:chatId`，默认只发 main channel |
| `--output-format` | 复盘输出格式：`html` / `context` / `inline` / `markdown` |

定时任务编排入口默认使用 `.venv/bin/python -m a_share_info_hub daily-update` 和 `daily-review`，并通过 Claude Code 非交互命令先生成 `external-background-fusion.json`，再生成 `llm-review-sections.json`。任务状态写入 `reports/daily-jobs/YYYY-MM-DD/`；发送配置必须通过本机环境变量或命令行参数提供，不能提交到仓库或写入报告产物。

### 定时任务配置示例

第一版不在仓库内实现长期驻留调度服务。生产推荐由 OpenClaw cron / scheduler 读取 `docs/openclaw-a-share-daily-orchestrator.prompt.md` 和 `docs/openclaw-a-share-daily-watchdog.prompt.md`，再由 OpenClaw 调用本地编排脚本。报告消息通过 OpenClaw `feishu` channel 发给 main 和 candy 两个 channel，监控/告警只发给 main channel；飞书自定义机器人 webhook 仅作为本地 fallback，使用 `FEISHU_WEBHOOK_URL` 和可选 `FEISHU_WEBHOOK_SECRET`，不能提交到仓库或写入报告产物。

`--timeout-seconds 7200` 是 OpenClaw agent turn 的最外层兜底，不是日报业务 SLA。业务超时由编排脚本的分阶段 hard timeout、`heartbeat.json` 和 watchdog 判断；如果后续新增脚本级 overall hard kill，应把 OpenClaw 外层 timeout 调整为脚本 overall hard timeout 加 5-10 分钟缓冲。

```cron
# OpenClaw cron 主路径
openclaw cron add \
  --name a-share-daily-report \
  --agent main \
  --session isolated \
  --tools exec,read,write \
  --cron "0 16 * * 1-5" \
  --tz Asia/Shanghai \
  --timeout-seconds 7200 \
  --message "$(cat docs/openclaw-a-share-daily-orchestrator.prompt.md)"

openclaw cron add \
  --name a-share-daily-report-watchdog \
  --agent main \
  --session isolated \
  --tools exec,read,write \
  --cron "0 17 * * 1-5" \
  --tz Asia/Shanghai \
  --timeout-seconds 900 \
  --message "$(cat docs/openclaw-a-share-daily-watchdog.prompt.md)"

# 如果必须使用系统 cron，仍触发 OpenClaw prompt，不绕过 OpenClaw 调 Python 脚本
0 16 * * 1-5 cd /path/to/a-share-info-hub && openclaw agent --agent main --message "$(cat docs/openclaw-a-share-daily-orchestrator.prompt.md)" >> logs/openclaw-a-share-daily-report.cron.log 2>&1

0 17 * * 1-5 cd /path/to/a-share-info-hub && openclaw agent --agent main --message "$(cat docs/openclaw-a-share-daily-watchdog.prompt.md)" >> logs/openclaw-a-share-daily-watchdog.cron.log 2>&1
```

历史日期回放默认不会发送飞书消息；只有显式传入 `--send` 才会发送。重复发送同一 `trade_date` 会被阻止，除非显式传入 `--force-send`。

### 数据状态语义

| 状态 | 含义 |
| --- | --- |
| `passed` | 主表和其他表均非空，DuckDB 写入成功 |
| `partial` | 主表可用但部分增强接口失败或缺失 |
| `failed` | 主表不可用或交易日历验证失败 |
| `skipped` | 目标日期非 A 股交易日，未调用行情接口 |
| `missing` | 指定日期没有已存在的采集运行记录 |

### 运行测试

```bash
pytest tests/ -v
```

测试使用 fixture 和 mock，不依赖真实 AKShare 网络调用。

### 技术栈

| 组件 | 用途 |
| --- | --- |
| [AKShare](https://github.com/akfamily/akshare) | A 股公开行情数据接口 |
| [DuckDB](https://duckdb.org/) | 本地嵌入式分析数据库 |
| [Pandas](https://pandas.pydata.org/) / [PyArrow](https://arrow.apache.org/) | 数据处理和列式存储 |
| [Pydantic](https://docs.pydantic.dev/) | 数据模型校验和契约约束 |

### 架构说明

采集链路采用接口→原始保存→标准化→多格式输出的分层架构。数据路径上每层各自保存产物，不依赖上层缓存推断下层的状态。复盘工作流采用 evidence packet → LLM sections → 校验器 → 报告渲染的四阶段流水线，LLM 输出在被写入用户可读 HTML 之前必须通过 Pydantic 结构校验和业务规则阻断检查。

### Agent 开发设计经验

本项目在 Agent 架构上的核心思路是**用确定性代码定义 LLM 的边界，而非依赖 prompt 约束**。数据采集完成后，确定性代码先将原始表编译为版本化的 `review-context.json` 证据包——其中明确列出 `allowed_sections`、`blocked_sections`、`forbidden_claims` 和 `facts`，LLM 被要求只基于此 context 生成 sections JSON，不得引入外部知识。LLM 输出在进入用户可读 HTML 之前，必须通过 Pydantic 结构校验和业务规则扫描（禁用词表、blocked section 越界检查、信息密度门槛）的双层门禁——任何一层未通过即阻断渲染并返回具体原因。系统同时提供 `deterministic` 渲染模式，接收相同 context、产出相同结构的 sections，使流水线可在无 LLM 环境下完整测试；LLM 输出异常时切换到此模式即可快速定位问题在 context 还是 LLM。所有组件间 JSON 契约均带 `Literal` 锁定的 `schema_version`，字段演进时上下游不会静默断裂。外部背景融合采用 6 路并行子 Agent 各负责一个本地 topic，由确定性代码合并结果——既控制了单 Agent 上下文规模，也用代码而非 LLM 完成最终汇总。综合来看，可迁移的经验只有一句话：**把 LLM 当作受控文本生成组件，而不是流程编排器；软约束放在 prompt 里，硬约束放在代码里。**

---

## English

### Overview

`a-share-info-hub` is a daily A-share public market data collection, normalization, and research review toolkit. It fetches end-of-day snapshots — full-market quotes, limit-up/down pools, Dragon Tiger List (LHB) details, exchange summaries, and industry/concept board snapshots — from AKShare, normalizes them into Parquet tables and a local DuckDB database, then generates research-only daily review reports.

**Boundary**: This project is for data collection and research review only. It does not produce trading advice, buy/sell signals, position sizing, price targets, or stop-loss/take-profit directives.

### Core Capabilities

- **Daily Snapshot Collection** — Fetches 14 public AKShare interfaces per trading day after verifying the A-share trading calendar, then normalizes results into 5 standard tables
- **Multi-source Data Aggregation** — Covers individual stock quotes, limit-up/down pools (fresh/previous/strong/sub-new/broken-board/limit-down), LHB details (Sina/EastMoney/institutional), SSE/SZSE summaries, and industry/concept board snapshots
- **Normalized Storage** — Unified field mapping and type coercion producing Parquet tables and a per-date replaceable DuckDB query layer
- **Traceable Status** — Each run produces `interface-status.json`, a human-readable summary, and a failure log; failures, empty results, and schema changes are tracked separately
- **Research Review Reports** — A `review-context.json` evidence packet → LLM sections → validator → HTML report pipeline generates strategy-analyst-role reports for ordinary investors, covering market overview, breadth, sentiment/events, board structure, risk observations, and follow-up research questions
- **External Background Fusion** — Optional integration with `daily-financial-briefing` outputs (US Macro and investment bank views) as risk observations and verify-later questions within the local A-share evidence boundary
- **Safety Output Boundaries** — Multi-layer validation blocks trading-action language, internal diagnostic leaks, and conclusions that exceed data-gap constraints

### Project Layout

```text
a_share_info_hub/    CLI package entry and daily review module
scripts/             Collection script and data-contract probe script
skills/              Reusable agent skills (review, financial briefing)
data/
  raw/               AKShare raw responses, per date and interface
  normalized/        Normalized Parquet tables
reports/
  daily-jobs/        Scheduled report job status, heartbeat, summary, and stage logs
  daily-runs/        Per-run status report and summary
  daily-reviews/     Per-date review HTML, technical notes, and context
logs/                External interface failure JSONL log
tests/               Unit tests and fixtures
docs/                Design and implementation docs
```

### Quick Start

**Requirements**: Python 3.11+, dependencies listed in `requirements.txt`.

```bash
# Install dependencies
pip install -r requirements.txt

# Run daily data collection (T-day snapshot)
python -m a_share_info_hub daily-update --trade-date 2026-06-20

# Generate review evidence packet
python -m a_share_info_hub daily-review --trade-date 2026-06-20 --output-format context

# Generate HTML review report from LLM sections
python -m a_share_info_hub daily-review \
  --trade-date 2026-06-20 \
  --llm-output reports/daily-reviews/2026-06-20/llm-review-sections.json \
  --output-format html
```

**Optional flags**:

| Flag | Description |
| --- | --- |
| `--trade-date` | Trade date in `YYYY-MM-DD`, defaults to today |
| `--output-root` | Project root for data/logs/reports output |
| `--ignore-proxy` | Bypass system HTTP proxy for direct connections |
| `--skip-duckdb` | Skip DuckDB writes for diagnostics |
| `--refresh-mode daily_update` | Run data refresh before review generation |
| `--render-mode deterministic` | Use deterministic fallback for local testing |
| `--external-background` | Path to external financial background JSON |
| `--skip-external-background` | Skip scheduled-job external background generation and use local A-share context only |
| `--output-format` | Review output: `html` / `context` / `inline` / `markdown` |

### Data Status Semantics

| Status | Meaning |
| --- | --- |
| `passed` | Main table and all enhanced tables non-empty, DuckDB write succeeded |
| `partial` | Main table available but some enhanced interfaces failed or missing |
| `failed` | Main table unavailable or trading calendar verification failed |
| `skipped` | Target date is not an A-share trading day, no market interfaces called |
| `missing` | No existing collection run found for the specified date |

### Running Tests

```bash
pytest tests/ -v
```

Tests use fixtures and mocks; no live AKShare network calls are made.

### Tech Stack

| Component | Role |
| --- | --- |
| [AKShare](https://github.com/akfamily/akshare) | Public A-share market data interfaces |
| [DuckDB](https://duckdb.org/) | Embedded analytical database |
| [Pandas](https://pandas.pydata.org/) / [PyArrow](https://arrow.apache.org/) | Data processing and columnar storage |
| [Pydantic](https://docs.pydantic.dev/) | Data model validation and contract enforcement |

### Architecture

The collection pipeline follows a layered architecture: interface call → raw persistence → normalization → multi-format output. Each layer stores its own artifacts; no layer infers a downstream layer's state from an upstream cache. The review workflow follows a four-stage pipeline: evidence packet → LLM sections → validator → report rendering. LLM output must pass Pydantic structural validation and business-rule boundary checks before being written into user-readable HTML.

### Agent Development Design Experience

The core architectural philosophy of this project is **using deterministic code to define the LLM's boundaries, rather than relying on prompt constraints**. After data collection, deterministic code compiles raw tables into a versioned `review-context.json` evidence packet — explicitly listing `allowed_sections`, `blocked_sections`, `forbidden_claims`, and `facts` — and the LLM is instructed to generate sections JSON from this context alone, with no external knowledge. LLM output passes through a dual-layer gate (Pydantic structural validation + business rule scanning for forbidden terms, blocked-section boundary violations, and information-density thresholds) before reaching user-readable HTML; either layer failing blocks rendering with a specific reason. The system also provides a `deterministic` render mode that accepts the same context and produces the same sections structure, enabling full pipeline testing without an LLM and fast fault isolation when LLM output fails validation. All inter-component JSON contracts carry a `Literal`-locked `schema_version`, preventing silent breakage during field evolution. External background fusion decomposes into 6 parallel sub-agents each handling one local topic, with deterministic code performing the final merge — controlling per-agent context size while keeping synthesis in code, not the LLM. The portable takeaway: **treat the LLM as a constrained text-generation component, not a flow orchestrator; put soft constraints in prompts, hard constraints in code.**

### Agent Skills

The repository includes two Claude Code / Codex agent skills:

| Skill | Purpose |
| --- | --- |
| `a-share-daily-review` | Drives the full review workflow from context generation through LLM sections to HTML report, with optional parallel sub-agent external background fusion |
| `daily-financial-briefing` | Produces cited US Macro and investment bank view briefings from public sources as external background for the A-share review |

### License

MIT
