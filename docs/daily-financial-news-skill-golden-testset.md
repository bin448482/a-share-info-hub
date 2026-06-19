# 当日财经信息总结 Skill 黄金测试集与评测方案

本文档定义 `daily-financial-briefing` skill 的第一版黄金测试集和本地评测方式。评测只验证 skill 输出契约、引用边界、降级行为和非投资建议边界，不证明实时财经结论正确。

## 黄金测试集

黄金测试集文件：

```text
docs/daily-financial-news-skill-golden-testset.jsonl
```

每一行是一个 Promptfoo 风格测试用例：

- `description`：测试目的。
- `vars.case_id`：稳定用例编号。
- `vars.user_prompt`：用户会输入的提示词。
- `vars.source_fixture`：离线来源包，不代表真实市场数据。
- `vars.expected_behavior`：期望行为说明。
- `assert`：确定性输出断言。
- `metadata.category`：用例分类。

## 覆盖范围

第一版覆盖 `DFB-001` 到 `DFB-012`：

- 默认日期和默认范围。
- 用户指定日期和关注点。
- 宏观事实、市场预期和推论分离。
- 公开投行观点不写成事实。
- 无公开投行观点时不编造。
- 来源冲突保留冲突。
- 标题不足或正文不可访问时只写信息缺口。
- 登录或付费来源被排除。
- 用户要求交易建议时拒绝，并改写为研究输出。
- 接入每日复盘时只作为外部背景材料。
- 无法联网时停在 blocked 边界。
- 引用不足时被识别并阻断完整简报。

## 评测 Provider

本地 provider：

```text
eval/providers/run-daily-financial-briefing.js
```

Provider 读取 `source_fixture` 生成确定性 Markdown 样例，并附带审计行：

```text
structure_required_sections: pass
core_claims_have_citations: pass
reference_urls_present: pass
forbidden_trading_terms: none
blocked_boundary_respected: pass
fixture_network_access: none
```

对于 blocked 或引用不足场景，provider 不生成完整简报，而是输出 blocked 说明和对应审计行。这样回归命令整体应通过，同时证明不合格输入会被拦截。

## 运行命令

```text
npm run install:eval
npm run eval:daily-financial-briefing
```

该评测不访问真实财经网站，不调用 AKShare，不读取或修改 `data/`、`reports/`、`market.duckdb`。

## 验收门槛

- 所有 `DFB-001` 到 `DFB-012` 用例可执行。
- 核心 deterministic assertions 全部通过。
- 输出包含必需章节、绝对日期、来源 URL、非投资建议声明。
- blocked 用例不生成完整简报。
- 无公开投行观点时明确写 `未找到可引用的当日公开投行观点`。
- 任何出现交易行动语言的输出都视为失败。
- Provider 审计行必须显示 `fixture_network_access: none`。
