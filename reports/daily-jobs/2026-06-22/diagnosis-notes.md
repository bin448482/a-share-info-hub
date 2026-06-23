# 2026-06-22 诊断备注

## 问题：HTML 报告生成被验证器阻断

### 失败日志
```
daily_review_html exited with code 1
LLM sections 未通过运行时校验，已阻断 HTML 生成。
失败摘要：review output contains forbidden trading terms: ['仓位建议']
```

### 根因分析
`enforce_research_boundary()` 在 `daily_review.py:2440` 入参 `FORBIDDEN_OUTPUT_TERMS` 包含"仓位建议"，使用全文本 substring 匹配。

实际命中位置是 `not_investment_advice_note` 字段的免责声明文本：
```
不构成任何形式的投资建议、买卖指令、仓位建议或价格预测。
```
这是一个 **false positive**：声明"不构成"仓位建议的免责文本被 substring 匹配误判为违规。

### 受影响的字段
- `not_investment_advice_note` — 声明本身是合法的合规措辞

### 建议修复
将 `not_investment_advice_note` 字段排除出 `enforce_research_boundary()` 的扫描范围，或使用上下文感知正则（如排除"不构成"后的"仓位建议"）。

### 其他备注
| 指标 | 值 |
|------|-----|
| daily_update status | passed (partial data, 5527 rows, 7 failed sources) |
| LLM sections status | passed |
| HTML status | failed (validator false positive) |
| 告警发送 | main 已收到 critical alert |
| research_only | true |

### 交付状态
- job-status.json ✅
- job-summary.md ✅
- heartbeat.json (finished) ✅
- 告警已发送给 `main` ✅
- HTML 报告未发送（validator 阻断，合规）✅
- 未发送任何市场结论 ✅
