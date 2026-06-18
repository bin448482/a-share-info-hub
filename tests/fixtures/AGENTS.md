# tests/fixtures 目录索引

本文件是 `tests/fixtures/` 的目录索引。新增、删除、改名或移动 fixture 时，必须同步更新这里的说明。

## 目录用途

- 保存单元测试使用的最小样例数据。
- fixture 是结构测试材料，不代表真实市场数据验证。
- 不要把 fixture 输出当作 AKShare 当前可用性证据。

## 文件索引

- `AGENTS.md`：本目录索引和维护规则。
- `claude.md`：Claude/Codex 入口引用文件，内容固定为 `@agents.md`。
- `stock_zh_a_spot_success.json`：主表标准化成功场景。
- `stock_zh_a_spot_empty.json`：主表空结果场景。
- `stock_zh_a_spot_schema_changed.json`：主表缺少关键字段的 schema 变化场景。
- `limit_pool_empty.json`：增强事件接口空结果场景。
- `limit_pool_success.json`：涨跌停增强表标准化成功场景。
- `lhb_schema_changed.json`：龙虎榜增强表缺少股票代码的 schema 变化场景。

## 更新要求

- 每个 JSON fixture 必须包含 `description` 和 `rows` 字段。
- 新增 fixture 时，同步说明它服务的测试场景和边界。
- 修改 fixture 结构时，同步更新读取 fixture 的测试 helper。
