# A 股每日复盘角色化报告改造实施计划

本文档用于 review `a-share-daily-review` 的角色化报告改造方案。当前状态：已实施，代码、prompt、测试、评测、用户文档和 2026-06-18 样例报告已按本文档更新。

## 背景问题

当前 `reports/daily-reviews/2026-06-18/a-share-daily-review.html` 已经解决了旧版报告裸露 `analysis_mode:`、`data_status:` 这类机器键值行的问题，但正文仍然像调试/审计输出，而不是普通投资者能直接阅读的复盘报告。

典型问题：

- 摘要和风险观察反复出现 `partial`、`blocked_sections`、`board_snapshot` 等内部状态词。
- 板块数据缺失时，正文直接写接口失败和 source key，而不是说明这对读者理解市场结构有什么影响。
- 情绪和事件观察停留在记录数、来源分布、原始分类编码和校验提示，缺少策略分析师视角下的解释。
- 黄金测试集主要验证“不越界”和“状态可见”，没有验证报告是否具备专业复盘表达。
- LLM prompt 没有明确写作者角色和读者角色，导致输出容易按数据契约而不是阅读场景组织。

## 目标

默认报告角色固定为：

- 写作者：策略分析师。
- 读者：普通投资者。
- 报告性质：研究复盘，不是交易建议。

目标输出应满足：

- HTML 正文优先回答读者关心的市场状态、结构线索、情绪线索、风险含义和后续验证问题。
- 技术状态、接口失败、source key、`blocked_sections`、`data_status` 等信息进入独立 Markdown 技术参考文件。
- 原始枚举和分类编码，例如 `strong_limit_up`、`sub_new_limit_up`、`previous_limit_up`、`broken_board`、`stock_lhb_detail_em`，只能进入技术参考文件；HTML 正文必须使用中文含义或概括表达。
- 缺失数据在正文中只表达为“当前证据不足以确认某类结论”，不展示内部字段名或接口错误。
- Python 继续负责证据边界、状态判断、禁用交易建议和最终校验。
- LLM 只负责把已允许事实写成符合角色关系的可读报告。

## 不做事项

- 不提供买入、卖出、持有、加仓、减仓建议。
- 不提供仓位、目标价、止盈止损或实盘时点建议。
- 不根据单日快照输出历史趋势、胜率、回测收益或预测。
- 不让 LLM 使用 `review-context.json` 之外的事实。
- 不把技术参考文件隐藏为唯一交付；HTML 仍是普通读者主报告。

## 实施 DAG

| 工作项 | 输入 | 输出 | 依赖 | 触碰文件/模块 | 风险 | 验证方式 |
| --- | --- | --- | --- | --- | --- | --- |
| 1. 冻结报告角色契约 | 当前用户反馈、现有 prompt、现有 HTML | 写作者/读者/语气/禁用边界定义 | 无 | `skills/a-share-daily-review/references/report-prompt.md` | 角色语言过强导致投资建议化 | prompt 中明确 research-only 和非交易建议边界 |
| 2. 拆分正文与技术说明 | `review-context.json`、现有 HTML metadata、issues | HTML 主报告 + 技术 Markdown 文件 | 1 | `a_share_info_hub/daily_review.py` | 技术信息被过度隐藏，影响可审计性 | 技术 MD 包含完整状态和接口失败原因 |
| 3. 调整 LLM sections 写作规则 | 现有 `LlmReviewSections` schema | 角色化 sections 内容规则 | 1 | `report-prompt.md`、必要时 `daily_review.py` | 仍输出内部字段或过度保守 | pytest 检查 HTML 正文禁用内部字段 |
| 4. 调整 validator | 现有 blocked section 校验、禁用词校验 | 禁止正文裸露内部字段，同时允许技术 MD 记录 | 2,3 | `daily_review.py` | 误杀正常解释性文本 | 分别测试 HTML 正文和技术 MD |
| 5. 更新黄金测试集和 Promptfoo | 现有 JSONL、provider deterministic fixture | 新断言覆盖用户可读性和技术外置 | 2,4 | `docs/a-share-daily-review-skill-golden-testset.jsonl`、`eval/providers/run-a-share-daily-review.js` | 只测字符串仍不足以衡量质量 | 新增 not-contains 和技术 MD contains 断言 |
| 6. 更新用户文档和索引 | 现有用户指南、workflow reference | 新的报告交付说明 | 2,5 | `docs/`、`skills/a-share-daily-review/references/` | 文档与实际命令漂移 | 运行测试和 skill quick validate |

## 设计变更

### Prompt 角色层

在 `report-prompt.md` 中新增角色定义：

