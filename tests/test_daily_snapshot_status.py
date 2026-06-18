"""验证每日快照状态归类和异常语义。"""

from __future__ import annotations

from datetime import date

import pandas as pd

from scripts.collect_daily_snapshot import (
    FAILED,
    MAIN_SOURCE_KEY,
    OVERALL_FAILED,
    OVERALL_PARTIAL,
    OVERALL_PASSED,
    SCHEMA_CHANGED,
    SUCCESS,
    SUCCESS_EMPTY,
    CallResult,
    SourceRecord,
    SourceSpec,
    build_overall_status,
    normalize_source,
)


TRADE_DATE = date(2026, 6, 18)
FETCHED_AT = "2026-06-18T15:10:00+08:00"


def call_result(status: str, dataframe: pd.DataFrame) -> CallResult:
    """构造本地测试使用的接口调用结果。"""

    return CallResult(
        status=status,
        dataframe=dataframe,
        row_count=len(dataframe.index),
        columns=[str(column) for column in dataframe.columns],
        failure_reason=None,
        fetched_at=FETCHED_AT,
        elapsed_seconds=0.01,
        attempts=1,
    )


def record(source_key: str, category: str, status: str) -> SourceRecord:
    """构造整体状态归类测试使用的接口记录。"""

    return SourceRecord(
        source_key=source_key,
        function_name=source_key,
        category=category,
        params={},
        status=status,
        row_count=1 if status == SUCCESS else 0,
        columns=[],
        failure_reason=None,
        fetched_at=FETCHED_AT,
        raw_path=None,
        metadata_path=None,
        elapsed_seconds=0.01,
        attempts=1,
    )


def test_empty_main_result_fails_overall_contract() -> None:
    """主表空结果应导致当日整体状态失败。"""

    spec = SourceSpec(MAIN_SOURCE_KEY, "stock_zh_a_spot", "main")
    status, normalized, reason = normalize_source(
        spec, call_result(SUCCESS_EMPTY, pd.DataFrame()), TRADE_DATE, min_main_rows=1
    )

    assert status == SUCCESS_EMPTY
    assert normalized is None
    assert reason is None
    assert (
        build_overall_status([record(MAIN_SOURCE_KEY, "main", status)], "written")
        == OVERALL_FAILED
    )


def test_empty_enhancement_result_is_not_failed() -> None:
    """增强接口空结果不应把主表成功的运行降级为 failed。"""

    spec = SourceSpec(
        "stock_zt_pool_em",
        "stock_zt_pool_em",
        "limit_pool",
        pool_type="limit_up",
    )
    status, normalized, reason = normalize_source(
        spec, call_result(SUCCESS_EMPTY, pd.DataFrame()), TRADE_DATE, min_main_rows=1
    )

    assert status == SUCCESS_EMPTY
    assert normalized is not None
    assert normalized.empty
    assert reason is None
    overall = build_overall_status(
        [
            record(MAIN_SOURCE_KEY, "main", SUCCESS),
            record("stock_zt_pool_em", "limit_pool", status),
        ],
        "written",
    )
    assert overall == OVERALL_PASSED


def test_enhancement_schema_change_makes_partial() -> None:
    """主表成功时增强字段变化应把整体状态标记为 partial。"""

    overall = build_overall_status(
        [
            record(MAIN_SOURCE_KEY, "main", SUCCESS),
            record("stock_lhb_detail_em", "lhb", SCHEMA_CHANGED),
        ],
        "written",
    )

    assert overall == OVERALL_PARTIAL


def test_main_failure_makes_failed() -> None:
    """主表接口失败必须阻断当日成功状态。"""

    overall = build_overall_status(
        [
            record(MAIN_SOURCE_KEY, "main", FAILED),
            record("stock_zt_pool_em", "limit_pool", SUCCESS),
        ],
        "written",
    )

    assert overall == OVERALL_FAILED
