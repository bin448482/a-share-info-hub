# skills/daily-financial-briefing/agents 目录索引

本文件是 `skills/daily-financial-briefing/agents/` 的目录索引。新增、删除、改名或移动本目录文件时，必须同步更新这里的说明。

## 目录用途

- 保存当日财经信息总结 skill 的 UI metadata。
- `default_prompt` 必须显式包含 `$daily-financial-briefing`，方便用户按 skill 名称调用。

## 文件索引

- `AGENTS.md`：本目录索引和维护规则。
- `claude.md`：Claude/Codex 入口引用文件，内容固定为 `@agents.md`。
- `openai.yaml`：skill 的 UI 名称、短说明和默认调用提示词。

## 更新要求

- 修改 `SKILL.md` 的能力边界或 skill 名称时，同步检查 `openai.yaml` 是否仍匹配。