- 你是面向普通投资者写盘后研究复盘的策略分析师。
- 你的任务不是复述数据契约，而是解释可用事实代表的市场含义和需要保持谨慎的地方。
- 读者不关心接口名、表名或内部状态字段；这些内容不得进入 HTML 正文。
- 当某类数据不可用时，用读者语言说明“该维度证据不足”，不要输出 source key、`blocked_sections` 或 traceback。

建议正文语气：

- 可以写：“从已获取的全市场快照看，当日下跌家数明显多于上涨家数，市场宽度偏弱。”
- 可以写：“板块层面的确认数据不足，因此本报告不把涨跌停情绪中的行业集中直接上升为市场主线。”
- 不要写：“board_snapshot 已被列入 blocked_sections。”
- 不要写：“stock_board_industry_name_em 和 stock_board_concept_name_em 均失败。”

### HTML 主报告

HTML 正文默认包含：

- 摘要。
- 市场宽度观察。
- 情绪与事件观察。
- 板块和结构观察。
- 风险观察。
- 后续验证问题。

正文中不得出现：

- `blocked_sections`
- `board_snapshot`
- `stock_board_industry_name_em`
- `stock_board_concept_name_em`
- `data_status: partial`
- `strong_limit_up`
- `sub_new_limit_up`
- `previous_limit_up`
- `broken_board`
- `limit_down`
- `stock_lhb_detail_em`
- `stock_lhb_detail_daily_sina`
- `stock_lhb_jgmmtj_em`
- traceback、ConnectionError、RemoteDisconnected 等接口错误细节

HTML 可以在页脚用一句用户语言提示：

```text
详细数据状态和接口说明见同目录技术参考文件。
```

### 技术参考 Markdown

新增输出：

```text
reports/daily-reviews/YYYY-MM-DD/a-share-daily-review-data-notes.md
```

该文件面向 review 和排障，允许包含：

- `trade_date`
- `data_status`
- `blocked_sections`
- `data_sources_used`
- 接口状态摘要
- failed source key 和失败原因
- normalized table 行数
- DuckDB 状态
- 修复建议或重跑命令

技术参考文件不是普通投资者主报告，不要求隐藏内部字段。

### Python 校验

保留现有边界：

- blocked 维度不能被正向推断。
- partial 不能写成完整复盘。
- 禁止交易建议语言。

新增边界：

- HTML 正文不得裸露内部字段、source key 或接口错误。
- 技术参考 Markdown 必须记录被 HTML 正文隐藏的关键诊断信息。
- `render_mode=deterministic` 也必须遵守正文与技术说明拆分，避免 eval 路径和真实路径不一致。

## 黄金测试调整

需要调整的重点用例：

- ADR-GOLDEN-002：从“partial 状态显式标记 blocked”改为“HTML 正文用户可读，技术 MD 记录 blocked 细节”。
- ADR-GOLDEN-010：从“顶部暴露 partial/failed/missing 状态”改为“顶部用用户语言说明数据覆盖限制，内部状态进入技术 MD”。
- 新增角色化用例：确认报告以策略分析师口吻写给普通投资者，不输出调试字段，不输出交易建议。
- 新增技术参考用例：确认 `a-share-daily-review-data-notes.md` 包含 `blocked_sections`、`board_snapshot` 和失败接口信息。

建议新增断言：

- HTML contains：`主表覆盖 5527 只证券`
- HTML contains：`市场宽度偏弱`
- HTML contains：`板块层面的确认依据不足`
- HTML not-contains：`blocked_sections`
- HTML not-contains：`board_snapshot`
- HTML not-contains：`stock_board_industry_name_em`
- HTML not-contains：`ConnectionError`
- 技术 MD contains：`blocked_sections`
- 技术 MD contains：`board_snapshot`
- 技术 MD contains：`stock_board_industry_name_em`
- 技术 MD contains：`strong_limit_up`
- 技术 MD contains：`stock_lhb_detail_em`

## 验证计划

实施后至少运行：

```text
python -m py_compile a_share_info_hub/__main__.py a_share_info_hub/daily_review.py
.venv\Scripts\python.exe -m pytest tests
npm run eval:a-share-daily-review
python C:/Users/zhanb.BIINN/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/a-share-daily-review
```

人工 review 重点：

- HTML 是否像策略分析师给普通投资者写的复盘，而不是接口状态报告。
- 技术 Markdown 是否足够支撑排障和审计。
- 报告是否在不提供交易建议的前提下，给出可理解的专业洞察。
- 缺失板块数据时，正文是否保持克制但不显得像程序固定模板。

## 成功标准

