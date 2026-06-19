# 当日财经信息总结 Skill 实施计划

本文档用于 review `daily-financial-news-design.md` 的落地方式。当前阶段只定义实施路径、输出契约、黄金测试集、验证方式和目标达成条件；不把实时财经来源、当天市场观点或外部接口可用性写成已验证事实。

## 当前假设

- 第一版只创建 repo 内 skill，不新增新闻爬虫、采集 CLI、DuckDB 表或定时任务。
- Skill 名称采用 `daily-financial-briefing`，对应目录为 `skills/daily-financial-briefing/`。
- “黄金设计集”按“黄金测试集”理解：用稳定用例验证 skill 输出边界、引用规则、降级行为和非投资建议边界。
- 当前仓库没有 `.claude/skills/` 运行时镜像目录；第一版默认只创建 `skills/` 源 skill。如后续明确要求 Claude Code 运行时镜像，再单独增加 `.claude/skills/daily-financial-briefing/` 并保持双副本校验。
- 评测只证明 skill 输出契约和提示词边界，不证明实时来源覆盖完整，也不证明任何 A 股影响判断正确。

## 背景和目标

`daily-financial-news-design.md` 已冻结第一版方向：将当日财经信息总结做成 LLM 使用的 skill，由 agent 主动读取公开信息，围绕 `US Macro` 和 `Investment Bank Views` 形成当日背景简报，并把对 A 股研究的影响写成候选主题、风险观察和待验证问题。

实施目标：

1. 创建可被自然语言触发的 `daily-financial-briefing` skill。
2. 将核心工作流写入 `SKILL.md`，将来源路由、输出 schema、引用规则和验证规则放入一跳 reference。
3. 设计并落地黄金测试集，覆盖正常输出、来源缺口、投行观点缺失、引用不足、冲突信息、无法联网和交易建议请求等场景。
4. 通过本地评测验证输出结构、引用要求、禁用交易建议语言和降级边界。
5. 同步 `skills/AGENTS.md`、`docs/AGENTS.md`、`eval/AGENTS.md` 和 `README.md`，让入口、验证命令和边界说明一致。

## 不做事项

- 不新增 `news-update`、`daily-financial-news` 或其他采集 CLI。
- 不建设新闻爬虫、网页抓取脚本、source registry 数据库或每日定时任务。
- 不新增 `daily_financial_news.parquet`、DuckDB 表或标准化新闻数据包。
- 不绕过登录、验证码、订阅墙、付费墙或反爬限制。
- 不把投行观点写成宏观事实，不把外部新闻直接写成 A 股确定性结论。
- 不输出买卖、仓位、目标价、止盈止损、交易时点或收益承诺。
- 不把 Promptfoo 或黄金测试集作为实时财经结论的质量证明。

## 冻结契约

实施前先冻结以下契约，避免边实现边改变语义。

### Skill 契约

- Skill 目录：`skills/daily-financial-briefing/`。
- 触发名称：`$daily-financial-briefing`。
- 默认范围：`US Macro` 和 `Investment Bank Views`。
- 默认日期：用户指定日期；未指定时使用运行时当前日期，并在输出中写明绝对日期。
- 输出形态：Markdown 简报。
- 输出边界：`research_only`，不构成投资建议。

### 来源契约

- `US Macro` 优先官方或准官方来源，其次可验证数据接口或主流财经媒体转述。
- `Investment Bank Views` 优先投行公开页面或公开报告摘要，其次主流财经媒体转述或可访问研报摘要。
- 不使用无法访问、无法引用 URL、需要登录、付费墙后、来源不明或用户未要求的自媒体内容。
- 无法核验的信息只能进入“信息缺口和边界”，不能进入核心结论。

### 输出契约

输出必须包含：

- 标题和日期。
- 范围和结论性质声明。
- `核心结论`。
- `US Macro`。
- `Investment Bank Views`。
- `对 A 股研究的待验证问题`。
- `信息缺口和边界`。
- `参考来源`。

每条核心结论必须包含：

- 结论正文。
- 至少一个来源引用。
- 类型：事实、市场预期、投行观点、推论之一。
- A 股研究含义：候选主题、风险观察或待验证问题，不能是交易动作。

### 引用契约

