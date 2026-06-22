"""验证每日定时报告编排、飞书发送门禁、健康评估和 watchdog。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from scripts.run_daily_report_job import (
    DEFAULT_OPENCLAW_CANDY_TARGET,
    DEFAULT_OPENCLAW_MAIN_TARGET,
    DELIVERY_PROVIDER_OPENCLAW,
    DELIVERY_PROVIDER_OPENCLAW_AGENT,
    FeishuDeliveryResult,
    FeishuMessageRequest,
    JobConfig,
    StageExecution,
    StageResult,
    StageSla,
    run_daily_report_job,
    run_subprocess_stage,
    run_watchdog_check,
    send_openclaw_agent_message,
    send_openclaw_message,
)


TRADE_DATE = "2026-06-18"


def make_stage_result(
    execution: StageExecution,
    *,
    status: str = "passed",
    exit_code: int = 0,
    elapsed_seconds: float = 1.0,
    soft_warning: bool = False,
    timed_out: bool = False,
    failure_reason: str | None = None,
) -> StageResult:
    """构造每日任务测试使用的阶段结果。"""

    log_path = execution.job_dir / "logs" / f"{execution.stage}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(f"{execution.stage} log\n", encoding="utf-8")
    return StageResult(
        stage=execution.stage,
        started_at="2026-06-18T16:00:00+08:00",
        finished_at="2026-06-18T16:00:01+08:00",
        elapsed_seconds=elapsed_seconds,
        exit_code=exit_code,
        status=status,
        log_path=str(log_path.relative_to(execution.output_root)),
        failure_reason=failure_reason,
        soft_warning=soft_warning,
        timed_out=timed_out,
    )


def write_interface_status(root: Path, status: str = "passed", main_rows: int = 300) -> None:
    """写入编排测试需要的最小 interface-status.json。"""

    run_dir = root / "reports" / "daily-runs" / TRADE_DATE
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "trade_date": TRADE_DATE,
        "overall_status": status,
        "duckdb_status": "written" if status != "skipped" else "skipped",
        "table_row_counts": {
            "daily_stock_snapshot": main_rows,
            "limit_pool_events": 1,
            "lhb_events": 1,
            "market_summary": 1,
            "board_snapshot": 1,
        },
        "sources": [
            {"source_key": "stock_zh_a_spot", "status": "success", "row_count": main_rows},
            {"source_key": "stock_lhb_detail_em", "status": "success", "row_count": 1},
        ],
    }
    (run_dir / "interface-status.json").write_text(json.dumps(payload), encoding="utf-8")
    (run_dir / "daily-data-summary.md").write_text("# summary\n", encoding="utf-8")


def write_context(root: Path, blocked_sections: list[str] | None = None) -> None:
    """写入编排测试需要的最小 review-context.json。"""

    review_dir = root / "reports" / "daily-reviews" / TRADE_DATE
    review_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "trade_date": TRADE_DATE,
        "data_status": "passed",
        "blocked_sections": blocked_sections or [],
    }
    (review_dir / "review-context.json").write_text(json.dumps(payload), encoding="utf-8")


def write_external_background_fusion(root: Path) -> None:
    """写入编排测试需要的最小 external_background_fusion.v1 JSON。"""

    review_dir = root / "reports" / "daily-reviews" / TRADE_DATE
    review_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "external_background_fusion.v1",
        "source_skill": "daily-financial-briefing",
        "trade_date": TRADE_DATE,
        "not_investment_advice": True,
        "topic_findings": [
            {
                "text": "FOMC 政策路径仍依赖后续通胀数据。",
                "type": "macro_fact",
                "local_relevance": "观察 A 股上涨家数和成长板块成交是否同步变化。",
                "citations": [
                    {
                        "source_name": "Federal Reserve",
                        "title": "Policy statement",
                        "published_at": TRADE_DATE,
                        "accessed_at": TRADE_DATE,
                        "url": "https://www.federalreserve.gov/example",
                    }
                ],
            }
        ],
        "risk_candidates": [],
        "follow_up_candidates": [],
        "citations": [],
        "information_gaps": [],
        "issues": [],
    }
    (review_dir / "external-background-fusion.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


def write_llm_sections(root: Path) -> None:
    """写入可解析的模拟 llm-review-sections.json。"""

    review_dir = root / "reports" / "daily-reviews" / TRADE_DATE
    review_dir.mkdir(parents=True, exist_ok=True)
    (review_dir / "llm-review-sections.json").write_text('{"schema_version": "daily_review_sections.v1"}', encoding="utf-8")


def write_html_outputs(root: Path) -> None:
    """写入模拟 HTML 主报告和技术参考。"""

    review_dir = root / "reports" / "daily-reviews" / TRADE_DATE
    review_dir.mkdir(parents=True, exist_ok=True)
    (review_dir / "a-share-daily-review.html").write_text("<html></html>\n", encoding="utf-8")
    (review_dir / "a-share-daily-review-data-notes.md").write_text("# notes\n", encoding="utf-8")


class FakeStageRunner:
    """按场景写入预期 artifacts 并返回阶段结果。"""

    def __init__(
        self,
        root: Path,
        *,
        failures: dict[str, dict[str, Any]] | None = None,
        interface_status: str = "passed",
        main_rows: int = 300,
        blocked_sections: list[str] | None = None,
        omit_llm: bool = False,
        omit_external_background: bool = False,
        omit_html: bool = False,
        soft_warning_stage: str | None = None,
    ) -> None:
        """保存 fake runner 的 artifact 和失败注入配置。"""

        self.root = root
        self.failures = failures or {}
        self.interface_status = interface_status
        self.main_rows = main_rows
        self.blocked_sections = blocked_sections
        self.omit_llm = omit_llm
        self.omit_external_background = omit_external_background
        self.omit_html = omit_html
        self.soft_warning_stage = soft_warning_stage
        self.commands: list[list[str]] = []

    def __call__(self, execution: StageExecution) -> StageResult:
        """模拟执行一个编排阶段。"""

        self.commands.append(execution.command)
        failure = self.failures.get(execution.stage)
        if failure:
            return make_stage_result(execution, **failure)
        if execution.stage == "daily_update":
            write_interface_status(self.root, self.interface_status, self.main_rows)
        elif execution.stage in {"daily_review_context", "daily_review_context_with_external"}:
            write_context(self.root, self.blocked_sections)
        elif execution.stage == "external_background_fusion" and not self.omit_external_background:
            write_external_background_fusion(self.root)
        elif execution.stage == "claude_code_sections" and not self.omit_llm:
            write_llm_sections(self.root)
        elif execution.stage == "daily_review_html" and not self.omit_html:
            write_html_outputs(self.root)
        return make_stage_result(
            execution,
            soft_warning=execution.stage == self.soft_warning_stage,
            elapsed_seconds=999.0 if execution.stage == self.soft_warning_stage else 1.0,
        )


class FakeFeishuSender:
    """记录飞书消息并按配置返回成功或失败。"""

    def __init__(self, status: str = "passed") -> None:
        """保存模拟发送状态。"""

        self.status = status
        self.messages: list[FeishuMessageRequest] = []

    def __call__(self, request: FeishuMessageRequest) -> FeishuDeliveryResult:
        """模拟一次飞书发送。"""

        self.messages.append(request)
        if self.status == "passed":
            return FeishuDeliveryResult(
                status="passed",
                provider=request.delivery_provider,
                response_code=200,
                response_status_code=0,
            )
        return FeishuDeliveryResult(
            status="failed",
            provider=request.delivery_provider,
            response_code=500,
            failure_reason="webhook failed",
        )


def make_config(root: Path, *, send: bool = True, force_send: bool = False) -> JobConfig:
    """构造测试用 JobConfig。"""

    return JobConfig(
        trade_date=TRADE_DATE,
        output_root=root,
        python_bin=".venv/bin/python",
        claude_bin="claude",
        send=send,
        force_send=force_send,
        feishu_webhook_url="https://example.feishu.cn/webhook/token",
        feishu_secret="secret-value",
        heartbeat_interval_seconds=0.01,
        min_main_rows=100,
        stage_sla={
            "daily_update": StageSla(10, 20),
            "daily_review_context": StageSla(10, 20),
            "external_background_fusion": StageSla(10, 20),
            "daily_review_context_with_external": StageSla(10, 20),
            "claude_code_sections": StageSla(10, 20),
            "daily_review_html": StageSla(10, 20),
            "feishu_send": StageSla(10, 20),
            "watchdog_check": StageSla(10, 20),
        },
    )


def test_daily_report_job_success_sends_report_and_uses_public_cli(tmp_path: Path) -> None:
    """成功路径应调用公开 CLI、生成状态文件并发送报告消息。"""

    runner = FakeStageRunner(tmp_path)
    sender = FakeFeishuSender()

    status = run_daily_report_job(make_config(tmp_path), stage_runner=runner, feishu_sender=sender)

    assert status["overall_status"] == "passed"
    assert status["html_status"] == "passed"
    assert status["send_status"] == "passed"
    assert status["quality_metrics"]["llm_sections_validated"] is True
    assert status["quality_metrics"]["external_background_status"] == "passed"
    assert status["quality_metrics"]["external_background_schema"] == "external_background_fusion.v1"
    assert status["quality_metrics"]["external_background_topic_results"] == 1
    assert status["artifacts"]["external_background"] == f"reports/daily-reviews/{TRADE_DATE}/external-background-fusion.json"
    assert status["artifacts"]["html_report"] == f"reports/daily-reviews/{TRADE_DATE}/a-share-daily-review.html"
    assert sender.messages[0].message_kind == "report"
    assert [command[3] if len(command) > 3 and command[1:3] == ["-m", "a_share_info_hub"] else "claude" for command in runner.commands[:5]] == [
        "daily-update",
        "daily-review",
        "claude",
        "daily-review",
        "claude",
    ]
    assert runner.commands[0][:4] == [".venv/bin/python", "-m", "a_share_info_hub", "daily-update"]
    external_path = str(tmp_path / "reports" / "daily-reviews" / TRADE_DATE / "external-background-fusion.json")
    context_with_external = runner.commands[3]
    html_command = runner.commands[5]
    assert context_with_external[-2:] == ["--external-background", external_path]
    assert html_command[-2:] == ["--external-background", external_path]
    assert (tmp_path / "reports" / "daily-jobs" / TRADE_DATE / "job-status.json").exists()
    assert "https://example.feishu.cn" not in (tmp_path / "reports" / "daily-jobs" / TRADE_DATE / "job-status.json").read_text(encoding="utf-8")


def test_daily_update_failed_blocks_market_report_and_sends_alert(tmp_path: Path) -> None:
    """daily-update 失败时不得继续生成市场报告，应发送 critical 告警。"""

    runner = FakeStageRunner(
        tmp_path,
        failures={"daily_update": {"status": "failed", "exit_code": 1, "failure_reason": "daily-update failed"}},
    )
    sender = FakeFeishuSender()

    status = run_daily_report_job(make_config(tmp_path), stage_runner=runner, feishu_sender=sender)

    assert status["overall_status"] == "failed"
    assert status["context_status"] == "pending"
    assert status["html_status"] == "pending"
    assert sender.messages[0].message_kind == "alert"
    assert "市场结论" in sender.messages[0].text


def test_claude_timeout_or_missing_sections_blocks_html(tmp_path: Path) -> None:
    """Claude Code 超时或未生成 sections 时不得进入 HTML 发送。"""

    runner = FakeStageRunner(
        tmp_path,
        failures={
            "claude_code_sections": {
                "status": "failed",
                "exit_code": 124,
                "timed_out": True,
                "failure_reason": "claude timeout",
            }
        },
        omit_llm=True,
    )
    sender = FakeFeishuSender()

    status = run_daily_report_job(make_config(tmp_path), stage_runner=runner, feishu_sender=sender)

    assert status["overall_status"] == "failed"
    assert status["llm_sections_status"] == "failed"
    assert status["html_status"] == "pending"
    assert status["quality_metrics"]["llm_sections_exists"] is False
    assert sender.messages[0].message_kind == "alert"


def test_external_background_failure_blocks_sections_and_html(tmp_path: Path) -> None:
    """external background 未生成时不得继续生成 sections 或 HTML。"""

    runner = FakeStageRunner(
        tmp_path,
        failures={
            "external_background_fusion": {
                "status": "failed",
                "exit_code": 1,
                "failure_reason": "external background failed",
            }
        },
        omit_external_background=True,
    )
    sender = FakeFeishuSender()

    status = run_daily_report_job(make_config(tmp_path), stage_runner=runner, feishu_sender=sender)

    assert status["overall_status"] == "failed"
    assert status["quality_metrics"]["external_background_status"] == "failed"
    assert status["llm_sections_status"] == "pending"
    assert status["html_status"] == "pending"
    assert "claude_code_sections" not in status["stage_results"]
    assert sender.messages[0].message_kind == "alert"


def test_existing_external_background_is_reused_without_generation(tmp_path: Path) -> None:
    """传入现成 external background 时应跳过生成阶段并在 context/html 中复用。"""

    external_background = tmp_path / "input-external-background.json"
    write_external_background_fusion(tmp_path)
    generated_path = tmp_path / "reports" / "daily-reviews" / TRADE_DATE / "external-background-fusion.json"
    external_background.write_text(generated_path.read_text(encoding="utf-8"), encoding="utf-8")
    config = make_config(tmp_path)
    config.external_background_path = external_background
    runner = FakeStageRunner(tmp_path)
    sender = FakeFeishuSender()

    status = run_daily_report_job(config, stage_runner=runner, feishu_sender=sender)

    stages = [result["stage"] for result in status["stage_results"].values()]
    assert "external_background_fusion" not in stages
    assert status["quality_metrics"]["external_background_path"] == "input-external-background.json"
    assert status["quality_metrics"]["external_background_generated"] is False
    assert any(command[-2:] == ["--external-background", str(external_background)] for command in runner.commands)


def test_html_validation_failure_blocks_report_send(tmp_path: Path) -> None:
    """daily-review HTML 校验失败时不发送报告消息。"""

    runner = FakeStageRunner(
        tmp_path,
        failures={
            "daily_review_html": {
                "status": "failed",
                "exit_code": 1,
                "failure_reason": "validator rejected sections",
            }
        },
        omit_html=True,
    )
    sender = FakeFeishuSender()

    status = run_daily_report_job(make_config(tmp_path), stage_runner=runner, feishu_sender=sender)

    assert status["overall_status"] == "failed"
    assert status["html_status"] == "failed"
    assert status["quality_metrics"]["llm_sections_validated"] is False
    assert [message.message_kind for message in sender.messages] == ["alert"]


def test_feishu_failure_marks_job_failed_but_keeps_report_artifacts(tmp_path: Path) -> None:
    """飞书发送失败应使任务失败，同时保留已生成报告路径。"""

    runner = FakeStageRunner(tmp_path)
    sender = FakeFeishuSender(status="failed")

    status = run_daily_report_job(make_config(tmp_path), stage_runner=runner, feishu_sender=sender)

    assert status["overall_status"] == "failed"
    assert status["send_status"] == "failed"
    assert status["artifacts"]["html_report"].endswith("a-share-daily-review.html")
    assert any(alert["stage"] == "feishu_send" for alert in status["alerts"])


def test_openclaw_message_provider_routes_report_to_feishu_channel_targets(tmp_path: Path) -> None:
    """OpenClaw message provider 应把报告发给 main 和 candy 飞书 channel。"""

    config = make_config(tmp_path)
    config.delivery_provider = DELIVERY_PROVIDER_OPENCLAW
    config.openclaw_account = "main"
    runner = FakeStageRunner(tmp_path)
    sender = FakeFeishuSender()

    status = run_daily_report_job(config, stage_runner=runner, feishu_sender=sender)

    assert status["send_status"] == "passed"
    assert status["quality_metrics"]["delivery_provider"] == DELIVERY_PROVIDER_OPENCLAW
    assert status["quality_metrics"]["delivery_status"] == "passed"
    assert status["quality_metrics"]["delivery_recipients"] == [
        DEFAULT_OPENCLAW_MAIN_TARGET,
        DEFAULT_OPENCLAW_CANDY_TARGET,
    ]
    assert sender.messages[0].delivery_provider == DELIVERY_PROVIDER_OPENCLAW
    assert sender.messages[0].openclaw_report_targets == [
        DEFAULT_OPENCLAW_MAIN_TARGET,
        DEFAULT_OPENCLAW_CANDY_TARGET,
    ]
    assert status["send_results"][0]["provider"] == DELIVERY_PROVIDER_OPENCLAW


def test_openclaw_message_provider_routes_warning_and_report_targets(tmp_path: Path) -> None:
    """OpenClaw message provider 应把告警发 main，报告发 main,candy。"""

    config = make_config(tmp_path)
    config.delivery_provider = DELIVERY_PROVIDER_OPENCLAW
    runner = FakeStageRunner(
        tmp_path,
        interface_status="partial",
        blocked_sections=["board_snapshot"],
        soft_warning_stage="daily_update",
    )
    sender = FakeFeishuSender()

    status = run_daily_report_job(config, stage_runner=runner, feishu_sender=sender)

    assert status["send_status"] == "passed"
    assert [message.message_kind for message in sender.messages] == ["alert", "report"]
    assert sender.messages[0].openclaw_alert_targets == [DEFAULT_OPENCLAW_MAIN_TARGET]
    assert sender.messages[1].openclaw_report_targets == [
        DEFAULT_OPENCLAW_MAIN_TARGET,
        DEFAULT_OPENCLAW_CANDY_TARGET,
    ]
    assert status["send_results"][0]["recipients"] == [DEFAULT_OPENCLAW_MAIN_TARGET]
    assert status["send_results"][1]["recipients"] == [
        DEFAULT_OPENCLAW_MAIN_TARGET,
        DEFAULT_OPENCLAW_CANDY_TARGET,
    ]
    assert status["quality_metrics"]["delivery_recipients"] == [
        DEFAULT_OPENCLAW_MAIN_TARGET,
        DEFAULT_OPENCLAW_MAIN_TARGET,
        DEFAULT_OPENCLAW_CANDY_TARGET,
    ]


def test_openclaw_agent_provider_routes_report_and_alert_recipients(tmp_path: Path) -> None:
    """OpenClaw agent provider 应把报告发给 main,candy，告警只发给 main。"""

    config = make_config(tmp_path)
    config.delivery_provider = DELIVERY_PROVIDER_OPENCLAW_AGENT
    runner = FakeStageRunner(
        tmp_path,
        interface_status="partial",
        blocked_sections=["board_snapshot"],
        soft_warning_stage="daily_update",
    )
    sender = FakeFeishuSender()

    status = run_daily_report_job(config, stage_runner=runner, feishu_sender=sender)

    assert status["send_status"] == "passed"
    assert [message.message_kind for message in sender.messages] == ["alert", "report"]
    assert sender.messages[0].openclaw_alert_agents == ["main"]
    assert sender.messages[1].openclaw_report_agents == ["main", "candy"]
    assert status["send_results"][0]["recipients"] == ["main"]
    assert status["send_results"][1]["recipients"] == ["main", "candy"]
    assert status["quality_metrics"]["delivery_recipients"] == ["main", "main", "candy"]


def test_openclaw_sender_requires_target() -> None:
    """OpenClaw provider 缺少 target 时应返回可诊断失败。"""

    result = send_openclaw_message(
        FeishuMessageRequest(
            message_kind="alert",
            level="critical",
            title="title",
            text="body",
            delivery_provider=DELIVERY_PROVIDER_OPENCLAW,
            webhook_url=None,
            secret=None,
            openclaw_bin="openclaw",
            openclaw_channel="feishu",
            openclaw_target=None,
            openclaw_account=None,
            timeout_seconds=1,
        )
    )

    assert result.status == "failed"
    assert result.provider == DELIVERY_PROVIDER_OPENCLAW
    assert "targets are not configured" in (result.failure_reason or "")


def test_openclaw_message_sender_calls_feishu_channel_targets(monkeypatch: Any) -> None:
    """OpenClaw message sender 应逐个调用 feishu channel target。"""

    commands: list[list[str]] = []

    class Completed:
        """保存模拟 OpenClaw 命令返回值。"""

        returncode = 0
        stdout = '{"ok": true}'
        stderr = ""

    def fake_run(command: list[str], **_: Any) -> Completed:
        """记录模拟 OpenClaw 子进程命令。"""

        commands.append(command)
        return Completed()

    monkeypatch.setattr("scripts.run_daily_report_job.subprocess.run", fake_run)

    result = send_openclaw_message(
        FeishuMessageRequest(
            message_kind="report",
            level="info",
            title="title",
            text="body",
            delivery_provider=DELIVERY_PROVIDER_OPENCLAW,
            webhook_url=None,
            secret=None,
            openclaw_bin="openclaw",
            openclaw_channel="feishu",
            openclaw_target=None,
            openclaw_account=None,
            openclaw_report_targets=[DEFAULT_OPENCLAW_MAIN_TARGET, DEFAULT_OPENCLAW_CANDY_TARGET],
            openclaw_alert_targets=[DEFAULT_OPENCLAW_MAIN_TARGET],
            timeout_seconds=1,
        )
    )

    assert result.status == "passed"
    assert [command[:9] for command in commands] == [
        [
            "openclaw",
            "message",
            "send",
            "--channel",
            "feishu",
            "--target",
            "oc_d0fc6f1a86e4fad2a43f7b35acaf951a",
            "--message",
            "body",
        ],
        [
            "openclaw",
            "message",
            "send",
            "--channel",
            "feishu",
            "--target",
            "oc_17f6cf4c298256bda98b2dcc571135f2",
            "--message",
            "body",
        ],
    ]
    assert [command[-2:] for command in commands] == [
        ["--account", "main"],
        ["--account", "candy"],
    ]


def test_openclaw_agent_sender_records_command_failure() -> None:
    """OpenClaw agent 命令失败时应返回 delivery failure，而不是伪造成功。"""

    result = send_openclaw_agent_message(
        FeishuMessageRequest(
            message_kind="report",
            level="info",
            title="title",
            text="body",
            delivery_provider=DELIVERY_PROVIDER_OPENCLAW_AGENT,
            webhook_url=None,
            secret=None,
            openclaw_bin=sys.executable,
            openclaw_channel="feishu",
            openclaw_target=None,
            openclaw_account=None,
            openclaw_report_agents=["wrong-agent"],
            openclaw_alert_agents=["main"],
            timeout_seconds=1,
        )
    )

    assert result.status == "failed"
    assert result.provider == DELIVERY_PROVIDER_OPENCLAW_AGENT
    assert "wrong-agent" in (result.failure_reason or "")


def test_data_quality_warning_and_soft_warning_are_recorded(tmp_path: Path) -> None:
    """数据质量异常和 soft warning 应进入状态与告警，但不中断阶段。"""

    runner = FakeStageRunner(
        tmp_path,
        interface_status="partial",
        main_rows=300,
        blocked_sections=["board_snapshot"],
        soft_warning_stage="daily_update",
    )
    sender = FakeFeishuSender()

    status = run_daily_report_job(make_config(tmp_path), stage_runner=runner, feishu_sender=sender)

    assert status["overall_status"] == "partial"
    assert status["health_level"] == "warning"
    assert any(alert["level"] == "warning" and alert["stage"] == "daily_update" for alert in status["alerts"])
    assert any(alert["stage"] == "daily_review_context" for alert in status["alerts"])
    assert [message.message_kind for message in sender.messages] == ["alert", "report"]


def test_low_main_rows_escalates_to_critical_even_when_processes_pass(tmp_path: Path) -> None:
    """主表行数过低时即使子进程退出码为 0 也应标记 critical。"""

    runner = FakeStageRunner(tmp_path, main_rows=3)
    sender = FakeFeishuSender()

    status = run_daily_report_job(make_config(tmp_path), stage_runner=runner, feishu_sender=sender)

    assert status["overall_status"] == "failed"
    assert status["health_level"] == "critical"
    assert any(alert["stage"] == "data_quality" for alert in status["alerts"])
    assert sender.messages[0].message_kind == "alert"


def test_consecutive_failures_escalate_history_alert(tmp_path: Path) -> None:
    """连续两次失败时应记录 consecutive_failures 并提升历史告警。"""

    previous_dir = tmp_path / "reports" / "daily-jobs" / "2026-06-17"
    previous_dir.mkdir(parents=True)
    (previous_dir / "job-status.json").write_text(
        json.dumps({"overall_status": "failed", "health_level": "critical"}),
        encoding="utf-8",
    )
    runner = FakeStageRunner(tmp_path, main_rows=3)
    sender = FakeFeishuSender()

    status = run_daily_report_job(make_config(tmp_path), stage_runner=runner, feishu_sender=sender)

    assert status["quality_metrics"]["consecutive_failures"] == 2
    assert any(alert["stage"] == "history" for alert in status["alerts"])


def test_subprocess_stage_hard_timeout_terminates_process(tmp_path: Path) -> None:
    """真实子进程超过 hard timeout 时应被终止并记录 124。"""

    job_dir = tmp_path / "reports" / "daily-jobs" / TRADE_DATE
    heartbeat_path = job_dir / "heartbeat.json"
    execution = StageExecution(
        stage="claude_code_sections",
        command=[sys.executable, "-c", "import time; time.sleep(5)"],
        cwd=tmp_path,
        output_root=tmp_path,
        job_dir=job_dir,
        heartbeat_path=heartbeat_path,
        heartbeat_interval_seconds=0.01,
        sla=StageSla(soft_warning_seconds=0.01, hard_timeout_seconds=0.05),
    )

    result = run_subprocess_stage(execution)

    assert result.status == "failed"
    assert result.exit_code == 124
    assert result.timed_out is True
    assert heartbeat_path.exists()


def test_duplicate_send_guard_blocks_second_report(tmp_path: Path) -> None:
    """同一交易日已经成功发送时，默认阻止重复发送报告。"""

    first_sender = FakeFeishuSender()
    run_daily_report_job(make_config(tmp_path), stage_runner=FakeStageRunner(tmp_path), feishu_sender=first_sender)
    second_sender = FakeFeishuSender()

    status = run_daily_report_job(make_config(tmp_path), stage_runner=FakeStageRunner(tmp_path), feishu_sender=second_sender)

    assert status["overall_status"] == "failed"
    assert status["send_status"] == "skipped_duplicate"
    assert status["quality_metrics"]["duplicate_send_guard"] is True
    assert second_sender.messages == []


def test_skipped_non_trading_day_does_not_send_market_conclusion(tmp_path: Path) -> None:
    """skipped 状态应停止复盘链路并且默认不发送市场结论。"""

    runner = FakeStageRunner(tmp_path, interface_status="skipped", main_rows=0)
    sender = FakeFeishuSender()

    status = run_daily_report_job(make_config(tmp_path), stage_runner=runner, feishu_sender=sender)

    assert status["overall_status"] == "skipped"
    assert status["context_status"] == "skipped"
    assert status["send_status"] == "skipped"
    assert sender.messages == []


def test_watchdog_detects_missing_job_and_sends_critical_alert(tmp_path: Path) -> None:
    """主任务未运行且超过预期截止后，watchdog 应识别 missed-run 并发送告警。"""

    sender = FakeFeishuSender()
    config = make_config(tmp_path)
    config.expected_deadline_minutes = -1
    config.watchdog_assume_trading_day = True

    status = run_watchdog_check(config, feishu_sender=sender)

    assert status["overall_status"] == "failed"
    assert status["quality_metrics"]["missed_run_detected"] is True
    assert sender.messages[0].message_kind == "alert"


def test_watchdog_detects_stale_heartbeat(tmp_path: Path) -> None:
    """running 状态下 heartbeat 停止更新时，watchdog 应发送 critical 告警。"""

    job_dir = tmp_path / "reports" / "daily-jobs" / TRADE_DATE
    job_dir.mkdir(parents=True)
    (job_dir / "job-status.json").write_text(
        json.dumps({"trade_date": TRADE_DATE, "overall_status": "running", "health_level": "info"}),
        encoding="utf-8",
    )
    (job_dir / "heartbeat.json").write_text(
        json.dumps({"current_stage": "daily_update", "current_stage_elapsed_seconds": 30, "updated_at": "2026-06-18T16:00:00+08:00"}),
        encoding="utf-8",
    )
    sender = FakeFeishuSender()
    config = make_config(tmp_path)
    config.watchdog_stale_seconds = -1

    status = run_watchdog_check(config, feishu_sender=sender)

    assert status["overall_status"] == "failed"
    assert status["quality_metrics"]["stale_heartbeat_detected"] is True
    assert sender.messages[0].message_kind == "alert"


def test_watchdog_alerts_when_job_status_is_failed(tmp_path: Path) -> None:
    """已有 job-status 为 failed 时，watchdog 应向 main 飞书 channel 发送监控摘要。"""

    job_dir = tmp_path / "reports" / "daily-jobs" / TRADE_DATE
    job_dir.mkdir(parents=True)
    (job_dir / "job-status.json").write_text(
        json.dumps(
            {
                "trade_date": TRADE_DATE,
                "overall_status": "failed",
                "health_level": "critical",
                "artifacts": {"job_status": f"reports/daily-jobs/{TRADE_DATE}/job-status.json"},
                "failure_reason": "HTML validation failed",
            }
        ),
        encoding="utf-8",
    )
    sender = FakeFeishuSender()
    config = make_config(tmp_path)
    config.delivery_provider = DELIVERY_PROVIDER_OPENCLAW

    status = run_watchdog_check(config, feishu_sender=sender)

    assert status["overall_status"] == "failed"
    assert any(alert["message"] == "job-status.json is failed or critical." for alert in status["alerts"])
    assert sender.messages[0].message_kind == "alert"
    assert sender.messages[0].delivery_provider == DELIVERY_PROVIDER_OPENCLAW
    assert sender.messages[0].openclaw_alert_targets == [DEFAULT_OPENCLAW_MAIN_TARGET]
    assert status["send_results"][0]["recipients"] == [DEFAULT_OPENCLAW_MAIN_TARGET]


def test_diagnosis_prompt_keeps_repairs_human_confirmed() -> None:
    """受限诊断 prompt 必须禁止无人确认修改代码、cron、密钥或历史产物。"""

    prompt = Path("docs/openclaw-a-share-daily-diagnosis.prompt.md").read_text(encoding="utf-8")

    assert "只做 L0/L1/L2 动作" in prompt
    assert "不修改代码、skill、prompt、cron、密钥或历史产物" in prompt
    assert "等待人工确认" in prompt