- 生成 HTML 主报告和技术参考 Markdown 两份产物。
- HTML 正文不出现内部字段、接口名或错误堆栈。
- 技术 Markdown 完整保留数据状态和失败细节。
- partial 场景下，报告仍能优先呈现市场宽度、情绪事件和风险含义。
- 黄金测试和 pytest 明确覆盖“用户可读正文”和“技术信息外置”。
- 报告继续保持 research-only，不输出任何交易行动建议。

## 目标达成条件

本改造只有同时满足以下条件，才视为目标达成：

1. 代码实现完成：
   - `a_share_info_hub daily-review` 在 HTML 输出路径下同时生成主报告和技术参考 Markdown。
   - LLM prompt 明确写入“策略分析师 -> 普通投资者”的角色关系。
   - deterministic fallback 与 LLM render 路径都遵守正文与技术说明拆分。
   - validator 同时覆盖交易建议禁用、blocked 维度禁止正向推断、HTML 正文内部字段禁用、技术 Markdown 诊断信息保留。

2. 产物验证完成：
   - 使用 `2026-06-18` 这类 `partial` 样本重新生成报告。
   - 新 HTML 正文不再出现 `blocked_sections`、`board_snapshot`、`stock_board_industry_name_em`、`stock_board_concept_name_em`、`ConnectionError`。
   - 新 HTML 正文不再出现 `strong_limit_up`、`sub_new_limit_up`、`previous_limit_up`、`broken_board`、`stock_lhb_detail_em` 等原始分类编码。
   - 新 HTML 正文仍包含主表覆盖、上涨/下跌/平盘、市场宽度、涨跌停情绪、龙虎榜事件和板块证据不足的用户可读表达。
   - 新技术参考 Markdown 包含被 HTML 隐藏的 `data_status`、`blocked_sections`、失败接口、失败原因、原始分类编码、数据来源和重跑/排障建议。

3. 自动化验证完成：
   - `python -m py_compile a_share_info_hub/__main__.py a_share_info_hub/daily_review.py` 通过。
   - `.venv\Scripts\python.exe -m pytest tests` 通过。
   - `npm run eval:a-share-daily-review` 通过。
   - `python C:/Users/zhanb.BIINN/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/a-share-daily-review` 通过。

4. 黄金测试和回归覆盖完成：
   - ADR-GOLDEN-002 和 ADR-GOLDEN-010 不再要求 HTML 正文包含内部 blocked 字段。
   - 新增或更新用例覆盖角色化表达、HTML 正文禁用内部字段、技术 Markdown 保留诊断信息。
   - Promptfoo provider 能读取并返回 HTML 与技术 Markdown 内容，避免只验证其中一个产物。

5. 文档同步完成：
   - 更新 `skills/a-share-daily-review/references/report-prompt.md` 和 `daily-review-workflow.md`。
   - 更新 `docs/a-share-daily-review-skill-user-guide.md`，说明普通用户报告和技术参考文件的区别。
   - 更新 `docs/a-share-daily-review-skill-golden-testset.md`，说明新的评测边界。
   - 更新 `README.md` 中每日复盘使用说明。
   - 如新增、删除、改名或移动文件，按目录规则同步对应 `AGENTS.md` 索引。

6. 人工 review 条件满足：
   - 报告读起来像策略分析师写给普通投资者的盘后研究复盘，而不是接口状态报告。
   - 技术 Markdown 足以让开发者或 agent 复查数据质量问题。
   - 报告没有把“证据不足”写成“确定性主线”，也没有把研究观察写成交易动作。

## 实施验证记录

已完成的验证：

- `python -m py_compile a_share_info_hub/__main__.py a_share_info_hub/daily_review.py` 通过。
- `.venv\Scripts\python.exe -m pytest tests` 通过，结果为 39 passed。
- `npm run eval:a-share-daily-review` 通过，结果为 11/11 passed。
- `python C:/Users/zhanb.BIINN/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/a-share-daily-review` 通过，结果为 `Skill is valid!`。
- `reports/daily-reviews/2026-06-18/a-share-daily-review.html` 已重新生成，正文包含角色化复盘、主表宽度、情绪事件和板块证据不足表达。
- `reports/daily-reviews/2026-06-18/a-share-daily-review-data-notes.md` 已生成，记录 `data_status`、`blocked_sections`、失败接口、失败原因、数据来源和重跑建议。
- 追加修正：HTML 正文已禁止 `strong_limit_up`、`sub_new_limit_up`、`previous_limit_up`、`broken_board`、`stock_lhb_detail_em` 等原始分类编码；这些编码已写入技术参考 Markdown 的“原始分类统计”。
