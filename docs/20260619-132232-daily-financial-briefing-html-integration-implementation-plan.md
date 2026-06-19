# $daily-financial-briefing 融入每日复盘 HTML 实施计划

本文档用于 review 将 `$daily-financial-briefing` 输出融入 `a-share-daily-review` HTML 主报告的实施方案。当前阶段只定义实施路径、契约、验证方式和目标达成条件；不直接改代码，不把实时财经判断写成已验证事实。

## 背景和目标

当前仓库已有两条相互独立的能力：

- `$a-share-daily-review`：读取本地每日 A 股快照 artifacts，生成 `review-context.json`、LLM sections、HTML 主报告和技术参考 Markdown。
- `$daily-financial-briefing`：由 agent 读取公开来源，围绕 `US Macro` 和 `Investment Bank Views` 生成带引用的当日财经信息简报。

目标是在不破坏 A 股本地证据边界的前提下，把财经简报中的外部宏观和机构观点背景纳入每日复盘 HTML，让用户在一份 HTML 中同时看到 A 股市场复盘、外部背景、风险观察和待验证问题。

## 核心决策

- 不把 `$daily-financial-briefing` 生成的 Markdown 原文直接拼进 HTML。
- 新增受控的 `external_background` 输入包，由 agent 或用户提供 `$daily-financial-briefing` 输出摘要、引用和边界。
- Python 只校验 `external_background` 的结构、安全边界和引用完整性，不负责联网读取财经来源。
- LLM sections 增加外部背景相关字段，HTML renderer 只展示通过校验的摘要、风险观察、待验证问题和参考来源。
- 外部背景只能影响“待验证问题”和“风险观察”，不能覆盖、改写或补全本地 A 股行情数据。

## 不做事项

- 不新增新闻采集 CLI。
- 不在 `daily-review` 中自动调用浏览器、搜索引擎或 `$daily-financial-briefing`。
- 不把外部财经背景写入 `data/normalized/`、`market.duckdb` 或每日快照主表。
- 不允许 LLM 根据外部新闻补推本地缺失板块、情绪或个股结论。
- 不输出交易行动建议。
- 不把没有 URL 或来源名称的外部观点展示在 HTML 核心正文中。

## 输入和输出契约

第一版建议新增可选参数：

```text
python -m a_share_info_hub daily-review --trade-date <YYYY-MM-DD> --external-background <path-to-json>
```

`--external-background` 指向一个 JSON 文件。该文件由 `$daily-financial-briefing` 运行后人工保存或 agent 生成，不由 `daily-review` 自动联网生成。

建议 JSON schema：

```json
{
  "schema_version": "external_background.v1",
  "source_skill": "daily-financial-briefing",
  "briefing_date": "YYYY-MM-DD",
  "scope": ["US Macro", "Investment Bank Views"],
  "not_investment_advice": true,
  "core_points": [
    {
      "text": "",
      "type": "fact|market_expectation|bank_view|inference",
      "a_share_relevance": "",
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
  "follow_up_questions": [],
  "information_gaps": [],
  "blocked": false,
  "blocked_reason": ""
}
```

要求：

- `schema_version` 固定为 `external_background.v1`。
- `source_skill` 固定为 `daily-financial-briefing`。
- `briefing_date` 必须等于 `trade_date`，除非用户显式要求引用非当日中期背景；这种情况必须进入边界说明。
- 每个 `core_points[*].citations[*]` 必须包含 `source_name` 和 `url`。
- `type=bank_view` 只能作为机构观点，不能被写成事实。
- `blocked=true` 时，HTML 不展示外部背景正文，只展示“外部背景缺失/不可用”的用户可读说明。

`review-context.json` 增加：

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

- `not_provided`：未传入外部背景，HTML 保持现有结构。
- `passed`：外部背景结构和引用校验通过，可进入 LLM sections。
- `partial`：部分来源缺口或非当日观点，只能展示边界和待验证问题。
- `blocked`：来源不可用或 briefing 本身 blocked，不展示外部结论。
- `invalid`：JSON 结构或引用不合格，阻断外部背景进入 HTML，但不阻断 A 股本地复盘。

`LlmReviewSections` 增加：

```json
{
  "external_background_review": "",
  "external_background_risks": [],
  "external_background_follow_up_questions": [],
  "external_background_boundary_note": ""
}
```

HTML 主报告新增章节：

```text
外部宏观与机构观点背景
```

展示内容：

- 2-4 条外部背景摘要。
- 与 A 股研究相关的风险观察。
- 需要本地行情、板块、情绪或事件数据验证的问题。
- 简短边界说明。

技术参考 Markdown 增加：

- external background 原始状态。
- external background JSON 路径。
- 引用来源列表。
- 被拒绝或降级的原因。

## 实施工作 DAG

1. 冻结 external background schema
   - 输入：`$daily-financial-briefing` 输出规则、每日复盘 context 契约。
   - 输出：Pydantic 模型或等价校验函数。
   - 依赖：无。
   - 触碰模块：`a_share_info_hub/daily_review.py`。
   - 风险：schema 过宽导致无引用观点进入 HTML。
   - 验证：单元测试覆盖缺少 URL、blocked、partial 和 passed。

