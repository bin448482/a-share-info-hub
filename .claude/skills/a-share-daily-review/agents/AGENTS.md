# skills/a-share-daily-review/agents 目录索引

本文件是 `skills/a-share-daily-review/agents/` 的目录索引。新增、删除、改名或移动 agent metadata 时，必须同步更新这里的说明。

## 目录用途

- 保存 `a-share-daily-review` skill 的 UI 和运行时 metadata。
- Metadata 必须与 `SKILL.md` 的能力边界一致，并显式包含 `$a-share-daily-review` 默认提示词。

## 文件索引

- `AGENTS.md`：本目录索引和维护规则。
- `claude.md`：Claude/Codex 入口引用文件，内容固定为 `@agents.md`。
- `openai.yaml`：OpenAI UI metadata，包括 display name、short description 和 default prompt。

## 更新要求

- 修改 `SKILL.md` 名称、用途或默认用法时，同步检查 `openai.yaml` 是否仍一致。
- `default_prompt` 必须显式写 `$a-share-daily-review`，避免 PowerShell 变量展开导致 `$` 丢失。
