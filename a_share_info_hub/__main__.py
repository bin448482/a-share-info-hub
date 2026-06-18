"""提供 `python -m a_share_info_hub` 命令行入口。"""

from __future__ import annotations

import argparse
import traceback
from datetime import date
from pathlib import Path

import akshare as ak

from scripts.collect_daily_snapshot import (
    MAIN_MIN_ROWS,
    OVERALL_FAILED,
    OVERALL_PARTIAL,
    OVERALL_PASSED,
    REPORT_DATE_FMT,
    collect_daily_snapshot,
    configure_requests_proxy,
    install_default_requests_timeout,
    parse_trade_date,
)


def build_parser() -> argparse.ArgumentParser:
    """构建 A Share Info Hub 的顶层 CLI 参数解析器。"""

    parser = argparse.ArgumentParser(
        prog="python -m a_share_info_hub",
        description="Run A Share Info Hub data workflows.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    daily_update = subparsers.add_parser(
        "daily-update",
        help="Collect and normalize the daily A-share snapshot package.",
    )
    daily_update.add_argument(
        "--trade-date",
        default=date.today().strftime(REPORT_DATE_FMT),
        help="Trade date for the snapshot package, formatted as YYYY-MM-DD.",
    )
    daily_update.add_argument(
        "--output-root",
        default=".",
        help="Project root where data, logs, reports, and market.duckdb are written.",
    )
    daily_update.add_argument(
        "--request-timeout",
        type=float,
        default=12.0,
        help="Default seconds before an AKShare HTTP request times out.",
    )
    daily_update.add_argument(
        "--max-retries",
        type=int,
        default=2,
        help="Maximum attempts for each external interface.",
    )
    daily_update.add_argument(
        "--retry-sleep",
        type=float,
        default=1.0,
        help="Seconds to wait between failed interface attempts.",
    )
    daily_update.add_argument(
        "--skip-duckdb",
        action="store_true",
        help="Skip DuckDB writing for diagnosis; the run cannot be marked passed.",
    )
    daily_update.add_argument(
        "--ignore-proxy",
        action="store_true",
        help="Ignore HTTP proxy environment variables for AKShare requests in this run.",
    )
    daily_update.add_argument(
        "--min-main-rows",
        type=int,
        default=MAIN_MIN_ROWS,
        help="Minimum accepted main snapshot row count.",
    )
    return parser


def run_daily_update(args: argparse.Namespace) -> int:
    """执行每日快照更新子命令并返回进程退出码。"""

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
    return 0 if outputs.overall_status in {OVERALL_PASSED, OVERALL_PARTIAL} else 1


def main() -> int:
    """运行 A Share Info Hub 顶层 CLI。"""

    parser = build_parser()
    args = parser.parse_args()
    if args.command == "daily-update":
        return run_daily_update(args)
    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise
    except Exception:  # noqa: BLE001 - top-level failure should preserve traceback.
        traceback.print_exc()
        raise SystemExit(1)
