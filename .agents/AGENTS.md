# .agents 目录索引

本目录保存 Codex 当前仓库运行时可发现的 agent 配置和 skill 入口。

## 目录用途

- 让 Codex 从当前仓库根目录启动时扫描 `.agents/skills/`。
- 只保存运行时发现入口，不作为 skill 正文的权威维护位置。
- Skill 正文仍以仓库 `skills/` 目录为准。

## 子目录索引

- `AGENTS.md`：本目录索引和维护规则。
- `claude.md`：Claude/Codex 入口引用文件，内容固定为 `@agents.md`。
- `skills/`：Codex 当前仓库运行时可发现的 skill wrapper 目录，详见 `skills/AGENTS.md`。

## 更新要求

- 新增、删除、改名或移动 `.agents/` 下的文件或子目录时，同步更新本索引。
- 修改 wrapper 指向的源 skill 时，同步检查 `skills/` 源目录是否仍存在。
