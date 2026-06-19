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
    OVERALL_SKIPPED,
    REPORT_DATE_FMT,
    collect_daily_snapshot,
    configure_requests_proxy,
    install_default_requests_timeout,
    parse_trade_date,
)
from a_share_info_hub.daily_review import (
    OUTPUT_HTML,
    RENDER_LLM,
    DailyReviewRequest,
    generate_daily_review,
    generate_daily_review_from_prompt,
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
    daily_review = subparsers.add_parser(
        "daily-review",
        help="Generate a research-only A-share daily review from existing artifacts.",
    )
    daily_review.add_argument(
        "--trade-date",
        default=None,
        help="Trade date to review, formatted as YYYY-MM-DD. Defaults to the latest daily run.",
    )
    daily_review.add_argument(
        "--output-root",
        default=".",
        help="Project root where data, reports, and market.duckdb are read and written.",
    )
    daily_review.add_argument(
        "--output-format",
        choices=("html", "inline", "markdown", "context"),
        default=OUTPUT_HTML,
        help="Review output format.",
    )
    daily_review.add_argument(
        "--render-mode",
        choices=("llm", "deterministic"),
        default=RENDER_LLM,
        help="Use LLM sections JSON for the final report, or deterministic fallback for local validation.",
    )
    daily_review.add_argument(
        "--llm-output",
        default=None,
        help="Path to LLM-generated JSON sections to validate and render.",
    )
    daily_review.add_argument(
        "--external-background",
        default=None,
        help="Path to daily-financial-briefing external_background.v1 JSON.",
    )
    daily_review.add_argument(
        "--refresh-mode",
        choices=("none", "daily_update"),
        default="none",
        help="Whether to run the public daily-update CLI before review generation.",
    )
    daily_review.add_argument(
        "--ignore-proxy",
        action="store_true",
        help="Pass --ignore-proxy to daily-update when refresh-mode is daily_update.",
    )
    daily_review.add_argument(
        "--focus",
        default=None,
        help="Optional review focus such as risk, data quality, market width, or HTML report.",
    )
    daily_review.add_argument(
        "--user-prompt",
        default=None,
        help="Optional natural-language request used to infer review mode for golden tests.",
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
    return 0 if outputs.overall_status in {OVERALL_PASSED, OVERALL_PARTIAL, OVERALL_SKIPPED} else 1


def run_daily_review(args: argparse.Namespace) -> int:
    """执行每日复盘研究子命令并返回进程退出码。"""

    output_root = Path(args.output_root)
    if args.user_prompt:
        result = generate_daily_review_from_prompt(
            args.user_prompt,
            output_root=output_root,
            render_mode=args.render_mode,
            llm_output_path=Path(args.llm_output) if args.llm_output else None,
            external_background_path=Path(args.external_background) if args.external_background else None,
        )
    else:
        result = generate_daily_review(
            DailyReviewRequest(
                trade_date=args.trade_date,
                output_root=output_root,
                output_format=args.output_format,
                refresh_mode=args.refresh_mode,
                render_mode=args.render_mode,
                llm_output_path=Path(args.llm_output) if args.llm_output else None,
                external_background_path=Path(args.external_background) if args.external_background else None,
                focus=args.focus,
                ignore_proxy=args.ignore_proxy,
            )
        )
    print(result.message)
    return 0 if result.data_status in {OVERALL_PASSED, OVERALL_PARTIAL, OVERALL_SKIPPED, "blocked"} else 1


def main() -> int:
    """运行 A Share Info Hub 顶层 CLI。"""

    parser = build_parser()
    args = parser.parse_args()
    if args.command == "daily-update":
        return run_daily_update(args)
    if args.command == "daily-review":
        return run_daily_review(args)
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
