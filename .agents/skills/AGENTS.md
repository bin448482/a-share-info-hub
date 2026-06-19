# .agents/skills 目录索引

本目录保存 Codex 可扫描的当前仓库 skill wrapper。

## 目录用途

- 让 Codex 在当前仓库中发现可调用 skill。
- 每个 wrapper 的 `SKILL.md` 只负责加载 `skills/` 下的权威源 skill。
- 避免复制完整 skill 正文造成运行时入口和源文件漂移。

## 子目录索引

- `AGENTS.md`：本目录索引和维护规则。
- `claude.md`：Claude/Codex 入口引用文件，内容固定为 `@agents.md`。
- `a-share-daily-review/`：指向 `skills/a-share-daily-review/` 的 Codex 运行时入口。
- `daily-financial-briefing/`：指向 `skills/daily-financial-briefing/` 的 Codex 运行时入口。

## 更新要求

- 新增或移除 wrapper 时，同步更新本索引和根目录索引。
- 修改 skill 正文时，应修改 `skills/` 下的源 skill，而不是在本目录维护第二份正文。
