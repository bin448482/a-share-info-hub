# 每日定时采集和报告发送实施计划

本文档用于 review 每日定时任务的实施方案。当前阶段定义“如何用 OpenClaw 作为本机 orchestrator，把已有采集、Claude Code 复盘、Python 校验、报告发送、监控和受限自愈接成可运维的定时任务”。本文档本身不提交密钥、不配置真实生产调度器、不发送真实报告。

## 背景和当前状态

仓库已有两条公开 CLI：

- `python -m a_share_info_hub daily-update`：采集每日 A 股公开数据，写入 `data/`、`market.duckdb` 和 `reports/daily-runs/YYYY-MM-DD/`。
- `python -m a_share_info_hub daily-review`：读取已有 daily run，生成 `review-context.json`，并在提供 `llm-review-sections.json` 后校验渲染 HTML 和技术参考 Markdown。

当前缺口：

- 仓库需要明确 OpenClaw orchestrator 的调度 prompt、执行边界和状态回写。
- 仓库需要明确报告消息、监控消息和失败诊断分别发给哪些 OpenClaw agent。
- 默认 HTML 报告依赖 `review-context.json -> LLM sections JSON -> validator -> HTML`，生产环境需要明确 LLM sections 的生成方式。
- 自动调试和自动修复需要边界：无人值守任务可以诊断、重试安全步骤和生成补丁建议，但不应静默修改生产代码或绕过报告校验。

已确认约束：

- 发送渠道使用飞书。
- 定时任务运行在本机。
- 本机需要创建并使用仓库内 `.venv` Python 虚拟环境。
- LLM sections 由本机 Claude Code 非交互 agent runtime 生成；Claude Code 作为父 agent 调用 `$a-share-daily-review` skill。
- 运行质量监控必须作为核心功能，不只依赖进程退出码。
- OpenClaw 本机 Gateway 已可用；Feishu channel 已配置；OpenClaw 可作为任务调度、消息路由和人工介入入口。
- 报告消息通过 OpenClaw `feishu` channel 发送给 main 和 candy；监控、告警和修复请求只发送给 main。

## 目标

1. 在交易日收盘后自动执行每日数据采集。
2. 根据采集状态决定是否继续生成复盘报告。
3. 生成可审计的 `review-context.json`、`llm-review-sections.json`、HTML 主报告和技术参考 Markdown。
4. 通过飞书发送报告摘要、报告路径和失败诊断。
5. 失败时发送诊断摘要，避免静默失败。
6. 保留 research-only 边界，不生成交易建议、仓位建议、目标价或止盈止损指令。
7. 记录并监控运行质量，包括数据新鲜度、接口健康、报告校验、发送回执和连续失败。

## 不做事项

- 不在 Python 里实现长期驻留调度服务；调度由 OpenClaw cron / scheduler 或系统 `cron` 触发 OpenClaw 完成。
- 不绕过公开 CLI 直接调用 `scripts/collect_daily_snapshot.py`。
- 不把 OpenClaw agent 的自然语言回复当作数据门禁；数据状态、HTML 渲染和 research-only 边界仍由 Python CLI 校验。
- 不允许自动修复流程在无人确认时提交代码、改密钥、改调度器、删除历史产物或绕过失败门禁。
- 不把 `deterministic` 渲染模式当作正式研究报告的替代品；它只用于 smoke 和故障兜底验证。
- 不在定时任务失败时自动改用其他交易日。
- 不把 `partial` 状态伪装成完整报告；缺失维度必须进入技术参考。
- 不把“脚本退出码为 0”当作任务质量通过；必须读取状态文件和报告校验结果。

## 必须确认的输入

实施前需要确认以下输入。任一项未确认时，生产定时发送应停在 waitpoint：

- OpenClaw 调度方式：使用 `openclaw cron` 还是系统 `cron` 调 `openclaw agent`；生产只选择一种，避免重复执行。
- OpenClaw Feishu channel route：报告消息为 main 和 candy；监控消息为 main；脚本内部使用 `account:chatId` 路由，如需变更必须写入配置而不是 prompt 中临时改写。
- 飞书发送形态：由 OpenClaw Feishu channel 负责发送到对应 channel route；如 fallback 到飞书自定义机器人 webhook，需要另行确认 webhook 和密钥保存方式。
- Claude Code 调用方式：需要确认本机可用的非交互 CLI 命令、工作目录、认证状态、超时、退出码语义和日志路径。
- OpenClaw 调用 Claude Code 的方式：OpenClaw 任务 prompt 可以要求执行 `claude -p`，但必须指定 repo 工作目录、目标 output path、超时和日志路径。
- 交易日运行时间：首次真实交易日 dry-run 定在北京时间 2026-06-22 16:00；后续根据 AKShare 数据稳定性和耗时观测再决定是否调整到 16:30 或更晚。

## LLM Sections 说明

`LLM sections` 指 `llm-review-sections.json`，是给 Python HTML 渲染器使用的结构化报告内容，不是最终 HTML，也不是自由 Markdown。

现有复盘链路分三层：

```text
review-context.json
  -> LLM 只基于 context 写出 llm-review-sections.json
  -> daily-review 校验 JSON 并渲染 a-share-daily-review.html
```

`review-context.json` 是事实包，包含数据状态、可用事实、阻断维度和禁止声明。`llm-review-sections.json` 是表达层，字段包括 `headline`、`summary`、`market_overview_assessment`、`market_overview_structure`、`risk_observations`、`follow_up_questions` 等。Python 会校验这个 JSON 的 schema、禁用交易语言、blocked section 越界和 HTML 正文边界；校验失败时不得发送 HTML 主报告。

第一版不接独立 LLM API。生产路径由 Claude Code 读取 skill 和 context，生成 `llm-review-sections.json`，再交给 Python CLI 校验和渲染。Python 校验仍是最终门禁；Claude Code 输出不合法时不得发送 HTML 主报告。

## 推荐架构：OpenClaw Orchestrator

