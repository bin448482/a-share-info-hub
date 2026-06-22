"""采集并标准化每日 A 股快照数据。"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import akshare as ak
import duckdb
import pandas as pd
import requests


AK_DATE_FMT = "%Y%m%d"
REPORT_DATE_FMT = "%Y-%m-%d"
SOURCE_PREFIX = "akshare"
SUCCESS = "success"
SUCCESS_EMPTY = "success_empty"
IGNORED = "ignored"
FAILED = "failed"
SCHEMA_CHANGED = "schema_changed"
OVERALL_PASSED = "passed"
OVERALL_PARTIAL = "partial"
OVERALL_FAILED = "failed"
OVERALL_SKIPPED = "skipped"
DUCKDB_SKIPPED = "skipped"
DUCKDB_WRITTEN = "written"
DUCKDB_FAILED = "failed"
MAIN_SOURCE_KEY = "stock_zh_a_spot"
MAIN_MIN_ROWS = 100
TRADING_CALENDAR_SOURCE = "akshare.tool_trade_date_hist_sina"

MAIN_FIELD_MAP = {
    "symbol": "代码",
    "name": "名称",
    "last_price": "最新价",
    "change_amount": "涨跌额",
    "change_pct": "涨跌幅",
    "bid_price": "买入",
    "ask_price": "卖出",
    "prev_close": "昨收",
    "open": "今开",
    "high": "最高",
    "low": "最低",
    "volume": "成交量",
    "amount": "成交额",
    "snapshot_time": "时间戳",
}

NUMERIC_MAIN_FIELDS = {
    "last_price",
    "change_amount",
    "change_pct",
    "bid_price",
    "ask_price",
    "prev_close",
    "open",
    "high",
    "low",
    "volume",
    "amount",
}

MAIN_COLUMNS = [
    "trade_date",
    "symbol",
    "name",
    "last_price",
    "change_amount",
    "change_pct",
    "bid_price",
    "ask_price",
    "prev_close",
    "open",
    "high",
    "low",
    "volume",
    "amount",
    "snapshot_time",
    "fetched_at",
    "source",
]

SYMBOL_ALIASES = ("代码", "股票代码", "证券代码", "symbol", "code")
NAME_ALIASES = ("名称", "股票简称", "证券简称", "name")
PRICE_ALIASES = ("最新价", "收盘价", "当前价", "价格")
CHANGE_PCT_ALIASES = ("涨跌幅", "涨幅", "涨跌幅(%)")
AMOUNT_ALIASES = ("成交额", "成交金额")
TURNOVER_ALIASES = ("换手率", "换手率%")
BOARD_CODE_ALIASES = ("板块代码", "代码", "board_code")
BOARD_NAME_ALIASES = ("板块名称", "名称", "行业名称", "概念名称", "board_name")

LIMIT_EVENT_COLUMNS = [
    "trade_date",
    "pool_type",
    "symbol",
    "name",
    "last_price",
    "change_pct",
    "amount",
    "turnover_pct",
    "first_limit_time",
    "last_limit_time",
    "open_count",
    "limit_up_stat",
    "streak_count",
    "industry",
    "fetched_at",
    "source",
    "raw_payload",
]

LHB_EVENT_COLUMNS = [
    "trade_date",
    "event_type",
    "symbol",
    "name",
    "reason",
    "fetched_at",
    "source",
    "raw_payload",
]

MARKET_SUMMARY_COLUMNS = [
    "trade_date",
    "market",
    "row_index",
    "fetched_at",
    "source",
    "raw_payload",
]

BOARD_SNAPSHOT_COLUMNS = [
    "trade_date",
    "board_type",
    "board_code",
    "board_name",
    "change_pct",
    "fetched_at",
    "source",
    "raw_payload",
]


class SchemaChangedError(Exception):
    """表示外部接口字段无法映射到当前标准表契约。"""


@dataclass(frozen=True)
class SourceSpec:
    """描述一个每日快照外部接口的调用方式和归属表。"""

    source_key: str
    function_name: str
    category: str
    params: dict[str, Any] = field(default_factory=dict)
    pool_type: str | None = None
    board_type: str | None = None
    market: str | None = None


@dataclass
class CallResult:
    """保存一次外部接口调用的结果、状态和诊断信息。"""

    status: str
    dataframe: pd.DataFrame
    row_count: int
    columns: list[str]
    failure_reason: str | None
    fetched_at: str
    elapsed_seconds: float
    attempts: int


@dataclass
class SourceRecord:
    """记录一个接口从调用到标准化后的最终状态。"""

    source_key: str
    function_name: str
    category: str
    params: dict[str, Any]
    status: str
    row_count: int
    columns: list[str]
    failure_reason: str | None
    fetched_at: str
    raw_path: str | None
    metadata_path: str | None
    elapsed_seconds: float
    attempts: int


@dataclass
class RunOutputs:
    """保存一次每日运行生成的标准化表和状态摘要。"""

    source_records: list[SourceRecord]
    tables: dict[str, pd.DataFrame]
    duckdb_status: str
    duckdb_failure_reason: str | None
    overall_status: str
    output_paths: dict[str, str]


@dataclass(frozen=True)
class TradingDayCheck:
    """记录采集前交易日验证结果和事实来源。"""

    status: str
    is_trading_day: bool
    reason: str
    checked_at: str
    source: str


def parse_args() -> argparse.Namespace:
    """解析每日快照采集脚本的命令行参数。"""

    parser = argparse.ArgumentParser(
        description="Collect and normalize the daily A-share snapshot data package."
    )
    parser.add_argument(
        "--trade-date",
        default=date.today().strftime(REPORT_DATE_FMT),
        help="Trade date for the snapshot package, formatted as YYYY-MM-DD.",
    )
    parser.add_argument(
        "--output-root",
        default=".",
        help="Project root where data, logs, reports, and market.duckdb are written.",
    )
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=12.0,
        help="Default seconds before an AKShare HTTP request times out.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=2,
        help="Maximum attempts for each external interface.",
    )
    parser.add_argument(
        "--retry-sleep",
        type=float,
        default=1.0,
        help="Seconds to wait between failed interface attempts.",
    )
    parser.add_argument(
        "--skip-duckdb",
        action="store_true",
        help="Skip DuckDB writing for diagnosis; the run cannot be marked passed.",
    )
    parser.add_argument(
        "--ignore-proxy",
        action="store_true",
        help="Ignore HTTP proxy environment variables for AKShare requests in this run.",
    )
    parser.add_argument(
        "--min-main-rows",
        type=int,
        default=MAIN_MIN_ROWS,
        help="Minimum accepted main snapshot row count.",
    )
    return parser.parse_args()


def parse_trade_date(value: str) -> date:
    """把命令行交易日期转换为 date，并拒绝不明确格式。"""

    try:
        return datetime.strptime(value, REPORT_DATE_FMT).date()
    except ValueError as exc:
        raise ValueError("trade date must be formatted as YYYY-MM-DD") from exc


def parse_calendar_trade_date(value: Any) -> date | None:
    """把交易日历返回的日期值解析为 date。"""

    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat", "none"}:
        return None
    if text.endswith(".0"):
        text = text[:-2]
    for date_format in (AK_DATE_FMT, REPORT_DATE_FMT, "%Y/%m/%d"):
        try:
            return datetime.strptime(text, date_format).date()
        except ValueError:
            continue
    return None


def check_trading_day(trade_date: date, ak_module: Any) -> TradingDayCheck:
    """验证目标日期是否为 A 股交易日，失败时阻断后续行情采集。"""

    if trade_date.weekday() >= 5:
        return TradingDayCheck(
            status=SUCCESS,
            is_trading_day=False,
            reason="weekend is not an A-share trading day",
            checked_at=current_timestamp(),
            source="weekday",
        )
    try:
        calendar = result_to_dataframe(ak_module.tool_trade_date_hist_sina())
        if "trade_date" not in calendar.columns:
            raise SchemaChangedError("trading calendar missing trade_date column")
        trading_dates = {
            parsed
            for parsed in (
                parse_calendar_trade_date(value)
                for value in calendar["trade_date"].tolist()
            )
            if parsed is not None
        }
        if not trading_dates:
            raise SchemaChangedError("trading calendar has no parseable trade dates")
    except Exception as exc:  # noqa: BLE001 - calendar verification is an external boundary.
        return TradingDayCheck(
            status=FAILED,
            is_trading_day=False,
            reason=f"trading calendar unavailable: {format_exception(exc)}",
            checked_at=current_timestamp(),
            source=TRADING_CALENDAR_SOURCE,
        )
    if trade_date in trading_dates:
        return TradingDayCheck(
            status=SUCCESS,
            is_trading_day=True,
            reason="trade date is listed in AKShare trading calendar",
            checked_at=current_timestamp(),
            source=TRADING_CALENDAR_SOURCE,
        )
    return TradingDayCheck(
        status=SUCCESS,
        is_trading_day=False,
        reason="trade date is not listed in AKShare trading calendar",
        checked_at=current_timestamp(),
        source=TRADING_CALENDAR_SOURCE,
    )


def format_ak_date(day: date) -> str:
    """把 date 转成 AKShare 日期参数使用的 YYYYMMDD。"""

    return day.strftime(AK_DATE_FMT)


def install_default_requests_timeout(timeout: float) -> None:
    """为未显式设置 timeout 的 requests 调用安装默认超时。"""

    original_request = requests.sessions.Session.request

    def request_with_timeout(
        self: requests.Session, method: str, url: str, **kwargs: Any
    ) -> requests.Response:
        """给 AKShare 内部 requests 调用补上默认超时。"""

        kwargs.setdefault("timeout", timeout)
        return original_request(self, method, url, **kwargs)

    requests.sessions.Session.request = request_with_timeout


def configure_requests_proxy(ignore_proxy: bool) -> None:
    """按运行参数决定 requests 是否读取系统代理环境变量。"""

    if not ignore_proxy:
        return
    for name in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        os.environ.pop(name, None)
    original_init = requests.sessions.Session.__init__

    def init_without_proxy_env(self: requests.Session, *args: Any, **kwargs: Any) -> None:
        """创建 requests session 时禁用环境代理读取。"""

        original_init(self, *args, **kwargs)
        self.trust_env = False

    requests.sessions.Session.__init__ = init_without_proxy_env


def build_source_specs(trade_date: date) -> list[SourceSpec]:
    """根据交易日期构造 v1 每日快照固定接口清单。"""

    ak_date = format_ak_date(trade_date)
    return [
        SourceSpec(MAIN_SOURCE_KEY, "stock_zh_a_spot", "main"),
        SourceSpec("stock_zt_pool_em", "stock_zt_pool_em", "limit_pool", {"date": ak_date}, "limit_up"),
        SourceSpec(
            "stock_zt_pool_previous_em",
            "stock_zt_pool_previous_em",
            "limit_pool",
            {"date": ak_date},
            "previous_limit_up",
        ),
        SourceSpec(
            "stock_zt_pool_strong_em",
            "stock_zt_pool_strong_em",
            "limit_pool",
            {"date": ak_date},
            "strong_limit_up",
        ),
        SourceSpec(
            "stock_zt_pool_sub_new_em",
            "stock_zt_pool_sub_new_em",
            "limit_pool",
            {"date": ak_date},
            "sub_new_limit_up",
        ),
        SourceSpec(
            "stock_zt_pool_zbgc_em",
            "stock_zt_pool_zbgc_em",
            "limit_pool",
            {"date": ak_date},
            "broken_board",
        ),
        SourceSpec(
            "stock_zt_pool_dtgc_em",
            "stock_zt_pool_dtgc_em",
            "limit_pool",
            {"date": ak_date},
            "limit_down",
        ),
        SourceSpec(
            "stock_lhb_detail_daily_sina",
            "stock_lhb_detail_daily_sina",
            "lhb",
            {"date": ak_date},
        ),
        SourceSpec(
            "stock_lhb_detail_em",
            "stock_lhb_detail_em",
            "lhb",
            {"start_date": ak_date, "end_date": ak_date},
        ),
        SourceSpec(
            "stock_lhb_jgmmtj_em",
            "stock_lhb_jgmmtj_em",
            "lhb",
            {"start_date": ak_date, "end_date": ak_date},
        ),
        SourceSpec(
            "stock_sse_deal_daily",
            "stock_sse_deal_daily",
            "market_summary",
            {"date": ak_date},
            market="sse",
        ),
        SourceSpec(
            "stock_szse_summary",
            "stock_szse_summary",
            "market_summary",
            {"date": ak_date},
            market="szse",
        ),
        SourceSpec(
            "stock_board_industry_name_em",
            "stock_board_industry_name_em",
            "board_snapshot",
            board_type="industry",
        ),
        SourceSpec(
            "stock_board_concept_name_em",
            "stock_board_concept_name_em",
            "board_snapshot",
            board_type="concept",
        ),
    ]


def call_source(
    spec: SourceSpec,
    ak_module: Any,
    max_retries: int,
    retry_sleep: float,
) -> CallResult:
    """调用一个 AKShare 接口并转换为统一 DataFrame 结果。"""

    started = time.perf_counter()
    attempts = 0
    last_error: str | None = None
    fetched_at = current_timestamp()
    for attempts in range(1, max_retries + 1):
        try:
            fn = getattr(ak_module, spec.function_name)
            raw_result = fn(**spec.params)
            dataframe = result_to_dataframe(raw_result)
            row_count = int(len(dataframe.index))
            status = SUCCESS if row_count > 0 else SUCCESS_EMPTY
            return CallResult(
                status=status,
                dataframe=dataframe,
                row_count=row_count,
                columns=[str(column) for column in dataframe.columns],
                failure_reason=None,
                fetched_at=fetched_at,
                elapsed_seconds=round(time.perf_counter() - started, 3),
                attempts=attempts,
            )
        except Exception as exc:  # noqa: BLE001 - external failures must be reported.
            last_error = format_exception(exc)
            if attempts < max_retries:
                time.sleep(retry_sleep)
    return CallResult(
        status=FAILED,
        dataframe=pd.DataFrame(),
        row_count=0,
        columns=[],
        failure_reason=last_error,
        fetched_at=fetched_at,
        elapsed_seconds=round(time.perf_counter() - started, 3),
        attempts=attempts,
    )


def result_to_dataframe(value: Any) -> pd.DataFrame:
    """把 AKShare 返回值转换为 DataFrame，保留可审计字段。"""

    if isinstance(value, pd.DataFrame):
        return value.copy()
    if isinstance(value, pd.Series):
        return value.to_frame().T
    if isinstance(value, list):
        return pd.DataFrame(value)
    if isinstance(value, dict):
        return pd.DataFrame([value])
    if value is None:
        return pd.DataFrame()
    return pd.DataFrame([{"value": value}])


def normalize_source(
    spec: SourceSpec,
    result: CallResult,
    trade_date: date,
    min_main_rows: int,
) -> tuple[str, pd.DataFrame | None, str | None]:
    """根据接口类别生成标准化表片段和最终状态。"""

    if result.status == FAILED:
        return FAILED, None, result.failure_reason
    if result.status == SUCCESS_EMPTY:
        return SUCCESS_EMPTY, empty_frame_for_category(spec.category), None
    try:
        if spec.category == "main":
            if result.row_count < min_main_rows:
                raise SchemaChangedError(
                    f"main snapshot row count {result.row_count} below minimum {min_main_rows}"
                )
            return SUCCESS, normalize_main_snapshot(result.dataframe, trade_date, result.fetched_at), None
        if spec.category == "limit_pool":
            return SUCCESS, normalize_limit_pool_events(spec, result.dataframe, trade_date, result.fetched_at), None
        if spec.category == "lhb":
            return SUCCESS, normalize_lhb_events(spec, result.dataframe, trade_date, result.fetched_at), None
        if spec.category == "market_summary":
            return SUCCESS, normalize_market_summary(spec, result.dataframe, trade_date, result.fetched_at), None
        if spec.category == "board_snapshot":
            return SUCCESS, normalize_board_snapshot(spec, result.dataframe, trade_date, result.fetched_at), None
        raise SchemaChangedError(f"unknown source category: {spec.category}")
    except SchemaChangedError as exc:
        return SCHEMA_CHANGED, None, str(exc)


def empty_frame_for_category(category: str) -> pd.DataFrame | None:
    """为自然空结果返回对应标准表的空结构。"""

    if category == "limit_pool":
        return pd.DataFrame(columns=LIMIT_EVENT_COLUMNS)
    if category == "lhb":
        return pd.DataFrame(columns=LHB_EVENT_COLUMNS)
    if category == "market_summary":
        return pd.DataFrame(columns=MARKET_SUMMARY_COLUMNS)
    if category == "board_snapshot":
        return pd.DataFrame(columns=BOARD_SNAPSHOT_COLUMNS)
    return None


def normalize_main_snapshot(
    dataframe: pd.DataFrame, trade_date: date, fetched_at: str
) -> pd.DataFrame:
    """把主快照字段转换为 `daily_stock_snapshot` 标准表。"""

    missing = [
        raw_name for raw_name in MAIN_FIELD_MAP.values() if raw_name not in dataframe.columns
    ]
    if missing:
        raise SchemaChangedError(f"missing main snapshot columns: {missing}")
    output = pd.DataFrame(index=dataframe.index)
    output["trade_date"] = trade_date.isoformat()
    for target, source in MAIN_FIELD_MAP.items():
        output[target] = dataframe[source]
    for column in NUMERIC_MAIN_FIELDS:
        output[column] = pd.to_numeric(output[column], errors="coerce")
    output["symbol"] = output["symbol"].astype(str)
    output["name"] = output["name"].astype(str)
    output["fetched_at"] = fetched_at
    output["source"] = f"{SOURCE_PREFIX}.stock_zh_a_spot"
    return output[MAIN_COLUMNS]


def normalize_limit_pool_events(
    spec: SourceSpec, dataframe: pd.DataFrame, trade_date: date, fetched_at: str
) -> pd.DataFrame:
    """把涨跌停和情绪池接口转换为事件增强表。"""

    symbol_column = find_column(dataframe, SYMBOL_ALIASES)
    if symbol_column is None:
        raise SchemaChangedError(f"{spec.source_key} missing symbol column")
    name_column = find_column(dataframe, NAME_ALIASES)
    output = pd.DataFrame(index=dataframe.index)
    output["trade_date"] = trade_date.isoformat()
    output["pool_type"] = spec.pool_type or spec.source_key
    output["symbol"] = dataframe[symbol_column].astype(str)
    output["name"] = column_or_none(dataframe, name_column)
    output["last_price"] = numeric_column(dataframe, find_column(dataframe, PRICE_ALIASES))
    output["change_pct"] = numeric_column(dataframe, find_column(dataframe, CHANGE_PCT_ALIASES))
    output["amount"] = numeric_column(dataframe, find_column(dataframe, AMOUNT_ALIASES))
    output["turnover_pct"] = numeric_column(dataframe, find_column(dataframe, TURNOVER_ALIASES))
    output["first_limit_time"] = column_or_none(dataframe, find_column(dataframe, ("首次封板时间", "首次涨停时间")))
    output["last_limit_time"] = column_or_none(dataframe, find_column(dataframe, ("最后封板时间", "最后涨停时间")))
    output["open_count"] = numeric_column(dataframe, find_column(dataframe, ("炸板次数", "打开次数")))
    output["limit_up_stat"] = column_or_none(dataframe, find_column(dataframe, ("涨停统计", "封板结构")))
    output["streak_count"] = numeric_column(dataframe, find_column(dataframe, ("连板数", "连续涨停")))
    output["industry"] = column_or_none(dataframe, find_column(dataframe, ("所属行业", "行业")))
    output["fetched_at"] = fetched_at
    output["source"] = f"{SOURCE_PREFIX}.{spec.function_name}"
    output["raw_payload"] = rows_to_payload(dataframe)
    return output[LIMIT_EVENT_COLUMNS]


def normalize_lhb_events(
    spec: SourceSpec, dataframe: pd.DataFrame, trade_date: date, fetched_at: str
) -> pd.DataFrame:
    """把龙虎榜接口转换为保留明细原因的事件增强表。"""

    symbol_column = find_column(dataframe, SYMBOL_ALIASES)
    if symbol_column is None:
        raise SchemaChangedError(f"{spec.source_key} missing symbol column")
    name_column = find_column(dataframe, NAME_ALIASES)
    reason_column = find_column(dataframe, ("上榜原因", "解读", "原因", "类型"))
    output = pd.DataFrame(index=dataframe.index)
    output["trade_date"] = trade_date.isoformat()
    output["event_type"] = spec.source_key
    output["symbol"] = dataframe[symbol_column].astype(str)
    output["name"] = column_or_none(dataframe, name_column)
    output["reason"] = column_or_none(dataframe, reason_column)
    output["fetched_at"] = fetched_at
    output["source"] = f"{SOURCE_PREFIX}.{spec.function_name}"
    output["raw_payload"] = rows_to_payload(dataframe)
    return output[LHB_EVENT_COLUMNS]


def normalize_market_summary(
    spec: SourceSpec, dataframe: pd.DataFrame, trade_date: date, fetched_at: str
) -> pd.DataFrame:
    """把交易所市场概况转换为市场级增强表。"""

    output = pd.DataFrame(index=dataframe.index)
    output["trade_date"] = trade_date.isoformat()
    output["market"] = spec.market or spec.source_key
    output["row_index"] = range(len(dataframe.index))
    output["fetched_at"] = fetched_at
    output["source"] = f"{SOURCE_PREFIX}.{spec.function_name}"
    output["raw_payload"] = rows_to_payload(dataframe)
    return output[MARKET_SUMMARY_COLUMNS]


def normalize_board_snapshot(
    spec: SourceSpec, dataframe: pd.DataFrame, trade_date: date, fetched_at: str
) -> pd.DataFrame:
    """把行业和概念板块快照转换为板块增强表。"""

    board_name_column = find_column(dataframe, BOARD_NAME_ALIASES)
    if board_name_column is None:
        raise SchemaChangedError(f"{spec.source_key} missing board name column")
    output = pd.DataFrame(index=dataframe.index)
    output["trade_date"] = trade_date.isoformat()
    output["board_type"] = spec.board_type or spec.source_key
    output["board_code"] = column_or_none(dataframe, find_column(dataframe, BOARD_CODE_ALIASES))
    output["board_name"] = dataframe[board_name_column].astype(str)
    output["change_pct"] = numeric_column(dataframe, find_column(dataframe, CHANGE_PCT_ALIASES))
    output["fetched_at"] = fetched_at
    output["source"] = f"{SOURCE_PREFIX}.{spec.function_name}"
    output["raw_payload"] = rows_to_payload(dataframe)
    return output[BOARD_SNAPSHOT_COLUMNS]


def find_column(dataframe: pd.DataFrame, aliases: tuple[str, ...]) -> str | None:
    """按候选字段名在 DataFrame 中寻找第一个存在的列。"""

    for alias in aliases:
        if alias in dataframe.columns:
            return alias
    return None


def column_or_none(dataframe: pd.DataFrame, column: str | None) -> pd.Series:
    """返回指定列；列不存在时返回等长 None 序列。"""

    if column is None:
        return pd.Series([None] * len(dataframe.index), index=dataframe.index)
    return dataframe[column]


def numeric_column(dataframe: pd.DataFrame, column: str | None) -> pd.Series:
    """返回指定列的数值化结果；列不存在时返回空值序列。"""

    values = column_or_none(dataframe, column)
    return pd.to_numeric(values, errors="coerce")


def rows_to_payload(dataframe: pd.DataFrame) -> list[str]:
    """把每一行原始字段序列化为 JSON 字符串，便于追溯。"""

    records = dataframe.to_dict(orient="records")
    return [json.dumps(to_jsonable(record), ensure_ascii=False, sort_keys=True) for record in records]


def process_source(
    spec: SourceSpec,
    trade_date: date,
    raw_root: Path,
    ak_module: Any,
    max_retries: int,
    retry_sleep: float,
    min_main_rows: int,
) -> tuple[SourceRecord, pd.DataFrame | None]:
    """完成单个接口的调用、标准化状态判定和原始落盘。"""

    call_result = call_source(spec, ak_module, max_retries, retry_sleep)
    final_status, normalized, normalize_failure = normalize_source(
        spec, call_result, trade_date, min_main_rows
    )
    failure_reason = normalize_failure or call_result.failure_reason
    if should_ignore_external_failure(spec, final_status, failure_reason):
        final_status = IGNORED
        normalized = None
    raw_path, metadata_path = write_raw_artifacts(
        raw_root, trade_date, spec, call_result, final_status, failure_reason
    )
    record = SourceRecord(
        source_key=spec.source_key,
        function_name=spec.function_name,
        category=spec.category,
        params=dict(spec.params),
        status=final_status,
        row_count=call_result.row_count,
        columns=call_result.columns,
        failure_reason=failure_reason,
        fetched_at=call_result.fetched_at,
        raw_path=raw_path,
        metadata_path=metadata_path,
        elapsed_seconds=call_result.elapsed_seconds,
        attempts=call_result.attempts,
    )
    return record, normalized


def should_ignore_external_failure(
    spec: SourceSpec, status: str, failure_reason: str | None
) -> bool:
    """识别临时忽略的 Eastmoney push2 代理断连增强接口失败。"""

    if spec.source_key == MAIN_SOURCE_KEY or status != FAILED:
        return False
    if not failure_reason:
        return False
    reason = failure_reason.lower()
    proxy_disconnected = any(
        marker in reason
        for marker in (
            "proxyerror",
            "unable to connect to proxy",
            "remotedisconnected",
        )
    )
    return "push2.eastmoney.com" in reason and proxy_disconnected


def write_raw_artifacts(
    raw_root: Path,
    trade_date: date,
    spec: SourceSpec,
    result: CallResult,
    status: str,
    failure_reason: str | None,
) -> tuple[str | None, str]:
    """保存外部接口原始响应和元数据。"""

    source_dir = raw_root / trade_date.isoformat() / spec.source_key
    source_dir.mkdir(parents=True, exist_ok=True)
    raw_path: str | None = None
    if result.status in {SUCCESS, SUCCESS_EMPTY} or status == SCHEMA_CHANGED:
        response_path = source_dir / "response.json"
        write_json(response_path, dataframe_to_records(result.dataframe))
        raw_path = str(response_path)
    metadata_path = source_dir / "metadata.json"
    write_json(
        metadata_path,
        {
            "source": f"{SOURCE_PREFIX}.{spec.function_name}",
            "function_name": spec.function_name,
            "params": spec.params,
            "fetched_at": result.fetched_at,
            "row_count": result.row_count,
            "columns": result.columns,
            "status": status,
            "failure_reason": failure_reason,
            "raw_path": raw_path,
            "elapsed_seconds": result.elapsed_seconds,
            "attempts": result.attempts,
        },
    )
    return raw_path, str(metadata_path)


def dataframe_to_records(dataframe: pd.DataFrame) -> list[dict[str, Any]]:
    """把 DataFrame 转成 JSON 可写入的记录列表。"""

    return to_jsonable(dataframe.to_dict(orient="records"))


def collect_daily_snapshot(
    trade_date: date,
    output_root: Path,
    ak_module: Any,
    max_retries: int,
    retry_sleep: float,
    skip_duckdb: bool,
    min_main_rows: int,
) -> RunOutputs:
    """执行一次完整每日快照采集、标准化、入库和报告生成。"""

    output_root = output_root.resolve()
    trading_day_check = check_trading_day(trade_date, ak_module)
    if trading_day_check.status == FAILED:
        return build_no_collection_outputs(
            trade_date=trade_date,
            output_root=output_root,
            trading_day_check=trading_day_check,
            overall_status=OVERALL_FAILED,
        )
    if not trading_day_check.is_trading_day:
        return build_no_collection_outputs(
            trade_date=trade_date,
            output_root=output_root,
            trading_day_check=trading_day_check,
            overall_status=OVERALL_SKIPPED,
        )

    raw_root = output_root / "data" / "raw"
    normalized_root = output_root / "data" / "normalized"
    logs_root = output_root / "logs"
    report_root = output_root / "reports" / "daily-runs" / trade_date.isoformat()
    for path in (raw_root, normalized_root, logs_root, report_root):
        path.mkdir(parents=True, exist_ok=True)
    source_records: list[SourceRecord] = []
    normalized_by_table: dict[str, list[pd.DataFrame]] = {
        "daily_stock_snapshot": [],
        "limit_pool_events": [],
        "lhb_events": [],
        "market_summary": [],
        "board_snapshot": [],
    }
    for spec in build_source_specs(trade_date):
        record, normalized = process_source(
            spec,
            trade_date,
            raw_root,
            ak_module,
            max_retries,
            retry_sleep,
            min_main_rows,
        )
        source_records.append(record)
        append_status_log(logs_root / "external-interface-failures.jsonl", record, trade_date)
        table_name = table_name_for_category(spec.category)
        if table_name and normalized is not None:
            normalized_by_table[table_name].append(normalized)
    tables = build_standard_tables(normalized_by_table)
    write_normalized_tables(normalized_root, tables)
    duckdb_status, duckdb_failure = write_duckdb_tables(
        output_root / "market.duckdb", tables, trade_date, skip_duckdb
    )
    overall_status = build_overall_status(source_records, duckdb_status)
    interface_status_path = report_root / "interface-status.json"
    summary_path = report_root / "daily-data-summary.md"
    write_interface_status(
        interface_status_path,
        trade_date,
        source_records,
        tables,
        duckdb_status,
        duckdb_failure,
        overall_status,
        trading_day_check,
    )
    write_daily_summary(
        summary_path,
        trade_date,
        source_records,
        tables,
        duckdb_status,
        duckdb_failure,
        overall_status,
        trading_day_check,
    )
    output_paths = {
        "raw_root": str(raw_root / trade_date.isoformat()),
        "normalized_root": str(normalized_root),
        "failure_log": str(logs_root / "external-interface-failures.jsonl"),
        "interface_status": str(interface_status_path),
        "daily_summary": str(summary_path),
        "duckdb": str(output_root / "market.duckdb"),
    }
    return RunOutputs(
        source_records=source_records,
        tables=tables,
        duckdb_status=duckdb_status,
        duckdb_failure_reason=duckdb_failure,
        overall_status=overall_status,
        output_paths=output_paths,
    )


def build_no_collection_outputs(
    trade_date: date,
    output_root: Path,
    trading_day_check: TradingDayCheck,
    overall_status: str,
) -> RunOutputs:
    """为非交易日或交易日历失败生成状态报告，不调用行情接口。"""

    report_root = output_root / "reports" / "daily-runs" / trade_date.isoformat()
    tables = build_empty_standard_tables()
    interface_status_path = report_root / "interface-status.json"
    summary_path = report_root / "daily-data-summary.md"
    write_interface_status(
        interface_status_path,
        trade_date,
        [],
        tables,
        DUCKDB_SKIPPED,
        None,
        overall_status,
        trading_day_check,
    )
    write_daily_summary(
        summary_path,
        trade_date,
        [],
        tables,
        DUCKDB_SKIPPED,
        None,
        overall_status,
        trading_day_check,
    )
    return RunOutputs(
        source_records=[],
        tables=tables,
        duckdb_status=DUCKDB_SKIPPED,
        duckdb_failure_reason=None,
        overall_status=overall_status,
        output_paths={
            "interface_status": str(interface_status_path),
            "daily_summary": str(summary_path),
        },
    )


def table_name_for_category(category: str) -> str | None:
    """返回接口类别对应的标准化表名。"""

    return {
        "main": "daily_stock_snapshot",
        "limit_pool": "limit_pool_events",
        "lhb": "lhb_events",
        "market_summary": "market_summary",
        "board_snapshot": "board_snapshot",
    }.get(category)


def build_standard_tables(
    normalized_by_table: dict[str, list[pd.DataFrame]]
) -> dict[str, pd.DataFrame]:
    """合并各接口片段，生成每日标准化表集合。"""

    return {
        "daily_stock_snapshot": concat_or_empty(
            normalized_by_table["daily_stock_snapshot"], MAIN_COLUMNS
        ),
        "limit_pool_events": concat_or_empty(
            normalized_by_table["limit_pool_events"], LIMIT_EVENT_COLUMNS
        ),
        "lhb_events": concat_or_empty(normalized_by_table["lhb_events"], LHB_EVENT_COLUMNS),
        "market_summary": concat_or_empty(
            normalized_by_table["market_summary"], MARKET_SUMMARY_COLUMNS
        ),
        "board_snapshot": concat_or_empty(
            normalized_by_table["board_snapshot"], BOARD_SNAPSHOT_COLUMNS
        ),
    }


def build_empty_standard_tables() -> dict[str, pd.DataFrame]:
    """生成不含数据但保留 schema 的标准化表集合。"""

    return build_standard_tables(
        {
            "daily_stock_snapshot": [],
            "limit_pool_events": [],
            "lhb_events": [],
            "market_summary": [],
            "board_snapshot": [],
        }
    )


def concat_or_empty(frames: list[pd.DataFrame], columns: list[str]) -> pd.DataFrame:
    """合并表片段；没有片段时保留空表结构。"""

    if not frames:
        return pd.DataFrame(columns=columns)
    return pd.concat(frames, ignore_index=True)


def write_normalized_tables(normalized_root: Path, tables: dict[str, pd.DataFrame]) -> None:
    """把标准化表写入 Parquet 文件。"""

    normalized_root.mkdir(parents=True, exist_ok=True)
    for table_name, dataframe in tables.items():
        dataframe.to_parquet(normalized_root / f"{table_name}.parquet", index=False)


def write_duckdb_tables(
    database_path: Path,
    tables: dict[str, pd.DataFrame],
    trade_date: date,
    skip_duckdb: bool,
) -> tuple[str, str | None]:
    """把标准化表写入本地 DuckDB，并按交易日期替换旧记录。"""

    if skip_duckdb:
        return DUCKDB_SKIPPED, None
    try:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        with duckdb.connect(str(database_path)) as connection:
            for table_name, dataframe in tables.items():
                incoming_name = f"incoming_{table_name}"
                connection.register(incoming_name, dataframe)
                existing_rows = pd.DataFrame()
                if duckdb_table_exists(connection, table_name):
                    existing_rows = connection.execute(
                        f"SELECT * FROM {table_name} WHERE trade_date <> ?",
                        [trade_date.isoformat()],
                    ).fetchdf()
                combined = pd.concat([existing_rows, dataframe], ignore_index=True)
                combined_name = f"combined_{table_name}"
                connection.register(combined_name, combined)
                connection.execute(
                    f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM {combined_name}"
                )
                connection.unregister(incoming_name)
                connection.unregister(combined_name)
        return DUCKDB_WRITTEN, None
    except Exception as exc:  # noqa: BLE001 - storage failures must be reported.
        return DUCKDB_FAILED, format_exception(exc)


def duckdb_table_exists(connection: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    """检查 DuckDB 中是否已有指定标准化表。"""

    rows = connection.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
        [table_name],
    ).fetchone()
    return bool(rows and rows[0] > 0)


def build_overall_status(source_records: list[SourceRecord], duckdb_status: str) -> str:
    """根据主表、增强表和 DuckDB 状态计算当日整体状态。"""

    main_record = next(
        (record for record in source_records if record.source_key == MAIN_SOURCE_KEY), None
    )
    if main_record is None or main_record.status != SUCCESS:
        return OVERALL_FAILED
    if duckdb_status == DUCKDB_FAILED:
        return OVERALL_FAILED
    enhanced_problem = any(
        record.source_key != MAIN_SOURCE_KEY and record.status in {FAILED, SCHEMA_CHANGED}
        for record in source_records
    )
    if enhanced_problem or duckdb_status == DUCKDB_SKIPPED:
        return OVERALL_PARTIAL
    return OVERALL_PASSED


def append_status_log(log_path: Path, record: SourceRecord, trade_date: date) -> None:
    """把失败、空结果和字段变化追加到外部接口状态 JSONL。"""

    if record.status in {SUCCESS, IGNORED}:
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                to_jsonable(
                    {
                        "logged_at": current_timestamp(),
                        "trade_date": trade_date.isoformat(),
                        "source": f"{SOURCE_PREFIX}.{record.function_name}",
                        "function_name": record.function_name,
                        "params": record.params,
                        "failure_type": record.status,
                        "failure_reason": record.failure_reason,
                        "fallback_used": False,
                        "raw_path": record.raw_path,
                    }
                ),
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n"
        )


def write_interface_status(
    path: Path,
    trade_date: date,
    source_records: list[SourceRecord],
    tables: dict[str, pd.DataFrame],
    duckdb_status: str,
    duckdb_failure: str | None,
    overall_status: str,
    trading_day_check: TradingDayCheck | None = None,
) -> None:
    """写入机器可读的每日接口状态报告。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "trade_date": trade_date.isoformat(),
        "generated_at": current_timestamp(),
        "overall_status": overall_status,
        "duckdb_status": duckdb_status,
        "duckdb_failure_reason": duckdb_failure,
        "table_row_counts": {
            table_name: int(len(dataframe.index))
            for table_name, dataframe in tables.items()
        },
        "sources": [asdict(record) for record in source_records],
    }
    if trading_day_check is not None:
        payload["trading_day_check"] = asdict(trading_day_check)
    write_json(path, payload)


