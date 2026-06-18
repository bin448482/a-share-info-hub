"""验证仓库级 CLI 的每日更新入口。"""

from __future__ import annotations

from argparse import Namespace
from datetime import date
from pathlib import Path
from unittest.mock import patch

from a_share_info_hub.__main__ import build_parser, run_daily_update


def test_cli_daily_update_parser_accepts_parameterized_date() -> None:
    """CLI 应通过参数接收日期，而不是依赖 hard-coded 命令。"""

    parser = build_parser()
    args = parser.parse_args(
        ["daily-update", "--trade-date", "2026-06-18", "--ignore-proxy"]
    )

    assert args.command == "daily-update"
    assert args.trade_date == "2026-06-18"
    assert args.ignore_proxy is True


def test_cli_daily_update_parser_defaults_to_today() -> None:
    """未传交易日期时，CLI 应默认使用运行当天。"""

    parser = build_parser()
    args = parser.parse_args(["daily-update"])

    assert args.command == "daily-update"
    assert args.trade_date == date.today().strftime("%Y-%m-%d")


def test_run_daily_update_calls_collection_with_parsed_arguments(tmp_path: Path) -> None:
    """daily-update 子命令应调用采集函数并传递解析后的参数。"""

    args = Namespace(
        command="daily-update",
        trade_date="2026-06-18",
        output_root=str(tmp_path),
        request_timeout=12.0,
        max_retries=1,
        retry_sleep=0.0,
        skip_duckdb=False,
        ignore_proxy=True,
        min_main_rows=1,
    )
    fake_outputs = Namespace(
        overall_status="partial",
        output_paths={"interface_status": str(tmp_path / "interface-status.json")},
    )

    with (
        patch("a_share_info_hub.__main__.install_default_requests_timeout") as timeout,
        patch("a_share_info_hub.__main__.configure_requests_proxy") as proxy,
        patch("a_share_info_hub.__main__.collect_daily_snapshot", return_value=fake_outputs) as collect,
    ):
        exit_code = run_daily_update(args)

    assert exit_code == 0
    timeout.assert_called_once_with(12.0)
    proxy.assert_called_once_with(True)
    collect.assert_called_once()
    call_kwargs = collect.call_args.kwargs
    assert call_kwargs["trade_date"].isoformat() == "2026-06-18"
    assert call_kwargs["output_root"] == tmp_path
    assert call_kwargs["max_retries"] == 1
    assert call_kwargs["retry_sleep"] == 0.0
    assert call_kwargs["skip_duckdb"] is False
    assert call_kwargs["min_main_rows"] == 1
