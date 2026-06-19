# skills/daily-financial-briefing 目录索引

本文件是 `skills/daily-financial-briefing/` 的目录索引。新增、删除、改名或移动本 skill 文件时，必须同步更新这里的说明。

## 目录用途

- 保存当日财经信息总结 skill 的源文件。
- Skill 围绕 `US Macro` 和 `Investment Bank Views` 主动读取公开信息，生成带来源引用的 A 股研究背景简报。
- 输出只能作为 `research_only` 外部背景材料，不提供交易建议，不改变每日复盘或每日快照数据契约。

## 文件和子目录索引

- `AGENTS.md`：本目录索引和维护规则。
- `claude.md`：Claude/Codex 入口引用文件，内容固定为 `@agents.md`。
- `SKILL.md`：skill 触发 metadata、核心工作流、边界和 blocked 输出格式。
- `agents/`：UI metadata 目录，默认提示词必须显式包含 `$daily-financial-briefing`。
- `references/`：一跳 reference，保存来源路由、输出 schema、引用规则和评测规则。

## 更新要求

- 修改来源边界、输出格式、引用要求或禁用语言时，同步更新 reference、黄金测试集和评测 provider。
- 不在 skill 内新增新闻采集管线、DuckDB 表、Parquet 输出或定时任务。
- 如后续增加 `.claude/skills/` 运行时镜像，必须保持源 skill 和镜像内容一致，并分别通过 validator。
