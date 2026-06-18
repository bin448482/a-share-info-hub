# A Share Info Hub

本仓库用于验证和落地每日 A 股免费数据采集链路。当前主入口是每日快照采集，不生成预测，也不提供交易建议。

## 每日快照采集

实施入口是仓库 CLI：

```text
python -m a_share_info_hub daily-update
```

需要指定日期时，使用参数传入，不要把日期写死到脚本或文档流程里：

```text
python -m a_share_info_hub daily-update --trade-date <YYYY-MM-DD>
```

如果当前环境代理导致 AKShare 接口失败，可以显式忽略代理：

```text
python -m a_share_info_hub daily-update --ignore-proxy
```

主要输出：

- `data/raw/YYYY-MM-DD/<source>/response.json`
- `data/raw/YYYY-MM-DD/<source>/metadata.json`
- `data/normalized/daily_stock_snapshot.parquet`
- `data/normalized/limit_pool_events.parquet`
- `data/normalized/lhb_events.parquet`
- `data/normalized/market_summary.parquet`
- `data/normalized/board_snapshot.parquet`
- `logs/external-interface-failures.jsonl`
- `reports/daily-runs/YYYY-MM-DD/interface-status.json`
- `reports/daily-runs/YYYY-MM-DD/daily-data-summary.md`
- `market.duckdb`

## 验证命令

```text
python -m py_compile a_share_info_hub/__main__.py scripts/collect_daily_snapshot.py
python -m pytest tests
python -c "import akshare, pandas, duckdb, pyarrow"
```

真实接口验证需要指定日期运行每日采集脚本；单元测试只验证本地解析、状态和落盘逻辑。
