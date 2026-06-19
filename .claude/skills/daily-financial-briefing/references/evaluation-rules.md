# 评测规则

本文件定义当日财经信息总结 skill 的黄金测试、离线评测和 forward test 边界。评测证明 skill 输出契约，不证明实时财经判断正确。

## 黄金测试集

黄金测试集文件：

```text
docs/daily-financial-news-skill-golden-testset.jsonl
```

说明文件：

```text
docs/daily-financial-news-skill-golden-testset.md
```

每个用例必须包含：

- `description`：测试目的。
- `vars.case_id`：稳定用例编号。
- `vars.user_prompt`：用户输入。
- `vars.source_fixture` 或 `vars.artifact_state`：离线来源状态。
- `vars.expected_behavior`：期望行为。
- `assert`：可自动检查的断言。
- `metadata.category`：用例分类。

## 必覆场景

- 默认日期和默认范围。
- 用户指定日期和关注点。
- 宏观事实、市场预期和推论分离。
- 公开投行观点不写成事实。
- 无公开投行观点时不编造。
- 来源冲突保留冲突。
- 标题不足或正文不可访问时只写信息缺口。
- 登录或付费来源被排除。
- 用户要求交易建议时拒绝并改写为研究输出。
- 接入每日复盘时只作为外部背景材料。
- 无法联网时 blocked。
- 引用不足时失败。

## 离线评测

Promptfoo provider 必须使用 fixture source packet，不访问真实外部财经网站。Provider 可以生成确定性 Markdown 样例，并附带审计行：

```text
structure_required_sections: pass
core_claims_have_citations: pass
reference_urls_present: pass
forbidden_trading_terms: none
blocked_boundary_respected: pass
fixture_network_access: none
```

离线评测必须检查：

- 必需章节。
- 日期为绝对日期。
- 参考来源包含 URL。
- 每条核心结论包含 `依据` 和 `类型`。
- blocked 场景不生成完整简报。
- 禁用交易语言不出现在输出中。

## Forward Test

真实联网 forward test 至少覆盖：

- 一个正常公开来源场景，核心结论都有 URL。
- 一个来源缺口或无投行观点场景，不编造内容。

Forward test 是人工可 review 验收，不进入稳定回归门禁。测试结果需要说明具体日期、范围、来源可用性和是否触发降级。