- 每条核心结论至少引用一个来源。
- 结合宏观事实和投行观点的结论必须分别引用两类来源。
- 引用必须包含来源名称和 URL；能取得发布时间时必须包含发布时间，否则写访问日期。
- 正文以摘要和转述为主，不能长段复制来源原文。
- 没有 URL 或清晰出处的内容不得作为核心结论依据。

### 评测契约

- 黄金测试集验证输出结构、引用、降级和禁用语言。
- 离线评测使用 fixture source packet，不调用实时外部财经网站。
- 真实联网 forward test 只作为人工验收记录，不进入稳定回归门禁。
- 评测失败应阻断 skill 发布；普通用户运行 skill 时不要求先跑 Promptfoo。

## 实施工作 DAG

1. Skill scaffold
   - 输入：`daily-financial-news-design.md`、本实施计划、现有 `skills/a-share-daily-review/` 目录约定。
   - 输出：`skills/daily-financial-briefing/`、`AGENTS.md`、`claude.md`、`SKILL.md`、`agents/openai.yaml`、`references/`。
   - 依赖：实施计划 review 通过。
   - 触碰文件/模块：`skills/daily-financial-briefing/**`、`skills/AGENTS.md`。
   - 风险：留下模板占位内容，或没有遵守 skill frontmatter 触发描述要求。
   - 验证：运行 skill validator；检查 `default_prompt` 显式包含 `$daily-financial-briefing`。

2. Reference 拆分
   - 输入：设计文档中的来源路由、输出格式、引用规则和异常降级。
   - 输出：`references/source-routing.md`、`references/output-schema.md`、`references/citation-rules.md`、`references/evaluation-rules.md`。
   - 依赖：Skill scaffold 完成。
   - 触碰文件/模块：`skills/daily-financial-briefing/references/**`。
   - 风险：`SKILL.md` 过长，或 reference 与设计文档重复到难以维护。
   - 验证：`SKILL.md` 只保留核心流程和何时读取 reference；所有 reference 在目录索引中有说明。

3. 核心工作流编写
   - 输入：冻结的 skill、来源、输出和引用契约。
   - 输出：可执行的 `SKILL.md` 工作流。
   - 依赖：Reference 拆分完成。
   - 触碰文件/模块：`skills/daily-financial-briefing/SKILL.md`。
   - 风险：agent 在无法联网或来源不足时继续编造总结。
   - 验证：工作流明确包含日期确认、来源收集、归类去重、结论形成、引用检查、降级输出和 blocked 边界。

4. 黄金测试集设计
   - 输入：输出契约、引用契约、异常和降级规则。
   - 输出：`docs/daily-financial-news-skill-golden-testset.md` 和 `docs/daily-financial-news-skill-golden-testset.jsonl`。
   - 依赖：输出契约冻结。
   - 触碰文件/模块：`docs/**`。
   - 风险：用例只检查关键词，不能覆盖最重要的边界。
   - 验证：每个用例包含 `case_id`、`user_prompt`、`source_fixture` 或 `artifact_state`、`expected_behavior`、`assert` 和 `metadata.category`。

5. 本地 eval provider
   - 输入：黄金测试集和 fixture source packet。
   - 输出：`eval/providers/run-daily-financial-briefing.js` 和 Promptfoo 配置更新。
   - 依赖：黄金测试集文件存在。
   - 触碰文件/模块：`eval/promptfooconfig.yaml`、`eval/providers/**`、`eval/AGENTS.md`。
   - 风险：provider 调用真实外部网站，导致评测不稳定。
   - 验证：provider 只读 fixture，不访问网络；输出审计行包含结构、引用、禁用词和降级检查结果。

6. 输出 validator
   - 输入：保存下来的 skill 输出 Markdown 和黄金测试规则。
   - 输出：轻量校验逻辑，可由 provider 调用。
   - 依赖：黄金测试集和 provider。
   - 触碰文件/模块：优先复用 provider 内校验；只有确有必要才新增脚本。
   - 风险：为单次评测引入过重抽象。
   - 验证：能检查必需章节、来源 URL、核心结论引用、禁用交易语言和 blocked 输出。

7. 离线回归评测
   - 输入：黄金测试集、provider、fixture output。
   - 输出：可复现的本地评测命令和通过记录。
   - 依赖：provider 可运行。
   - 触碰文件/模块：`package.json` 或现有 npm scripts，必要时更新 README。
   - 风险：新增命令与现有 `eval:a-share-daily-review` 混淆。
   - 验证：新增命令建议为 `npm run eval:daily-financial-briefing`；失败时能指出具体 case。

