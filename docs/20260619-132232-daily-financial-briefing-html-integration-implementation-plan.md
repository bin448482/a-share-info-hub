# $daily-financial-briefing 融入每日复盘 HTML 实施计划

本文档用于 review 将 `$daily-financial-briefing` 的外部财经信息融入 `$a-share-daily-review` HTML 主报告的修正方案。2026-06-19 再次复审后，最终设计调整为：由 `$a-share-daily-review` skill 在 agent runtime 内 spawn 6 个并行子 Agent，每个子 Agent 自己使用 `$daily-financial-briefing` 完成对应本地主题的外部研究；Python 只负责本地 evidence packet、受控 JSON 校验、HTML 渲染和可选的结构化审计辅助。

## 背景和问题

当前仓库已有两条相互独立的能力：

- `$a-share-daily-review`：读取本地每日 A 股快照 artifacts，生成 `review-context.json`、LLM sections、HTML 主报告和技术参考 Markdown。
- `$daily-financial-briefing`：由 agent 读取公开来源，围绕 `US Macro` 和 `Investment Bank Views` 生成带引用的当日财经信息简报。

修正目标是在不破坏 A 股本地证据边界的前提下，让外部信息围绕 `review-context.json` 中已经出现的本地主题发挥作用：解释风险约束、形成待验证问题、提示外部变量，但不能独立生成或覆盖 A 股结论。

HTML 不新增独立的 `外部宏观与机构观点背景` 章节。外部利率、通胀、汇率、投行观点等内容只能融合进 `大盘观察`、唯一的 `风险观察` 和唯一的 `下一步研究问题`。

## 为什么前两次设计不是这个方案

第一次设计偏差：

- 把问题理解成“`daily-review` 如何消费一个已经存在的 external background JSON”。
- 实施重点落在 Python 渲染层：读取 `external_background.v1` / `external_background_fusion.v1`、合并 sections、去掉独立 HTML 章节。
- 缺失点是没有设计真实外部信息获取链路，也没有回答 `$a-share-daily-review` 如何实际调用 `$daily-financial-briefing`。

第二次设计偏差：

- 把缺失的编排层继续放进 Python：`ThreadPoolExecutor + TopicRunner + FixtureTopicRunner + AgentCommandTopicRunner`。
- 这个方向可测试，但抽象边界错了。Python 可以并行执行函数或 subprocess，但不能直接调用 Codex/Claude runtime 的 skill。
- `AgentCommandTopicRunner` 只是一个 shell 命令适配器。未配置命令时只会 blocked；即使配置命令，也仍缺少自然语言 prompt 生成、skill 调用、浏览器/搜索和结果写回。
- Promptfoo 通过的是 fixture runner/fusion/HTML 链路，不证明真实 `$daily-financial-briefing` 被调用。

正确抽象：

- Skill 内部写“调用另一个 skill”通常仍是当前 agent 的串行工作流。
- 真正的并行能力来自 agent runtime 的 `Agent` 工具。
- `$a-share-daily-review` 应在自己的 workflow 中 spawn 6 个子 Agent，每个子 Agent 是独立上下文，分别使用 `$daily-financial-briefing` 聚焦一个本地主题。
- Python 层的 `external_background.py` 可以保留为 fixture smoke、schema 校验或可选 fusion 辅助，但不再是生产主编排路径。

## 核心决策

- 主编排发生在 `$a-share-daily-review` skill workflow，不发生在 Python subprocess runner。
- `$a-share-daily-review` 生成 `review-context.json` 后，抽取 6 个固定本地主题。
- 父 agent 同时 spawn 6 个子 Agent；每个子 Agent 自己调用 `$daily-financial-briefing`。
- 每个子 Agent 只返回结构化 `TopicResult` JSON，不返回 Markdown 简报正文。
- 父 agent 等 6 个子 Agent 全部完成后汇总为 `external_background_fusion.v1`。
- `daily-review --external-background <fusion.json>` 只读取受控 JSON，不联网、不搜索、不调用 skill。
- `AgentCommandTopicRunner` 和 `--runner agent` 不作为生产方案或目标达成条件；最多作为 legacy/diagnostic 占位。
- `--runner fixture` 只用于 Python 管道 smoke 和回归测试，不能代表真实外部背景链路。

## 目标流程

