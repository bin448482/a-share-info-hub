"""Probe AKShare interfaces and generate a verifiable daily data contract report."""

from __future__ import annotations

import argparse
import inspect
import json
import math
import time
import traceback
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import akshare as ak
import pandas as pd
import requests


DATE_FMT = "%Y%m%d"
REPORT_DATE_FMT = "%Y-%m-%d"
CONTRACT_VERSION = "daily_data_contract.v1"


@dataclass(frozen=True)
class InterfaceSpec:
    """Describe one deterministic AKShare probe target."""

    interface_id: str
    function_name: str
    description: str
    category: str
    today_params: dict[str, Any]
    history_mode: str
    history_params: dict[str, Any]
    data_frequency_hint: str
    historical_contract_candidate: bool
    exclusion_note: str | None = None


@dataclass
class CallResult:
    """Capture one AKShare call result and its validation metadata."""

    call_status: str
    row_count: int
    columns: list[str]
    sample_rows: list[dict[str, Any]]
    failure_reason: str | None
    elapsed_seconds: float


def parse_args() -> argparse.Namespace:
    """Parse command-line options for the contract probe run."""

    parser = argparse.ArgumentParser(
        description="Generate AKShare daily data contract probe reports."
    )
    parser.add_argument(
        "--probe-date",
        default=date.today().strftime(DATE_FMT),
        help="Baseline date for today's capability probe, formatted as YYYYMMDD.",
    )
    parser.add_argument(
        "--history-start-date",
        default="19900101",
        help="Earliest date to consider during history floor probing.",
    )
    parser.add_argument(
        "--output-dir",
        default="reports",
        help="Directory where JSON and Markdown reports will be written.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=2,
        help="Maximum call attempts for each AKShare interface.",
    )
    parser.add_argument(
        "--retry-sleep",
        type=float,
        default=1.0,
        help="Seconds to wait between failed call attempts.",
    )
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=12.0,
        help="Default seconds before an AKShare requests call times out.",
    )
    parser.add_argument(
        "--max-history-boundary-probes",
        type=int,
        default=80,
        help="Maximum coarse boundary calls for each history-probed interface.",
    )
    return parser.parse_args()


def install_default_requests_timeout(timeout: float) -> None:
    """Install a default timeout for AKShare requests calls that omit one."""

    original_request = requests.sessions.Session.request

    def request_with_timeout(self: requests.Session, method: str, url: str, **kwargs: Any) -> requests.Response:
        """Apply the configured timeout to requests calls without an explicit timeout."""

        kwargs.setdefault("timeout", timeout)
        return original_request(self, method, url, **kwargs)

    requests.sessions.Session.request = request_with_timeout


