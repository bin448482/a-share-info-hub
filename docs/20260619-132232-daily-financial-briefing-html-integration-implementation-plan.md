# $daily-financial-briefing 融入每日复盘 HTML 实施计划

本文档用于 review 将 `$daily-financial-briefing` 的外部财经信息融入 `a-share-daily-review` HTML 主报告的修正方案。当前阶段只定义实施路径、契约、工作流、验证方式和目标达成条件；不直接改代码，不把实时财经判断写成已验证事实。

## 背景和问题

当前仓库已有两条相互独立的能力：

- `$a-share-daily-review`：读取本地每日 A 股快照 artifacts，生成 `review-context.json`、LLM sections、HTML 主报告和技术参考 Markdown。
- `$daily-financial-briefing`：由 agent 读取公开来源，围绕 `US Macro` 和 `Investment Bank Views` 生成带引用的当日财经信息简报。

旧方案把外部宏观和机构观点设计成 HTML 独立章节，导致三个问题：

- 主报告中出现独立的 `外部宏观与机构观点背景`，打断每日复盘主线。
- 外部背景章节内部又有 `风险观察`，和主报告 `风险观察` 重复。
- `passed`、模拟输入、HTML 展示形态等工程说明容易进入用户正文，不符合“策略分析师写给普通投资者”的报告角色。

修正目标是在不破坏 A 股本地证据边界的前提下，让外部信息围绕本地 `review-context.json` 中已经出现的主题发挥作用：帮助解释风险约束、形成待验证问题、提示外部变量，但不能独立生成或覆盖 A 股结论。

## 核心决策

- 不把 `$daily-financial-briefing` 生成的 Markdown 原文直接拼进 HTML。
- 不在 HTML 主报告中新增 `外部宏观与机构观点背景` 独立章节。
- 先生成本地 `review-context.json`，再由 agent 根据本地主题并行调用外部信息 skill。
- 并行调用粒度按本地报告主题拆分，例如大盘定性、大盘结构、市场宽度、情绪事件、板块结构和风险约束。
- 外部信息经 agent 汇总为受控 `external_background` 或后续融合输入包，再进入 LLM sections。
- LLM sections 必须把外部背景融入主报告已有 section：`大盘观察`、`风险观察`、`下一步研究问题`，不能独立成章。
- Python CLI 不负责联网搜索、浏览器抓取或自动调用 `$daily-financial-briefing`；Python 只负责读取受控输入、校验、渲染 HTML 和写技术参考。
- 外部背景状态、模拟说明、来源缺口、引用 URL 和降级原因进入技术参考 Markdown，不进入普通用户 HTML 正文。

## 不做事项

- 不新增新闻采集 CLI。
- 不在 `daily-review` 中自动调用浏览器、搜索引擎、LLM API 或 `$daily-financial-briefing`。
- 不把外部财经背景写入 `data/normalized/`、`market.duckdb` 或每日快照主表。
- 不允许 LLM 根据外部新闻补推本地缺失板块、情绪或个股结论。
- 不输出买入、卖出、仓位、目标价、止盈止损或实盘时点建议。
- 不把没有 URL 或来源名称的外部观点用于 HTML 正文。
- 不在 HTML 正文中展示 `passed`、`partial`、`blocked`、`invalid`、模拟输入、fixture、schema 名称或其他工程状态。

## 目标生成流程

目标流程分为两层：agent 编排层和 Python 渲染层。

```text
本地 daily run artifacts
  -> Python 生成 review-context.json
  -> Agent 读取本地 context 并抽取本地主题
  -> Agent 按主题并行调用外部信息 skill
  -> Agent 汇总外部信息与本地主题的关系
  -> Agent 生成 LLM sections JSON
  -> Python 校验 sections 和证据边界
  -> Python 渲染 HTML 主报告和技术参考 Markdown
```

HTML 主报告顺序为：

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

说明：

- `1.1 大盘` 应改为 `大盘观察`，保留 `大盘定性` 和 `大盘结构` 两个内容维度。
- 不再渲染独立的 `外部宏观与机构观点背景`。
- 外部利率、通胀、汇率、投行观点等内容只能作为背景句、风险观察或待验证问题融入主报告。
- 引用来源和 external background 状态默认写入技术参考 Markdown。

## Agent 并行编排

Agent 在拿到本地 `review-context.json` 后，先抽取本地主题包。第一版主题包固定为：

