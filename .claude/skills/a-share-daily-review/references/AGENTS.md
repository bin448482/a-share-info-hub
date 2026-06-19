# skills/a-share-daily-review/references 目录索引

本文件是 `skills/a-share-daily-review/references/` 的目录索引。新增、删除、改名或移动 reference 时，必须同步更新这里的说明。

## 目录用途

- 保存每日复盘 skill 的详细执行规则，供 `SKILL.md` 按需引用。
- Reference 只写 agent 运行需要的契约和步骤，不保存用户侧长文档。

## 文件索引

- `AGENTS.md`：本目录索引和维护规则。
- `claude.md`：Claude/Codex 入口引用文件，内容固定为 `@agents.md`。
- `daily-review-workflow.md`：每日复盘 skill 的 context 生成、6 子 Agent external background 接入、Python fixture helper 边界、LLM sections、HTML 渲染、安全边界和验证规则。
- `report-prompt.md`：LLM 将 `review-context.json` 转换为可校验 sections JSON 的提示词约束，包含 external background 字段边界。

## 更新要求

- 调整 review CLI、报告路径、数据状态或禁用语言时，同步更新本 reference 和相关测试。