推荐把 OpenClaw 放在最外层，作为“调度、步骤编排、消息路由、失败诊断和人工介入入口”。仓库内 Python CLI 仍只负责确定性业务门禁；Claude Code 仍只负责调用 skill 生成 `llm-review-sections.json`。

```text
OpenClaw scheduler / cron
  -> OpenClaw daily orchestrator prompt
      -> inspect previous job state and repo readiness
      -> run .venv/bin/python -m a_share_info_hub daily-update --trade-date <YYYY-MM-DD>
      -> read reports/daily-runs/YYYY-MM-DD/interface-status.json
      -> if passed/partial:
           run .venv/bin/python -m a_share_info_hub daily-review --trade-date <YYYY-MM-DD> --output-format context
           run Claude Code non-interactive prompt with $a-share-daily-review + $daily-financial-briefing to write external-background-fusion.json
           re-run daily-review context with --external-background external-background-fusion.json
           run Claude Code non-interactive prompt with $a-share-daily-review to write llm-review-sections.json
           run .venv/bin/python -m a_share_info_hub daily-review --trade-date <YYYY-MM-DD> --external-background ... --llm-output ... --output-format html
         else:
           stop market-report path and prepare diagnostic message
      -> evaluate job health from artifacts, not only exit codes
      -> write reports/daily-jobs/YYYY-MM-DD/job-status.json and job-summary.md
      -> send report message to OpenClaw Feishu channels main,candy
      -> send monitoring / alert / repair-needed message to OpenClaw Feishu channel main

OpenClaw watchdog prompt
  -> after expected deadline, check job-status.json and heartbeat/logs
  -> if missing, running too long, stale, or critical:
       send critical monitoring message to main
       optionally launch bounded diagnosis prompt
```

OpenClaw 可以负责“调用谁、何时调用、把结果发给谁、失败后启动哪类诊断”。但 OpenClaw 不应负责“判定 HTML 是否可发送”或“放宽 research-only 边界”；这些必须由仓库确定性代码和状态文件证明。

## OpenClaw 每日任务 Prompt 模板

该 prompt 应作为 OpenClaw cron 任务的固定正文，调度时只注入日期和必要环境变量。不要在 prompt 里写密钥。

```text
你是 a-share-info-hub 的每日定时任务 orchestrator。请在本机仓库
/mnt/tool/2-projects/a-share-info-hub 执行今天的 A 股收盘后数据采集、复盘报告生成、校验、发送和状态记录。

运行参数：
- trade_date: {{YYYY-MM-DD，默认 Asia/Shanghai 今日}}
- output_root: /mnt/tool/2-projects/a-share-info-hub
- python: .venv/bin/python
- report recipients: OpenClaw Feishu channels main,candy
- monitoring recipients: OpenClaw Feishu channel main
- research_only: true

硬性边界：
1. 只通过公开 CLI 调用采集和复盘：
   - .venv/bin/python -m a_share_info_hub daily-update
   - .venv/bin/python -m a_share_info_hub daily-review
2. 不直接调用 scripts/collect_daily_snapshot.py。
3. 不发送任何未经 Python validator 校验通过的 HTML 主报告。
4. 没有合法 llm-review-sections.json 时，不发送 HTML 主报告。
5. failed、missing、skipped 不生成或发送市场结论。
6. partial 可以发送报告，但标题和摘要必须标记“数据维度不完整”，并引用技术参考。
7. 不生成交易建议、仓位建议、目标价、止盈止损或确定性买卖指令。
8. 不把 secret、token、webhook URL 写入日志、状态 JSON、HTML 或 Markdown。
9. 自动调试只能诊断、重试安全命令、生成补丁建议；不得无人确认地修改代码、改 cron、改密钥、删除历史产物或绕过校验。

执行步骤：
1. 进入仓库目录，确认 .venv/bin/python 可用，记录开始时间。
2. 写入 reports/daily-jobs/{{trade_date}}/heartbeat.json，当前阶段为 daily_update。
3. 执行 daily-update，并把 stdout/stderr 写入 reports/daily-jobs/{{trade_date}}/logs/daily_update.log。
4. 读取 reports/daily-runs/{{trade_date}}/interface-status.json：
   - skipped：写 job-status.json，发送 skipped/监控摘要给 main，不发送市场结论。
   - failed 或缺失：写 failed job-status.json，发送 critical 诊断给 main，停止报告路径。
   - passed/partial：继续。
5. 执行 daily-review --output-format context，生成 review-context.json。
6. 调用 Claude Code 非交互命令，让它使用 $a-share-daily-review skill，只基于 review-context.json 写出 llm-review-sections.json。
7. 执行 daily-review --llm-output ... --output-format html。只有该命令返回 0，且 HTML 和技术参考都存在时，才允许发送报告。
8. 聚合质量指标：阶段退出码、主表行数、失败接口数、blocked_sections、llm_sections_validated、html_exists、data_notes_exists、连续失败、重复发送风险。
9. 写 job-status.json 和 job-summary.md。
10. 发送：
    - 报告消息：通过 OpenClaw `feishu` channel 发给 main,candy，包含交易日期、整体状态、HTML 路径、技术参考路径、数据质量摘要和非投资建议声明。
    - 监控/告警消息：只通过 OpenClaw `feishu` channel 发给 main，包含失败阶段、诊断摘要、复查命令、关键 artifact 路径和是否需要人工介入。
11. 如果任何阶段 critical，启动“受限诊断”而不是自动修复生产代码；见本文档“自动调试和受限自愈策略”。

完成条件：
- job-status.json 已写入；
- job-summary.md 已写入；
- heartbeat 显示 finished 或 failed；
- 发送结果已记录；
- 若报告发送，Python HTML validator 已通过。
```

## OpenClaw Watchdog Prompt 模板

watchdog 应在主任务预期完成后 30-60 分钟执行，目标是发现“主任务根本没启动”或“任务卡住”。