```json
{
  "schema_version": "daily_review_local_topics.v1",
  "trade_date": "YYYY-MM-DD",
  "topics": [
    {
      "topic_key": "market_overview_assessment",
      "local_summary": "",
      "evidence_boundary": ""
    },
    {
      "topic_key": "market_overview_structure",
      "local_summary": "",
      "evidence_boundary": ""
    },
    {
      "topic_key": "market_breadth",
      "local_summary": "",
      "evidence_boundary": ""
    },
    {
      "topic_key": "sentiment_and_events",
      "local_summary": "",
      "evidence_boundary": ""
    },
    {
      "topic_key": "board_and_structure",
      "local_summary": "",
      "evidence_boundary": ""
    },
    {
      "topic_key": "risk_observations",
      "local_summary": "",
      "evidence_boundary": ""
    }
  ]
}
```

每个主题可以并行调用外部信息 skill。每个并行任务的输入必须包含：

- `trade_date`
- `topic_key`
- `local_summary`
- `evidence_boundary`
- 允许查询的外部范围，例如 `US Macro`、`Investment Bank Views`
- 禁止交易建议和禁止覆盖本地证据的边界

每个并行任务的输出必须是主题相关结论，而不是通用新闻摘要：

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

汇总器负责把并行结果合并、去重、降级和归类。汇总后写出受控融合输入包：

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

第一版可以继续兼容现有 `external_background.v1` 输入，但 HTML 不再直接展示该对象本身；它只作为融合材料或技术审计材料。

## Python 输入和输出契约

`daily-review` 保留可选参数：

```text
python -m a_share_info_hub daily-review --trade-date <YYYY-MM-DD> --external-background <path-to-json>
```

参数语义调整为：

- `--external-background` 指向 agent 已生成的受控外部背景或融合输入包。
- Python 读取后只做结构校验、引用校验、状态记录和边界校验。
- Python 不根据该文件单独渲染 HTML 章节。
- 如果文件不可用、blocked 或 invalid，本地 A 股复盘仍继续生成。

`review-context.json` 保留独立字段：

```json
{
  "external_background": {
    "status": "not_provided|passed|partial|blocked|invalid",
    "briefing_date": "YYYY-MM-DD",
    "source_skill": "daily-financial-briefing",
    "core_points": [],
    "follow_up_questions": [],
    "information_gaps": [],
    "citations": [],
    "issues": []
  }
}
```

状态语义：

- `not_provided`：未传入外部背景，HTML 保持本地复盘结构。
- `passed`：外部背景结构和引用校验通过，可作为 LLM sections 融合材料。
- `partial`：部分来源缺口、非当日观点或主题匹配不足，只能作为风险或待验证问题候选。
- `blocked`：来源不可用或 briefing 本身 blocked，不进入 HTML 正文。
- `invalid`：JSON 结构或引用不合格，不进入 HTML 正文，但不阻断本地 A 股复盘。

`LlmReviewSections` 不应再依赖独立外部背景正文。第一版可以保留旧字段以兼容现有输入，但渲染策略必须变化：

```json
{
  "external_background_review": "",
  "external_background_risks": [],
  "external_background_follow_up_questions": [],
  "external_background_boundary_note": ""
}
```

兼容规则：

- `external_background_risks` 应合并进主 `risk_observations`。
- `external_background_follow_up_questions` 应合并进主 `follow_up_questions`。
- `external_background_review` 只能被 LLM 改写后融入 `market_overview_structure`、`risk_observations` 或 `follow_up_questions`。
- `external_background_boundary_note` 不进入 HTML 正文；对应技术说明进入 data notes。

后续更干净的契约可以改为：

```json
{
  "market_external_context_note": "",
  "risk_observations": [],
  "follow_up_questions": []
}
```

但第一版实施不强制做 schema 大迁移，避免一次改动过大。

## 实施工作 DAG

1. 修正设计和文档
   - 输入：当前用户反馈、旧实施计划、角色化报告方案。
   - 输出：本文档、用户指南和 workflow reference 的新边界。
   - 依赖：无。
   - 触碰文件：`docs/`、`skills/a-share-daily-review/references/`。
   - 风险：文档仍保留“独立外部背景章节”的旧描述。
   - 验证：全文搜索 `外部宏观与机构观点背景`，只允许作为“不再新增”的反例出现。

2. 调整 HTML 渲染结构
   - 输入：已校验 `ValidatedReviewReport`。
   - 输出：不含独立外部背景章节的 HTML。
   - 依赖：设计文档已冻结。
   - 触碰模块：`a_share_info_hub/daily_review.py`。
   - 风险：删除章节后外部引用完全不可审计。
   - 验证：HTML 不包含独立外部背景章节；data notes 仍包含 external background 状态、路径、引用和降级原因。

