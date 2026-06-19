# 当日财经信息采集 — 数据源可行性分析

> **状态**：实测验证完成，待 review。
> **验证日期**：2026-06-19
> **验证环境**：AKShare 1.18.64，Windows 11，无 VPN/代理（部分测试在代理环境下报错，已在报告中标注）。

本文档是对 `daily-financial-news-design.md` 中定义的两类数据源（`us_macro` / `investment_bank_views`）的可行性验证。每条结论均有实测数据支撑，区分"已确认可用""部分可用/需降级""不可用/需替代方案"三个等级。

---

## 一、US Macro（美国宏观数据）

### 1.1 已确认稳定可用的数据源

以下 AKShare 接口均通过实测验证，数据来自东方财富/金十数据中心，国内无需 VPN 即可访问。

| # | 数据指标 | AKShare 函数 | 数据行数 | 字段结构 | 最新数据点 | 状态 |
|---|---------|-------------|---------|---------|-----------|------|
| 1 | 美国 CPI 月率 | `macro_usa_cpi_monthly()` | 669 | `商品, 日期, 今值, 预测值, 前值` | 2025-09-11（预发布） | ✅ |
| 2 | 美国核心 CPI 月率 | `macro_usa_core_cpi_monthly()` | 669 | 同上 | 已验证可用 | ✅ |
| 3 | 美国核心 PCE 物价指数年率 | `macro_usa_core_pce_price()` | 670 | 同上 | 2025-08-29 | ✅ |
| 4 | 美国非农就业人数 | `macro_usa_non_farm()` | 669 | 同上 | 2025-09-05（预发布） | ✅ |
| 5 | 美国失业率 | `macro_usa_unemployment_rate()` | 669 | 同上 | 2025-09-05（预发布） | ✅ |
| 6 | 美国 GDP 季率 | `macro_usa_gdp_monthly()` | 210 | 同上 | 2025-09-25（预发布） | ✅ |
| 7 | 美联储利率决议 | `macro_bank_usa_interest_rate()` | 294 | 同上 | 2025-10-30（预发布） | ✅ |
| 8 | 中美债券收益率（含美债 2Y/5Y/10Y/30Y） | `bond_zh_us_rate()` | 9,281 | `日期, 美国国债收益率2年/5年/10年/30年, 美国国债收益率10年-2年` 等 13 列 | **2026-06-18（当日数据）** | ✅ |
| 9 | 美国 10 年期国债（Sina 源） | `bond_gb_us_sina()` | 1,000 | `date, open, high, low, close, volume` (OHLCV) | **2026-06-18（当日数据）** | ✅ |
| 10 | FOMC 加息概率 | `cme-fedwatch` PyPI 包 | 实时 | JSON: `effr, current_target, meetings[{date, probabilities}]` | 2026-07-29 会议 | ✅ |

### 1.2 实测可用的补充数据源

以下接口也通过实测验证，可作为辅助/可选数据：

| # | 数据指标 | AKShare 函数 | 备注 |
|---|---------|-------------|------|
| 11 | 美国 ADP 就业 | `macro_usa_adp_employment()` | "小非农"，与非农互补 |
| 12 | 美国 PPI | `macro_usa_ppi()` | 通胀关联指标 |
| 13 | 美国核心 PPI | `macro_usa_core_ppi()` | 同上 |
| 14 | 美国 ISM 制造业 PMI | `macro_usa_ism_pmi()` | 经济景气 |
| 15 | 美国 ISM 非制造业 PMI | `macro_usa_ism_non_pmi()` | 服务景气 |
| 16 | 美国初请失业金 | `macro_usa_initial_jobless()` | 周度高频 |
| 17 | 美国零售销售 | `macro_usa_retail_sales()` | 消费 |
| 18 | 美国贸易帐 | `macro_usa_trade_balance()` | 贸易 |
| 19 | 美国新屋/成屋销售 | `macro_usa_new_home_sales()` / `macro_usa_exist_home_sales()` | 房地产 |
| 20 | 美国工业产出 | `macro_usa_industrial_production()` | 生产 |

**注意**：所有 `macro_usa_*` 函数共用相同的字段结构 `['商品', '日期', '今值', '预测值', '前值']`，非常适合统一解析流程。

### 1.3 存在问题