2. 扩展 CLI 参数
   - 输入：`--external-background <path>`。
   - 输出：`daily-review` 可读取可选 JSON 文件。
   - 依赖：schema 已冻结。
   - 触碰模块：`a_share_info_hub/__main__.py`、`a_share_info_hub/daily_review.py`。
   - 风险：参数路径错误时阻断整个复盘。
   - 验证：路径不存在或 JSON invalid 时只降级外部背景，不阻断本地 A 股复盘。

3. 扩展 review context
   - 输入：daily run artifacts、external background JSON。
   - 输出：`review-context.json.external_background`。
   - 依赖：CLI 参数读取完成。
   - 触碰模块：`daily_review.py`。
   - 风险：把外部背景混入本地数据源列表，造成证据层混乱。
   - 验证：context 明确区分 `data_sources_used` 和 `external_background.citations`。

4. 扩展 LLM sections 和 prompt
   - 输入：扩展后的 review context。
   - 输出：外部背景相关 LLM sections。
   - 依赖：context 扩展完成。
   - 触碰模块：`daily_review.py`、`skills/a-share-daily-review/references/report-prompt.md`。
   - 风险：LLM 把外部背景写成交易方向或确定性主线。
   - 验证：Pydantic 校验和禁用词检查覆盖新增字段。

5. 扩展 HTML 和技术 Markdown
   - 输入：已校验的 report sections。
   - 输出：HTML 新章节和 data notes 新诊断段。
   - 依赖：LLM sections 扩展完成。
   - 触碰模块：`daily_review.py`。
   - 风险：HTML 首屏过长或外部背景压过本地复盘。
   - 验证：HTML 章节位置固定；外部背景不替代 `1.1 大盘`、市场宽度、情绪事件和板块结构。

6. 更新 eval provider 和黄金测试集
   - 输入：新增 CLI 参数和 fixture。
   - 输出：Promptfoo 用例覆盖 external background passed、partial、blocked、invalid。
   - 依赖：HTML 输出完成。
   - 触碰文件：`docs/a-share-daily-review-skill-golden-testset.jsonl`、`docs/a-share-daily-review-skill-golden-testset.md`、`eval/providers/run-a-share-daily-review.js`。
   - 风险：只测 context 不测 HTML 正文。
   - 验证：断言同时检查 HTML 新章节、技术 Markdown 诊断和禁用越界语言。

7. 更新文档和索引
   - 输入：最终 CLI、context、HTML、eval 行为。
   - 输出：README、用户指南、skill workflow reference 和目录索引同步。
   - 依赖：测试通过。
   - 触碰文件：`README.md`、`docs/a-share-daily-review-skill-user-guide.md`、`skills/a-share-daily-review/references/daily-review-workflow.md`、`docs/AGENTS.md`。
   - 风险：用户不知道 external background JSON 如何生成。
   - 验证：README 给出 `$daily-financial-briefing` 到 JSON 再到 `daily-review --external-background` 的示例链路。

## 异常处理

- external background 文件不存在：`external_background.status=invalid`，HTML 只说明外部背景未接入，本地复盘继续。
- JSON 解析失败：同上，并在技术 Markdown 写入错误摘要。
- citation 缺少 URL：该条 `core_point` 丢弃；若全部丢弃则 status 为 `invalid`。
- briefing_date 与 trade_date 不一致：status 最高为 `partial`，HTML 必须写明“非当日背景”。
- `blocked=true`：不展示外部结论，只展示 `blocked_reason`。
- external background 包含交易行动语言：阻断该背景进入 HTML，并在技术 Markdown 记录原因。
- external background 试图引用付费墙、登录后内容或无来源观点：降级为 information gap。

## 测试计划

新增或调整 pytest：

- `daily-review --external-background valid.json` 生成 context，`external_background.status=passed`。
- valid 背景进入 HTML，出现 `外部宏观与机构观点背景` 章节。
- 缺少 URL 的 core point 不进入 HTML。
- blocked external background 不阻断本地复盘。
- invalid JSON 不阻断本地复盘，但技术 Markdown 写入错误。
- 非当日 `briefing_date` 降级为 partial，并在 HTML 显示边界。
- 外部背景不能补推 `blocked_sections`。
- 新增 LLM sections 字段如果出现交易行动语言，应阻断 HTML。

新增或调整 Promptfoo：

- ADR-GOLDEN 新增 external background passed 用例。
- ADR-GOLDEN 新增 external background blocked 用例。
- ADR-GOLDEN 新增 invalid citation 用例。
- HTML contains：`外部宏观与机构观点背景`。
- HTML contains：`仍需用 A 股行情、板块和情绪数据验证`。
- HTML not-contains：无 URL 的外部观点。
- 技术 Markdown contains：`external_background`、JSON 路径、降级原因。

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

- `daily-review` 支持 `--external-background <json>` 可选参数。
- `review-context.json` 包含独立的 `external_background` 字段，不污染本地行情数据契约。
- HTML 在有合格背景时展示 `外部宏观与机构观点背景` 章节。
- HTML 在无背景、blocked、invalid 背景时保持本地复盘可用，并清楚说明外部背景缺口。
- 技术参考 Markdown 记录 external background 输入路径、状态、引用和降级原因。
- 外部背景所有核心点都有来源名称和 URL。
- 外部背景不会生成交易行动建议，不会补推本地缺失数据，不会覆盖 `1.1 大盘` 和本地市场宽度结论。
- pytest 和 Promptfoo 覆盖 passed、partial、blocked、invalid 四类 external background 状态。
- README、用户指南、daily-review workflow reference 和 `docs/AGENTS.md` 已同步。
