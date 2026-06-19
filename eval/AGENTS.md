# eval 目录索引

本文件是 `eval/` 的目录索引。新增、删除、改名或移动评测配置、provider 或黄金测试适配文件时，必须同步更新这里的说明。

## 目录用途

- 保存本仓库 skill 和 prompt 的本地评测配置。
- 第一版评测优先使用 Promptfoo 风格配置和本地 provider，不依赖真实 AKShare 网络调用。
- Promptfoo 是黄金测试和回归评测层，不是普通日报生成的运行时 gate。
- 评测输出只证明 prompt/skill 契约，不证明真实市场结论有效。

## 文件和子目录索引

- `AGENTS.md`：本目录索引和维护规则。
- `claude.md`：Claude/Codex 入口引用文件，内容固定为 `@agents.md`。
- `promptfooconfig.daily-financial-briefing.yaml`：当日财经信息总结 skill 的 Promptfoo 配置，读取对应黄金测试集并调用本地 fixture provider，不访问真实财经网站。
- `promptfooconfig.yaml`：每日复盘 skill 的 Promptfoo 配置草案，读取 docs 下的黄金测试集。
- `providers/`：Promptfoo 本地 provider 目录；本地 fixture 覆盖 passed、partial、skipped、failed、missing、external background parallel_agent_skill 审计、fixture_smoke 区分、blocked/invalid citation、HTML 正文边界、技术参考 Markdown 和刷新契约场景。

## 更新要求

- 新增每日复盘评测用例或 provider 行为时，同步更新 `docs/a-share-daily-review-skill-golden-testset.md`。
- 新增当日财经信息总结评测用例或 provider 行为时，同步更新 `docs/daily-financial-news-skill-golden-testset.md`。
- 不在 provider 中调用外部行情接口；需要数据状态时使用 fixture 或 prompt 变量。
