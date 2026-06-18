"""验证每日快照标准化逻辑。"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from scripts.collect_daily_snapshot import (
    LIMIT_EVENT_COLUMNS,
    MAIN_COLUMNS,
    SchemaChangedError,
    SourceSpec,
    normalize_lhb_events,
    normalize_limit_pool_events,
    normalize_main_snapshot,
)


FIXTURE_ROOT = Path(__file__).parent / "fixtures"
TRADE_DATE = date(2026, 6, 18)
FETCHED_AT = "2026-06-18T15:10:00+08:00"


def load_frame(name: str) -> pd.DataFrame:
    """从 fixture JSON 读取 DataFrame，用于本地结构测试。"""

    payload = json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))
    return pd.DataFrame(payload["rows"])


def test_main_snapshot_normalization_success() -> None:
    """主表 fixture 应转换为每日快照标准字段。"""

    result = normalize_main_snapshot(
        load_frame("stock_zh_a_spot_success.json"), TRADE_DATE, FETCHED_AT
    )

    assert list(result.columns) == MAIN_COLUMNS
    assert len(result.index) == 2
    assert result.loc[0, "trade_date"] == "2026-06-18"
    assert result.loc[0, "symbol"] == "000001"
    assert result.loc[0, "source"] == "akshare.stock_zh_a_spot"
    assert result.loc[0, "fetched_at"] == FETCHED_AT


def test_main_snapshot_schema_changed_raises() -> None:
    """主表缺少关键字段时必须暴露 schema 变化。"""

    with pytest.raises(SchemaChangedError, match="missing main snapshot columns"):
        normalize_main_snapshot(
            load_frame("stock_zh_a_spot_schema_changed.json"), TRADE_DATE, FETCHED_AT
        )


def test_limit_pool_normalization_keeps_event_fields() -> None:
    """涨跌停池应保留事件来源、股票代码和 raw payload。"""

    spec = SourceSpec(
        source_key="stock_zt_pool_em",
        function_name="stock_zt_pool_em",
        category="limit_pool",
        pool_type="limit_up",
    )

    result = normalize_limit_pool_events(
        spec, load_frame("limit_pool_success.json"), TRADE_DATE, FETCHED_AT
    )

    assert list(result.columns) == LIMIT_EVENT_COLUMNS
    assert result.loc[0, "pool_type"] == "limit_up"
    assert result.loc[0, "symbol"] == "000001"
    assert result.loc[0, "source"] == "akshare.stock_zt_pool_em"
    assert "平安银行" in result.loc[0, "raw_payload"]


def test_lhb_schema_changed_when_symbol_missing() -> None:
    """龙虎榜增强缺少可关联代码时应标记为字段变化。"""

    spec = SourceSpec(
        source_key="stock_lhb_detail_em",
        function_name="stock_lhb_detail_em",
        category="lhb",
    )

    with pytest.raises(SchemaChangedError, match="missing symbol column"):
        normalize_lhb_events(
            spec, load_frame("lhb_schema_changed.json"), TRADE_DATE, FETCHED_AT
        )
