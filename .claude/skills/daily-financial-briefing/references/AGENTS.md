# skills/daily-financial-briefing/references 目录索引

本文件是 `skills/daily-financial-briefing/references/` 的目录索引。新增、删除、改名或移动 reference 时，必须同步更新这里的说明。

## 目录用途

- 保存当日财经信息总结 skill 的一跳 reference。
- 详细规则从 `SKILL.md` 拆出，避免 skill body 过长，同时保持 agent 可按需读取。

## 文件索引

- `AGENTS.md`：本目录索引和维护规则。
- `claude.md`：Claude/Codex 入口引用文件，内容固定为 `@agents.md`。
- `source-routing.md`：公开来源优先级、禁止来源和主题覆盖边界。
- `output-schema.md`：Markdown 简报结构、核心结论字段和 blocked 输出要求。
- `citation-rules.md`：引用粒度、来源字段、低可信度信息和版权边界。
- `evaluation-rules.md`：黄金测试集、离线 fixture、Promptfoo/provider 和真实 forward test 的验证规则。

## 更新要求

- 修改任一规则时，同步检查 `docs/daily-financial-news-skill-golden-testset.jsonl` 和 `eval/providers/run-daily-financial-briefing.js`。