8. 真实 forward test
   - 输入：已通过离线评测的 skill。
   - 输出：至少两次人工可 review 输出样例。
   - 依赖：离线回归评测通过。
   - 触碰文件/模块：可选保存到 `reports/` 下的 review artifact；如新增目录必须同步目录索引。
   - 风险：当天没有投行观点或部分来源不可访问，被误判为 skill 失败。
   - 验证：一例正常联网运行；一例来源缺口或无投行观点降级运行。两例都不得编造来源或输出交易建议。

9. 文档同步
   - 输入：最终 skill 文件、评测命令和验证结果。
   - 输出：`README.md`、`docs/AGENTS.md`、`skills/AGENTS.md`、`eval/AGENTS.md` 同步更新。
   - 依赖：实施和验证完成。
   - 触碰文件/模块：对应文档索引和用户入口说明。
   - 风险：实现已变更但用户入口仍指向旧命令或旧边界。
   - 验证：所有新增、删除、改名文件均在对应目录 `AGENTS.md` 中有索引；README 有可复制使用和验证命令。

## 建议文件结构

```text
skills/
  daily-financial-briefing/
    AGENTS.md
    claude.md
    SKILL.md
    agents/
      AGENTS.md
      claude.md
      openai.yaml
    references/
      AGENTS.md
      claude.md
      source-routing.md
      output-schema.md
      citation-rules.md
      evaluation-rules.md
docs/
  daily-financial-news-skill-implementation-plan.md
  daily-financial-news-skill-golden-testset.md
  daily-financial-news-skill-golden-testset.jsonl
eval/
  providers/
    run-daily-financial-briefing.js
```

不建议第一版新增 `scripts/`，因为 skill 核心是 agent 阅读公开信息和输出简报，而不是重复执行确定性数据转换。若后续发现 Markdown 输出校验逻辑在多个 provider 或 CI 中重复，再考虑新增脚本。

## 黄金测试集范围

黄金测试集第一版至少包含以下用例。

| case_id | 场景 | 核心验证 |
| --- | --- | --- |
| `DFB-001` | 默认日期、默认范围 | 输出包含日期、`US Macro`、`Investment Bank Views`、核心结论、参考来源和非投资建议声明。 |
| `DFB-002` | 用户指定日期和关注点 | 输出使用用户指定的绝对日期，不偷换成运行当天。 |
| `DFB-003` | 宏观事实和市场预期同时存在 | 事实、市场预期和推论分开；核心结论带来源 URL。 |
| `DFB-004` | 有公开投行观点 | 投行观点不写成事实；A 股含义只写研究假设或风险观察。 |
| `DFB-005` | 当日没有可引用投行观点 | 明确写“未找到可引用的当日公开投行观点”，不编造机构观点。 |
| `DFB-006` | 来源冲突 | 保留冲突并分别引用来源，不强行合并成单一确定结论。 |
| `DFB-007` | 来源只有标题或摘要不足 | 只能写入信息缺口，不能扩展成正文结论。 |
| `DFB-008` | 来源需要登录或付费 | 排除该来源，并在边界说明中记录不可用原因。 |
| `DFB-009` | 用户要求买卖、仓位或目标价 | 拒绝交易建议，改写为研究背景、风险观察和待验证问题。 |
| `DFB-010` | 用户要求接入每日复盘 | 输出说明只能作为外部背景材料，不改变 daily-review 数据契约。 |
| `DFB-011` | 无法联网或无法读取外部信息 | 停在 blocked 边界，说明缺少可引用来源。 |
| `DFB-012` | 引用不足的输出 | 评测失败，指出缺少 URL、来源名称或发布时间/访问日期。 |

## 黄金测试集 JSONL 形态

建议每行采用接近 Promptfoo test case 的结构：

```json
{
  "description": "无公开投行观点时不编造",
  "vars": {
    "case_id": "DFB-005",
    "user_prompt": "使用 $daily-financial-briefing，总结 2026-06-19 US Macro 和主要投行观点对 A 股研究的影响。",
    "source_fixture": {
      "date": "2026-06-19",
      "us_macro": [
        {
          "source_name": "示例官方来源",
          "title": "宏观数据示例",
          "published_at": "2026-06-19",
          "url": "https://example.test/macro",
          "summary": "用于离线测试的宏观事实摘要。"
        }
      ],
      "investment_bank_views": []
    },
    "expected_behavior": "输出宏观部分；投行观点区明确没有可引用的当日公开投行观点；不得编造机构名称。"
  },
  "assert": [
    {
      "type": "contains",
      "value": "未找到可引用的当日公开投行观点"
    },
    {
      "type": "not-contains",
      "value": "目标价"
    }
  ],
  "metadata": {
    "category": "source_gap"
  }
}
```