```text
你是 a-share-info-hub 的 watchdog。请检查 /mnt/tool/2-projects/a-share-info-hub
中 trade_date={{YYYY-MM-DD}} 的每日任务是否按预期完成。

检查项：
1. 是否存在 reports/daily-jobs/{{trade_date}}/job-status.json。
2. 如果不存在且当前时间已超过预期 deadline，发送 critical missed-run 告警给 OpenClaw agent main。
3. 如果 job-status.json 为 running，读取 heartbeat.json：
   - heartbeat 超过阈值未更新，发送 critical stale-heartbeat 告警给 main。
   - current_stage_elapsed_seconds 超过该阶段 hard timeout，发送 critical timeout 告警给 main。
4. 如果 overall_status 为 failed 或 health_level 为 critical，发送监控摘要给 main。
5. 不生成市场结论，不修改业务代码，不重跑采集；只做检查、告警和受限诊断建议。

输出：
- 写入或更新 reports/daily-jobs/{{trade_date}}/watchdog-status.json。
- 监控消息只发给 main。
```

## 实施工作 DAG

1. 运行环境基线
   - 输入：`requirements.txt`、目标机器 Python 版本、网络访问能力。
   - 输出：仓库内 `.venv` 和依赖安装记录。
   - 依赖：无。
   - 触碰模块：部署文档或运维说明；不改业务代码。
   - 风险：当前环境缺少 `duckdb`、`pyarrow`、`pydantic`、`pytest`。
   - 验证：`.venv/bin/python -m pytest tests/ -q` 通过；`.venv/bin/python -m a_share_info_hub --help` 可执行。

   建议初始化命令：

   ```text
   python3 -m venv .venv
   .venv/bin/python -m pip install --upgrade pip
   .venv/bin/python -m pip install -r requirements.txt
   ```

2. 编排入口
   - 输入：OpenClaw cron 触发、交易日期、输出根目录、是否忽略代理、报告模式。
   - 输出：一次 OpenClaw orchestrated job 的状态 JSON、人读摘要和消息发送审计。
   - 依赖：运行环境基线。
   - 触碰模块：OpenClaw task prompt、可选仓库薄编排入口；复用现有 CLI，不重写采集或复盘逻辑。
   - 风险：OpenClaw prompt 变成隐式业务逻辑，导致与 `daily-update` / `daily-review` 语义不一致。
   - 验证：mock 成功、`partial`、`failed`、`skipped` 四类状态；断言 OpenClaw 最终仍调用公开 CLI 并读取状态文件。

3. 交易日期解析
   - 输入：调度运行时本地日期和可选 `--trade-date`。
   - 输出：传递给公开 CLI 的 `YYYY-MM-DD`。
   - 依赖：编排入口。
   - 触碰模块：编排入口参数解析。
   - 风险：跨时区或节假日导致跑错日期。
   - 验证：默认使用 Asia/Shanghai 日期；显式日期不被覆盖；非交易日保持 `skipped`。

4. 数据采集阶段
   - 输入：`trade_date`。
   - 输出：`reports/daily-runs/YYYY-MM-DD/interface-status.json` 和 `daily-data-summary.md`。
   - 依赖：交易日期解析。
   - 触碰模块：不改采集核心；只调用 `daily-update`。
   - 风险：AKShare 接口失败、代理干扰、交易日历不可用。
   - 验证：`passed` / `partial` 继续下一步；`failed` 阻断报告；`skipped` 发送非交易日摘要或不发送，按用户配置决定。

5. Context 生成阶段
   - 输入：daily run artifacts。
   - 输出：`reports/daily-reviews/YYYY-MM-DD/review-context.json`。
   - 依赖：数据采集状态为 `passed` 或 `partial`。
   - 触碰模块：不改复盘核心；只调用 `daily-review --output-format context`。
   - 风险：标准化表缺失或状态文件损坏。
   - 验证：context 文件存在且通过现有 Pydantic 校验。

6. LLM sections 生成阶段
   - 输入：`review-context.json` 和 `skills/a-share-daily-review/references/report-prompt.md`。
   - 输出：`llm-review-sections.json`。
   - 依赖：Context 生成成功。
   - 触碰模块：编排入口调用 Claude Code 非交互命令；不新增独立 LLM API adapter。
   - 风险：Claude Code 认证失效、CLI 卡在交互、skill 未被发现、输出路径缺失、LLM 输出越界、缺字段、包含交易行动语言或引用缺失事实。
   - 验证：Claude Code 命令必须在无人输入时退出；必须生成目标 `llm-review-sections.json`；最终必须由 `daily-review --llm-output ... --output-format html` 校验；校验失败不发送用户报告。

7. HTML 渲染阶段
   - 输入：context 和 `llm-review-sections.json`。
   - 输出：`a-share-daily-review.html` 和 `a-share-daily-review-data-notes.md`。
   - 依赖：LLM sections 生成成功。
   - 触碰模块：不改渲染核心；只调用公开 CLI。
   - 风险：HTML 校验失败或技术字段泄漏。
   - 验证：CLI 返回 0；两个输出文件存在；技术参考记录 `partial` 和接口失败。

8. 发送通道
   - 输入：HTML 报告、技术参考、任务状态摘要、收件人配置。
   - 输出：发送成功记录或失败原因。
   - 依赖：OpenClaw Feishu channel 已配置；HTML 渲染成功或失败摘要已生成。
   - 触碰模块：OpenClaw message 发送配置；可选仓库发送 adapter 只负责调用 OpenClaw。
   - 风险：OpenClaw Gateway 不可用、channel target 配错、重复发送、消息过长、发送成功但状态未落盘。
   - 验证：报告消息发送给 main,candy；监控消息只发送给 main；失败时不无限重试；发送结果写入任务状态。

