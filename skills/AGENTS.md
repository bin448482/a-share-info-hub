# skills 目录索引

本文件是 `skills/` 的目录索引。新增、删除、改名或移动 skill 时，必须同步更新这里的说明。

## 目录用途

- 保存仓库内可复用的 Codex/Claude skill 源文件。
- Skill 只保存 agent 执行所需的最小指令、metadata 和一跳 reference，不保存面向用户的 README。
- 仓库内每日数据分析 skill 必须遵守 research-only 边界，不输出交易建议。

## 子目录索引

- `AGENTS.md`：本目录索引和维护规则。
- `claude.md`：Claude/Codex 入口引用文件，内容固定为 `@agents.md`。
- `a-share-daily-review/`：基于每日快照 artifacts 生成 A 股每日复盘研究、HTML report、数据质量诊断和安全拒绝输出的 skill。

## 更新要求

- 新增 skill 时，同步更新根目录 `AGENTS.md`、README 和本索引。
- 修改 skill 能力、入口命令或输出边界时，同步更新对应实施文档、用户指南和黄金测试集。
- 如果后续增加 `.claude/skills/` 运行时镜像，必须保持源 skill 和镜像内容一致，并分别通过 validator。
