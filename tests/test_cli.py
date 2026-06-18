"""验证仓库级 CLI 的每日更新入口。"""

from __future__ import annotations

from argparse import Namespace
from datetime import date
from pathlib import Path
from unittest.mock import patch

from a_share_info_hub.__main__ import build_parser, run_daily_review, run_daily_update


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


def test_cli_daily_review_parser_accepts_output_and_refresh_mode() -> None:
    """daily-review 子命令应接收输出格式和刷新模式参数。"""

    parser = build_parser()
    args = parser.parse_args(
        [
            "daily-review",
            "--trade-date",
            "2026-06-18",
            "--output-format",
            "context",
            "--render-mode",
            "deterministic",
            "--llm-output",
            "llm-review-sections.json",
            "--refresh-mode",
            "daily_update",
        ]
    )

    assert args.command == "daily-review"
    assert args.trade_date == "2026-06-18"
    assert args.output_format == "context"
    assert args.render_mode == "deterministic"
    assert args.llm_output == "llm-review-sections.json"
    assert args.refresh_mode == "daily_update"


def test_run_daily_review_calls_review_generator(tmp_path: Path) -> None:
    """daily-review 子命令应调用复盘生成函数并输出返回消息。"""

    args = Namespace(
        command="daily-review",
        trade_date="2026-06-18",
        output_root=str(tmp_path),
        output_format="inline",
        refresh_mode="none",
        render_mode="llm",
        llm_output=None,
        ignore_proxy=False,
        focus="风险",
        user_prompt=None,
    )
    fake_result = Namespace(
        data_status="partial",
        message="analysis_mode: research_only\nnot_investment_advice: true",
    )

    with patch("a_share_info_hub.__main__.generate_daily_review", return_value=fake_result) as review:
        exit_code = run_daily_review(args)

    assert exit_code == 0
    review.assert_called_once()
    request = review.call_args.args[0]
    assert request.trade_date == "2026-06-18"
    assert request.output_root == tmp_path
    assert request.output_format == "inline"
    assert request.refresh_mode == "none"
    assert request.render_mode == "llm"
    assert request.llm_output_path is None
