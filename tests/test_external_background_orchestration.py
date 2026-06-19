"""验证每日复盘外部背景 topic 编排、fusion 汇总和 CLI 入口。"""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from a_share_info_hub.__main__ import build_parser, run_daily_review_external_background
from a_share_info_hub.daily_review import load_external_background_context
from a_share_info_hub.external_background import (
    LOCAL_TOPICS_SCHEMA_VERSION,
    TOPIC_KEYS,
    FixtureTopicRunner,
    build_fusion_payload,
    build_topic_tasks,
    extract_local_topics,
    orchestrate_external_background,
    render_orchestration_message,
    run_topic_tasks,
)
from tests.test_daily_review import TRADE_DATE, write_duckdb, write_status, write_tables
from a_share_info_hub.daily_review import DailyReviewRequest, generate_daily_review


def write_review_context_fixture(root: Path) -> Path:
    """写入外部背景编排测试使用的 review-context.json。"""

    write_status(root)
    write_tables(root)
    write_duckdb(root)
    result = generate_daily_review(
        DailyReviewRequest(output_root=root, output_format="context")
    )
    assert result.context_artifact is not None
    return Path(result.context_artifact)


def test_extract_local_topics_emits_fixed_six_topics(tmp_path: Path) -> None:
    """topic 抽取器必须从 review-context.json 生成固定 6 个本地主题。"""

    context_path = write_review_context_fixture(tmp_path)
    context = json.loads(context_path.read_text(encoding="utf-8"))

    package = extract_local_topics(generate_daily_review_context(context_path))

    assert package.schema_version == LOCAL_TOPICS_SCHEMA_VERSION
    assert package.trade_date == TRADE_DATE
    assert [topic.topic_key for topic in package.topics] == list(TOPIC_KEYS)
    assert all(topic.local_summary.strip() for topic in package.topics)
    assert all("不能覆盖" in topic.evidence_boundary for topic in package.topics)
    assert context["schema_version"] == "daily_review_context.v1"


def test_fixture_runner_is_called_once_per_topic(tmp_path: Path) -> None:
    """fixture runner 必须逐 topic 派发，不能复用单个 external background fixture。"""

    package = extract_local_topics(generate_daily_review_context(write_review_context_fixture(tmp_path)))
    tasks = build_topic_tasks(package)
    runner = FixtureTopicRunner()

    results = run_topic_tasks(tasks, runner)

    assert len(runner.calls) == 6
    assert len(results) == 6
    assert {call.topic_key for call in runner.calls} == set(TOPIC_KEYS)
    assert {result.topic_key for result in results} == set(TOPIC_KEYS)


def test_blocked_topic_still_writes_fusion_with_issues(tmp_path: Path) -> None:
    """单个 topic blocked 时，fusion 仍应保留其它结果并记录 blocked reason。"""

    package = extract_local_topics(generate_daily_review_context(write_review_context_fixture(tmp_path)))
    tasks = build_topic_tasks(package)
    results = run_topic_tasks(tasks, FixtureTopicRunner(blocked_topic="market_breadth"))

    fusion = build_fusion_payload(TRADE_DATE, results)

    assert fusion["schema_version"] == "external_background_fusion.v1"
    assert len(results) == 6
    assert len(fusion["topic_findings"]) == 5
    assert any("market_breadth: market_breadth fixture blocked" == issue for issue in fusion["issues"])
    assert fusion["citations"]


def test_fusion_from_topic_results_is_accepted_by_daily_review_loader(tmp_path: Path) -> None:
    """topic results 汇总出的 fusion JSON 必须通过每日复盘外部背景校验路径。"""

    context_path = write_review_context_fixture(tmp_path)
    output_path = tmp_path / "reports" / "daily-reviews" / TRADE_DATE / "external-background-fusion.json"

    result = orchestrate_external_background(context_path, output_path, FixtureTopicRunner())
    external_context = load_external_background_context(output_path, TRADE_DATE)

    assert result.topic_count == 6
    assert result.result_count == 6
    assert result.source == "fixture_smoke"
    assert external_context.status == "passed"
    assert external_context.core_points
    assert external_context.citations
    assert external_context.follow_up_questions


def test_cli_daily_review_external_background_smoke(tmp_path: Path) -> None:
    """公开 CLI 子命令应写出 local topics、topic results 和 fusion 三个产物。"""

    context_path = write_review_context_fixture(tmp_path)
    output_path = tmp_path / "reports" / "daily-reviews" / TRADE_DATE / "external-background-fusion.json"
    args = Namespace(
        command="daily-review-external-background",
        context=str(context_path),
        output=str(output_path),
        runner="fixture",
        fixture_blocked_topic=None,
    )

    exit_code = run_daily_review_external_background(args)

    assert exit_code == 0
    topics_path = output_path.with_name("external-background-local-topics.json")
    results_path = output_path.with_name("external-background-topic-results.json")
    assert topics_path.exists()
    assert results_path.exists()
    assert output_path.exists()
    topics = json.loads(topics_path.read_text(encoding="utf-8"))
    topic_results = json.loads(results_path.read_text(encoding="utf-8"))
    fusion = json.loads(output_path.read_text(encoding="utf-8"))
    assert topics["schema_version"] == "daily_review_local_topics.v1"
    assert len(topics["topics"]) == 6
    assert len(topic_results["tasks"]) == 6
    assert len(topic_results["results"]) == 6
    assert fusion["schema_version"] == "external_background_fusion.v1"


def test_fixture_orchestration_message_marks_fixture_smoke(tmp_path: Path) -> None:
    """本地辅助入口的审计输出必须标记为 fixture_smoke。"""

    context_path = write_review_context_fixture(tmp_path)
    output_path = tmp_path / "reports" / "daily-reviews" / TRADE_DATE / "external-background-fusion.json"

    result = orchestrate_external_background(context_path, output_path, FixtureTopicRunner())
    message = render_orchestration_message(result)

    assert "external_background_source: fixture_smoke" in message
    assert "external_background_orchestration_topics: 6" in message
    assert "external_background_orchestration_results: 6" in message


def test_cli_parser_accepts_external_background_command() -> None:
    """顶层 parser 应暴露 daily-review-external-background 子命令。"""

    parser = build_parser()
    args = parser.parse_args(
        [
            "daily-review-external-background",
            "--context",
            "reports/daily-reviews/2026-06-18/review-context.json",
            "--output",
            "reports/daily-reviews/2026-06-18/external-background-fusion.json",
            "--runner",
            "fixture",
        ]
    )

    assert args.command == "daily-review-external-background"
    assert args.runner == "fixture"


def generate_daily_review_context(context_path: Path):
    """读取测试生成的 review-context.json 并返回 Pydantic context。"""

    from a_share_info_hub.daily_review import ReviewContext

    return ReviewContext.model_validate(json.loads(context_path.read_text(encoding="utf-8")))
