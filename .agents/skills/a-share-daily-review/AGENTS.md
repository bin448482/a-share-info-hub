# .agents/skills/a-share-daily-review 目录索引

本目录保存 `a-share-daily-review` 的 Codex 运行时发现入口。

## 目录用途

- 让 Codex 在当前仓库中通过 `$a-share-daily-review` 发现每日 A 股复盘 skill。
- `SKILL.md` 只转发到 `skills/a-share-daily-review/SKILL.md`，源 skill 目录负责真实工作流和 references。

## 文件索引

- `AGENTS.md`：本目录索引和维护规则。
- `claude.md`：Claude/Codex 入口引用文件，内容固定为 `@agents.md`。
- `SKILL.md`：Codex skill wrapper，要求读取源 skill 后执行。

## 更新要求

- 修改工作流、引用或输出边界时，更新 `skills/a-share-daily-review/` 源目录。
- 只有 wrapper 名称、描述或源路径变化时才修改本目录文件。