```text
$a-share-daily-review skill
  │
  ├─ 1. 生成 review-context.json
  │
  ├─ 2. 从 review-context.json 抽取 6 个本地主题
  │
  ├─ 3. spawn 6 个并行子 Agent
  │     ├─ Agent: 大盘定性 -> 使用 $daily-financial-briefing
  │     ├─ Agent: 大盘结构 -> 使用 $daily-financial-briefing
  │     ├─ Agent: 市场宽度 -> 使用 $daily-financial-briefing
  │     ├─ Agent: 情绪与事件 -> 使用 $daily-financial-briefing
  │     ├─ Agent: 板块和结构 -> 使用 $daily-financial-briefing
  │     └─ Agent: 风险观察 -> 使用 $daily-financial-briefing
  │
  ├─ 4. 汇总 6 个 TopicResult -> external_background_fusion.v1
  │
  ├─ 5. 用 --external-background fusion.json 重新生成 context
  │
  ├─ 6. 生成 llm-review-sections.json
  │
  └─ 7. Python 校验并渲染 HTML + 技术参考 Markdown
```

HTML 主报告顺序保持：

```text
header：标题、交易日期、报告角色、声明
摘要
大盘观察
  大盘定性
  大盘结构
市场宽度观察
情绪与事件观察
板块和结构观察
风险观察
下一步研究问题
数据边界
metadata JSON
```

## 并行 Agent 编排契约

第一版固定 6 个本地主题：

```text
market_overview_assessment
market_overview_structure
market_breadth
sentiment_and_events
board_and_structure
risk_observations
```

父 agent 从 `review-context.json` 为每个主题构造一个 topic task：

```json
{
  "trade_date": "YYYY-MM-DD",
  "topic_key": "market_overview_structure",
  "local_summary": "极端上涨样本 136 只，极端下跌样本 24 只；blocked_sections=['board_snapshot']。",
  "evidence_boundary": "外部信息只能解释风险约束、形成待验证问题或提示变量；不能覆盖、补全或改写本地 A 股快照证据。",
  "allowed_external_scopes": ["US Macro", "Investment Bank Views"],
  "forbidden_boundaries": [
    "不得输出买入、卖出、仓位、目标价、止盈止损或实盘时点建议。",
    "不得把外部新闻或机构观点写成本地 A 股确定性结论。",
    "不得补推本地缺失的市场宽度、情绪事件、龙虎榜或板块结构。"
  ]
}
```

父 agent 对每个 topic spawn 一个子 Agent。子 Agent prompt 必须包含：

```text
使用 $daily-financial-briefing。

你只负责一个每日复盘本地主题，不输出通用新闻摘要。

输入：
- trade_date: <trade_date>
- topic_key: <topic_key>
- local_summary: <local_summary>
- evidence_boundary: <evidence_boundary>
- allowed_external_scopes: US Macro, Investment Bank Views
- forbidden_boundaries: <forbidden_boundaries>

任务：
1. 只在 allowed_external_scopes 内查找公开可引用信息。
2. 只输出与该 topic 相关的外部变量、风险候选或待验证问题。
3. 每个 finding 必须有 source_name 和 URL。
4. 不得输出交易建议。
5. 不得覆盖、补全或改写本地 A 股证据。
6. 不得补推本地缺失的板块、情绪、龙虎榜或市场宽度结论。

输出：
只返回 TopicResult JSON。不要返回 Markdown 正文。
```

每个子 Agent 返回：

```json
{
  "topic_key": "market_overview_structure",
  "external_findings": [
    {
      "text": "",
      "type": "fact|market_expectation|bank_view|inference",
      "report_usage": "context_note|risk_observation|follow_up_question",
      "local_relevance": "",
      "citations": [
        {
          "source_name": "",
          "title": "",
          "published_at": "",
          "accessed_at": "",
          "url": ""
        }
      ]
    }
  ],
  "information_gaps": [],
  "blocked": false,
  "blocked_reason": ""
}
```

父 agent 汇总 6 个结果，写出：

```json
{
  "schema_version": "external_background_fusion.v1",
  "source_skill": "daily-financial-briefing",
  "trade_date": "YYYY-MM-DD",
  "not_investment_advice": true,
  "topic_findings": [],
  "risk_candidates": [],
  "follow_up_candidates": [],
  "citations": [],
  "information_gaps": [],
  "issues": []
}
```

推荐同时保存审计产物：

```text
reports/daily-reviews/YYYY-MM-DD/external-background-topic-results.json
reports/daily-reviews/YYYY-MM-DD/external-background-fusion.json
```

