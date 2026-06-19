# eval/providers 目录索引

本文件是 `eval/providers/` 的目录索引。新增、删除、改名或移动 provider 时，必须同步更新这里的说明。

## 目录用途

- 保存 Promptfoo 或其他评测框架调用本仓库逻辑的本地 provider。
- Provider 应调用仓库公开 CLI 或公开 Python API，不复制实现逻辑。

## 文件索引

- `AGENTS.md`：本目录索引和维护规则。
- `claude.md`：Claude/Codex 入口引用文件，内容固定为 `@agents.md`。
- `run-a-share-daily-review.js`：Promptfoo 本地 provider，创建隔离 daily run；`parallel_agent_skill` 用例用本地 helper 生成等价 fusion 包但只输出 runtime 验收审计行，`fixture_smoke` 用例显式标记为 fixture，blocked/invalid citation 用例保留 legacy fixture；随后调用 `python -m a_share_info_hub daily-review --user-prompt ... --render-mode deterministic`，并返回 HTML 正文边界、external background 融合、唯一风险/问题板块和技术参考 Markdown 诊断审计结果。
- `run-daily-financial-briefing.js`：Promptfoo 本地 provider，读取 `source_fixture` 生成确定性 Markdown 简报或 blocked 输出，并返回结构、引用、禁用交易语言和不联网审计行。

## 更新要求

- Provider 参数变化时，同步更新对应 Promptfoo 配置和黄金测试说明。
