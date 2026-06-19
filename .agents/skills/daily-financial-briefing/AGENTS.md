# .agents/skills/daily-financial-briefing 目录索引

本目录保存 `daily-financial-briefing` 的 Codex 运行时发现入口。

## 目录用途

- 让 Codex 在当前仓库中通过 `$daily-financial-briefing` 发现每日外部财经简报 skill。
- `SKILL.md` 只转发到 `skills/daily-financial-briefing/SKILL.md`，源 skill 目录负责真实工作流和 references。

## 文件索引

- `AGENTS.md`：本目录索引和维护规则。
- `claude.md`：Claude/Codex 入口引用文件，内容固定为 `@agents.md`。
- `SKILL.md`：Codex skill wrapper，要求读取源 skill 后执行。

## 更新要求

- 修改工作流、引用或输出边界时，更新 `skills/daily-financial-briefing/` 源目录。
- 只有 wrapper 名称、描述或源路径变化时才修改本目录文件。