9. 运行质量评估
   - 输入：各阶段退出码、Claude Code 退出码和日志、`interface-status.json`、`review-context.json`、HTML/技术参考路径、OpenClaw delivery receipt、历史 job 状态。
   - 输出：`job-health` 判断、质量指标、告警级别和 OpenClaw/飞书通知内容。
   - 依赖：数据采集、报告渲染和发送通道。
   - 触碰模块：编排入口的状态聚合逻辑。
   - 风险：只记录失败，不识别数据质量下降；只看当日，不识别连续失败。
   - 验证：用 fixture 模拟主表行数过低、增强接口连续失败、HTML 校验失败、OpenClaw/飞书发送失败和重复发送。

10. Watchdog 检查
   - 输入：预期运行时间、`reports/daily-jobs/YYYY-MM-DD/job-status.json`、最近一次 delivery 状态。
   - 输出：missed-run 告警或 heartbeat 记录。
   - 依赖：OpenClaw watchdog prompt、调度配置草案和任务状态目录。
   - 触碰模块：OpenClaw watchdog task；可作为编排入口的 `--check-latest` 模式，或单独的轻量检查命令。
   - 风险：主任务没有启动时，没有任何状态文件；只靠主任务内部告警无法发现。
   - 验证：删除或移动当日 job 状态文件，watchdog 必须向 main 发送 critical 告警。

11. 调度配置
   - 输入：目标机器、OpenClaw cron 命令、运行时间、Feishu channel target 配置、环境变量。
   - 输出：OpenClaw cron 或系统 cron 调 OpenClaw 的配置说明。
   - 依赖：编排入口和发送通道已通过 smoke。
   - 触碰模块：部署文档；生产机器配置不提交密钥。
   - 风险：工作目录错误、OpenClaw Gateway 不可用、channel target 配错、PATH 中无 `openclaw` 或 `.venv/bin/python`。
   - 验证：手动触发一次完整 dry-run；再由 OpenClaw scheduler 触发一次真实运行。

12. 运维和回放
    - 输入：任务状态、日志、历史 artifacts。
    - 输出：重跑命令、失败诊断路径和发送审计记录。
    - 依赖：调度配置。
    - 触碰模块：报告目录或日志目录。
    - 风险：历史重跑覆盖当日状态、重复发送旧报告。
    - 验证：指定 `--trade-date` 重跑不会自动发送，除非显式开启发送；重复发送必须要求人工确认或显式 force。

13. 自动调试和受限自愈
    - 输入：失败阶段、阶段日志、job-status.json、watchdog-status.json、最近一次测试结果。
    - 输出：诊断摘要、可重跑命令、最小补丁建议、是否需要人工确认。
    - 依赖：运行质量评估和 watchdog。
    - 触碰模块：OpenClaw diagnosis prompt；默认不改业务代码。
    - 风险：LLM 误判并自动改坏生产链路、隐藏失败、重复发送、泄漏密钥。
    - 验证：故障注入后，自动诊断只能执行只读检查和安全重试；任何代码修改、cron 修改、密钥修改、历史产物删除都必须停在人工确认。

## 核心契约

- 日常采集入口只使用 `python -m a_share_info_hub daily-update`。
- 日常复盘入口只使用 `python -m a_share_info_hub daily-review`。
- 定时任务实际命令必须使用 `.venv/bin/python -m ...`，避免依赖系统 Python 或 shell 激活状态。
- OpenClaw 是最外层 orchestrator；OpenClaw 可以调度、调用 CLI、调用 Claude Code、发送消息和启动诊断，但不能替代 Python validator。
- OpenClaw Feishu channel 当前为 main 和 candy；报告消息发送给二者，监控、告警和修复请求只发送给 main。
- Claude Code 必须以非交互方式运行；如果命令需要人工输入、认证确认或 IDE 会话，则不能进入 cron。
- Claude Code 运行必须显式指定仓库工作目录，并把 stdout/stderr 写入 job 日志。
- `failed`、`missing` 不生成或发送市场结论。
- `skipped` 不调用行情接口；是否发送非交易日摘要由配置决定。
- `partial` 可以发送报告，但飞书标题必须标记“数据维度不完整”，正文引用技术参考。
- 没有合法 `llm-review-sections.json` 时，不发送 HTML 主报告。
- OpenClaw token、飞书 webhook、secret、签名密钥不得写入仓库、日志、HTML、Markdown 或状态 JSON。
- 每次任务必须写出机器可读状态，至少包含 `trade_date`、阶段状态、报告路径、飞书发送状态、质量指标、告警级别和失败摘要。
- 自动修复默认是“建议和待确认补丁”，不是无人值守写代码；只有明确列入 allowlist 的安全动作可以自动执行。

## 自动调试和受限自愈策略

自动化失败处理分四级，OpenClaw 只能在对应级别内行动：

| 级别 | 允许动作 | 禁止动作 | 发送对象 |
| --- | --- | --- | --- |
| L0 记录 | 写状态、汇总日志、发送告警 | 修改代码或重跑会改变状态的命令 | `main` |
| L1 只读诊断 | 读取日志、读取 JSON、运行 `--help`、运行 `pytest`、检查 OpenClaw/Gateway 状态 | 改文件、改 cron、发送报告 | `main` |
| L2 安全重试 | 重试网络瞬断类发送、重跑纯校验命令、重新读取状态 | 重跑 `daily-update` 覆盖当日采集、改交易日、跳过 validator | `main` |
| L3 人工确认修复 | 生成最小补丁、给出 apply 命令和验证命令 | 自动提交、自动部署、自动改密钥、删除历史产物 | `main` |

允许自动执行的安全动作：

- 重新读取 `job-status.json`、`heartbeat.json`、`interface-status.json`、`review-context.json`。
- 查看阶段日志和 `logs/external-interface-failures.jsonl`。
- 运行 `.venv/bin/python -m a_share_info_hub --help`。
- 运行 `.venv/bin/python -m pytest tests/ -q`。
- 在同一 output_root 下重新运行 `daily-review --output-format context` 或 HTML validator，但前提是不覆盖已发送成功的报告状态。
- 在发送失败且未成功发送过同一 `trade_date` 时，有限次数重试 OpenClaw 消息发送。

必须人工确认的动作：