def write_daily_summary(
    path: Path,
    trade_date: date,
    source_records: list[SourceRecord],
    tables: dict[str, pd.DataFrame],
    duckdb_status: str,
    duckdb_failure: str | None,
    overall_status: str,
    trading_day_check: TradingDayCheck | None = None,
) -> None:
    """写入面向 review 的每日数据摘要报告。"""

    main_record = next(
        (record for record in source_records if record.source_key == MAIN_SOURCE_KEY), None
    )
    lines = [
        "# 每日 A 股快照数据摘要",
        "",
        f"- 交易日期：`{trade_date.isoformat()}`",
        f"- 生成时间：`{current_timestamp()}`",
        f"- 当日整体状态：`{overall_status}`",
        f"- DuckDB 状态：`{duckdb_status}`",
    ]
    if trading_day_check is not None:
        lines.extend(
            [
                f"- 交易日检查状态：`{trading_day_check.status}`",
                f"- 是否交易日：`{trading_day_check.is_trading_day}`",
                f"- 交易日检查来源：`{trading_day_check.source}`",
                f"- 交易日检查说明：`{trading_day_check.reason}`",
            ]
        )
    if duckdb_failure:
        lines.append(f"- DuckDB 失败原因：`{duckdb_failure}`")
    if trading_day_check is not None and overall_status == OVERALL_SKIPPED:
        lines.extend(
            [
                "",
                "## 采集跳过",
                "",
                "- 目标日期不是 A 股交易日，本运行未调用行情接口。",
                "- 本运行不写入原始行情、标准化表或 DuckDB。",
                "",
                "## 边界",
                "",
                "- 本运行不生成预测。",
                "- 本运行不生成交易建议。",
                "- 非交易日跳过不代表接口失败。",
                "",
            ]
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines), encoding="utf-8")
        return
    if trading_day_check is not None and trading_day_check.status == FAILED:
        lines.extend(
            [
                "",
                "## 采集阻断",
                "",
                "- 交易日历验证失败，本运行未调用行情接口。",
                "- 需要先恢复交易日历验证，再执行行情采集。",
                "",
                "## 边界",
                "",
                "- 本运行不生成预测。",
                "- 本运行不生成交易建议。",
                "- 未确认交易日时不能把行情接口结果当作有效每日数据包。",
                "",
            ]
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines), encoding="utf-8")
        return
    lines.extend(
        [
            "",
            "## 主表状态",
            "",
            f"- 主表接口：`{MAIN_SOURCE_KEY}`",
            f"- 主表状态：`{main_record.status if main_record else 'missing'}`",
            f"- 主表原始行数：`{main_record.row_count if main_record else 0}`",
            f"- 标准化主表行数：`{len(tables['daily_stock_snapshot'].index)}`",
            "",
            "## 增强接口状态",
            "",
            "| 来源 | 类别 | 状态 | 原始行数 | 失败或说明 |",
            "| --- | --- | --- | ---: | --- |",
        ]
    )
    for record in source_records:
        if record.source_key == MAIN_SOURCE_KEY:
            continue
        reason = record.failure_reason or ""
        lines.append(
            f"| `{record.source_key}` | `{record.category}` | `{record.status}` | "
            f"{record.row_count} | {reason} |"
        )
    lines.extend(
        [
            "",
            "## 标准化表行数",
            "",
            "| 表 | 行数 |",
            "| --- | ---: |",
        ]
    )
    for table_name, dataframe in tables.items():
        lines.append(f"| `{table_name}` | {len(dataframe.index)} |")
    lines.extend(
        [
            "",
            "## 边界",
            "",
            "- 本运行不生成预测。",
            "- 本运行不生成交易建议。",
            "- 快照型主表只表达获取时点，不承诺历史回放。",
            "- 事件型增强数据不会补齐成全股票字段。",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    """以稳定 UTF-8 JSON 格式写入可复查文件。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(to_jsonable(data), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def to_jsonable(value: Any) -> Any:
    """把 pandas、datetime、NaN 和标量转换为 JSON 安全值。"""

    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if not isinstance(value, (dict, list, tuple)):
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
    if hasattr(value, "item"):
        try:
            return to_jsonable(value.item())
        except Exception:  # noqa: BLE001 - best-effort scalar conversion.
            pass
    return value


def format_exception(exc: Exception) -> str:
    """把异常转换为适合写入报告的简短说明。"""

    message = str(exc).replace("\n", " ").strip()
    if len(message) > 700:
        message = message[:700] + "..."
    return f"{type(exc).__name__}: {message}"


def current_timestamp() -> str:
    """返回带本地时区信息的 ISO 时间戳。"""

    return datetime.now(timezone.utc).astimezone().isoformat()


def main() -> int:
    """运行兼容脚本入口；日常调用优先使用顶层 CLI。"""

    args = parse_args()
    trade_date = parse_trade_date(args.trade_date)
    install_default_requests_timeout(args.request_timeout)
    configure_requests_proxy(args.ignore_proxy)
    outputs = collect_daily_snapshot(
        trade_date=trade_date,
        output_root=Path(args.output_root),
        ak_module=ak,
        max_retries=args.max_retries,
        retry_sleep=args.retry_sleep,
        skip_duckdb=args.skip_duckdb,
        min_main_rows=args.min_main_rows,
    )
    print(f"Daily snapshot status: {outputs.overall_status}")
    for name, path in outputs.output_paths.items():
        print(f"{name}: {path}")
    return 0 if outputs.overall_status in {OVERALL_PASSED, OVERALL_PARTIAL, OVERALL_SKIPPED} else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise
    except Exception:  # noqa: BLE001 - top-level failure should preserve traceback.
        traceback.print_exc()
        raise SystemExit(1)
