"""验证每日复盘 evidence packet、LLM sections 校验、HTML 输出和安全边界。"""

from __future__ import annotations

import json
from pathlib import Path
from subprocess import CompletedProcess

import duckdb
import pandas as pd
import pytest
from pydantic import ValidationError

from a_share_info_hub.daily_review import (
    DATA_STATUS_MISSING,
    DATA_STATUS_SKIPPED,
    DailyReviewRequest,
    LlmReviewSections,
    ReviewContext,
    build_daily_update_command,
    generate_daily_review,
    generate_daily_review_from_prompt,
    infer_request_from_prompt,
)


TRADE_DATE = "2026-06-18"


def write_status(root: Path, overall_status: str = "passed", board_failed: bool = False) -> None:
    """写入每日复盘测试所需的最小接口状态。"""

    run_dir = root / "reports" / "daily-runs" / TRADE_DATE
    run_dir.mkdir(parents=True)
    sources = [
        {"source_key": "stock_zh_a_spot", "category": "main", "status": "success", "row_count": 3},
        {"source_key": "stock_zt_pool_em", "category": "limit_pool", "status": "success", "row_count": 1},
        {"source_key": "stock_lhb_detail_em", "category": "lhb", "status": "success", "row_count": 1},
        {"source_key": "stock_sse_deal_daily", "category": "market_summary", "status": "success", "row_count": 1},
        {
            "source_key": "stock_board_industry_name_em",
            "category": "board_snapshot",
            "status": "failed" if board_failed else "success",
            "row_count": 0 if board_failed else 1,
            "failure_reason": "ConnectionError" if board_failed else None,
        },
    ]
    payload = {
        "trade_date": TRADE_DATE,
        "overall_status": overall_status,
        "duckdb_status": "written",
        "sources": sources,
        "table_row_counts": {
            "daily_stock_snapshot": 3,
            "limit_pool_events": 1,
            "lhb_events": 1,
            "market_summary": 1,
            "board_snapshot": 0 if board_failed else 1,
        },
    }
    (run_dir / "interface-status.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    (run_dir / "daily-data-summary.md").write_text("# summary\n", encoding="utf-8")


def write_skipped_status(root: Path) -> None:
    """写入非交易日跳过采集的最小接口状态。"""

    run_dir = root / "reports" / "daily-runs" / TRADE_DATE
    run_dir.mkdir(parents=True)
    payload = {
        "trade_date": TRADE_DATE,
        "overall_status": DATA_STATUS_SKIPPED,
        "duckdb_status": "skipped",
        "sources": [],
        "table_row_counts": {
            "daily_stock_snapshot": 0,
            "limit_pool_events": 0,
            "lhb_events": 0,
            "market_summary": 0,
            "board_snapshot": 0,
        },
        "trading_day_check": {
            "status": "success",
            "is_trading_day": False,
            "source": "weekday",
            "reason": "weekend is not an A-share trading day",
        },
    }
    (run_dir / "interface-status.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    (run_dir / "daily-data-summary.md").write_text("# skipped\n", encoding="utf-8")


def write_tables(root: Path, with_board: bool = True) -> None:
    """写入每日复盘测试使用的最小标准化 Parquet 表。"""

    normalized = root / "data" / "normalized"
    normalized.mkdir(parents=True)
    pd.DataFrame(
        [
            {"trade_date": TRADE_DATE, "symbol": "000001", "name": "平安银行", "change_pct": 1.2, "amount": 1000000},
            {"trade_date": TRADE_DATE, "symbol": "000002", "name": "万科A", "change_pct": -2.4, "amount": 2000000},
            {"trade_date": TRADE_DATE, "symbol": "000003", "name": "测试股", "change_pct": 0.0, "amount": 3000000},
        ]
    ).to_parquet(normalized / "daily_stock_snapshot.parquet", index=False)
    pd.DataFrame(
        [{"trade_date": TRADE_DATE, "pool_type": "limit_up", "industry": "银行"}]
    ).to_parquet(normalized / "limit_pool_events.parquet", index=False)
    pd.DataFrame(
        [{"trade_date": TRADE_DATE, "event_type": "stock_lhb_detail_em", "symbol": "000001"}]
    ).to_parquet(normalized / "lhb_events.parquet", index=False)
    pd.DataFrame(
        [{"trade_date": TRADE_DATE, "market": "sse", "row_index": 0}]
    ).to_parquet(normalized / "market_summary.parquet", index=False)
    board_rows = [{"trade_date": TRADE_DATE, "board_name": "银行", "change_pct": 1.1}] if with_board else []
    pd.DataFrame(
        board_rows,
        columns=["trade_date", "board_name", "change_pct"],
    ).to_parquet(normalized / "board_snapshot.parquet", index=False)


def write_duckdb(root: Path) -> None:
    """写入可查询主表的最小 DuckDB 数据库。"""

    with duckdb.connect(str(root / "market.duckdb")) as connection:
        connection.execute(
            "CREATE TABLE daily_stock_snapshot AS SELECT * FROM read_parquet(?)",
            [str(root / "data" / "normalized" / "daily_stock_snapshot.parquet")],
        )


def write_llm_sections(path: Path, board_text: str = "板块快照记录 1 条，仅作为结构观察。") -> None:
    """写入可通过 Pydantic 校验的模拟 LLM sections JSON。"""

    payload = {
        "schema_version": "daily_review_sections.v1",
        "headline": "2026-06-18 A 股每日复盘研究",
        "summary": ["策略分析师基于当日快照给普通投资者做研究复盘。", "主表覆盖 3 只证券，上涨 1 只，下跌 1 只，平盘 1 只。"],
        "market_breadth_review": "主表覆盖 3 只证券，上涨 1，下跌 1，平盘 1。",
        "sentiment_and_events_review": "涨跌停情绪池和龙虎榜均有可读记录。",
        "board_and_structure_review": board_text,
        "risk_observations": ["本报告只基于单日快照。"],
        "follow_up_questions": ["后续可补充连续交易日数据验证观察。"],
        "data_boundary_note": "本报告只引用已生成的复盘证据包；详细数据状态和接口说明见同目录技术参考文件。",
        "not_investment_advice_note": "本报告仅用于研究复盘，不构成投资建议。",
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_daily_review_emits_pydantic_context(tmp_path: Path) -> None:
    """context 输出应生成 review-context.json 并通过 Pydantic 校验。"""

    write_status(tmp_path)
    write_tables(tmp_path)
    write_duckdb(tmp_path)

    result = generate_daily_review(
        DailyReviewRequest(output_root=tmp_path, output_format="context")
    )

    assert result.data_status == "passed"
    assert result.context_artifact is not None
    payload = json.loads(Path(result.context_artifact).read_text(encoding="utf-8"))
    context = ReviewContext.model_validate(payload)
    assert context.schema_version == "daily_review_context.v1"
    assert context.market_breadth["sample_count"] == 3
    assert "review-context.json" in result.message


def test_review_context_rejects_invalid_status() -> None:
    """Pydantic 应阻断非法 context 枚举值。"""

    with pytest.raises(ValidationError):
        ReviewContext.model_validate(
            {
                "trade_date": TRADE_DATE,
                "data_status": "almost",
            }
        )


def test_daily_review_skipped_non_trading_day_blocks_market_review(tmp_path: Path) -> None:
    """非交易日 skipped 应生成 context，但不误报为 failed。"""

    write_skipped_status(tmp_path)

    result = generate_daily_review(
        DailyReviewRequest(trade_date=TRADE_DATE, output_root=tmp_path, output_format="inline")
    )

    assert result.data_status == DATA_STATUS_SKIPPED
    assert result.context_artifact is not None
    payload = json.loads(Path(result.context_artifact).read_text(encoding="utf-8"))
    context = ReviewContext.model_validate(payload)
    assert context.data_status == DATA_STATUS_SKIPPED
    assert "trading_day_check" in context.source_health
    assert "目标日期不是 A 股交易日" in result.message
    assert "请指定最近一个 A 股交易日" in result.message


def test_daily_review_requires_llm_output_for_default_html(tmp_path: Path) -> None:
    """默认 LLM 模式只生成 context 并等待 LLM sections JSON。"""

    write_status(tmp_path)
    write_tables(tmp_path)
    write_duckdb(tmp_path)

    result = generate_daily_review(DailyReviewRequest(output_root=tmp_path))

    assert result.report_artifact is None
    assert result.context_artifact is not None
    assert "llm_output_required: true" in result.message
    assert "report_artifact: null" in result.message


def test_daily_review_validates_llm_sections_and_generates_html(tmp_path: Path) -> None:
    """合法 LLM sections 应通过校验并生成用户可读 HTML。"""

    write_status(tmp_path)
    write_tables(tmp_path)
    write_duckdb(tmp_path)
    llm_output = tmp_path / "llm-review-sections.json"
    write_llm_sections(llm_output)

    result = generate_daily_review(
        DailyReviewRequest(output_root=tmp_path, llm_output_path=llm_output)
    )

    assert result.data_status == "passed"
    assert result.report_artifact is not None
    assert result.data_notes_artifact is not None
    report_path = Path(result.report_artifact)
    notes_path = Path(result.data_notes_artifact)
    assert report_path.exists()
    assert notes_path.exists()
    html = report_path.read_text(encoding="utf-8")
    notes = notes_path.read_text(encoding="utf-8")
    assert "review-metadata" in html
    assert "策略分析师写给普通投资者" in html
    assert "not_investment_advice" in notes
    assert "analysis_mode:" not in html
    assert "data_status:" not in html
    assert "blocked_sections:" not in html
    assert "data_status:" in notes
    assert "blocked_sections:" in notes


def test_daily_review_blocks_llm_board_claim_when_board_blocked(tmp_path: Path) -> None:
    """板块数据 blocked 时，LLM 不能输出板块主线结论。"""

    write_status(tmp_path, overall_status="partial", board_failed=True)
    write_tables(tmp_path, with_board=False)
    write_duckdb(tmp_path)
    llm_output = tmp_path / "llm-review-sections.json"
    write_llm_sections(llm_output, board_text="板块主线已经确认，银行为领涨板块。")

    result = generate_daily_review(
        DailyReviewRequest(output_root=tmp_path, llm_output_path=llm_output)
    )

    assert result.data_status == "failed"
    assert result.report_artifact is None
    assert "validation_status: failed" in result.message
    assert "blocked section board_snapshot" in result.message


def test_daily_review_deterministic_fallback_generates_html_for_local_eval(tmp_path: Path) -> None:
    """确定性 fallback 生成用户报告和技术参考，并拆分内部字段。"""

    write_status(tmp_path, overall_status="partial", board_failed=True)
    write_tables(tmp_path, with_board=False)

    result = generate_daily_review(
        DailyReviewRequest(output_root=tmp_path, render_mode="deterministic")
    )

    assert result.data_status == "partial"
    assert "board_snapshot" in result.blocked_sections
    assert result.report_artifact is not None
    assert result.data_notes_artifact is not None
    html = Path(result.report_artifact).read_text(encoding="utf-8")
    notes = Path(result.data_notes_artifact).read_text(encoding="utf-8")
    assert "板块层面的确认依据不足" in html
    assert "主表覆盖 3 只证券" in html
    assert "analysis_mode:" not in html
    assert "data_status:" not in html
    assert "blocked_sections" not in html
    assert "board_snapshot" not in html
    assert "stock_board_industry_name_em" not in html
    assert "ConnectionError" not in html
    assert "strong_limit_up" not in html
    assert "stock_lhb_detail_em" not in html
    assert "blocked_sections:" in notes
    assert "board_snapshot" in notes
    assert "stock_board_industry_name_em" in notes
    assert "ConnectionError" in notes


def test_daily_review_failed_main_blocks_market_conclusions(tmp_path: Path) -> None:
    """主表失败时应阻断市场复盘结论。"""

    write_status(tmp_path, overall_status="failed")
    write_tables(tmp_path)
    status_path = tmp_path / "reports" / "daily-runs" / TRADE_DATE / "interface-status.json"
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    payload["sources"][0]["status"] = "failed"
    payload["sources"][0]["failure_reason"] = "ReadTimeout"
    status_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    result = generate_daily_review(
        DailyReviewRequest(trade_date=TRADE_DATE, output_root=tmp_path, output_format="inline")
    )

    assert result.data_status == "failed"
    assert "已阻断完整市场复盘" in result.message
    assert "市场宽度观察" not in result.message


def test_daily_review_missing_date_does_not_use_other_date(tmp_path: Path) -> None:
    """指定日期缺失时不应自动改用其他日期。"""

    write_status(tmp_path)
    write_tables(tmp_path)

    result = generate_daily_review(
        DailyReviewRequest(trade_date="2026-01-02", output_root=tmp_path)
    )

    assert result.data_status == DATA_STATUS_MISSING
    assert "2026-01-02" in result.message
    assert "python -m a_share_info_hub daily-update --trade-date 2026-01-02" in result.message


def test_daily_review_refuses_trade_action_prompt(tmp_path: Path) -> None:
    """交易行动提示词应被改写为研究-only 边界说明。"""

    result = generate_daily_review_from_prompt(
        "调用 a-share-daily-review，看看今天哪些股票可以买，给我仓位建议。",
        output_root=tmp_path,
    )

    assert result.data_status == "blocked"
    assert "不能提供交易行动建议" in result.message
    assert "仓位建议" not in result.message
    assert "not_investment_advice: true" in result.message


def test_llm_sections_reject_missing_required_fields() -> None:
    """LLM sections 缺少核心字段时应由 Pydantic 阻断。"""

    with pytest.raises(ValidationError):
        LlmReviewSections.model_validate(
            {
                "schema_version": "daily_review_sections.v1",
                "headline": "",
                "summary": [],
                "data_boundary_note": "",
                "not_investment_advice_note": "",
            }
        )


def test_daily_review_rejects_forbidden_trading_language(tmp_path: Path) -> None:
    """LLM 输出交易行动语言时应阻断 HTML 生成。"""

    write_status(tmp_path)
    write_tables(tmp_path)
    write_duckdb(tmp_path)
    llm_output = tmp_path / "llm-review-sections.json"
    write_llm_sections(llm_output)
    payload = json.loads(llm_output.read_text(encoding="utf-8"))
    payload["follow_up_questions"] = ["建议买入强势样本。"]
    llm_output.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    result = generate_daily_review(
        DailyReviewRequest(output_root=tmp_path, llm_output_path=llm_output)
    )

    assert result.data_status == "failed"
    assert "forbidden trading terms" in result.message


def test_daily_review_refresh_uses_public_module_cli(tmp_path: Path) -> None:
    """刷新模式应构造公开 CLI 命令而不是脚本路径。"""

    seen: dict[str, list[str]] = {}

    def fake_runner(command: list[str], **_: object) -> CompletedProcess[str]:
        """记录刷新命令并模拟失败，避免测试真实采集。"""

        seen["command"] = command
        return CompletedProcess(command, 1, stdout="", stderr="boom")

    result = generate_daily_review(
        DailyReviewRequest(
            trade_date=TRADE_DATE,
            output_root=tmp_path,
            refresh_mode="daily_update",
        ),
        refresh_runner=fake_runner,
    )

    command = seen["command"]
    assert command[1:4] == ["-m", "a_share_info_hub", "daily-update"]
    assert "scripts/collect_daily_snapshot.py" not in " ".join(command)
    assert result.data_status == "failed"
    assert "python -m a_share_info_hub daily-update --trade-date 2026-06-18" in result.message


def test_build_daily_update_command_keeps_date_parameterized(tmp_path: Path) -> None:
    """公开 CLI 命令应通过参数传日期并避免本机绝对脚本路径。"""

    command = build_daily_update_command(TRADE_DATE, tmp_path, ignore_proxy=True)

    assert command[1:4] == ["-m", "a_share_info_hub", "daily-update"]
    assert "--trade-date" in command
    assert TRADE_DATE in command
    assert "--ignore-proxy" in command
    assert "collect_daily_snapshot.py" not in " ".join(command)


def test_prompt_inference_respects_no_refresh_instruction(tmp_path: Path) -> None:
    """提示词明确不刷新时，不应因为包含“刷新”二字而触发 daily-update。"""

    request = infer_request_from_prompt(
        "调用 a-share-daily-review，只使用当前仓库已有的 2026-06-18 数据，不刷新接口，生成 HTML 复盘报告。",
        tmp_path,
    )

    assert request.trade_date == "2026-06-18"
    assert request.refresh_mode == "none"
    assert request.output_format == "html"