- 修改 Python、skill、prompt、cron 或 OpenClaw 配置。
- 修改 `.env.local`、OpenClaw secrets、飞书 app credentials。
- 删除或移动 `reports/daily-runs/`、`reports/daily-reviews/`、`reports/daily-jobs/` 中的历史产物。
- 对同一 `trade_date` 强制重复发送报告。
- 在 `daily-update failed`、`missing` 或 `skipped` 时生成市场结论。
- 用 `deterministic` 报告替代正式 LLM sections 报告发送给用户。

### 自动诊断 Prompt 模板

```text
你是 a-share-info-hub 的受限诊断 agent。请诊断 trade_date={{YYYY-MM-DD}} 的每日任务失败。

边界：
- 只做 L0/L1/L2 动作；不要修改代码、cron、密钥或历史产物。
- 不生成市场结论或投资建议。
- 不发送 HTML 主报告。
- 如果发现需要代码或配置修改，只输出最小补丁建议、风险和验证命令，等待人工确认。

请检查：
1. reports/daily-jobs/{{trade_date}}/job-status.json
2. reports/daily-jobs/{{trade_date}}/heartbeat.json
3. reports/daily-jobs/{{trade_date}}/logs/*.log
4. reports/daily-runs/{{trade_date}}/interface-status.json
5. reports/daily-reviews/{{trade_date}}/review-context.json
6. reports/daily-reviews/{{trade_date}}/llm-review-sections.json
7. reports/daily-reviews/{{trade_date}}/a-share-daily-review.html
8. reports/daily-reviews/{{trade_date}}/a-share-daily-review-data-notes.md

输出：
- 失败阶段
- 直接证据
- 是否可安全重试
- 如需人工介入，列出具体原因
- 下一条建议命令
- 不超过 5 条的最小修复建议
```

## OpenClaw Cron 配置草案

OpenClaw cron 可作为生产调度主路径。第一版建议注册两个 job：

- 主任务：交易日收盘后执行每日任务 prompt。
- Watchdog：预期完成后检查 job 状态和 heartbeat。

示例命令使用 `--agent main`，因为调度、监控和修复请求的 owner 是 `main`。报告正文仍按 prompt 通过 OpenClaw `feishu` channel 发送给 main,candy。

下面的 `--timeout-seconds 7200` 是 OpenClaw agent turn 的最外层兜底，不是业务 SLA，也不是 `overall watchdog deadline`。第一版各阶段 hard timeout 合计约 6720 秒，外层 7200 秒只用于防止 agent turn 永久挂起；如果后续在脚本内实现严格 overall hard kill，再把 OpenClaw 外层 timeout 调整为“脚本 overall hard timeout + 5-10 分钟缓冲”。

```text
openclaw cron add \
  --name a-share-daily-report \
  --description "A-share daily update, review, validation, delivery" \
  --agent main \
  --session isolated \
  --tools exec,read,write \
  --cron "0 16 * * 1-5" \
  --tz Asia/Shanghai \
  --timeout-seconds 7200 \
  --message "$(cat docs/openclaw-a-share-daily-orchestrator.prompt.md)"

openclaw cron add \
  --name a-share-daily-report-watchdog \
  --description "A-share daily report missed-run and stale heartbeat watchdog" \
  --agent main \
  --session isolated \
  --tools exec,read,write \
  --cron "0 17 * * 1-5" \
  --tz Asia/Shanghai \
  --timeout-seconds 900 \
  --message "$(cat docs/openclaw-a-share-daily-watchdog.prompt.md)"
```

如果系统 cron 仍作为外层触发器，它也应该触发 OpenClaw prompt，而不是直接绕过 OpenClaw 调 `.venv/bin/python`：

```text
0 16 * * 1-5 cd /mnt/tool/2-projects/a-share-info-hub && openclaw agent --agent main --message "$(cat docs/openclaw-a-share-daily-orchestrator.prompt.md)" >> logs/openclaw-a-share-daily-report.cron.log 2>&1
0 17 * * 1-5 cd /mnt/tool/2-projects/a-share-info-hub && openclaw agent --agent main --message "$(cat docs/openclaw-a-share-daily-watchdog.prompt.md)" >> logs/openclaw-a-share-daily-watchdog.cron.log 2>&1
```

上述 prompt 文件是建议落盘形态；如果暂不新增文件，也必须把本文档中的 prompt 模板原样复制到 OpenClaw cron job 配置中，并记录配置快照。生产配置不得包含密钥。

## 建议新增文件

第一版如需实施，建议新增最少文件：

```text
docs/
  openclaw-a-share-daily-orchestrator.prompt.md
  openclaw-a-share-daily-watchdog.prompt.md
scripts/
  run_daily_report_job.py
```

prompt 文件保存 OpenClaw 固定任务正文；脚本入口只做可测试的状态聚合和发送辅助，不实现采集、标准化或 HTML 渲染。若发送适配变复杂，再按已确认渠道拆分；不要在未确认渠道前预建多套 adapter。

如果选择不在仓库内放编排脚本，也可以只写 OpenClaw prompt 并让 OpenClaw 直接调用现有 CLI。但必须确保状态写入、失败分支、重复发送和 watchdog 都有可审计产物。

## 任务状态建议

建议每次任务写入：

```text
reports/daily-jobs/YYYY-MM-DD/job-status.json
reports/daily-jobs/YYYY-MM-DD/job-summary.md
```

状态字段建议：

- `trade_date`
- `started_at`
- `finished_at`
- `overall_status`
- `daily_update_status`
- `context_status`
- `llm_sections_status`
- `html_status`
- `send_status`
- `health_status`
- `health_level`
- `quality_metrics`
- `alerts`
- `artifacts`
- `failure_reason`
- `not_investment_advice`

质量指标至少包含：