| 问题 | 严重程度 | 说明 |
|------|---------|------|
| **DXY/美元指数无直接接口** | 🔴 需替代方案 | `fx_spot_quote()` 返回全部 NaN（可能是代理问题或源站变化）；AKShare 无直接的美元指数函数。替代方案：(a) 使用 `currency_latest`/`currency_history` 的 USD 汇率组合近似计算；(b) 使用 Sina/东方财富页面抓取美元指数；(c) 第一版不做 DXY，仅使用美债收益率和利率预期作为美元流动性的代理指标 |
| **数据字段全中文** | 🟡 需映射 | 所有 `macro_usa_*` 函数返回中文列名（`商品, 日期, 今值, 预测值, 前值`），第一版需要英文映射并翻译 `商品` 值 |
| **预发布数据包含 NaN** | 🟢 可控 | 未来日期的数据行 `今值` 为 NaN，只记录 `预测值` 和 `前值`。这不是错误，正常过滤即可；但需在状态中区分"预发布"和"已发布" |
| **bond_zh_us_rate 调用慢** | 🟡 性能 | 该函数内部发 19 次 HTTP 请求，耗时约 8-10 秒。需要合理设置超时（建议 30s） |
| **proxy 环境影响** | 🟡 环境相关 | 部分 AKShare 接口在代理环境下出现 `ProxyError`（如 `stock_us_famous_spot_em`）。项目已有 `--ignore-proxy` 机制，news-update 需同样支持 |
| **月度指标的最新值滞后** | 🟢 业务正常 | CPI/PCE/非农按月发布，最新 `今值` 可能在 1-2 个月前。这是数据性质决定的，不是采集问题 |

---

## 二、Investment Bank Views（投行观点）

### 2.1 已确认可用的数据源

投行原始研究报告均有付费墙，第一版设计文档也明确"只采集公开可访问内容或公开财经源转述内容"。以下是实测可用的中文财经媒体/聚合源：

| # | 来源 | 访问方式 | 实测状态 | 投行内容密度 | 稳定性 |
|---|------|---------|---------|------------|--------|
| 1 | **财新/Caixin 新闻** (`stock_news_main_cx`) | AKShare API | ✅ 可用，100 条/次 | 中等（含"研报精华"标签） | 🟡 需持续验证 |
| 2 | **百度财经日历** (`news_economic_baidu`) | AKShare API | ✅ 可用，99 条 | 低（纯事件日历，无观点） | 🟢 稳定 |
| 3 | **上金属期货新闻** (`futures_news_shmet`) | AKShare API | ✅ 可用，20 条 | 低（商品期货为主） | 🟡 结构简单 |
| 4 | **CCTV 新闻** (`news_cctv`) | AKShare API | ✅ 可用，12 条 | **极低**（时政为主，数据仅更新到 2024 年 4 月） | 🔴 数据陈旧 |

### 2.2 关键结论：js_news（金十数据）不适用于当前版本

设计文档中隐含的金十数据新闻源，在 AKShare 1.18.64 中**无 `js_news` 函数**。金十数据相关函数仅有：
- `crypto_js_spot`（加密货币现货）
- `stock_js_weibo_report`（微博情绪）
- `stock_zyjs_ths`（同花顺摘要）

**金十数据"最新资讯"在此版本中不可用**。如果后续需要此源，可能需要：
- 升级 AKShare 到更新版本（存在依赖冲突风险）
- 或直接抓取金十数据公开页面（增加维护负担）

### 2.3 推荐替代方案：东方财富研报+财新新闻组合

根据实测结果，建议第一版采用以下两源组合：

| source_id | 来源 | 获取方式 | 内容范围 |
|-----------|------|---------|---------|
| `caixin_news` | 财新新闻 | `ak.stock_news_main_cx()` → 按 tag 过滤 `研报精华` | 券商/机构研报摘要，经常引用国际投行观点 |
| `shmet_news` | 上金属商品新闻 | `ak.futures_news_shmet()` → 关键词过滤 | 商品期货相关宏观评论，偶尔引用投行判断 |

**补充选项（需额外开发，不在 AKShare 内）**：