3. 合并外部背景到主 sections
   - 输入：`LlmReviewSections`、`context.external_background`。
   - 输出：唯一的 `风险观察` 和唯一的 `下一步研究问题`。
   - 依赖：HTML 渲染结构已调整。
   - 触碰模块：`daily_review.py`、`report-prompt.md`。
   - 风险：外部背景被机械追加，缺少与本地主题的关系。
   - 验证：测试断言风险和问题必须包含本地验证语义，例如市场宽度、板块、情绪或汇率/利率传导。

4. 增加用户正文边界校验
   - 输入：HTML sections 文本。
   - 输出：工程状态和模拟描述不能进入 HTML 正文。
   - 依赖：合并策略明确。
   - 触碰模块：`daily_review.py`。
   - 风险：误杀必要的用户可读边界说明。
   - 验证：`passed 状态模拟输入`、`HTML 展示形态`、`external_background.status`、`schema_version` 等词进入 HTML 时测试失败。

5. 更新 agent workflow reference
   - 输入：本地 context、主题包 schema、并行任务输出 schema。
   - 输出：可执行的 agent 编排说明。
   - 依赖：契约冻结。
   - 触碰文件：`skills/a-share-daily-review/references/daily-review-workflow.md`。
   - 风险：把 Python CLI 写成自动联网工具。
   - 验证：workflow 明确 agent 负责并行调用，Python 负责受控输入和渲染。

6. 更新 eval provider 和黄金测试集
   - 输入：新 HTML 结构和融合规则。
   - 输出：Promptfoo 覆盖 external background passed、partial、blocked、invalid。
   - 依赖：HTML 和 prompt 更新完成。
   - 触碰文件：`docs/a-share-daily-review-skill-golden-testset.jsonl`、`docs/a-share-daily-review-skill-golden-testset.md`、`eval/providers/run-a-share-daily-review.js`。
   - 风险：只验证 context，不验证 HTML 正文是否真正融合。
   - 验证：断言同时检查 HTML、技术 Markdown、禁用工程状态和唯一风险板块。

7. 更新用户文档和索引
   - 输入：最终 CLI、context、HTML、workflow 行为。
   - 输出：README、用户指南、skill workflow reference 和目录索引同步。
   - 依赖：测试通过。
   - 触碰文件：`README.md`、`docs/a-share-daily-review-skill-user-guide.md`、`docs/AGENTS.md`。
   - 风险：用户误以为 `daily-review` 会自动联网获取外部信息。
   - 验证：文档清楚区分 agent 编排层和 Python 渲染层。

## 异常处理

- external background 文件不存在：`external_background.status=invalid`，本地复盘继续；HTML 不展示外部背景缺口，技术 Markdown 记录路径错误。
- JSON 解析失败：同上，并在技术 Markdown 写入错误摘要。
- citation 缺少 URL：该条外部观点不能进入 HTML 正文；若全部无引用则 status 为 `invalid`。
- briefing_date 与 trade_date 不一致：status 最高为 `partial`；HTML 只能写成中期背景或待验证问题，不能写成当日外部事实确认。
- `blocked=true`：不进入 HTML 正文，只在技术 Markdown 记录 `blocked_reason`。
- external background 包含交易行动语言：阻断该背景进入 HTML，并在技术 Markdown 记录原因。
- external background 试图覆盖本地证据：阻断该背景进入 HTML。
- 并行外部任务之间结论冲突：不合并为确定性判断，转为风险观察或待验证问题。
- 模拟输入、fixture 或测试数据：允许进入技术 Markdown，禁止进入 HTML 正文。

## 测试计划

新增或调整 pytest：

- `daily-review --external-background valid.json` 生成 context，`external_background.status=passed`。
- valid 背景不生成 `外部宏观与机构观点背景` 独立 HTML 章节。
- valid 背景中的风险候选进入唯一的 `风险观察`。
- valid 背景中的待验证问题进入唯一的 `下一步研究问题`。
- 缺少 URL 的 core point 不进入 HTML 正文。
- blocked external background 不阻断本地复盘，也不展示外部结论。
- invalid JSON 不阻断本地复盘，但技术 Markdown 写入错误。
- 非当日 `briefing_date` 降级为 partial，并且只能进入边界、风险或待验证问题。
- 外部背景不能补推 `blocked_sections`。
- HTML 正文不得包含 `passed 状态模拟输入`、`HTML 展示形态`、`external_background.status`、`schema_version`。
- HTML 包含 `大盘观察`、`大盘定性`、`大盘结构`，不再要求 `1.1 大盘`。