- `freshness_minutes`：任务完成时间和目标交易日收盘后预期完成时间的偏差。
- `daily_update_exit_code`、`daily_review_context_exit_code`、`external_background_exit_code`、`daily_review_context_with_external_exit_code`、`daily_review_html_exit_code`。
- `claude_code_exit_code`、`claude_code_log_path`、`external_background_log_path`、`external_background_path`、`llm_sections_path`。
- `daily_update_overall_status`：来自 `interface-status.json.overall_status`。
- `main_snapshot_rows`：主表行数，低于阈值时告警。
- `failed_source_count`、`schema_changed_source_count`、`success_empty_source_count`。
- `blocked_sections`：来自 `review-context.json`。
- `html_exists`、`data_notes_exists`、`llm_sections_exists`、`llm_sections_validated`。
- `delivery_provider`：推荐 `openclaw_message`，兼容旧 `openclaw_agent`，或 fallback `feishu_webhook`。
- `delivery_status`、`delivery_response_code`、`delivery_recipients`。
- `consecutive_failures`：从历史 job 状态计算。
- `duplicate_send_guard`：同一 `trade_date` 是否已经成功发送过。
- `watchdog_checked_at`、`expected_job_deadline`、`missed_run_detected`。
- `current_stage`、`current_stage_started_at`、`current_stage_elapsed_seconds`。
- `heartbeat_path`、`heartbeat_updated_at`、`heartbeat_age_seconds`。
- `stage_sla`：每个阶段的 soft warning 和 hard timeout。

新增 `reports/daily-jobs/` 时必须同步创建该目录的 `AGENTS.md` 和 `claude.md`，并更新 `reports/AGENTS.md`。

## 运行质量监控

运行质量分三层判断：

- `job_status`：编排流程是否跑完，例如 `passed`、`partial`、`failed`、`skipped`。
- `data_quality_status`：数据是否足够支持报告，例如主表行数、接口失败数、blocked section、DuckDB 状态。
- `delivery_status`：OpenClaw 是否成功把本次结果送达对应 Feishu channel target。

建议告警级别：

- `info`：非交易日 `skipped`、正常发送成功、仅有可接受的事件型空结果。
- `warning`：`partial`、增强接口失败、板块快照缺失、发送重试后成功、主表行数显著低于近 5 次均值。
- `critical`：`failed`、`missing`、主表不可用、HTML 校验失败、OpenClaw/飞书发送失败、连续 2 次以上任务失败、同一交易日重复发送风险。
- `critical` 还包括 Claude Code 非交互命令失败、超时、未生成 `llm-review-sections.json` 或 sections 未通过 Python 校验。
- `critical` 还包括预期运行截止时间后仍没有当日 job 状态文件，即 missed-run。

OpenClaw/飞书消息必须区分“报告消息”和“告警消息”：

- 报告消息：交易日期、整体状态、报告路径、技术参考路径、核心数据质量摘要和非投资建议声明。
- 告警消息：失败阶段、失败摘要、可复查命令、关键 artifact 路径、是否需要人工介入。

监控不能只依赖发送成功。即使 OpenClaw/飞书发送成功，只要数据质量为 `critical`，任务整体仍应标记为失败或需要人工处理。

必须设计 missed-run 监控：主任务没有启动、OpenClaw cron 未加载、机器睡眠或虚拟环境路径错误时，主任务不会写失败状态，也不会主动发送告警。第一版建议在主任务预期完成后 30-60 分钟运行一个 watchdog 检查：如果当日应为交易日但没有 `job-status.json`，或状态仍停在 `running` 超过阈值，就向 main 发送 critical 告警。

## 分阶段 SLA 和 Heartbeat 策略

任务耗时不能用单一固定值判断。`timeout` 的退出码 `124` 只表示某个子进程被 `timeout` 杀掉，不表示任务应该在 124 秒内完成。正式实现必须按阶段设置 soft warning、hard timeout 和 heartbeat。

### 阶段计时

每个阶段都必须记录：

- `stage`
- `started_at`
- `finished_at`
- `elapsed_seconds`
- `exit_code`
- `status`
- `log_path`

建议阶段：

- `daily_update`
- `daily_review_context`
- `external_background_fusion`
- `daily_review_context_with_external`
- `claude_code_sections`
- `daily_review_html`
- `delivery_send`
- `watchdog_check`

### 初始阈值

第一版使用保守固定阈值，运行 10 个交易日后再用历史数据调参。

| 阶段 | soft warning | hard timeout |
| --- | ---: | ---: |
| `daily_update` | 25 分钟 | 60 分钟 |
| `daily_review_context` | 3 分钟 | 10 分钟 |
| `external_background_fusion` | 10 分钟 | 30 分钟 |
| `daily_review_context_with_external` | 3 分钟 | 10 分钟 |
| `claude_code_sections` | 10 分钟 | 30 分钟 |
| `daily_review_html` | 3 分钟 | 10 分钟 |
| `delivery_send` | 30 秒 | 2 分钟 |
| overall watchdog deadline | 45 分钟 | 90 分钟 |

soft warning 只写入 `job-status.json` 并发送 warning 级别监控告警，不主动杀进程。hard timeout 才终止对应子进程，标记为 `critical`。

`overall watchdog deadline` 是运行质量和 missed-run/stale-run 判断阈值，不是 OpenClaw cron 的 `--timeout-seconds`，也不替代单阶段 hard timeout。OpenClaw 外层 timeout 只能作为最后兜底，必须留出阶段超时、状态落盘和告警发送的缓冲；业务是否通过仍以 `job-status.json`、阶段结果、Python validator 和 watchdog 为准。

### Heartbeat

编排入口必须每 30-60 秒写入：

```text
reports/daily-jobs/YYYY-MM-DD/heartbeat.json
```

建议字段：

- `trade_date`
- `pid`
- `current_stage`
- `current_stage_started_at`
- `current_stage_elapsed_seconds`
- `last_log_path`
- `last_log_updated_at`
- `updated_at`

watchdog 如果发现 `heartbeat.json` 超过阈值未更新，或 `current_stage_elapsed_seconds` 超过该阶段 hard timeout，应向 main 发送 `critical` 告警。heartbeat 用于发现“进程还在但没有进展”的情况，不能替代最终状态文件。