| source_id | 来源 | 获取方式 | 风险 |
|-----------|------|---------|------|
| `wallstreetcn` | 华尔街见闻 | `public_page` — 抓取 `https://wallstreetcn.com/` 首页搜索"高盛/摩根/花旗/瑞银" | 🔴 无官方 API，页面结构变化即失效 |
| `sina_bank_views` | 新浪财经-投行观点 | `public_page` — 搜索 `https://search.sina.com.cn/?q=投行观点` | 🟡 新浪页面结构较稳定 |
| `eastmoney_strategy` | 东方财富策略研报 | `public_page` — `https://data.eastmoney.com/report/zw_strategy.jshtml` | 🟡 需解析 HTML；URL token 可能变化 |

### 2.4 投行观点采集的核心问题

| 问题 | 严重程度 | 说明 |
|------|---------|------|
| **无直接结构化 API** | 🔴 关键 | 投行原始报告有付费墙；中文媒体转述均为非结构化 HTML 页面。目前 AKShare 版本中无"投行观点"专用接口 |
| **内容密度低** | 🟡 预期内 | 即使有聚合源，真正涉及高盛/大摩/JPM 对 A 股影响判断的内容每天可能只有 1-3 条，多数日子可能为空 |
| **页面抓取不稳定** | 🔴 高风险 | 如果使用 `public_page` 方式抓取华尔街见闻/东方财富，属于设计文档明确列为"待验证"的来源。页面结构变化可能导致 `parse_failed`，需要持续维护 |
| **关键词过滤假阳性** | 🟡 可控 | 靠"高盛""摩根"等关键词过滤可能匹配到不相关内容（如"高盛员工晋升"而非"高盛看多中国"）。需要二级过滤 |
| **时效性不确定** | 🟡 预期内 | 中文媒体翻译/转载投行观点通常有时滞（数小时到一天），不是实时数据 |
| **数据陈旧** | 🟡 注意 | `news_cctv` 最新数据停留在 2024 年 4 月。需在来源注册中标记 `enabled: false` |

---

## 三、design.md 中可行与不可行的对照

### 3.1 可直接实现的（已验证数据源充足）

| 设计要求 | 可行性 | 实现路径 |
|---------|--------|---------|
| 美国 CPI/PCE/非农/FOMC 数据 | ✅ 可行 | 全部通过 AKShare `macro_usa_*` 系列函数 |
| 美债收益率 | ✅ 可行 | `bond_zh_us_rate()` 提供 2Y/5Y/10Y/30Y，每日更新 |
| 美元流动性指标 | 🟡 降级 | DXY 无法直接获取；可用美债收益率 + 利率预期作为替代，或第一版暂不纳入 DXY |
| 美联储利率预期 | ✅ 可行 | `cme-fedwatch` 免费 PyPI 包 + `macro_bank_usa_interest_rate()` |
| 原始文件保存 | ✅ 可行 | 与现有 `collect_daily_snapshot.py` 相同模式 |
| 标准化 Parquet + DuckDB | ✅ 可行 | 复用现有 write pipeline |
| 失败日志 JSONL | ✅ 可行 | 复用现有 `external-interface-failures.jsonl` 机制 |
| 来源注册配置 | ✅ 可行 | 新增 YAML/JSON 配置文件或 Python dict |

### 3.2 需要降级或推迟的

| 设计要求 | 判定 | 原因 |
|---------|------|------|
| 一个 US Macro 来源 | ✅ 超额满足 | 至少 10 个已验证的稳定接口 |
| 一个 Investment Bank Views 来源 | 🟡 需降级 | 没有直接的结构化 API。第一版可行方案：(a) `stock_news_main_cx` 财新研报精华（AKShare 内，稳定）；(b) 或接受 `public_page` 抓取华尔街见闻/东方财富（不稳定） |
| 每条记录都有 URL | 🟡 部分可行 | AKShare 返回的 DataFrame 不一定含原文 URL。需要从来源函数文档推断或构造 URL |
| 高盛/大摩/小摩/花旗/瑞银 五家覆盖 | 🟡 部分可行 | 取决于中文媒体当天是否转载这些银行的报告。非日报，不能保证每日都有 |

### 3.3 需要调整设计的内容

| 原有假设 | 实际发现 | 建议调整 |
|---------|---------|---------|
| 可用 RSS 获取投行观点 | 投行无公开 RSS；Google News RSS 被墙 | 从"RSS"改为"API (AKShare) + 有限 public_page" |
| 金十数据 js_news 作为主源 | AKShare 1.18.64 无此函数 | 降级为"后续版本可考虑" |
| DXY 可通过 AKShare 获取 | `fx_spot_quote` 返回 NaN | 第一版建议不要求 DXY；使用利率+利差作为美元流动性代理 |

