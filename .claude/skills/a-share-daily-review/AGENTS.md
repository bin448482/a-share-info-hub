# skills/a-share-daily-review 目录索引

本文件是 `skills/a-share-daily-review/` 的目录索引。新增、删除、改名或移动本 skill 文件时，必须同步更新这里的说明。

## 目录用途

- 保存每日 A 股复盘研究 skill 的源文件。
- Skill 通过仓库 CLI `python -m a_share_info_hub daily-review` 先生成 `review-context.json` evidence packet，再让 LLM 生成 sections JSON，并由 Python 校验后渲染 HTML。
- 如需生成外部财经背景，生产 workflow 必须由父 agent spawn 6 个并行子 Agent，每个子 Agent 使用 `$daily-financial-briefing` 处理一个本地 topic，再汇总为 `external_background_fusion.v1`。
- 必要时通过公开 `daily-update` 子命令刷新数据；输出必须保持 `analysis_mode: research_only` 和 `not_investment_advice: true` 边界。

## 文件和子目录索引

- `AGENTS.md`：本目录索引和维护规则。
- `claude.md`：Claude/Codex 入口引用文件，内容固定为 `@agents.md`。
- `SKILL.md`：skill 触发 metadata 和核心工作流。
- `agents/`：UI metadata 目录，默认提示词必须显式包含 `$a-share-daily-review`。
- `references/`：一跳 reference，保存 workflow、LLM report prompt、输出契约和测试说明。

## 更新要求

- 修改 CLI、输出路径、数据状态语义或禁用语言时，同步更新 `SKILL.md`、reference、实施文档和测试。
- 不在 skill 内 hard code 日期、本机绝对路径或 `scripts/collect_daily_snapshot.py` 作为日常入口。