### 动态阈值

积累至少 10 个交易日后，阈值可以基于历史耗时自动调整：

```text
soft = max(固定下限, 历史 P95 * 1.5)
hard = max(固定下限, 历史 P95 * 3)
```

动态阈值只能放宽或收紧单阶段 SLA，不能覆盖安全门禁：主表失败、HTML 校验失败、OpenClaw/飞书发送失败、Claude Code 未生成 JSON 仍然必须是 `critical`。

### 子进程 Timeout 方式

`timeout` 应包在每个子进程上，而不是只包整个任务：

```text
timeout 3600 .venv/bin/python -m a_share_info_hub daily-update ...
timeout 1800 claude -p ...
timeout 600 .venv/bin/python -m a_share_info_hub daily-review ...
timeout 120 openclaw agent --agent main --message ...
```

这样可以准确定位慢或卡死的阶段。若退出码为 `124`，记录为该阶段 hard timeout，而不是把 `124` 当成秒数或业务状态。

## 验收标准

实施完成后，至少满足：

- `pytest tests/ -q` 通过。
- mock 成功路径生成 HTML 并记录发送成功。
- mock `daily-update failed` 时不生成市场报告，只发送或记录失败摘要。
- mock `daily-review` 校验失败时不发送 HTML。
- mock Claude Code 失败、超时或未生成 `llm-review-sections.json` 时不发送 HTML，并向 main 发送或记录 critical 告警。
- mock 发送失败时任务整体状态为 failed 或 partial-failed，并保留报告 artifacts。
- mock 数据质量异常时生成 warning 或 critical 告警，即使进程退出码为 0。
- mock 单阶段超过 soft warning 时不中断任务，但写入 warning 并发送监控 warning。
- mock 单阶段超过 hard timeout 时终止该阶段，任务标记 critical。
- mock heartbeat 停止更新时，watchdog 向 main 发送 critical。
- mock 连续失败时提升告警级别。
- mock 同一 `trade_date` 已成功发送时阻止重复发送，除非显式传入强制发送参数。
- mock 主任务未运行时，watchdog 能识别缺失的 job 状态并向 main 发送 critical 告警。
- mock OpenClaw Gateway 不可用或 channel target 配错时，任务保留报告 artifacts，`delivery_status` 为 failed，并记录 critical 诊断。
- mock 报告发送路由：报告消息只发送给 main,candy，监控/告警/修复请求只发送给 main。
- mock 自动诊断：只读检查和安全重试可执行；代码修改、cron 修改、密钥修改和重复发送必须停在人工确认。
- 非交易日返回 `skipped`，不调用行情接口，不发送市场结论。
- 所有产物路径使用相对项目根或显式 `output_root`，不写本机绝对路径。
- 日志不包含 secret、token、完整飞书 webhook URL、OpenClaw token 或收件人敏感信息。

## 已运行 Smoke 验证

以下验证在本机工作区执行，验证对象是 Claude Code 非交互运行、skill 发现、sections 产物、Python validator 和超时捕捉。验证过程中的临时 smoke 文件已清理，不作为正式报告产物保留。

### 本机环境

- Claude Code CLI：`/home/binzhan/.local/bin/claude`
- Claude Code 版本：`2.1.185 (Claude Code)`
- 非交互模式：`claude -p`
- 本机 Python 虚拟环境：`.venv`
- 依赖验证：`.venv/bin/python -m pytest tests/ -q`，结果 `47 passed`

### Claude Code 非交互和 Skill 发现

- 使用 `timeout 180s claude -p --permission-mode acceptEdits --output-format json <prompt>` 执行 smoke。
- Claude Code 在无人输入下完成，退出码 `0`，耗时约 `97s`。
- skill 发现 smoke 能识别 `$a-share-daily-review`，返回 `skill_loaded: true`，并能读取该 skill 的第一步工作流。
- 注意：shell 命令中不能直接把 `$a-share-daily-review` 放在双引号里，否则 `$a` 会被 shell 变量展开。正式实现必须使用 prompt 文件、单引号 here-doc 或转义 `$`。

### Sections 产物和 Python 校验

- Claude Code 能写出 `llm-review-sections.json`，JSON 可解析，`schema_version` 为 `daily_review_sections.v1`。
- 使用 `.venv/bin/python -m a_share_info_hub daily-review --trade-date 2026-06-18 --external-background reports/daily-reviews/2026-06-18/external-background-fusion.json --llm-output <smoke-sections.json> --output-format html` 校验通过，退出码 `0`。
- 重要约束：context 阶段和 render 阶段必须传入一致的 `--external-background`。若 render 阶段遗漏该参数，Python validator 会因 external background sections 越界而阻断 HTML 生成；该阻断行为符合预期。

### 失败和超时捕捉

- 使用 `timeout 1s claude -p ...` 可得到退出码 `124`，可作为 Claude Code 超时失败信号。
- 正式编排必须同时检查：Claude Code 退出码、超时、目标 `llm-review-sections.json` 是否存在、JSON 是否可解析、Python validator 是否通过。
- Claude Code 的 `--output-format json` 包装的是 Claude Code 运行结果；其中 `result` 字段仍可能包含 Markdown fence。正式任务不能只解析 stdout，必须以目标 `llm-review-sections.json` 文件和 Python validator 作为最终门禁。

## 首次真实 Dry-run 前测试计划

北京时间 2026-06-22 16:00 是首次真实交易日 dry-run。在此之前可以并且应该执行多轮实施测试，目标是验证编排、状态、发送和故障处理，而不是伪造真实当日行情成功。

允许的预演测试：

1. 环境测试
   - 创建或复用 `.venv`。
   - 运行 `.venv/bin/python -m pytest tests/ -q`。
   - 运行 `.venv/bin/python -m a_share_info_hub --help`。