def build_candidate_interfaces(probe_date: str) -> list[InterfaceSpec]:
    """Build the deterministic A-share AKShare candidate interface list."""

    return [
        InterfaceSpec(
            "stock_zh_a_spot_em",
            "stock_zh_a_spot_em",
            "A-share realtime spot quote table.",
            "market_snapshot",
            {},
            "latest_snapshot",
            {},
            "latest_snapshot",
            False,
            "No date parameter; cannot prove arbitrary historical daily access.",
        ),
        InterfaceSpec(
            "stock_zh_a_spot_sina",
            "stock_zh_a_spot",
            "A-share realtime spot quote table from Sina.",
            "market_snapshot",
            {},
            "latest_snapshot",
            {},
            "latest_snapshot",
            False,
            "No date parameter; cannot prove arbitrary historical daily access.",
        ),
        InterfaceSpec(
            "stock_zh_a_hist_000001_daily",
            "stock_zh_a_hist",
            "Daily historical bar for sample A-share symbol 000001.",
            "daily_bar",
            {
                "symbol": "000001",
                "period": "daily",
                "start_date": probe_date,
                "end_date": probe_date,
                "adjust": "",
                "timeout": 10,
            },
            "full_range",
            {
                "symbol": "000001",
                "period": "daily",
                "start_date_param": "start_date",
                "end_date_param": "end_date",
                "adjust": "",
                "timeout": 10,
            },
            "daily_range",
            True,
            None,
        ),
        InterfaceSpec(
            "stock_zh_index_spot_em_important",
            "stock_zh_index_spot_em",
            "Important mainland index spot quote table.",
            "market_snapshot",
            {"symbol": "沪深重要指数"},
            "latest_snapshot",
            {},
            "latest_snapshot",
            False,
            "No date parameter; cannot prove arbitrary historical daily access.",
        ),
        InterfaceSpec(
            "stock_zh_index_daily_em_sh000001",
            "stock_zh_index_daily_em",
            "Shanghai Composite daily historical index bars.",
            "daily_bar",
            {"symbol": "sh000001", "start_date": probe_date, "end_date": probe_date},
            "full_range",
            {
                "symbol": "sh000001",
                "start_date_param": "start_date",
                "end_date_param": "end_date",
            },
            "daily_range",
            True,
            None,
        ),
        InterfaceSpec(
            "stock_zt_pool_em",
            "stock_zt_pool_em",
            "Daily limit-up pool.",
            "limit_pool",
            {"date": probe_date},
            "date_param",
            {"date_param": "date"},
            "daily_range",
            False,
            "Pool data can be naturally empty and is not a required daily contract field.",
        ),
        InterfaceSpec(
            "stock_zt_pool_previous_em",
            "stock_zt_pool_previous_em",
            "Previous limit-up pool.",
            "limit_pool",
            {"date": probe_date},
            "date_param",
            {"date_param": "date"},
            "daily_range",
            False,
            "Pool data can be naturally empty and is not a required daily contract field.",
        ),
        InterfaceSpec(
            "stock_zt_pool_strong_em",
            "stock_zt_pool_strong_em",
            "Strong limit-up pool.",
            "limit_pool",
            {"date": probe_date},
            "date_param",
            {"date_param": "date"},
            "daily_range",
            False,
            "Pool data can be naturally empty and is not a required daily contract field.",
        ),
        InterfaceSpec(
            "stock_zt_pool_sub_new_em",
            "stock_zt_pool_sub_new_em",
            "Sub-new stock limit-up pool.",
            "limit_pool",
            {"date": probe_date},
            "date_param",
            {"date_param": "date"},
            "daily_range",
            False,
            "Pool data can be naturally empty and is not a required daily contract field.",
        ),
        InterfaceSpec(
            "stock_zt_pool_zbgc_em",
            "stock_zt_pool_zbgc_em",
            "Limit-up broken-board pool.",
            "limit_pool",
            {"date": probe_date},
            "date_param",
            {"date_param": "date"},
            "daily_range",
            False,
            "Pool data can be naturally empty and is not a required daily contract field.",
        ),
        InterfaceSpec(
            "stock_zt_pool_dtgc_em",
            "stock_zt_pool_dtgc_em",
            "Limit-down pool.",
            "limit_pool",
            {"date": probe_date},
            "date_param",
            {"date_param": "date"},
            "daily_range",
            False,
            "Pool data can be naturally empty and is not a required daily contract field.",
        ),
        InterfaceSpec(
            "stock_lhb_detail_em",
            "stock_lhb_detail_em",
            "Dragon Tiger List details for a date window.",
            "event_window",
            {"start_date": probe_date, "end_date": probe_date},
            "range_param",
            {"start_param": "start_date", "end_param": "end_date"},
            "event_window",
            False,
            "Event data is not expected to be non-empty every trading day.",
        ),
        InterfaceSpec(
            "stock_lhb_jgmmtj_em",
            "stock_lhb_jgmmtj_em",
            "Institutional Dragon Tiger List buy/sell statistics.",
            "event_window",
            {"start_date": probe_date, "end_date": probe_date},
            "range_param",
            {"start_param": "start_date", "end_param": "end_date"},
            "event_window",
            False,
            "Event data is not expected to be non-empty every trading day.",
        ),
        InterfaceSpec(
            "stock_lhb_stock_statistic_em_month",
            "stock_lhb_stock_statistic_em",
            "Dragon Tiger List stock statistics for the latest month.",
            "event_window",
            {"symbol": "近一月"},
            "latest_snapshot",
            {},
            "latest_snapshot",
            False,
            "Relative-window endpoint; not an arbitrary historical daily source.",
        ),
        InterfaceSpec(
            "stock_individual_fund_flow_rank_today",
            "stock_individual_fund_flow_rank",
            "Individual stock capital-flow ranking for today.",
            "fund_flow",
            {"indicator": "今日"},
            "latest_snapshot",
            {},
            "latest_snapshot",
            False,
            "Indicator is a current short-window ranking, not arbitrary historical daily data.",
        ),
        InterfaceSpec(
            "stock_sector_fund_flow_rank_industry_today",
            "stock_sector_fund_flow_rank",
            "Industry capital-flow ranking for today.",
            "fund_flow",
            {"indicator": "今日", "sector_type": "行业资金流"},
            "latest_snapshot",
            {},
            "latest_snapshot",
            False,
            "Indicator is a current short-window ranking, not arbitrary historical daily data.",
        ),
        InterfaceSpec(
            "stock_sector_fund_flow_rank_concept_today",
            "stock_sector_fund_flow_rank",
            "Concept capital-flow ranking for today.",
            "fund_flow",
            {"indicator": "今日", "sector_type": "概念资金流"},
            "latest_snapshot",
            {},
            "latest_snapshot",
            False,
            "Indicator is a current short-window ranking, not arbitrary historical daily data.",
        ),
        InterfaceSpec(
            "stock_individual_fund_flow_600094",
            "stock_individual_fund_flow",
            "Individual stock capital-flow history for sample symbol 600094.",
            "fund_flow",
            {"stock": "600094", "market": "sh"},
            "embedded_history",
            {},
            "embedded_history",
            False,
            "No date-range parameters; earliest date can be observed but not requested directly.",
        ),
        InterfaceSpec(
            "stock_concept_fund_flow_hist_data_element",
            "stock_concept_fund_flow_hist",
            "Concept capital-flow history for sample concept 数据要素.",
            "fund_flow",
            {"symbol": "数据要素"},
            "embedded_history",
            {},
            "embedded_history",
            False,
            "No date-range parameters; earliest date can be observed but not requested directly.",
        ),
        InterfaceSpec(
            "stock_board_industry_name_em",
            "stock_board_industry_name_em",
            "Industry board list and spot metrics.",
            "board_snapshot",
            {},
            "latest_snapshot",
            {},
            "latest_snapshot",
            False,
            "No date parameter; cannot prove arbitrary historical daily access.",
        ),
        InterfaceSpec(
            "stock_board_concept_name_em",
            "stock_board_concept_name_em",
            "Concept board list and spot metrics.",
            "board_snapshot",
            {},
            "latest_snapshot",
            {},
            "latest_snapshot",
            False,
            "No date parameter; cannot prove arbitrary historical daily access.",
        ),
        InterfaceSpec(
            "stock_sse_summary",
            "stock_sse_summary",
            "Shanghai Stock Exchange market summary.",
            "exchange_summary",
            {},
            "latest_snapshot",
            {},
            "latest_snapshot",
            False,
            "No date parameter; cannot prove arbitrary historical daily access.",
        ),
        InterfaceSpec(
            "stock_szse_summary",
            "stock_szse_summary",
            "Shenzhen Stock Exchange market summary by date.",
            "exchange_summary",
            {"date": probe_date},
            "date_param",
            {"date_param": "date"},
            "daily_range",
            True,
            None,
        ),
        InterfaceSpec(
            "stock_info_a_code_name",
            "stock_info_a_code_name",
            "A-share code and name table.",
            "reference_snapshot",
            {},
            "latest_snapshot",
            {},
            "latest_snapshot",
            False,
            "Reference snapshot; not historical daily market data.",
        ),
        InterfaceSpec(
            "stock_zh_a_new",
            "stock_zh_a_new",
            "New A-share listing table.",
            "reference_snapshot",
            {},
            "latest_snapshot",
            {},
            "latest_snapshot",
            False,
            "Reference snapshot; not historical daily market data.",
        ),
        InterfaceSpec(
            "stock_xgsr_ths",
            "stock_xgsr_ths",
            "New-share subscription calendar.",
            "event_calendar",
            {},
            "latest_snapshot",
            {},
            "latest_snapshot",
            False,
            "Calendar snapshot; not arbitrary historical daily data.",
        ),
    ]