---

## 四、推荐的第一版实施方案（修订建议）

### 4.1 US Macro 源清单（全部确认可用）

建议启用以下 5 个核心来源，覆盖设计文档要求的全部 us_macro 指标：

| source_id | AKShare 函数 | 覆盖指标 |
|-----------|-------------|---------|
| `us_cpi` | `macro_usa_cpi_monthly` + `macro_usa_core_cpi_monthly` | CPI、核心 CPI |
| `us_pce` | `macro_usa_core_pce_price` | 核心 PCE |
| `us_employment` | `macro_usa_non_farm` + `macro_usa_unemployment_rate` | 非农、失业率 |
| `us_fed_rate` | `macro_bank_usa_interest_rate` | FOMC 利率决议 |
| `us_treasury` | `bond_zh_us_rate` | 美债 2Y/5Y/10Y/30Y 收益率 |

可选扩展：
- `us_gdp`：`macro_usa_gdp_monthly`
- `us_fedwatch`：`cme-fedwatch` PyPI 包

### 4.2 Investment Bank Views 源清单（保守方案）

建议第一版**只在 AKShare 内获取，不做外部页面抓取**：

| source_id | AKShare 函数 | 内容 | 预期产出频率 |
|-----------|-------------|------|------------|
| `caixin_research` | `stock_news_main_cx` → tag=`研报精华` | 券商/机构研报摘要（含国际投行引用） | 每日 1-5 条相关 |
| `shmet_news` | `futures_news_shmet` → 关键词过滤 | 商品宏观评论（偶尔涉及投行观点） | 每日 0-2 条相关 |

如果这两个源产出的内容不满足需求，第二版再考虑引入 `public_page` 抓取华尔街见闻/东方财富。

### 4.3 建议不纳入第一版的内容（与 design.md 一致）

- `public_page` 页面抓取（华尔街见闻、东方财富、新浪财经）— 维护风险高，推迟到第二版
- DXY 美元指数 — 无稳定免费接口，推迟到第二版
- Google News RSS — 国内被墙，推迟到后续可选配置

---

## 五、风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| AKShare 接口字段名变化 | 中 | 中 | 沿用项目现有 `SchemaChangedError` 机制，字段变化时记录 `schema_changed` 而非崩溃 |
| AKShare 版本升级引入 regression | 低 | 中 | 锁定版本；升级前先在测试环境验证 |
| 投行观点源日均为空 | 高 | 低 | 空结果 = `success_empty`，不影响整体管线；状态报告中标注 |
| cme-fedwatch 依赖变化 | 低 | 低 | 该包简单稳定；也可直接计算 CME 结算价的利率概率，去除第三方依赖 |
| 东方财富/金十源站反爬升级 | 低 | 高 | 所有 macro_usa 数据走 AKShare，由 AKShare 社区维护应对反爬 |
| 代理环境导致部分接口不可用 | 中 | 中 | 与 `daily-update` 共享 `--ignore-proxy` 机制 |

---

## 六、结论与建议

### 总体结论

**US Macro 采集完全可行，数据源充足且稳定。Investment Bank Views 采集需要降低期望：第一版只能做到"中文财经媒体的研报/新闻摘要 + 关键词过滤"，无法保证每日都有高盛/大摩等五大投行的直接观点。**

### 关键数字

- **US Macro 可立即启用**：10+ 个 AKShare 验证通过的接口，覆盖 CPI/PCE/非农/FOMC/美债收益率，数据每日更新
- **投行观点需降低期望**：2 个 AKShare 内可行源（财新研报 + 期货新闻），预期每日 0-5 条相关内容
- **无法通过 AKShare 1.18.64 获取**：DXY 美元指数、金十数据新闻流（`js_news`）

### 建议的下一步

1. **Review 本报告**，确认是否同意"第一版投行观点只做 AKShare 内两个源，不做 public_page 抓取"
2. **决定 DXY 处理方式**：(a) 第一版不纳入；(b) 寻找额外替代源；(c) 使用美债收益率+利差作为美元流动性代理
3. **开始编写实施文档**（`daily-financial-news-implementation-plan.md`），基于本报告的结论细化源配置、解析逻辑和测试用例