2. 历史日期回放测试
   - 使用已有 `2026-06-18` artifacts 执行 context、external background fusion、Claude Code sections、HTML validator 和 job 状态写入。
   - 不调用真实 `daily-update` 刷新历史行情，避免把旧样本误当作新的实盘采集验证。

3. OpenClaw 发送测试
   - 使用 OpenClaw Feishu channel 发送报告消息和告警消息。
   - 验证报告消息发给 main,candy，监控/告警消息只发给 main。
   - 验证 OpenClaw token、飞书密钥不进入日志、状态 JSON、HTML 或 Markdown。
   - 验证 OpenClaw Gateway 不可用、channel target 错误、发送超时能被记录为 delivery failure。

4. 故障注入测试
   - 模拟 `daily-update` 非零退出。
   - 模拟 Claude Code 超时、非零退出、未生成 `llm-review-sections.json`。
   - 模拟 HTML validator 失败。
   - 模拟 OpenClaw / 飞书发送失败。
   - 模拟重复发送同一 `trade_date`。
   - 模拟主任务未运行，让 watchdog 发现缺失的 `job-status.json`。
   - 模拟失败后自动诊断，确认不会自动改代码、改配置或跳过 validator。

5. 非交易日测试
   - 选择周末或明确休市日期，验证 `skipped` 不生成市场结论、不发送正式报告。
   - 如果发送非交易日摘要，飞书标题必须明确是 `skipped`，不能像交易日报告。

这些预演测试可以多次运行，但必须写入测试专用 job 目录或使用 dry-run 标记，避免和 2026-06-22 的首次真实交易日状态混淆。真实 dry-run 前的通过标准是：OpenClaw orchestrator dry-run 通过、main,candy 收到报告测试消息、main 收到监控/失败测试消息、重复发送保护有效、watchdog 能发出 missed-run 告警、自动诊断遵守受限自愈边界、所有失败都能在 `job-status.json` 中定位到阶段。

## 推荐上线顺序

1. 在本机创建 `.venv`，安装依赖并跑通测试。
2. 手动执行一次 `daily-update` 和 `daily-review --output-format context`。
3. 手动执行 Claude Code 非交互命令，确认它能调用 `$a-share-daily-review` skill 并生成 `llm-review-sections.json`。本项 smoke 已通过，但实施后仍需用正式编排入口再跑一次 dry-run。
4. 配置 OpenClaw cron / scheduler 和 OpenClaw Feishu channel 发送路由；报告给 main,candy，监控给 main。
5. 按“首次真实 Dry-run 前测试计划”完成多轮实施测试和故障注入。
6. 在北京时间 2026-06-22 16:00 执行首次真实交易日 dry-run，采集当日数据、生成报告、记录 job 状态并通过 OpenClaw 发送测试消息。
7. 配置 OpenClaw cron；如使用系统 cron，也只触发 OpenClaw prompt，不直接绕过 OpenClaw orchestrator。
8. 连续观察至少 3 个交易日，确认 `passed`、`partial`、发送结果和失败诊断都可追溯。

## 2026-06-21 仓库内实施结果

本次已完成第一版仓库内实施，范围仍遵守本文档开头的边界：不提交密钥、不配置真实生产调度器、不发送真实报告。

已新增或更新：

- `scripts/run_daily_report_job.py`：薄编排入口，只调用 `.venv/bin/python -m a_share_info_hub daily-update`、`.venv/bin/python -m a_share_info_hub daily-review` 和 Claude Code 非交互命令；写入 `job-status.json`、`job-summary.md`、`heartbeat.json`、阶段日志和发送审计；包含阶段 SLA、hard timeout、soft warning、重复发送保护、数据质量告警、连续失败统计和 watchdog 检查。
- `docs/openclaw-a-share-daily-orchestrator.prompt.md`：OpenClaw 主任务 prompt。
- `docs/openclaw-a-share-daily-watchdog.prompt.md`：OpenClaw missed-run/stale-heartbeat watchdog prompt。
- `docs/openclaw-a-share-daily-diagnosis.prompt.md`：受限诊断 prompt，只允许 L0/L1/L2 动作和人工确认前的补丁建议。
- `reports/daily-jobs/AGENTS.md` 和 `reports/daily-jobs/claude.md`：任务状态目录入口和索引。
- `tests/test_daily_report_job.py`：覆盖公开 CLI 调用、成功/partial/failed/skipped、Claude Code 超时或缺失 sections、HTML validator 失败、发送失败、OpenClaw message/agent 路由、soft/hard timeout、重复发送保护、连续失败和 watchdog missed-run/stale-heartbeat。
- `README.md` 和目录索引：补充 OpenClaw cron / system cron 触发 OpenClaw prompt 的配置方式，避免生产绕过 OpenClaw 直接调 Python 脚本。

已运行验证：

- `.venv/bin/python -m pytest tests/ -q`：`66 passed`。
- `.venv/bin/python -m py_compile scripts/run_daily_report_job.py`：通过。
- `.venv/bin/python -m a_share_info_hub --help`：可执行，公开 CLI 仍为 `daily-update` 和 `daily-review`。
- `.venv/bin/python scripts/run_daily_report_job.py --help`：可执行，支持 `feishu_webhook`、`openclaw_message`、兼容旧值 `openclaw`、`openclaw_agent`。
- 使用 `--trade-date 2026-06-21 --output-root /tmp/a-share-job-smoke` 做非交易日 smoke：输出 `overall_status=skipped`，未进入复盘/HTML/发送链路，状态路径使用相对 output_root。

## 剩余上线前置

Claude Code 非交互、skill 发现、sections 生成、Python 校验和超时捕捉已有历史 smoke；仓库内编排、状态、watchdog 和路由 mock 已完成。首次真实交易日 dry-run 时间定为北京时间 2026-06-22 16:00；正式接入 OpenClaw cron 前仍需要在目标机器完成 OpenClaw Gateway/Feishu channel 真发送验证、真实交易日 dry-run、自动诊断 dry-run，以及连续至少 3 个交易日观察。