如果父 agent 直接生成合格的 `external_background_fusion.v1`，可以直接传给 `daily-review --external-background`。如果需要额外校验，可以调用 Python 辅助逻辑读取 topic results 并重新生成 fusion，但这不是生产主编排要求。

## SKILL.md 更新要求

`skills/a-share-daily-review/SKILL.md` 的 workflow 需要把当前第 7 步改为并行 Agent 编排：

```text
7. If external background is requested and no ready external_background JSON is provided:
   - Read review-context.json.
   - Extract 6 local topics:
     market_overview_assessment, market_overview_structure, market_breadth,
     sentiment_and_events, board_and_structure, risk_observations.
   - Spawn 6 sub-agents in parallel. Each sub-agent must use
     $daily-financial-briefing, restricted to its topic and evidence boundary.
   - Each sub-agent returns TopicResult JSON.
   - After all sub-agents complete, merge their TopicResult outputs into
     external_background_fusion.v1 and write it under reports/daily-reviews/YYYY-MM-DD/.
   - Re-run daily-review context and HTML generation with
     --external-background reports/daily-reviews/YYYY-MM-DD/external-background-fusion.json.
```

`skills/a-share-daily-review/references/daily-review-workflow.md` 需要同步写清：

- Skill 内部串行调用另一个 skill 不是本方案。
- 并行外部背景获取必须通过 6 个子 Agent。
- 子 Agent 可以并行执行，每个子 Agent 内部自行使用 `$daily-financial-briefing`。
- Python 不自动联网、不自动调用 `$daily-financial-briefing`。
- `external_background_fusion.v1` 是进入 HTML 生成链路的唯一受控外部背景包。

## Python 边界

`daily-review` 保留可选参数：

```text
python -m a_share_info_hub daily-review --trade-date <YYYY-MM-DD> --external-background <path-to-external-background-fusion.json>
```

参数语义：

- `--external-background` 指向 agent 已生成的受控外部背景 JSON。
- Python 只做结构校验、引用校验、状态记录、边界校验和 HTML 渲染。
- Python 不搜索网页、不调用浏览器、不调用 LLM API、不调用 `$daily-financial-briefing`。
- 如果文件不可用、blocked 或 invalid，本地 A 股复盘仍继续生成。

`a_share_info_hub/external_background.py` 的定位调整为：

- 可保留：topic schema、fixture smoke、fusion 校验辅助、Promptfoo 离线回归。
- 不作为生产主路径：`AgentCommandTopicRunner`、`--runner agent`、subprocess command 不代表真实 skill 调用。
- 后续如继续使用，应把文档和测试名称明确标记为 legacy/fixture/validation helper，避免误判为真实 Agent 编排。

## 异常处理

- 子 Agent 无法找到可引用来源：该 topic 返回 `blocked=true` 和 `blocked_reason`，父 agent 不编造结论。
- 单个 topic blocked：fusion 仍可写出，但 `issues` 必须记录 blocked reason。
- 多个 topic blocked：外部背景最高只能作为 partial 或 blocked，不进入 HTML 核心正文。
- finding 缺少 URL 或 source_name：该 finding 不得进入 HTML 正文。
- 子 Agent 输出交易行动语言：丢弃该 finding，并在 fusion `issues` 记录原因。
- 子 Agent 试图覆盖本地 A 股证据：丢弃该 finding。
- 外部来源之间冲突：保留为风险观察或待验证问题，不合并成确定性判断。
- 子 Agent 返回非 JSON：父 agent 要求其修正一次；仍失败则该 topic blocked。
- 6 个子 Agent 未全部返回：不得把缺失 topic 静默视为通过。

## 测试和验收计划

新增或调整 pytest：

- `daily-review --external-background valid fusion` 生成 context，`external_background.status=passed`。
- valid fusion 不生成 `外部宏观与机构观点背景` 独立 HTML 章节。
- fusion 中的风险候选进入唯一的 `风险观察`。
- fusion 中的待验证问题进入唯一的 `下一步研究问题`。
- 缺少 URL 的 finding 不进入 HTML 正文。
- blocked external background 不阻断本地复盘，也不展示外部结论。
- invalid JSON 不阻断本地复盘，但技术 Markdown 写入错误。
- 外部背景不能补推 `blocked_sections`。
- HTML 正文不得包含 `passed`、`partial`、`blocked`、`invalid`、`schema_version`、`fixture`、模拟输入或内部状态说明。

