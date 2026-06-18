"""验证每日快照落盘、日志、摘要和 DuckDB 输出。"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

from scripts.collect_daily_snapshot import (
    DUCKDB_SKIPPED,
    DUCKDB_WRITTEN,
    FAILED,
    OVERALL_PASSED,
    OVERALL_SKIPPED,
    SUCCESS,
    SourceRecord,
    append_status_log,
    write_daily_summary,
    write_duckdb_tables,
    write_interface_status,
    write_raw_artifacts,
    CallResult,
    SourceSpec,
    collect_daily_snapshot,
)


TRADE_DATE = date(2026, 6, 18)
FETCHED_AT = "2026-06-18T15:10:00+08:00"


def make_record(source_key: str, category: str, status: str, row_count: int) -> SourceRecord:
    """构造输出测试使用的接口状态记录。"""

    return SourceRecord(
        source_key=source_key,
        function_name=source_key,
        category=category,
        params={},
        status=status,
        row_count=row_count,
        columns=["代码"],
        failure_reason=None if status == SUCCESS else "TimeoutError: timed out",
        fetched_at=FETCHED_AT,
        raw_path=None,
        metadata_path=None,
        elapsed_seconds=0.01,
        attempts=1,
    )


def test_failure_log_writes_jsonl(tmp_path: Path) -> None:
    """失败接口应追加可解析 JSONL 日志。"""

    log_path = tmp_path / "logs" / "external-interface-failures.jsonl"
    record = make_record("stock_lhb_detail_em", "lhb", FAILED, 0)

    append_status_log(log_path, record, TRADE_DATE)

    payload = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert payload["trade_date"] == "2026-06-18"
    assert payload["function_name"] == "stock_lhb_detail_em"
    assert payload["failure_type"] == FAILED
    assert payload["raw_path"] is None


def test_raw_artifacts_write_response_and_metadata(tmp_path: Path) -> None:
    """成功接口应写入原始响应和元数据。"""

    spec = SourceSpec("stock_zt_pool_em", "stock_zt_pool_em", "limit_pool")
    result = CallResult(
        status=SUCCESS,
        dataframe=pd.DataFrame([{"代码": "000001", "名称": "平安银行"}]),
        row_count=1,
        columns=["代码", "名称"],
        failure_reason=None,
        fetched_at=FETCHED_AT,
        elapsed_seconds=0.01,
        attempts=1,
    )

    raw_path, metadata_path = write_raw_artifacts(
        tmp_path / "raw", TRADE_DATE, spec, result, SUCCESS, None
    )

    assert raw_path is not None
    assert json.loads(Path(raw_path).read_text(encoding="utf-8"))[0]["代码"] == "000001"
    metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
    assert metadata["status"] == SUCCESS
    assert metadata["raw_path"] == raw_path


def test_reports_write_parseable_status_and_summary(tmp_path: Path) -> None:
    """接口状态 JSON 和每日摘要应落盘且包含核心边界。"""

    records = [
        make_record("stock_zh_a_spot", "main", SUCCESS, 2),
        make_record("stock_zt_pool_em", "limit_pool", SUCCESS, 0),
    ]
    tables = {
        "daily_stock_snapshot": pd.DataFrame([{"trade_date": "2026-06-18"}]),
        "limit_pool_events": pd.DataFrame(),
        "lhb_events": pd.DataFrame(),
        "market_summary": pd.DataFrame(),
        "board_snapshot": pd.DataFrame(),
    }
    status_path = tmp_path / "interface-status.json"
    summary_path = tmp_path / "daily-data-summary.md"

    write_interface_status(
        status_path,
        TRADE_DATE,
        records,
        tables,
        DUCKDB_WRITTEN,
        None,
        OVERALL_PASSED,
    )
    write_daily_summary(
        summary_path,
        TRADE_DATE,
        records,
        tables,
        DUCKDB_WRITTEN,
        None,
        OVERALL_PASSED,
    )

    status = json.loads(status_path.read_text(encoding="utf-8"))
    summary = summary_path.read_text(encoding="utf-8")
    assert status["overall_status"] == OVERALL_PASSED
    assert "本运行不生成预测" in summary
    assert "本运行不生成交易建议" in summary


def test_duckdb_replaces_same_trade_date(tmp_path: Path) -> None:
    """同一交易日重跑应替换 DuckDB 旧记录而不是追加重复行。"""

    database_path = tmp_path / "market.duckdb"
    first = {
        "daily_stock_snapshot": pd.DataFrame(
            [{"trade_date": "2026-06-18", "symbol": "000001", "last_price": 10.0}]
        )
    }
    second = {
        "daily_stock_snapshot": pd.DataFrame(
            [{"trade_date": "2026-06-18", "symbol": "000001", "last_price": 11.0}]
        )
    }

    assert write_duckdb_tables(database_path, first, TRADE_DATE, skip_duckdb=False)[0] == DUCKDB_WRITTEN
    assert write_duckdb_tables(database_path, second, TRADE_DATE, skip_duckdb=False)[0] == DUCKDB_WRITTEN

    with duckdb.connect(str(database_path)) as connection:
        rows = connection.execute(
            "SELECT COUNT(*), MAX(last_price) FROM daily_stock_snapshot WHERE trade_date = ?",
            ["2026-06-18"],
        ).fetchone()

    assert rows == (1, 11.0)


def test_duckdb_replaces_empty_table_schema_with_real_rows(tmp_path: Path) -> None:
    """空表先落库后再写真实行时，DuckDB schema 应随真实数据更新。"""

    database_path = tmp_path / "market.duckdb"
    empty = {
        "daily_stock_snapshot": pd.DataFrame(
            columns=["trade_date", "symbol", "last_price"]
        )
    }
    real = {
        "daily_stock_snapshot": pd.DataFrame(
            [{"trade_date": "2026-06-18", "symbol": "000001", "last_price": 11.0}]
        )
    }

    assert write_duckdb_tables(database_path, empty, TRADE_DATE, skip_duckdb=False)[0] == DUCKDB_WRITTEN
    assert write_duckdb_tables(database_path, real, TRADE_DATE, skip_duckdb=False)[0] == DUCKDB_WRITTEN

    with duckdb.connect(str(database_path)) as connection:
        rows = connection.execute(
            "SELECT trade_date, symbol, last_price FROM daily_stock_snapshot"
        ).fetchone()

    assert rows == ("2026-06-18", "000001", 11.0)


def test_collect_daily_snapshot_with_mock_module_reaches_passed(tmp_path: Path) -> None:
    """mock 接口全成功时，端到端运行应生成 passed 状态和全部输出。"""

    class MockAk:
        """提供每日快照脚本需要的最小 AKShare 函数集合。"""

        @staticmethod
        def tool_trade_date_hist_sina() -> pd.DataFrame:
            """返回包含目标日期的交易日历 fixture。"""

            return pd.DataFrame([{"trade_date": "2026-06-18"}])

        @staticmethod
        def stock_zh_a_spot() -> pd.DataFrame:
            """返回主表成功 fixture。"""

            return pd.DataFrame(
                [
                    {
                        "代码": "000001",
                        "名称": "平安银行",
                        "最新价": 10.5,
                        "涨跌额": 0.1,
                        "涨跌幅": 0.96,
                        "买入": 10.49,
                        "卖出": 10.5,
                        "昨收": 10.4,
                        "今开": 10.42,
                        "最高": 10.6,
                        "最低": 10.3,
                        "成交量": 100000,
                        "成交额": 1050000,
                        "时间戳": "2026-06-18 15:00:00",
                    }
                ]
            )

        @staticmethod
        def stock_zt_pool_em(date: str) -> pd.DataFrame:
            """返回涨停池空事件集。"""

            return pd.DataFrame()

        stock_zt_pool_previous_em = stock_zt_pool_em
        stock_zt_pool_strong_em = stock_zt_pool_em
        stock_zt_pool_sub_new_em = stock_zt_pool_em
        stock_zt_pool_zbgc_em = stock_zt_pool_em
        stock_zt_pool_dtgc_em = stock_zt_pool_em

        @staticmethod
        def stock_lhb_detail_daily_sina(date: str) -> pd.DataFrame:
            """返回龙虎榜空事件集。"""

            return pd.DataFrame()

        @staticmethod
        def stock_lhb_detail_em(start_date: str, end_date: str) -> pd.DataFrame:
            """返回龙虎榜空事件集。"""

            return pd.DataFrame()

        stock_lhb_jgmmtj_em = stock_lhb_detail_em

        @staticmethod
        def stock_sse_deal_daily(date: str) -> pd.DataFrame:
            """返回上交所市场摘要。"""

            return pd.DataFrame([{"单日情况": "成交概况", "股票": "A股"}])

        @staticmethod
        def stock_szse_summary(date: str) -> pd.DataFrame:
            """返回深交所市场摘要。"""

            return pd.DataFrame([{"证券类别": "股票", "数量": 1}])

        @staticmethod
        def stock_board_industry_name_em() -> pd.DataFrame:
            """返回行业板块快照。"""

            return pd.DataFrame([{"板块名称": "银行", "涨跌幅": 1.2}])

        @staticmethod
        def stock_board_concept_name_em() -> pd.DataFrame:
            """返回概念板块快照。"""

            return pd.DataFrame([{"板块名称": "数字经济", "涨跌幅": 2.3}])

    outputs = collect_daily_snapshot(
        trade_date=TRADE_DATE,
        output_root=tmp_path,
        ak_module=MockAk,
        max_retries=1,
        retry_sleep=0,
        skip_duckdb=False,
        min_main_rows=1,
    )

    assert outputs.overall_status == OVERALL_PASSED
    assert Path(outputs.output_paths["interface_status"]).exists()
    assert Path(outputs.output_paths["daily_summary"]).exists()
    assert Path(outputs.output_paths["duckdb"]).exists()


def test_collect_daily_snapshot_skips_weekend_without_source_calls(tmp_path: Path) -> None:
    """周末应直接标记 skipped，不能调用行情接口或写行情数据。"""

    class WeekendAk:
        """提供会在行情接口被调用时失败的 mock。"""

        @staticmethod
        def stock_zh_a_spot() -> pd.DataFrame:
            """如果周末仍调用主表接口，测试应失败。"""

            raise AssertionError("market source should not be called")

    weekend = date(2026, 6, 20)
    outputs = collect_daily_snapshot(
        trade_date=weekend,
        output_root=tmp_path,
        ak_module=WeekendAk,
        max_retries=1,
        retry_sleep=0,
        skip_duckdb=False,
        min_main_rows=1,
    )

    status = json.loads(Path(outputs.output_paths["interface_status"]).read_text(encoding="utf-8"))
    summary = Path(outputs.output_paths["daily_summary"]).read_text(encoding="utf-8")
    assert outputs.overall_status == OVERALL_SKIPPED
    assert outputs.duckdb_status == DUCKDB_SKIPPED
    assert outputs.source_records == []
    assert status["overall_status"] == OVERALL_SKIPPED
    assert status["sources"] == []
    assert status["trading_day_check"]["is_trading_day"] is False
    assert status["trading_day_check"]["source"] == "weekday"
    assert "本运行未调用行情接口" in summary
    assert not (tmp_path / "data" / "raw" / weekend.isoformat()).exists()


def test_collect_daily_snapshot_skips_calendar_non_trading_day(tmp_path: Path) -> None:
    """工作日不在交易日历中时，应标记 skipped 且不调用行情接口。"""

    class HolidayAk:
        """提供不包含目标日期的交易日历 mock。"""

        @staticmethod
        def tool_trade_date_hist_sina() -> pd.DataFrame:
            """返回不包含目标日期的交易日历。"""

            return pd.DataFrame([{"trade_date": "2026-06-18"}])

        @staticmethod
        def stock_zh_a_spot() -> pd.DataFrame:
            """如果非交易日仍调用主表接口，测试应失败。"""

            raise AssertionError("market source should not be called")

    holiday = date(2026, 6, 22)
    outputs = collect_daily_snapshot(
        trade_date=holiday,
        output_root=tmp_path,
        ak_module=HolidayAk,
        max_retries=1,
        retry_sleep=0,
        skip_duckdb=False,
        min_main_rows=1,
    )

    status = json.loads(Path(outputs.output_paths["interface_status"]).read_text(encoding="utf-8"))
    assert outputs.overall_status == OVERALL_SKIPPED
    assert status["trading_day_check"]["source"] == "akshare.tool_trade_date_hist_sina"
    assert status["trading_day_check"]["is_trading_day"] is False
    assert status["sources"] == []


def test_collect_daily_snapshot_blocks_when_calendar_unavailable(tmp_path: Path) -> None:
    """交易日历不可用时，应失败并阻断行情接口调用。"""

    class BrokenCalendarAk:
        """提供会让交易日历失败的 mock。"""

        @staticmethod
        def tool_trade_date_hist_sina() -> pd.DataFrame:
            """模拟 AKShare 交易日历不可用。"""

            raise RuntimeError("calendar unavailable")

        @staticmethod
        def stock_zh_a_spot() -> pd.DataFrame:
            """如果日历失败后仍调用主表接口，测试应失败。"""

            raise AssertionError("market source should not be called")

    outputs = collect_daily_snapshot(
        trade_date=TRADE_DATE,
        output_root=tmp_path,
        ak_module=BrokenCalendarAk,
        max_retries=1,
        retry_sleep=0,
        skip_duckdb=False,
        min_main_rows=1,
    )

    status = json.loads(Path(outputs.output_paths["interface_status"]).read_text(encoding="utf-8"))
    summary = Path(outputs.output_paths["daily_summary"]).read_text(encoding="utf-8")
    assert outputs.overall_status == FAILED
    assert status["overall_status"] == FAILED
    assert status["trading_day_check"]["status"] == FAILED
    assert "交易日历验证失败" in summary