def call_interface(
    spec: InterfaceSpec,
    params: dict[str, Any],
    max_retries: int,
    retry_sleep: float,
) -> CallResult:
    """Call one AKShare interface and normalize its result metadata."""

    started = time.perf_counter()
    last_error: str | None = None
    for attempt in range(1, max_retries + 1):
        try:
            fn = getattr(ak, spec.function_name)
            result = fn(**params)
            rows, columns, sample_rows = normalize_result(result)
            return CallResult(
                call_status="success",
                row_count=rows,
                columns=columns,
                sample_rows=sample_rows,
                failure_reason=None,
                elapsed_seconds=round(time.perf_counter() - started, 3),
            )
        except Exception as exc:  # noqa: BLE001 - report needs exact external failures.
            last_error = format_exception(exc)
            if attempt < max_retries:
                time.sleep(retry_sleep)
    return CallResult(
        call_status="failed",
        row_count=0,
        columns=[],
        sample_rows=[],
        failure_reason=last_error,
        elapsed_seconds=round(time.perf_counter() - started, 3),
    )


def normalize_result(result: Any) -> tuple[int, list[str], list[dict[str, Any]]]:
    """Convert an AKShare result into row count, columns, and sample rows."""

    if isinstance(result, pd.DataFrame):
        row_count = int(len(result.index))
        columns = [str(column) for column in result.columns]
        sample_rows = to_jsonable(result.head(3).to_dict(orient="records"))
        return row_count, columns, sample_rows
    if isinstance(result, pd.Series):
        data = result.to_frame().T
        return int(len(data.index)), [str(column) for column in data.columns], to_jsonable(
            data.head(3).to_dict(orient="records")
        )
    if isinstance(result, list):
        rows = len(result)
        columns = sorted({key for item in result if isinstance(item, dict) for key in item})
        sample_rows = to_jsonable(result[:3])
        return rows, [str(column) for column in columns], sample_rows
    if isinstance(result, dict):
        return 1, [str(key) for key in result.keys()], [to_jsonable(result)]
    if result is None:
        return 0, [], []
    return 1, ["value"], [{"value": to_jsonable(result)}]