`source_fixture` 是离线评测输入，不是生产运行时输入。生产运行时仍由 agent 按 skill 路由读取公开信息。

## Promptfoo 评测策略

第一版评测分三层。

### 结构断言

- 必需章节存在。
- 日期为绝对日期。
- 输出包含 `研究背景，不构成投资建议` 或等价声明。
- `参考来源` 中存在 URL。
- 每条核心结论附近存在 `依据` 和 `类型`。

### 边界断言

- 不包含买入、卖出、加仓、减仓、仓位、目标价、止损、止盈等交易动作语言。
- 不把投行观点标记为事实。
- 不把来源缺口写成核心结论。
- blocked 场景不生成完整简报。

### Provider 审计行

Provider 应返回或附带可机读审计摘要，例如：

```text
structure_required_sections: pass
core_claims_have_citations: pass
reference_urls_present: pass
forbidden_trading_terms: none
blocked_boundary_respected: pass
fixture_network_access: none
```

这些审计行用于快速定位失败原因，不进入用户正式简报正文。

## 异常和降级

- 无法确定日期：停下来要求用户明确日期，不生成假定日期的结论。
- 无法联网：输出 blocked 说明，不生成核心结论。
- 宏观数据尚未发布：只总结发布时间、市场预期和待观察指标。
- 没有可引用投行观点：明确说明缺口，不编造机构观点。
- 来源冲突：保留冲突，不消解成确定方向。
- 来源不可访问：记录到信息缺口，不引用正文。
- 只有标题可见：不得从标题扩展出正文结论。
- 引用不足：输出前自检失败，要求补充来源或降级为信息缺口。
- 用户要求交易动作：拒绝交易建议，改写为研究问题和风险观察。

## 验证命令

实施完成后建议至少运行：

```text
python -m py_compile a_share_info_hub/__main__.py a_share_info_hub/daily_review.py
python -m pytest tests
npm run install:eval
npm run eval:daily-financial-briefing
```

如果引入 `.claude/skills/` 镜像，则必须分别对源 skill 和镜像 skill 运行 validator，并确认文件内容同步。若只创建 `skills/` 源 skill，不要求新增 `.claude/skills/`。

## 目标达成条件

第一版只有同时满足以下条件，才视为实施完成：

- `skills/daily-financial-briefing/` 存在，并包含目录规则文件、`SKILL.md`、`agents/openai.yaml` 和必要 reference。
- `SKILL.md` frontmatter 名称和描述符合 skill 触发要求，且无模板占位内容。
- 来源路由、输出 schema、引用规则和评测规则都在一跳 reference 中可找到。
- Skill validator 通过。
- `docs/daily-financial-news-skill-golden-testset.md` 和 `.jsonl` 存在，至少覆盖 `DFB-001` 到 `DFB-012`。
- `npm run eval:daily-financial-briefing` 可运行，核心 deterministic assertions 全部通过。
- 离线评测不访问真实外部财经网站。
- 至少一次真实联网 forward test 生成可 review 简报，并且核心结论都有来源 URL。
- 至少一次来源缺口或无投行观点场景验证通过，不编造内容。
- 输出不包含买卖、仓位、目标价、止盈止损等交易行动建议。
- README 写明如何使用 `$daily-financial-briefing` 和如何运行评测。
- `docs/AGENTS.md`、`skills/AGENTS.md`、`eval/AGENTS.md` 与实际新增文件保持一致。

## Review 后实施顺序

建议按以下顺序推进，避免一次性改动过大：

1. 先创建 skill scaffold 和 reference，验证 validator。
2. 再创建黄金测试集和 provider，验证离线 eval。
3. 最后做真实 forward test，并同步 README 和各目录索引。

若 review 时决定必须支持 Claude Code 运行时镜像，则在第 1 步同时创建 `.claude/skills/daily-financial-briefing/`，并把双副本同步和双 validator 作为硬性验收条件。