新增或调整 Promptfoo / agent runtime 验收：

- external background passed 用例必须走并行 Agent 设计，输出审计行：

```text
external_background_source: parallel_agent_skill
external_background_parallel_agents: 6
external_background_topic_results: 6
external_background_schema: external_background_fusion.v1
```

- fixture 用例必须标记为：

```text
external_background_source: fixture_smoke
```

- `fixture_smoke` 不计入真实 `$daily-financial-briefing` 编排验收。
- 如果 eval provider 仍只使用手写 `external_background.v1` 或 `--runner fixture`，该用例只能算 legacy compatibility。
- 至少一个人工或 runtime 验收样例必须证明父 agent spawn 了 6 个子 Agent，而不是串行调用 6 次 skill。

审核命令：

```text
rg -n "AgentCommandTopicRunner|--runner agent|--runner fixture|external_background_source|parallel_agent_skill|external_background_parallel_agents" README.md docs skills eval a_share_info_hub tests
```

审核标准：

- 生产 workflow 说明中不得把 `--runner agent` 写成真实方案。
- 生产 workflow 说明中必须出现 `parallel_agent_skill` 或等价的 6 子 Agent 审计语义。
- `SKILL.md` 和 workflow reference 必须明确：并行发生在 agent 层，不发生在 Python runner 层。

## 目标达成条件

- `$a-share-daily-review` workflow 明确在需要外部背景时 spawn 6 个并行子 Agent。
- 每个子 Agent 独立使用 `$daily-financial-briefing`，并只处理一个本地 topic。
- 6 个子 Agent 返回 6 个 `TopicResult`，父 agent 汇总为 `external_background_fusion.v1`。
- `daily-review --external-background external-background-fusion.json` 能消费 fusion JSON 并生成 HTML。
- HTML 不出现独立 `外部宏观与机构观点背景` 章节。
- HTML 只有一个 `风险观察` 和一个 `下一步研究问题`。
- HTML 正文不出现工程状态、fixture、schema 名称或模拟说明。
- 技术参考 Markdown 记录 external background 输入路径、状态、引用、信息缺口和降级原因。
- 外部背景不会生成交易行动建议，不会补推本地缺失数据，不会覆盖本地市场宽度、情绪事件或板块结构结论。
- Promptfoo 或 runtime 验收能区分 `parallel_agent_skill` 与 `fixture_smoke`。
- README、用户指南、`SKILL.md`、workflow reference、黄金测试说明和目录索引已同步。

## 当前状态记录

截至 2026-06-19 本次清理后：

- 第一阶段 Python 渲染层已完成：`daily-review` 可以读取 external background JSON，HTML 不再渲染独立外部背景章节。
- 第二阶段 Python helper（`external_background.py`、`daily-review-external-background` CLI 子命令、`test_external_background_orchestration.py`）已移除。生产编排不应在 Python 层通过 `ThreadPoolExecutor + TopicRunner` 实现。
- 第三阶段已实施：`skills/a-share-daily-review/SKILL.md` 和 `skills/a-share-daily-review/references/daily-review-workflow.md` 已把生产外部背景获取改为父 agent spawn 6 个并行子 Agent；每个子 Agent 独立使用 `$daily-financial-briefing` 并返回 `TopicResult` JSON。
- README、用户指南、黄金测试说明、Promptfoo provider 和目录索引已同步区分 `parallel_agent_skill`、`fixture_smoke` 和 legacy compatibility。
- `daily-review --external-background reports/daily-reviews/2026-06-18/external-background-fusion.json --llm-output reports/daily-reviews/2026-06-18/llm-review-sections.json --output-format html` 已能消费 fusion JSON 并生成 HTML。
- Promptfoo provider 对 `parallel_agent_skill` 和 `fixture_smoke` 用例改为直接写 fusion JSON fixture，不再通过 Python CLI 子命令编排。

本次验证结果：

- `.venv\Scripts\python.exe -m py_compile a_share_info_hub\__main__.py a_share_info_hub\daily_review.py`：通过。
- `.venv\Scripts\python.exe -m pytest tests -q`：待运行。
- `npm run eval:a-share-daily-review`：待运行。
- 使用项目 `.venv` 运行 `quick_validate.py` 会因该虚拟环境未安装 `PyYAML` 失败；全局 Python 已验证 skill frontmatter 有效。