def to_jsonable(value: Any) -> Any:
    """Convert pandas, numpy, datetime, and scalar values into JSON-safe values."""

    if isinstance(value, dict):
        return {str(key): to_jsonable(val) for key, val in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if pd.isna(value) if not isinstance(value, (list, dict, tuple)) else False:
        return None
    if hasattr(value, "item"):
        try:
            return to_jsonable(value.item())
        except Exception:  # noqa: BLE001 - best-effort JSON conversion.
            pass
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def format_exception(exc: Exception) -> str:
    """Return a compact external-call failure reason."""

    exc_type = type(exc).__name__
    message = str(exc).replace("\n", " ").strip()
    if len(message) > 700:
        message = message[:700] + "..."
    return f"{exc_type}: {message}"


def build_today_capability(
    specs: list[InterfaceSpec],
    max_retries: int,
    retry_sleep: float,
) -> list[dict[str, Any]]:
    """Run today's capability probe for every candidate interface."""

    rows: list[dict[str, Any]] = []
    for spec in specs:
        result = call_interface(spec, spec.today_params, max_retries, retry_sleep)
        contract_candidate = (
            result.call_status == "success"
            and result.row_count > 0
            and len(result.columns) > 0
        )
        rows.append(
            {
                **asdict(spec),
                **asdict(result),
                "contract_candidate": contract_candidate,
                "today_exclusion_reason": today_exclusion_reason(spec, result),
                "signature": function_signature(spec.function_name),
            }
        )
    return rows


def today_exclusion_reason(spec: InterfaceSpec, result: CallResult) -> str | None:
    """Explain why an interface is not a today's non-empty contract candidate."""

    if result.call_status != "success":
        return "call_failed"
    if result.row_count <= 0:
        return "empty_result"
    if not result.columns:
        return "no_parseable_columns"
    if spec.exclusion_note:
        return spec.exclusion_note
    return None


def function_signature(function_name: str) -> str:
    """Return the installed AKShare function signature when available."""

    try:
        return str(inspect.signature(getattr(ak, function_name)))
    except Exception as exc:  # noqa: BLE001 - signature is diagnostic metadata.
        return f"unavailable: {format_exception(exc)}"


def build_trade_dates(start_date: str, end_date: str) -> list[str]:
    """Load the trading calendar and return YYYYMMDD dates within the probe range."""

    try:
        calendar = ak.tool_trade_date_hist_sina()
        if "trade_date" not in calendar.columns:
            raise ValueError("tool_trade_date_hist_sina result lacks trade_date column")
        values = []
        start = datetime.strptime(start_date, DATE_FMT).date()
        end = datetime.strptime(end_date, DATE_FMT).date()
        for item in calendar["trade_date"].tolist():
            parsed = parse_any_date(item)
            if parsed and start <= parsed <= end:
                values.append(parsed.strftime(DATE_FMT))
        return sorted(set(values))
    except Exception:
        return fallback_weekday_dates(start_date, end_date)


def parse_any_date(value: Any) -> date | None:
    """Parse AKShare date-like values into a date object."""

    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in (DATE_FMT, REPORT_DATE_FMT, "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def fallback_weekday_dates(start_date: str, end_date: str) -> list[str]:
    """Build a weekday-only date list when AKShare's trading calendar is unavailable."""

    start = datetime.strptime(start_date, DATE_FMT).date()
    end = datetime.strptime(end_date, DATE_FMT).date()
    values = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            values.append(current.strftime(DATE_FMT))
        current += timedelta(days=1)
    return values


def probe_history_floors(
    specs: list[InterfaceSpec],
    today_rows: list[dict[str, Any]],
    trade_dates: list[str],
    probe_date: str,
    history_start_date: str,
    max_retries: int,
    retry_sleep: float,
    max_boundary_probes: int,
) -> list[dict[str, Any]]:
    """Probe the earliest available date for every today-successful candidate."""

    today_by_id = {row["interface_id"]: row for row in today_rows}
    history_rows: list[dict[str, Any]] = []
    for spec in specs:
        today = today_by_id[spec.interface_id]
        if not today["contract_candidate"]:
            history_rows.append(
                history_not_probed(spec, today, "not_today_contract_candidate")
            )
            continue
        if not spec.historical_contract_candidate:
            history_rows.append(
                history_not_probed(spec, today, "not_historical_daily_contract_candidate")
            )
            continue
        if spec.history_mode == "latest_snapshot":
            history_rows.append(
                history_not_probed(spec, today, "latest_snapshot_no_history_parameter")
            )
            continue
        if spec.history_mode == "embedded_history":
            history_rows.append(probe_embedded_history(spec, today))
            continue
        if spec.history_mode == "full_range":
            history_rows.append(
                probe_full_range_history(
                    spec,
                    today,
                    probe_date,
                    history_start_date,
                    max_retries,
                    retry_sleep,
                )
            )
            continue
        if spec.history_mode == "date_param":
            history_rows.append(
                probe_date_param_history(
                    spec, today, trade_dates, max_retries, retry_sleep, max_boundary_probes
                )
            )
            continue
        if spec.history_mode == "range_param":
            history_rows.append(
                probe_range_param_history(
                    spec, today, trade_dates, max_retries, retry_sleep, max_boundary_probes
                )
            )
            continue
        history_rows.append(history_not_probed(spec, today, "unsupported_history_mode"))
    return history_rows


def history_not_probed(
    spec: InterfaceSpec, today: dict[str, Any], reason: str
) -> dict[str, Any]:
    """Build a history row for interfaces that cannot proceed to history probing."""

    return {
        "interface_id": spec.interface_id,
        "function_name": spec.function_name,
        "history_status": "not_probed",
        "history_mode": spec.history_mode,
        "data_frequency": spec.data_frequency_hint,
        "first_available_trade_date": None,
        "last_failed_before_first": None,
        "field_stability_status": "not_checked",
        "included_in_historical_daily_contract": False,
        "history_exclusion_reason": spec.exclusion_note or reason,
        "probe_evidence": [],
        "today_columns": today.get("columns", []),
        "history_columns": [],
    }


def probe_embedded_history(spec: InterfaceSpec, today: dict[str, Any]) -> dict[str, Any]:
    """Infer an observed earliest date from a current call result with embedded history."""

    sample_rows = today.get("sample_rows", [])
    observed_dates = []
    for row in sample_rows:
        if isinstance(row, dict):
            for value in row.values():
                parsed = parse_any_date(value)
                if parsed:
                    observed_dates.append(parsed.strftime(DATE_FMT))
    first_observed = min(observed_dates) if observed_dates else None
    return {
        "interface_id": spec.interface_id,
        "function_name": spec.function_name,
        "history_status": "observed_current_payload_only",
        "history_mode": spec.history_mode,
        "data_frequency": "embedded_history",
        "first_available_trade_date": first_observed,
        "last_failed_before_first": None,
        "field_stability_status": "not_applicable",
        "included_in_historical_daily_contract": False,
        "history_exclusion_reason": "embedded_history_without_date_request",
        "probe_evidence": [
            {
                "probe_type": "today_payload_sample",
                "observed_dates": observed_dates[:5],
            }
        ],
        "today_columns": today.get("columns", []),
        "history_columns": today.get("columns", []),
    }


def probe_full_range_history(
    spec: InterfaceSpec,
    today: dict[str, Any],
    probe_date: str,
    history_start_date: str,
    max_retries: int,
    retry_sleep: float,
) -> dict[str, Any]:
    """Probe an endpoint that can return the full requested history range."""

    params = {
        key: value
        for key, value in spec.history_params.items()
        if key not in {"start_date_param", "end_date_param"}
    }
    params[spec.history_params["start_date_param"]] = history_start_date
    params[spec.history_params["end_date_param"]] = probe_date
    result = call_interface(spec, params, max_retries, retry_sleep)
    evidence = [{"params": params, **asdict(result)}]
    first_date = first_date_from_sample(result.sample_rows)
    if result.call_status == "success" and result.row_count > 0:
        first_date = first_date or infer_first_date_from_full_call(spec, params)
    field_status = compare_columns(today.get("columns", []), result.columns)
    included = (
        result.call_status == "success"
        and result.row_count > 0
        and field_status == "passed"
        and spec.historical_contract_candidate
    )
    return {
        "interface_id": spec.interface_id,
        "function_name": spec.function_name,
        "history_status": "success" if result.call_status == "success" else "failed",
        "history_mode": spec.history_mode,
        "data_frequency": spec.data_frequency_hint,
        "first_available_trade_date": normalize_report_date(first_date),
        "last_failed_before_first": None,
        "field_stability_status": field_status,
        "included_in_historical_daily_contract": included,
        "history_exclusion_reason": None if included else history_exclusion_reason(spec, result, field_status),
        "probe_evidence": evidence,
        "today_columns": today.get("columns", []),
        "history_columns": result.columns,
    }


def infer_first_date_from_full_call(
    spec: InterfaceSpec, params: dict[str, Any]
) -> str | None:
    """Re-call a full-range endpoint and scan all returned rows for the earliest date."""

    try:
        result = getattr(ak, spec.function_name)(**params)
        if not isinstance(result, pd.DataFrame) or result.empty:
            return None
        date_columns = [column for column in result.columns if "日期" in str(column) or "date" in str(column).lower()]
        if not date_columns:
            return None
        parsed_dates = [
            parsed.strftime(DATE_FMT)
            for parsed in (parse_any_date(value) for value in result[date_columns[0]].tolist())
            if parsed
        ]
        return min(parsed_dates) if parsed_dates else None
    except Exception:
        return None


def probe_date_param_history(
    spec: InterfaceSpec,
    today: dict[str, Any],
    trade_dates: list[str],
    max_retries: int,
    retry_sleep: float,
    max_boundary_probes: int,
) -> dict[str, Any]:
    """Find the earliest non-empty date for a single-date parameter endpoint."""

    date_param = spec.history_params["date_param"]
    first_success: tuple[str, CallResult] | None = None
    last_failure: dict[str, Any] | None = None
    evidence = []
    for probe_day in boundary_probe_dates(trade_dates, max_boundary_probes):
        params = {date_param: probe_day}
        result = call_interface(spec, params, max_retries, retry_sleep)
        evidence.append({"params": params, **asdict(result)})
        if result.call_status == "success" and result.row_count > 0:
            first_success = (probe_day, result)
            break
        last_failure = {"date": probe_day, "reason": result.failure_reason or "empty_result"}
    if first_success:
        start = first_month_start(first_success[0])
        boundary_dates = [day for day in trade_dates if start <= day <= first_success[0]]
        for probe_day in boundary_dates:
            params = {date_param: probe_day}
            result = call_interface(spec, params, max_retries, retry_sleep)
            evidence.append({"params": params, **asdict(result)})
            if result.call_status == "success" and result.row_count > 0:
                first_success = (probe_day, result)
                break
            last_failure = {"date": probe_day, "reason": result.failure_reason or "empty_result"}
    return build_history_result_from_success(spec, today, first_success, last_failure, evidence)


def probe_range_param_history(
    spec: InterfaceSpec,
    today: dict[str, Any],
    trade_dates: list[str],
    max_retries: int,
    retry_sleep: float,
    max_boundary_probes: int,
) -> dict[str, Any]:
    """Find the earliest non-empty date window for a start/end parameter endpoint."""

    start_param = spec.history_params["start_param"]
    end_param = spec.history_params["end_param"]
    first_success: tuple[str, CallResult] | None = None
    last_failure: dict[str, Any] | None = None
    evidence = []
    for probe_day in monthly_probe_dates(trade_dates, max_boundary_probes):
        params = {
            start_param: first_month_start(probe_day),
            end_param: month_end_for_probe(probe_day, trade_dates[-1]),
        }
        result = call_interface(spec, params, max_retries, retry_sleep)
        evidence.append({"params": params, **asdict(result)})
        if result.call_status == "success" and result.row_count > 0:
            first_success = (probe_day, result)
            break
        last_failure = {"date": probe_day, "reason": result.failure_reason or "empty_result"}
    if first_success:
        start = first_month_start(first_success[0])
        boundary_dates = [day for day in trade_dates if start <= day <= first_success[0]]
        for probe_day in boundary_dates:
            params = {start_param: probe_day, end_param: probe_day}
            result = call_interface(spec, params, max_retries, retry_sleep)
            evidence.append({"params": params, **asdict(result)})
            if result.call_status == "success" and result.row_count > 0:
                first_success = (probe_day, result)
                break
            last_failure = {"date": probe_day, "reason": result.failure_reason or "empty_result"}
    return build_history_result_from_success(spec, today, first_success, last_failure, evidence)


def build_history_result_from_success(
    spec: InterfaceSpec,
    today: dict[str, Any],
    first_success: tuple[str, CallResult] | None,
    last_failure: dict[str, Any] | None,
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a normalized history result from boundary probe evidence."""

    if first_success is None:
        return {
            "interface_id": spec.interface_id,
            "function_name": spec.function_name,
            "history_status": "no_non_empty_history_found",
            "history_mode": spec.history_mode,
            "data_frequency": spec.data_frequency_hint,
            "first_available_trade_date": None,
            "last_failed_before_first": last_failure,
            "field_stability_status": "not_checked",
            "included_in_historical_daily_contract": False,
            "history_exclusion_reason": "no_non_empty_history_found",
            "probe_evidence": evidence,
            "today_columns": today.get("columns", []),
            "history_columns": [],
        }
    first_date, result = first_success
    field_status = compare_columns(today.get("columns", []), result.columns)
    included = (
        result.call_status == "success"
        and result.row_count > 0
        and field_status == "passed"
        and spec.historical_contract_candidate
    )
    return {
        "interface_id": spec.interface_id,
        "function_name": spec.function_name,
        "history_status": "success",
        "history_mode": spec.history_mode,
        "data_frequency": spec.data_frequency_hint,
        "first_available_trade_date": normalize_report_date(first_date),
        "last_failed_before_first": last_failure,
        "field_stability_status": field_status,
        "included_in_historical_daily_contract": included,
        "history_exclusion_reason": None if included else history_exclusion_reason(spec, result, field_status),
        "probe_evidence": evidence,
        "today_columns": today.get("columns", []),
        "history_columns": result.columns,
    }


def boundary_probe_dates(trade_dates: list[str], max_count: int) -> list[str]:
    """Return low-cost annual and monthly boundary dates for earliest-date probing."""

    yearly = []
    seen_years = set()
    for day in trade_dates:
        year = day[:4]
        if year not in seen_years:
            yearly.append(day)
            seen_years.add(year)
    values = yearly + [day for day in monthly_probe_dates(trade_dates, max_count) if day not in set(yearly)]
    return values[:max_count]


def monthly_probe_dates(trade_dates: list[str], max_count: int | None = None) -> list[str]:
    """Return the first known trading date for each month in ascending order."""

    values = []
    seen_months = set()
    for day in trade_dates:
        month = day[:6]
        if month not in seen_months:
            values.append(day)
            seen_months.add(month)
            if max_count is not None and len(values) >= max_count:
                break
    return values


def first_month_start(day: str) -> str:
    """Return the first calendar day of the month for a YYYYMMDD date string."""

    return f"{day[:6]}01"


def month_end_for_probe(day: str, max_day: str) -> str:
    """Return the last calendar day of the probe month, capped by the probe range."""

    parsed = datetime.strptime(day, DATE_FMT).date()
    if parsed.month == 12:
        next_month = date(parsed.year + 1, 1, 1)
    else:
        next_month = date(parsed.year, parsed.month + 1, 1)
    month_end = next_month - timedelta(days=1)
    cap = datetime.strptime(max_day, DATE_FMT).date()
    return min(month_end, cap).strftime(DATE_FMT)


def compare_columns(today_columns: list[str], history_columns: list[str]) -> str:
    """Check whether today's columns exactly match the historical probe columns."""

    if not today_columns or not history_columns:
        return "failed"
    return "passed" if today_columns == history_columns else "failed"


def history_exclusion_reason(
    spec: InterfaceSpec, result: CallResult, field_status: str
) -> str | None:
    """Explain why a history-probed interface is excluded from the daily contract."""

    if result.call_status != "success":
        return "history_call_failed"
    if result.row_count <= 0:
        return "history_empty_result"
    if field_status != "passed":
        return "field_stability_failed"
    if not spec.historical_contract_candidate:
        return spec.exclusion_note or "not_marked_as_historical_daily_contract_candidate"
    return None


def first_date_from_sample(sample_rows: list[dict[str, Any]]) -> str | None:
    """Infer the earliest date from sample rows when possible."""

    dates = []
    for row in sample_rows:
        for value in row.values():
            parsed = parse_any_date(value)
            if parsed:
                dates.append(parsed.strftime(DATE_FMT))
    return min(dates) if dates else None


def normalize_report_date(day: str | None) -> str | None:
    """Format YYYYMMDD strings as YYYY-MM-DD for human reports."""

    if not day:
        return None
    parsed = parse_any_date(day)
    return parsed.strftime(REPORT_DATE_FMT) if parsed else day


def build_contract(
    specs: list[InterfaceSpec],
    today_rows: list[dict[str, Any]],
    history_rows: list[dict[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    """Generate the JSON daily data contract from probe results."""

    specs_by_id = {spec.interface_id: spec for spec in specs}
    today_by_id = {row["interface_id"]: row for row in today_rows}
    included = [
        row
        for row in history_rows
        if row.get("included_in_historical_daily_contract") is True
    ]
    start_dates = [
        row["first_available_trade_date"]
        for row in included
        if row.get("first_available_trade_date")
    ]
    contract_start_date = max(start_dates) if start_dates else None
    interfaces = []
    for row in included:
        today = today_by_id[row["interface_id"]]
        spec = specs_by_id[row["interface_id"]]
        interfaces.append(
            {
                "interface_id": spec.interface_id,
                "function_name": spec.function_name,
                "description": spec.description,
                "data_frequency": row["data_frequency"],
                "first_available_trade_date": row["first_available_trade_date"],
                "required_parameters": spec.today_params,
                "columns": today["columns"],
                "required_non_empty": True,
                "field_stability_status": row["field_stability_status"],
                "evidence_refs": [
                    "today-capability-report.json",
                    "history-floor-report.json",
                ],
            }
        )
    return {
        "contract_version": CONTRACT_VERSION,
        "generated_at": generated_at,
        "akshare_version": getattr(ak, "__version__", "unknown"),
        "contract_start_date": contract_start_date,
        "max_today_contract": build_max_today_contract(today_rows),
        "historical_contract_options": build_historical_contract_options(history_rows),
        "interfaces": interfaces,
        "excluded_interfaces": build_excluded_interfaces(today_rows, history_rows),
        "validation_status": "pending_validation" if interfaces else "no_historical_daily_contract",
    }


def build_max_today_contract(today_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """List every interface that returned non-empty data on the probe date."""

    return [
        {
            "interface_id": row["interface_id"],
            "function_name": row["function_name"],
            "description": row["description"],
            "category": row["category"],
            "data_frequency_hint": row["data_frequency_hint"],
            "row_count": row["row_count"],
            "columns": row["columns"],
            "history_mode": row["history_mode"],
        }
        for row in today_rows
        if row["contract_candidate"]
    ]


def build_historical_contract_options(
    history_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Group included daily interfaces by their verified first available date."""

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in history_rows:
        if not row.get("included_in_historical_daily_contract"):
            continue
        start_date = row.get("first_available_trade_date")
        if not start_date:
            continue
        grouped.setdefault(start_date, []).append(
            {
                "interface_id": row["interface_id"],
                "function_name": row["function_name"],
                "data_frequency": row["data_frequency"],
                "field_stability_status": row["field_stability_status"],
            }
        )
    return [
        {
            "contract_start_date": start_date,
            "interface_count": len(interfaces),
            "interfaces": interfaces,
        }
        for start_date, interfaces in sorted(grouped.items())
    ]


def build_excluded_interfaces(
    today_rows: list[dict[str, Any]], history_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Create a compact exclusion list for the contract artifact."""

    history_by_id = {row["interface_id"]: row for row in history_rows}
    excluded = []
    for today in today_rows:
        history = history_by_id.get(today["interface_id"], {})
        if history.get("included_in_historical_daily_contract"):
            continue
        excluded.append(
            {
                "interface_id": today["interface_id"],
                "function_name": today["function_name"],
                "today_status": today["call_status"],
                "today_rows": today["row_count"],
                "history_status": history.get("history_status"),
                "reason": history.get("history_exclusion_reason")
                or today.get("today_exclusion_reason")
                or "not_included",
            }
        )
    return excluded


def validate_contract(
    contract: dict[str, Any],
    specs: list[InterfaceSpec],
    max_retries: int,
    retry_sleep: float,
) -> dict[str, Any]:
    """Validate that included contract interfaces still return non-empty rows."""

    specs_by_id = {spec.interface_id: spec for spec in specs}
    checks = []
    for item in contract["interfaces"]:
        spec = specs_by_id[item["interface_id"]]
        params = params_for_contract_date(spec, item["first_available_trade_date"])
        result = call_interface(spec, params, max_retries, retry_sleep)
        checks.append(
            {
                "interface_id": spec.interface_id,
                "function_name": spec.function_name,
                "validation_date": item["first_available_trade_date"],
                "params": params,
                **asdict(result),
                "passed": result.call_status == "success"
                and result.row_count > 0
                and result.columns == item["columns"],
            }
        )
    status = "passed" if checks and all(check["passed"] for check in checks) else "failed"
    if not checks:
        status = "no_historical_daily_contract"
    return {
        "contract_version": contract["contract_version"],
        "validated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "validation_status": status,
        "checks": checks,
    }


def params_for_contract_date(spec: InterfaceSpec, report_date: str) -> dict[str, Any]:
    """Build AKShare parameters for validating one contract date."""

    day = report_date.replace("-", "")
    if spec.history_mode == "date_param":
        return {spec.history_params["date_param"]: day}
    if spec.history_mode == "range_param":
        return {
            spec.history_params["start_param"]: day,
            spec.history_params["end_param"]: day,
        }
    if spec.history_mode == "full_range":
        params = {
            key: value
            for key, value in spec.history_params.items()
            if key not in {"start_date_param", "end_date_param"}
        }
        params[spec.history_params["start_date_param"]] = day
        params[spec.history_params["end_date_param"]] = day
        return params
    return dict(spec.today_params)


def write_json(path: Path, data: Any) -> None:
    """Write a JSON artifact with stable UTF-8 formatting."""

    path.write_text(
        json.dumps(to_jsonable(data), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown_report(
    path: Path,
    probe_date: str,
    generated_at: str,
    specs: list[InterfaceSpec],
    today_rows: list[dict[str, Any]],
    history_rows: list[dict[str, Any]],
    contract: dict[str, Any],
    validation: dict[str, Any],
) -> None:
    """Write the human-readable daily data contract report."""

    available_today = [row for row in today_rows if row["contract_candidate"]]
    included = contract["interfaces"]
    excluded = contract["excluded_interfaces"]
    lines = [
        "# 每日数据契约接口探测报告",
        "",
        "本报告由 AKShare 接口实测生成，用于决定哪些数据可以进入每日数据契约。",
        "",
        "## 执行摘要",
        "",
        f"- 探测日期：`{normalize_report_date(probe_date)}`",
        f"- 报告生成时间：`{generated_at}`",
        f"- AKShare 版本：`{getattr(ak, '__version__', 'unknown')}`",
        f"- 候选接口数量：`{len(specs)}`",
        f"- 今日可调用且非空接口数量：`{len(available_today)}`",
        f"- 历史每日契约纳入接口数量：`{len(included)}`",
        f"- 推荐历史契约起始日：`{contract['contract_start_date'] or '无'}`",
        f"- 契约验证状态：`{validation['validation_status']}`",
        "",
        "## 今日最大可获取数据",
        "",
        "| 接口 | 函数 | 行数 | 数据频率初判 | 今日状态 |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for row in today_rows:
        status = "可用" if row["contract_candidate"] else f"排除：{row['today_exclusion_reason']}"
        lines.append(
            f"| `{row['interface_id']}` | `{row['function_name']}` | "
            f"{row['row_count']} | `{row['data_frequency_hint']}` | {status} |"
        )
    lines.extend(
        [
            "",
            "## 历史最早可获取日",
            "",
            "| 接口 | 历史类型 | 历史状态 | 最早非空交易日 | 字段一致性 | 是否纳入历史每日契约 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in history_rows:
        included_text = "是" if row["included_in_historical_daily_contract"] else "否"
        lines.append(
            f"| `{row['interface_id']}` | `{row['data_frequency']}` | "
            f"`{row['history_status']}` | `{row['first_available_trade_date'] or '无'}` | "
            f"`{row['field_stability_status']}` | {included_text} |"
        )
    lines.extend(
        [
            "",
            "## 推荐每日数据契约",
            "",
        ]
    )
    if included:
        lines.extend(
            [
                f"- 契约版本：`{contract['contract_version']}`",
                f"- 起始交易日：`{contract['contract_start_date']}`",
                "- 纳入接口：",
            ]
        )
        for item in included:
            lines.append(
                f"  - `{item['interface_id']}`：`{item['function_name']}`，"
                f"最早 `{item['first_available_trade_date']}`，字段数 `{len(item['columns'])}`"
            )
    else:
        lines.append(
            "当前环境下没有接口同时满足“今日非空、可历史回放、字段稳定、适合作为每日必有数据”的条件。"
        )
        lines.append(
            "这不是生成空契约，而是明确阻止把不可验证或不可每日获取的数据写入契约。"
        )
    lines.extend(
        [
            "",
            "## 排除清单",
            "",
            "| 接口 | 函数 | 今日状态 | 今日行数 | 历史状态 | 排除原因 |",
            "| --- | --- | --- | ---: | --- | --- |",
        ]
    )
    for row in excluded:
        lines.append(
            f"| `{row['interface_id']}` | `{row['function_name']}` | "
            f"`{row['today_status']}` | {row['today_rows']} | "
            f"`{row.get('history_status')}` | {row['reason']} |"
        )
    lines.extend(
        [
            "",
            "## 验证证据",
            "",
            "- `candidate_interfaces.json`：候选接口、签名、参数和频率初判。",
            "- `today-capability-report.json`：今日接口调用状态、行数、字段和失败原因。",
            "- `today-contract-candidates.json`：今日可用且非空的候选接口。",
            "- `history-floor-report.json`：历史回溯结果、最早非空日期和字段一致性。",
            "- `daily-data-contract.v1.json`：最终每日数据契约 JSON。",
            "- `contract-validation-report.json`：契约纳入接口的复验结果。",
            "",
            "## 重要边界",
            "",
            "- 本报告只证明当前环境、当前 AKShare 版本和当前网络条件下的接口可用性。",
            "- 今日可用不等于可历史回放；快照型接口不会进入历史每日契约。",
            "- 事件型接口即使今日非空，也不代表每天必有数据。",
            "- 接口异常、代理失败和真实空数据分别记录，不互相替代。",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    """Run the full probe, contract generation, and validation pipeline."""

    args = parse_args()
    install_default_requests_timeout(args.request_timeout)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).astimezone().isoformat()
    specs = build_candidate_interfaces(args.probe_date)
    candidate_payload = {
        "generated_at": generated_at,
        "akshare_version": getattr(ak, "__version__", "unknown"),
        "candidate_count": len(specs),
        "interfaces": [asdict(spec) for spec in specs],
    }
    write_json(output_dir / "candidate_interfaces.json", candidate_payload)
    today_rows = build_today_capability(specs, args.max_retries, args.retry_sleep)
    write_json(output_dir / "today-capability-report.json", today_rows)
    today_candidates = [row for row in today_rows if row["contract_candidate"]]
    write_json(output_dir / "today-contract-candidates.json", today_candidates)
    trade_dates = build_trade_dates(args.history_start_date, args.probe_date)
    history_rows = probe_history_floors(
        specs,
        today_rows,
        trade_dates,
        args.probe_date,
        args.history_start_date,
        args.max_retries,
        args.retry_sleep,
        args.max_history_boundary_probes,
    )
    write_json(output_dir / "history-floor-report.json", history_rows)
    contract = build_contract(specs, today_rows, history_rows, generated_at)
    validation = validate_contract(contract, specs, args.max_retries, args.retry_sleep)
    contract["validation_status"] = validation["validation_status"]
    write_json(output_dir / "daily-data-contract.v1.json", contract)
    write_json(output_dir / "contract-validation-report.json", validation)
    write_markdown_report(
        output_dir / "daily-data-contract-report.md",
        args.probe_date,
        generated_at,
        specs,
        today_rows,
        history_rows,
        contract,
        validation,
    )
    print(f"Wrote daily data contract reports to {output_dir.resolve()}")
    print(f"Today usable interfaces: {len(today_candidates)} / {len(specs)}")
    print(f"Historical contract interfaces: {len(contract['interfaces'])}")
    print(f"Validation status: {validation['validation_status']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise
    except Exception:  # noqa: BLE001 - top-level failure should preserve traceback.
        traceback.print_exc()
        raise SystemExit(1)