新增或调整 Promptfoo：

- ADR-GOLDEN external background passed 用例：HTML 不包含独立外部背景章节，风险观察包含外部变量约束。
- ADR-GOLDEN external background blocked 用例：HTML 本地复盘可用，不展示外部结论。
- ADR-GOLDEN invalid citation 用例：无 URL 外部观点不进入 HTML，技术 Markdown 记录降级原因。
- HTML not-contains：`外部宏观与机构观点背景`。
- HTML not-contains：`外部背景风险观察`。
- HTML not-contains：`passed 状态模拟输入`。
- 技术 Markdown contains：`external_background`、JSON 路径、status、引用 URL、降级原因。

实施后运行：

```text
.venv\Scripts\python.exe -m py_compile a_share_info_hub/__main__.py a_share_info_hub/daily_review.py
.venv\Scripts\python.exe -m pytest tests
npm run eval:a-share-daily-review
npm run eval:daily-financial-briefing
python C:/Users/zhanb.BIINN/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/a-share-daily-review
python C:/Users/zhanb.BIINN/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/daily-financial-briefing
```

## 目标达成条件

- `daily-review` 支持读取受控 external background 或 fusion JSON，但不自动联网、不自动调用外部 skill。
- `review-context.json` 包含独立的 `external_background` 字段，不污染本地行情数据契约。
- HTML 不再出现独立的 `外部宏观与机构观点背景` 章节。
- HTML 只有一个 `风险观察` 板块，外部风险与本地风险合并表达。
- HTML 只有一个 `下一步研究问题` 板块，外部待验证问题与本地验证问题合并表达。
- HTML 使用 `大盘观察`，并保留 `大盘定性` 和 `大盘结构`。
- HTML 正文不出现 `passed`、`partial`、`blocked`、`invalid`、模拟输入、fixture、schema 名称或工程状态说明。
- 技术参考 Markdown 记录 external background 输入路径、状态、引用、信息缺口、降级原因和模拟说明。
- 外部背景所有进入正文的核心点都有来源名称和 URL。
- 外部背景不会生成交易行动建议，不会补推本地缺失数据，不会覆盖本地市场宽度、情绪事件或板块结构结论。
- Agent workflow 明确按本地主题并行调用外部信息 skill，并在生成 LLM sections 前完成融合。
- pytest 和 Promptfoo 覆盖 passed、partial、blocked、invalid 四类 external background 状态。
- README、用户指南、daily-review workflow reference 和 `docs/AGENTS.md` 已同步。

## 实施完成记录

截至 2026-06-19，本计划已完成实施：

- `daily-review` 已支持 `external_background.v1` 和 `external_background_fusion.v1`，Python 只读取受控 JSON 并校验引用、状态和边界，不联网、不调用外部 skill。
- HTML renderer 已取消独立 `外部宏观与机构观点背景` 章节；兼容字段 `external_background_review`、`external_background_risks`、`external_background_follow_up_questions` 会在渲染前融合进 `大盘观察`、唯一 `风险观察` 和唯一 `下一步研究问题`。
- HTML 正文使用 `大盘观察`，保留 `大盘定性` 与 `大盘结构`，并阻断 `passed`、`partial`、`blocked`、`invalid`、模拟、fixture、`schema_version`、`external_background.status` 等工程状态词进入用户正文。
- 技术参考 Markdown 保留 external background 输入路径、状态、引用 URL、信息缺口和降级原因。
- Agent workflow reference 已明确：agent 先读取本地 `review-context.json`、按本地主题并行调用外部信息 skill、再汇总成受控 JSON；Python CLI 不负责外部信息获取。
- 2026-06-18 样例报告已重新生成，HTML 独立外部背景章节数为 0，`风险观察` 和 `下一步研究问题` 各 1 个，external background 引用只进入技术参考 Markdown。

已运行验证：

```text
.venv\Scripts\python.exe -m py_compile a_share_info_hub\__main__.py a_share_info_hub\daily_review.py
.venv\Scripts\python.exe -m pytest tests -q
node --check eval\providers\run-a-share-daily-review.js
npm run eval:a-share-daily-review
npm run eval:daily-financial-briefing
python C:/Users/zhanb.BIINN/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/a-share-daily-review
python C:/Users/zhanb.BIINN/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/daily-financial-briefing
git diff --check
```
