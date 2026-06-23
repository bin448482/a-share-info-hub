"""编排每日定时采集、复盘报告生成、运行质量评估和飞书通知。"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, time as wall_time, timedelta
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo


JOB_SCHEMA_VERSION = "daily_report_job.v1"
WATCHDOG_SCHEMA_VERSION = "daily_report_watchdog.v1"
REPORT_DATE_FMT = "%Y-%m-%d"
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
STATUS_PASSED = "passed"
STATUS_PARTIAL = "partial"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"
STATUS_RUNNING = "running"
STATUS_PENDING = "pending"
STATUS_WARNING = "warning"
STATUS_CRITICAL = "critical"
STATUS_MISSING = "missing"
SEND_SKIPPED = "skipped"
SEND_DUPLICATE = "skipped_duplicate"
TIMEOUT_EXIT_CODE = 124
MAIN_MIN_ROWS = 100
DELIVERY_PROVIDER_FEISHU_WEBHOOK = "feishu_webhook"
DELIVERY_PROVIDER_OPENCLAW = "openclaw_message"
DELIVERY_PROVIDER_OPENCLAW_LEGACY = "openclaw"
DELIVERY_PROVIDER_OPENCLAW_AGENT = "openclaw_agent"
MAIN_TABLE = "daily_stock_snapshot"
LLM_SECTIONS_FILE = "llm-review-sections.json"
EXTERNAL_BACKGROUND_FUSION_FILE = "external-background-fusion.json"
HTML_REPORT_FILE = "a-share-daily-review.html"
DATA_NOTES_FILE = "a-share-daily-review-data-notes.md"
DEFAULT_OPENCLAW_MAIN_TARGET = "main:oc_d0fc6f1a86e4fad2a43f7b35acaf951a"
DEFAULT_OPENCLAW_CANDY_TARGET = "candy:oc_17f6cf4c298256bda98b2dcc571135f2"
FEISHU_WEBHOOK_RE = re.compile(r"https://[^\s\"']*(?:feishu|larksuite)[^\s\"']*", re.IGNORECASE)


@dataclass(frozen=True)
class StageSla:
    """保存单个阶段的 soft warning 和 hard timeout 阈值。"""

    soft_warning_seconds: float
    hard_timeout_seconds: float


@dataclass
class StageResult:
    """记录单个阶段的执行结果、耗时、日志路径和失败原因。"""

    stage: str
    started_at: str
    finished_at: str
    elapsed_seconds: float
    exit_code: int | None
    status: str
    log_path: str | None = None
    failure_reason: str | None = None
    soft_warning: bool = False
    timed_out: bool = False

    def to_dict(self) -> dict[str, Any]:
        """把阶段结果转换为可写入状态 JSON 的稳定字典。"""

        return {
            "stage": self.stage,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "exit_code": self.exit_code,
            "status": self.status,
            "log_path": self.log_path,
            "failure_reason": self.failure_reason,
            "soft_warning": self.soft_warning,
            "timed_out": self.timed_out,
        }


@dataclass(frozen=True)
class StageExecution:
    """描述一个待执行子进程阶段所需的命令、目录、日志和 SLA。"""

    stage: str
    command: list[str]
    cwd: Path
    output_root: Path
    job_dir: Path
    heartbeat_path: Path
    heartbeat_interval_seconds: float
    sla: StageSla
    log_command: list[str] | None = None


@dataclass
class FeishuMessageRequest:
    """保存一次消息发送请求的标题、正文、可选附件和发送配置。"""

    message_kind: str
    level: str
    title: str
    text: str
    delivery_provider: str
    webhook_url: str | None
    secret: str | None
    openclaw_bin: str
    openclaw_channel: str
    openclaw_target: str | None
    openclaw_account: str | None
    openclaw_report_targets: list[str] = field(default_factory=list)
    openclaw_alert_targets: list[str] = field(default_factory=list)
    openclaw_report_agents: list[str] = field(default_factory=list)
    openclaw_alert_agents: list[str] = field(default_factory=list)
    media_path: str | None = None
    timeout_seconds: float = 120.0


@dataclass(frozen=True)
class OpenClawMessageTarget:
    """保存 OpenClaw Feishu channel 的 account 和 target 组合。"""

    target: str
    account: str | None = None

    def audit_label(self) -> str:
        """返回不含密钥的发送目标审计标签。"""

        return f"{self.account}:{self.target}" if self.account else self.target


@dataclass
class FeishuDeliveryResult:
    """记录发送状态和去敏后的回执摘要。"""

    status: str
    provider: str
    response_code: int | None = None
    response_status_code: int | None = None
    response_status_message: str | None = None
    failure_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """把发送结果转换为可审计但不含 secret 的状态字典。"""

        return {
            "status": self.status,
            "provider": self.provider,
            "response_code": self.response_code,
            "response_status_code": self.response_status_code,
            "response_status_message": self.response_status_message,
            "failure_reason": self.failure_reason,
        }


@dataclass
class JobConfig:
    """保存每日定时任务运行所需的 CLI 参数和本机配置。"""

    trade_date: str | None = None
    output_root: Path = Path(".")
    python_bin: str = ".venv/bin/python"
    claude_bin: str = "claude"
    ignore_proxy: bool = False
    external_background_path: Path | None = None
    generate_external_background: bool = True
    send: bool = False
    send_skipped: bool = False
    force_send: bool = False
    delivery_provider: str = DELIVERY_PROVIDER_FEISHU_WEBHOOK
    feishu_webhook_url: str | None = None
    feishu_secret: str | None = None
    openclaw_bin: str = "openclaw"
    openclaw_channel: str = "feishu"
    openclaw_target: str | None = None
    openclaw_account: str | None = None
    openclaw_report_targets: list[str] = field(
        default_factory=lambda: [DEFAULT_OPENCLAW_MAIN_TARGET, DEFAULT_OPENCLAW_CANDY_TARGET]
    )
    openclaw_alert_targets: list[str] = field(default_factory=lambda: [DEFAULT_OPENCLAW_MAIN_TARGET])
    openclaw_report_agents: list[str] = field(default_factory=lambda: ["main", "candy"])
    openclaw_alert_agents: list[str] = field(default_factory=lambda: ["main"])
    heartbeat_interval_seconds: float = 30.0
    min_main_rows: int = MAIN_MIN_ROWS
    watchdog_stale_seconds: float = 180.0
    expected_deadline_minutes: float = 90.0
    watchdog_assume_trading_day: bool = False
    stage_sla: dict[str, StageSla] = field(default_factory=dict)

    def slas(self) -> dict[str, StageSla]:
        """返回配置中的阶段 SLA，缺省时使用第一版固定阈值。"""

        return self.stage_sla or default_stage_sla()


StageRunner = Callable[[StageExecution], StageResult]
FeishuSender = Callable[[FeishuMessageRequest], FeishuDeliveryResult]


def default_stage_sla() -> dict[str, StageSla]:
    """返回第一版每日任务各阶段的固定 SLA 阈值。"""

    return {
        "daily_update": StageSla(soft_warning_seconds=25 * 60, hard_timeout_seconds=60 * 60),
        "daily_review_context": StageSla(soft_warning_seconds=3 * 60, hard_timeout_seconds=10 * 60),
        "external_background_fusion": StageSla(soft_warning_seconds=10 * 60, hard_timeout_seconds=30 * 60),
        "daily_review_context_with_external": StageSla(soft_warning_seconds=3 * 60, hard_timeout_seconds=10 * 60),
        "claude_code_sections": StageSla(soft_warning_seconds=10 * 60, hard_timeout_seconds=30 * 60),
        "daily_review_html": StageSla(soft_warning_seconds=3 * 60, hard_timeout_seconds=10 * 60),
        "feishu_send": StageSla(soft_warning_seconds=30, hard_timeout_seconds=2 * 60),
        "watchdog_check": StageSla(soft_warning_seconds=30, hard_timeout_seconds=2 * 60),
    }


def now_shanghai() -> datetime:
    """返回当前北京时间，用于统一运行状态时间戳。"""

    return datetime.now(SHANGHAI_TZ)


def iso_timestamp(value: datetime | None = None) -> str:
    """把 datetime 转为秒级 ISO 字符串，默认使用当前北京时间。"""

    return (value or now_shanghai()).replace(microsecond=0).isoformat()


def parse_trade_date(value: str) -> date:
    """解析 YYYY-MM-DD 交易日期，并拒绝模糊日期格式。"""

    try:
        return datetime.strptime(value, REPORT_DATE_FMT).date()
    except ValueError as exc:
        raise ValueError("trade date must be formatted as YYYY-MM-DD") from exc


def resolve_trade_date(value: str | None) -> str:
    """解析显式交易日期；未提供时使用 Asia/Shanghai 当前日期。"""

    if value:
        return parse_trade_date(value).isoformat()
    return now_shanghai().date().isoformat()


def repo_root() -> Path:
    """返回仓库根目录，用作公开 CLI 和 Claude Code 的工作目录。"""

    return Path(__file__).resolve().parents[1]


def resolve_output_root(output_root: Path) -> Path:
    """把用户传入的输出根目录转换为绝对路径并创建目录。"""

    resolved = output_root.resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def status_path(path: Path | None, output_root: Path) -> str | None:
    """把 artifact 路径转换为相对 output_root 的状态字段。"""

    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(output_root.resolve()))
    except ValueError:
        return str(path)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """以稳定 UTF-8 JSON 格式写入机器可读状态文件。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any] | None:
    """读取 JSON 文件；缺失或解析失败时返回 None。"""

    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def sanitize_text(text: str, secrets: tuple[str | None, ...] = ()) -> str:
    """从日志和状态摘要中移除 webhook URL 与显式 secret。"""

    sanitized = FEISHU_WEBHOOK_RE.sub("[REDACTED_FEISHU_WEBHOOK]", text)
    for secret in secrets:
        if secret:
            sanitized = sanitized.replace(secret, "[REDACTED_SECRET]")
    return sanitized


def render_command(command: list[str]) -> str:
    """把命令列表渲染为适合日志审计的 shell 风格字符串。"""

    return " ".join(shlex.quote(part) for part in command)


def write_heartbeat(
    path: Path,
    trade_date: str,
    current_stage: str,
    stage_started_at: str | None,
    last_log_path: Path | None,
    output_root: Path,
) -> None:
    """写入当前阶段 heartbeat，供 watchdog 判断任务是否停滞。"""

    now = now_shanghai()
    elapsed: float | None = None
    if stage_started_at:
        try:
            started = datetime.fromisoformat(stage_started_at)
            elapsed = max(0.0, (now - started).total_seconds())
        except ValueError:
            elapsed = None
    last_log_updated_at = None
    if last_log_path and last_log_path.exists():
        last_log_updated_at = datetime.fromtimestamp(last_log_path.stat().st_mtime, SHANGHAI_TZ).replace(
            microsecond=0
        ).isoformat()
    write_json(
        path,
        {
            "trade_date": trade_date,
            "pid": os.getpid(),
            "current_stage": current_stage,
            "current_stage_started_at": stage_started_at,
            "current_stage_elapsed_seconds": None if elapsed is None else round(elapsed, 3),
            "last_log_path": status_path(last_log_path, output_root) if last_log_path else None,
            "last_log_updated_at": last_log_updated_at,
            "updated_at": iso_timestamp(now),
        },
    )


def make_job_dirs(output_root: Path, trade_date: str) -> tuple[Path, Path, Path, Path]:
    """创建并返回 job 目录、日志目录、状态文件和 heartbeat 路径。"""

    job_dir = output_root / "reports" / "daily-jobs" / trade_date
    logs_dir = job_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return job_dir, logs_dir, job_dir / "job-status.json", job_dir / "heartbeat.json"


def base_quality_metrics(config: JobConfig, trade_date: str, heartbeat_path: Path, output_root: Path) -> dict[str, Any]:
    """构造每次任务都要写入的质量指标骨架。"""

    slas = config.slas()
    return {
        "freshness_minutes": None,
        "daily_update_exit_code": None,
        "daily_review_context_exit_code": None,
        "external_background_exit_code": None,
        "daily_review_context_with_external_exit_code": None,
        "daily_review_html_exit_code": None,
        "claude_code_exit_code": None,
        "claude_code_log_path": None,
        "external_background_log_path": None,
        "external_background_path": status_path(config.external_background_path, output_root),
        "external_background_exists": False,
        "external_background_generated": config.external_background_path is None and config.generate_external_background,
        "external_background_status": STATUS_PENDING,
        "external_background_source": None,
        "external_background_schema": None,
        "llm_sections_path": None,
        "daily_update_overall_status": None,
        "main_snapshot_rows": None,
        "failed_source_count": 0,
        "schema_changed_source_count": 0,
        "success_empty_source_count": 0,
        "blocked_sections": [],
        "html_exists": False,
        "data_notes_exists": False,
        "llm_sections_exists": False,
        "llm_sections_validated": False,
        "feishu_delivery_status": SEND_SKIPPED,
        "feishu_response_code": None,
        "delivery_status": SEND_SKIPPED,
        "delivery_response_code": None,
        "delivery_recipients": [],
        "delivery_provider": config.delivery_provider,
        "consecutive_failures": 0,
        "duplicate_send_guard": False,
        "watchdog_checked_at": None,
        "expected_job_deadline": expected_job_deadline(trade_date, config).isoformat(),
        "missed_run_detected": False,
        "current_stage": STATUS_PENDING,
        "current_stage_started_at": None,
        "current_stage_elapsed_seconds": None,
        "heartbeat_path": status_path(heartbeat_path, output_root),
        "heartbeat_updated_at": None,
        "heartbeat_age_seconds": None,
        "stage_sla": {
            stage: {
                "soft_warning_seconds": sla.soft_warning_seconds,
                "hard_timeout_seconds": sla.hard_timeout_seconds,
            }
            for stage, sla in slas.items()
        },
    }


def expected_job_deadline(trade_date: str, config: JobConfig) -> datetime:
    """计算 watchdog 使用的交易日预期任务完成截止时间。"""

    day = parse_trade_date(trade_date)
    expected_start = datetime.combine(day, wall_time(hour=16), SHANGHAI_TZ)
    return expected_start + timedelta(minutes=config.expected_deadline_minutes)


def build_initial_status(
    config: JobConfig,
    trade_date: str,
    job_dir: Path,
    status_file: Path,
    heartbeat_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    """构造任务启动时写入的 job-status.json 内容。"""

    return {
        "schema_version": JOB_SCHEMA_VERSION,
        "trade_date": trade_date,
        "started_at": iso_timestamp(),
        "finished_at": None,
        "overall_status": STATUS_RUNNING,
        "daily_update_status": STATUS_PENDING,
        "context_status": STATUS_PENDING,
        "llm_sections_status": STATUS_PENDING,
        "html_status": STATUS_PENDING,
        "send_status": STATUS_PENDING,
        "health_status": STATUS_RUNNING,
        "health_level": "info",
        "quality_metrics": base_quality_metrics(config, trade_date, heartbeat_path, output_root),
        "alerts": [],
        "stage_results": {},
        "send_results": [],
        "artifacts": {
            "job_status": status_path(status_file, output_root),
            "job_summary": status_path(job_dir / "job-summary.md", output_root),
            "heartbeat": status_path(heartbeat_path, output_root),
        },
        "failure_reason": None,
        "not_investment_advice": True,
    }


def append_alert(alerts: list[dict[str, str]], level: str, stage: str, message: str) -> None:
    """追加一条去重后的运行质量告警。"""

    alert = {"level": level, "stage": stage, "message": message}
    if alert not in alerts:
        alerts.append(alert)


def update_running_status(
    status: dict[str, Any],
    status_file: Path,
    heartbeat_path: Path,
    output_root: Path,
    current_stage: str,
    stage_started_at: str | None,
    last_log_path: Path | None,
) -> None:
    """更新运行中状态文件和 heartbeat，暴露当前阶段。"""

    metrics = status["quality_metrics"]
    metrics["current_stage"] = current_stage
    metrics["current_stage_started_at"] = stage_started_at
    metrics["current_stage_elapsed_seconds"] = None
    metrics["heartbeat_updated_at"] = iso_timestamp()
    write_heartbeat(
        heartbeat_path,
        status["trade_date"],
        current_stage,
        stage_started_at,
        last_log_path,
        output_root,
    )
    write_json(status_file, status)


def run_subprocess_stage(execution: StageExecution) -> StageResult:
    """执行带 heartbeat 和 hard timeout 的子进程阶段。"""

    started = now_shanghai()
    started_at = iso_timestamp(started)
    log_path = execution.job_dir / "logs" / f"{execution.stage}.log"
    command_for_log = execution.log_command or execution.command
    write_heartbeat(
        execution.heartbeat_path,
        execution.job_dir.name,
        execution.stage,
        started_at,
        log_path,
        execution.output_root,
    )
    stdout = ""
    stderr = ""
    timed_out = False
    exit_code: int | None = None
    failure_reason: str | None = None
    try:
        process = subprocess.Popen(
            execution.command,
            cwd=execution.cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        exit_code = 127
        failure_reason = str(exc)
    else:
        deadline = time.monotonic() + execution.sla.hard_timeout_seconds
        heartbeat_interval = max(0.05, execution.heartbeat_interval_seconds)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                process.kill()
                collected_stdout, collected_stderr = process.communicate()
                stdout += collected_stdout or ""
                stderr += collected_stderr or ""
                exit_code = TIMEOUT_EXIT_CODE
                failure_reason = (
                    f"{execution.stage} exceeded hard timeout "
                    f"{execution.sla.hard_timeout_seconds:.0f}s"
                )
                break
            try:
                collected_stdout, collected_stderr = process.communicate(
                    timeout=min(heartbeat_interval, remaining)
                )
                stdout += collected_stdout or ""
                stderr += collected_stderr or ""
                exit_code = process.returncode
                break
            except subprocess.TimeoutExpired:
                write_heartbeat(
                    execution.heartbeat_path,
                    execution.job_dir.name,
                    execution.stage,
                    started_at,
                    log_path,
                    execution.output_root,
                )
                continue
    finished = now_shanghai()
    elapsed = max(0.0, (finished - started).total_seconds())
    if exit_code is None:
        exit_code = 1
    status = STATUS_PASSED if exit_code == 0 and not timed_out else STATUS_FAILED
    if status == STATUS_FAILED and failure_reason is None:
        failure_reason = f"{execution.stage} exited with code {exit_code}"
    soft_warning = elapsed > execution.sla.soft_warning_seconds
    log_lines = [
        f"stage: {execution.stage}",
        f"started_at: {started_at}",
        f"finished_at: {iso_timestamp(finished)}",
        f"elapsed_seconds: {elapsed:.3f}",
        f"exit_code: {exit_code}",
        f"status: {status}",
        f"soft_warning: {str(soft_warning).lower()}",
        f"timed_out: {str(timed_out).lower()}",
        f"command: {render_command(command_for_log)}",
        "",
        "## stdout",
        stdout,
        "",
        "## stderr",
        stderr,
    ]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("\n".join(log_lines), encoding="utf-8")
    return StageResult(
        stage=execution.stage,
        started_at=started_at,
        finished_at=iso_timestamp(finished),
        elapsed_seconds=elapsed,
        exit_code=exit_code,
        status=status,
        log_path=status_path(log_path, execution.output_root),
        failure_reason=failure_reason,
        soft_warning=soft_warning,
        timed_out=timed_out,
    )


def build_daily_update_command(config: JobConfig, trade_date: str) -> list[str]:
    """构造每日采集阶段的公开 CLI 命令。"""

    command = [
        config.python_bin,
        "-m",
        "a_share_info_hub",
        "daily-update",
        "--trade-date",
        trade_date,
        "--output-root",
        str(config.output_root),
    ]
    if config.ignore_proxy:
        command.append("--ignore-proxy")
    return command


def build_daily_review_context_command(
    config: JobConfig, trade_date: str, external_background_path: Path | None = None
) -> list[str]:
    """构造每日复盘 context 阶段的公开 CLI 命令。"""

    command = [
        config.python_bin,
        "-m",
        "a_share_info_hub",
        "daily-review",
        "--trade-date",
        trade_date,
        "--output-root",
        str(config.output_root),
        "--output-format",
        "context",
    ]
    background_path = external_background_path or config.external_background_path
    if background_path:
        command.extend(["--external-background", str(background_path)])
    return command


def build_daily_review_html_command(
    config: JobConfig,
    trade_date: str,
    llm_output_path: Path,
    external_background_path: Path | None = None,
) -> list[str]:
    """构造每日复盘 HTML 校验和渲染阶段的公开 CLI 命令。"""

    command = [
        config.python_bin,
        "-m",
        "a_share_info_hub",
        "daily-review",
        "--trade-date",
        trade_date,
        "--output-root",
        str(config.output_root),
        "--llm-output",
        str(llm_output_path),
        "--output-format",
        "html",
    ]
    background_path = external_background_path or config.external_background_path
    if background_path:
        command.extend(["--external-background", str(background_path)])
    return command


def build_claude_prompt(context_path: Path, llm_output_path: Path, trade_date: str, output_root: Path) -> str:
    """构造 Claude Code 非交互生成 LLM sections JSON 的提示词。"""

    context_ref = claude_path_ref(context_path, output_root)
    llm_ref = claude_path_ref(llm_output_path, output_root)
    return "\n".join(
        [
            "Use the $a-share-daily-review skill in this repository.",
            f"Trade date: {trade_date}",
            f"Read the evidence packet at: {context_ref}",
            "Read the controlled report prompt at: skills/a-share-daily-review/references/report-prompt.md",
            f"Write a valid daily_review_sections.v1 JSON file to: {llm_ref}",
            "The target file must be strict parseable JSON: no Markdown fences, no comments, no trailing commas, and no unescaped ASCII double quotes inside text values; use Chinese quotation marks instead.",
            "Only use facts from review-context.json and the referenced skill workflow.",
            "Do not write the final HTML report; Python validation will render it later.",
            "Preserve the research-only boundary. Do not include trading advice, position sizing, price targets, stop-loss, or take-profit instructions.",
            "After writing the target JSON file, return a short machine-readable completion summary.",
        ]
    )


def build_external_background_prompt(
    context_path: Path,
    external_background_path: Path,
    trade_date: str,
    output_root: Path,
) -> str:
    """构造 Claude Code 非交互生成 external_background_fusion.v1 的提示词。"""

    context_ref = claude_path_ref(context_path, output_root)
    external_ref = claude_path_ref(external_background_path, output_root)
    return "\n".join(
        [
            "Use the $a-share-daily-review skill in this repository.",
            "Also use the $daily-financial-briefing skill for external public background.",
            f"Trade date: {trade_date}",
            f"Read the evidence packet at: {context_ref}",
            "Read the external background workflow at: skills/a-share-daily-review/references/daily-review-workflow.md",
            f"Write exactly one external_background_fusion.v1 JSON object to: {external_ref}",
            "The target file must be strict parseable JSON: no Markdown fences, no comments, no trailing commas, and no unescaped ASCII double quotes inside text values; use Chinese quotation marks instead.",
            "Generate the fusion package by spawning 6 parallel sub-agents, one for each local topic: market_overview_assessment, market_overview_structure, market_breadth, sentiment_and_events, board_and_structure, and risk_observations.",
            "Each sub-agent must use $daily-financial-briefing scope US Macro and Investment Bank Views only, stay inside the local evidence boundary, and keep every external finding tied to a local A-share observation object.",
            "The JSON must include schema_version, source_skill, trade_date, not_investment_advice, topic_findings, risk_candidates, follow_up_candidates, citations, information_gaps, and issues.",
            "Every accepted topic_finding must include text, type, local_relevance, and at least one citation with source_name, title, published_at or accessed_at, and url.",
            "Do not include trading advice, position sizing, price targets, stop-loss, or take-profit instructions.",
            "Do not write llm-review-sections.json or the final HTML report in this stage.",
            "After writing the target JSON file, return a short machine-readable completion summary including external_background_schema: external_background_fusion.v1 and external_background_topic_results.",
        ]
    )


def claude_path_ref(path: Path, output_root: Path) -> str:
    """返回 Claude Code 在仓库根工作目录下可定位的 artifact 路径。"""

    if output_root.resolve() == repo_root().resolve():
        return status_path(path, output_root) or str(path)
    return str(path.resolve())


def build_claude_command(config: JobConfig, prompt: str) -> tuple[list[str], list[str]]:
    """构造 Claude Code 非交互命令，并返回用于日志的去长文本命令。"""

    command = [
        config.claude_bin,
        "-p",
        "--permission-mode",
        "acceptEdits",
        "--output-format",
        "json",
        prompt,
    ]
    log_command = [
        config.claude_bin,
        "-p",
        "--permission-mode",
        "acceptEdits",
        "--output-format",
        "json",
        "<prompt>",
    ]
    return command, log_command


def daily_run_paths(output_root: Path, trade_date: str) -> dict[str, Path]:
    """返回 daily-update 阶段应产生的状态和摘要路径。"""

    run_dir = output_root / "reports" / "daily-runs" / trade_date
    return {
        "interface_status": run_dir / "interface-status.json",
        "daily_data_summary": run_dir / "daily-data-summary.md",
    }


def daily_review_paths(output_root: Path, trade_date: str) -> dict[str, Path]:
    """返回 daily-review 阶段应产生的 context、sections、HTML 和技术参考路径。"""

    review_dir = output_root / "reports" / "daily-reviews" / trade_date
    return {
        "review_context": review_dir / "review-context.json",
        "external_background": review_dir / EXTERNAL_BACKGROUND_FUSION_FILE,
        "llm_sections": review_dir / LLM_SECTIONS_FILE,
        "html_report": review_dir / HTML_REPORT_FILE,
        "data_notes": review_dir / DATA_NOTES_FILE,
    }


def record_stage_result(status: dict[str, Any], result: StageResult, metric_key: str | None = None) -> None:
    """把阶段结果写入 job 状态并同步退出码指标。"""

    status["stage_results"][result.stage] = result.to_dict()
    if metric_key:
        status["quality_metrics"][metric_key] = result.exit_code
    if result.soft_warning:
        append_alert(
            status["alerts"],
            STATUS_WARNING,
            result.stage,
            f"{result.stage} exceeded soft warning threshold.",
        )


def load_interface_metrics(path: Path, metrics: dict[str, Any]) -> dict[str, Any] | None:
    """读取 interface-status.json 并提取数据质量指标。"""

    payload = read_json(path)
    if payload is None:
        return None
    sources = payload.get("sources") if isinstance(payload.get("sources"), list) else []
    table_rows = payload.get("table_row_counts") if isinstance(payload.get("table_row_counts"), dict) else {}
    metrics["daily_update_overall_status"] = payload.get("overall_status")
    metrics["main_snapshot_rows"] = table_rows.get(MAIN_TABLE)
    metrics["failed_source_count"] = sum(1 for source in sources if source.get("status") == STATUS_FAILED)
    metrics["schema_changed_source_count"] = sum(1 for source in sources if source.get("status") == "schema_changed")
    metrics["success_empty_source_count"] = sum(1 for source in sources if source.get("status") == "success_empty")
    return payload


def load_context_metrics(path: Path, metrics: dict[str, Any]) -> dict[str, Any] | None:
    """读取 review-context.json 并提取 blocked sections 等质量指标。"""

    payload = read_json(path)
    if payload is None:
        return None
    blocked_sections = payload.get("blocked_sections", [])
    metrics["blocked_sections"] = blocked_sections if isinstance(blocked_sections, list) else []
    return payload


def validate_json_file(path: Path) -> bool:
    """确认目标 JSON 文件存在且可解析为 JSON 对象。"""

    return read_json(path) is not None


def load_external_background_metrics(path: Path, metrics: dict[str, Any], output_root: Path) -> dict[str, Any] | None:
    """读取 external background JSON 并提取 schema 与来源审计字段。"""

    payload = read_json(path)
    metrics["external_background_exists"] = payload is not None
    if payload is None:
        return None
    metrics["external_background_path"] = status_path(path, output_root)
    metrics["external_background_schema"] = payload.get("schema_version")
    metrics["external_background_source"] = payload.get("source_skill")
    findings = payload.get("topic_findings")
    metrics["external_background_topic_results"] = len(findings) if isinstance(findings, list) else None
    return payload


def evaluate_quality_alerts(
    status: dict[str, Any],
    config: JobConfig,
    workflow_status: str,
    report_ready: bool,
) -> None:
    """基于状态文件、阶段退出码和 artifact 存在性生成质量告警。"""

    metrics = status["quality_metrics"]
    alerts = status["alerts"]
    daily_overall = metrics.get("daily_update_overall_status")
    main_rows = metrics.get("main_snapshot_rows")
    if workflow_status == STATUS_FAILED:
        append_alert(alerts, STATUS_CRITICAL, "workflow", status.get("failure_reason") or "daily report job failed.")
    if daily_overall == STATUS_PARTIAL:
        append_alert(alerts, STATUS_WARNING, "daily_update", "daily-update returned partial data.")
    if daily_overall == STATUS_FAILED:
        append_alert(alerts, STATUS_CRITICAL, "daily_update", "daily-update returned failed status.")
    if isinstance(main_rows, int) and main_rows < config.min_main_rows and daily_overall != STATUS_SKIPPED:
        append_alert(
            alerts,
            STATUS_CRITICAL,
            "data_quality",
            f"main snapshot rows {main_rows} below threshold {config.min_main_rows}.",
        )
    if metrics.get("failed_source_count", 0) > 0 and daily_overall != STATUS_FAILED:
        append_alert(alerts, STATUS_WARNING, "data_quality", "one or more enhanced sources failed.")
    if metrics.get("schema_changed_source_count", 0) > 0:
        append_alert(alerts, STATUS_WARNING, "data_quality", "one or more sources changed schema.")
    if metrics.get("blocked_sections"):
        append_alert(alerts, STATUS_WARNING, "daily_review_context", "review context contains blocked sections.")
    if metrics.get("external_background_status") == STATUS_FAILED:
        append_alert(alerts, STATUS_CRITICAL, "external_background_fusion", "external background fusion is not ready.")
    if not report_ready and workflow_status not in {STATUS_SKIPPED, STATUS_FAILED}:
        append_alert(alerts, STATUS_CRITICAL, "daily_review_html", "HTML report is not ready.")


def determine_health_level(alerts: list[dict[str, str]], workflow_status: str) -> str:
    """根据工作流状态和告警列表计算最终健康级别。"""

    if workflow_status == STATUS_FAILED or any(alert["level"] == STATUS_CRITICAL for alert in alerts):
        return STATUS_CRITICAL
    if workflow_status == STATUS_PARTIAL or any(alert["level"] == STATUS_WARNING for alert in alerts):
        return STATUS_WARNING
    return "info"


def determine_overall_status(
    workflow_status: str,
    health_level: str,
    daily_update_overall: str | None,
) -> str:
    """把工作流状态、数据状态和健康级别压缩为 job overall_status。"""

    if workflow_status in {STATUS_FAILED, STATUS_SKIPPED}:
        return workflow_status
    if health_level == STATUS_CRITICAL:
        return STATUS_FAILED
    if daily_update_overall == STATUS_PARTIAL or health_level == STATUS_WARNING:
        return STATUS_PARTIAL
    return STATUS_PASSED


def has_previous_successful_send(status_file: Path) -> bool:
    """判断同一交易日是否已经记录过成功发送。"""

    payload = read_json(status_file)
    if payload is None:
        return False
    if payload.get("send_status") == STATUS_PASSED:
        return True
    metrics = payload.get("quality_metrics") if isinstance(payload.get("quality_metrics"), dict) else {}
    return metrics.get("feishu_delivery_status") == STATUS_PASSED


def compute_consecutive_failures(output_root: Path, trade_date: str, current_failed: bool) -> int:
    """从历史 job-status.json 计算连续失败次数。"""

    jobs_root = output_root / "reports" / "daily-jobs"
    previous: list[tuple[str, dict[str, Any]]] = []
    if jobs_root.exists():
        for status_file in jobs_root.glob("*/job-status.json"):
            day = status_file.parent.name
            if day >= trade_date:
                continue
            payload = read_json(status_file)
            if payload:
                previous.append((day, payload))
    previous.sort(key=lambda item: item[0])
    count = 1 if current_failed else 0
    for _, payload in reversed(previous):
        failed = payload.get("overall_status") == STATUS_FAILED or payload.get("health_level") == STATUS_CRITICAL
        if not failed:
            break
        count += 1
    return count if current_failed else 0


def calculate_freshness_minutes(trade_date: str, finished_at: str) -> float:
    """计算任务完成时间相对交易日 16:00 的分钟偏差。"""

    day = parse_trade_date(trade_date)
    expected = datetime.combine(day, wall_time(hour=16), SHANGHAI_TZ)
    finished = datetime.fromisoformat(finished_at)
    return round((finished - expected).total_seconds() / 60, 3)


def build_report_message(status: dict[str, Any]) -> FeishuMessageRequest:
    """把成功或 partial 报告状态渲染为飞书报告消息。"""

    metrics = status["quality_metrics"]
    artifacts = status["artifacts"]
    title = f"{status['trade_date']} A 股每日复盘"
    if metrics.get("daily_update_overall_status") == STATUS_PARTIAL:
        title += "（数据维度不完整）"
    text = "\n".join(
        [
            title,
            f"整体状态：{status['overall_status']}",
            f"数据状态：{metrics.get('daily_update_overall_status')}",
            f"主表行数：{metrics.get('main_snapshot_rows')}",
            f"失败接口数：{metrics.get('failed_source_count')}",
            f"HTML 报告：{artifacts.get('html_report')}",
            f"技术参考：{artifacts.get('data_notes')}",
            "边界声明：本报告仅用于研究复盘，不构成投资建议。",
        ]
    )
    return FeishuMessageRequest(
        message_kind="report",
        level=status["health_level"],
        title=title,
        text=text,
        webhook_url=None,
        secret=None,
        delivery_provider=DELIVERY_PROVIDER_FEISHU_WEBHOOK,
        openclaw_bin="openclaw",
        openclaw_channel="feishu",
        openclaw_target=None,
        openclaw_account=None,
        openclaw_report_targets=[],
        openclaw_alert_targets=[],
        openclaw_report_agents=[],
        openclaw_alert_agents=[],
        media_path=artifacts.get("html_report"),
        timeout_seconds=default_stage_sla()["feishu_send"].hard_timeout_seconds,
    )


def build_alert_message(status: dict[str, Any], level: str) -> FeishuMessageRequest:
    """把失败、warning 或 watchdog 状态渲染为飞书告警消息。"""

    artifacts = status.get("artifacts", {})
    alerts = status.get("alerts", [])
    failure_reason = status.get("failure_reason") or "运行质量告警。"
    alert_lines = [f"- [{alert['level']}] {alert['stage']}: {alert['message']}" for alert in alerts]
    text = "\n".join(
        [
            f"{status['trade_date']} A 股日报任务告警",
            f"级别：{level}",
            f"整体状态：{status.get('overall_status')}",
            f"失败摘要：{failure_reason}",
            "告警明细：",
            *(alert_lines or ["- 未记录具体告警。"]),
            f"状态文件：{artifacts.get('job_status') or artifacts.get('watchdog_status')}",
            f"heartbeat：{artifacts.get('heartbeat')}",
            f"复查命令：.venv/bin/python scripts/run_daily_report_job.py --trade-date {status['trade_date']}",
            "边界声明：告警消息不包含市场结论或投资建议。",
        ]
    )
    return FeishuMessageRequest(
        message_kind="alert",
        level=level,
        title=f"{status['trade_date']} A 股日报任务告警",
        text=text,
        webhook_url=None,
        secret=None,
        delivery_provider=DELIVERY_PROVIDER_FEISHU_WEBHOOK,
        openclaw_bin="openclaw",
        openclaw_channel="feishu",
        openclaw_target=None,
        openclaw_account=None,
        openclaw_report_targets=[],
        openclaw_alert_targets=[],
        openclaw_report_agents=[],
        openclaw_alert_agents=[],
        timeout_seconds=default_stage_sla()["feishu_send"].hard_timeout_seconds,
    )


def build_skipped_message(status: dict[str, Any]) -> FeishuMessageRequest:
    """把非交易日 skipped 状态渲染为不含市场结论的飞书消息。"""

    text = "\n".join(
        [
            f"{status['trade_date']} A 股日报任务 skipped",
            "目标日期不是 A 股交易日或采集链路返回 skipped。",
            "本次未生成市场结论、HTML 主报告或交易建议。",
            f"状态文件：{status['artifacts'].get('job_status')}",
        ]
    )
    return FeishuMessageRequest(
        message_kind="skipped",
        level="info",
        title=f"{status['trade_date']} A 股日报任务 skipped",
        text=text,
        webhook_url=None,
        secret=None,
        delivery_provider=DELIVERY_PROVIDER_FEISHU_WEBHOOK,
        openclaw_bin="openclaw",
        openclaw_channel="feishu",
        openclaw_target=None,
        openclaw_account=None,
        openclaw_report_targets=[],
        openclaw_alert_targets=[],
        openclaw_report_agents=[],
        openclaw_alert_agents=[],
        timeout_seconds=default_stage_sla()["feishu_send"].hard_timeout_seconds,
    )


def sign_feishu_request(timestamp: str, secret: str) -> str:
    """按飞书自定义机器人 secret 规则生成 HMAC-SHA256 签名。"""

    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def send_feishu_message(request: FeishuMessageRequest) -> FeishuDeliveryResult:
    """按请求配置通过飞书 webhook 或 OpenClaw 发送文本消息。"""

    if request.delivery_provider in {DELIVERY_PROVIDER_OPENCLAW, DELIVERY_PROVIDER_OPENCLAW_LEGACY}:
        return send_openclaw_message(request)
    if request.delivery_provider == DELIVERY_PROVIDER_OPENCLAW_AGENT:
        return send_openclaw_agent_message(request)
    return send_feishu_webhook_message(request)


def send_feishu_webhook_message(request: FeishuMessageRequest) -> FeishuDeliveryResult:
    """通过飞书自定义机器人 webhook 发送文本消息并解析回包。"""

    if not request.webhook_url:
        return FeishuDeliveryResult(
            status=STATUS_FAILED,
            provider=DELIVERY_PROVIDER_FEISHU_WEBHOOK,
            failure_reason="FEISHU_WEBHOOK_URL is not configured",
        )
    payload: dict[str, Any] = {
        "msg_type": "text",
        "content": {"text": request.text},
    }
    if request.secret:
        timestamp = str(int(time.time()))
        payload["timestamp"] = timestamp
        payload["sign"] = sign_feishu_request(timestamp, request.secret)
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    http_request = urllib.request.Request(
        request.webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(http_request, timeout=request.timeout_seconds) as response:
            response_code = response.getcode()
            response_text = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return FeishuDeliveryResult(
            status=STATUS_FAILED,
            provider=DELIVERY_PROVIDER_FEISHU_WEBHOOK,
            response_code=exc.code,
            failure_reason=f"Feishu webhook HTTP error {exc.code}",
        )
    except (urllib.error.URLError, TimeoutError) as exc:
        return FeishuDeliveryResult(
            status=STATUS_FAILED,
            provider=DELIVERY_PROVIDER_FEISHU_WEBHOOK,
            failure_reason=f"Feishu webhook failed: {exc}",
        )
    try:
        response_payload = json.loads(response_text) if response_text else {}
    except json.JSONDecodeError:
        response_payload = {}
    business_code = response_payload.get("code", response_payload.get("StatusCode"))
    status_message = response_payload.get("msg", response_payload.get("StatusMessage"))
    if 200 <= response_code < 300 and business_code in (None, 0):
        return FeishuDeliveryResult(
            status=STATUS_PASSED,
            provider=DELIVERY_PROVIDER_FEISHU_WEBHOOK,
            response_code=response_code,
            response_status_code=business_code,
            response_status_message=status_message,
        )
    return FeishuDeliveryResult(
        status=STATUS_FAILED,
        provider=DELIVERY_PROVIDER_FEISHU_WEBHOOK,
        response_code=response_code,
        response_status_code=business_code if isinstance(business_code, int) else None,
        response_status_message=status_message if isinstance(status_message, str) else None,
        failure_reason=f"Feishu business response indicates failure: {business_code}",
    )


def send_openclaw_message(request: FeishuMessageRequest) -> FeishuDeliveryResult:
    """通过 OpenClaw Gateway 的 Feishu channel 发送文本和可选附件。"""

    targets = openclaw_message_targets_for_request(request)
    if not targets:
        return FeishuDeliveryResult(
            status=STATUS_FAILED,
            provider=DELIVERY_PROVIDER_OPENCLAW,
            failure_reason="OpenClaw Feishu channel targets are not configured",
        )
    failures: list[str] = []
    responses: list[str] = []
    for message_target in targets:
        command = [
            request.openclaw_bin,
            "message",
            "send",
            "--channel",
            request.openclaw_channel,
            "--target",
            message_target.target,
            "--message",
            request.text,
            "--json",
        ]
        if request.media_path:
            command.extend(["--media", str(Path(request.media_path).expanduser().resolve())])
        account = message_target.account or request.openclaw_account
        if account:
            command.extend(["--account", account])
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=request.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            failures.append(f"{message_target.audit_label()}: timed out")
            continue
        except FileNotFoundError as exc:
            return FeishuDeliveryResult(
                status=STATUS_FAILED,
                provider=DELIVERY_PROVIDER_OPENCLAW,
                failure_reason=f"OpenClaw executable not found: {exc}",
            )
        output = (completed.stdout or completed.stderr or "").strip()
        if output:
            responses.append(f"{message_target.audit_label()}: {output[:240]}")
        if completed.returncode != 0:
            failures.append(f"{message_target.audit_label()}: exit {completed.returncode}")
    if failures:
        return FeishuDeliveryResult(
            status=STATUS_FAILED,
            provider=DELIVERY_PROVIDER_OPENCLAW,
            response_code=1,
            response_status_message="; ".join(responses)[:500] if responses else None,
            failure_reason="OpenClaw message send failed: " + "; ".join(failures),
        )
    return FeishuDeliveryResult(
        status=STATUS_PASSED,
        provider=DELIVERY_PROVIDER_OPENCLAW,
        response_code=0,
        response_status_message="; ".join(responses)[:500] if responses else None,
    )


def openclaw_targets_for_message(request: FeishuMessageRequest) -> list[str]:
    """按消息类型选择 OpenClaw Feishu channel target 列表。"""

    if request.message_kind == "report":
        targets = request.openclaw_report_targets
    else:
        targets = request.openclaw_alert_targets
    if targets:
        return [target for target in targets if target]
    return [request.openclaw_target] if request.openclaw_target else []


def openclaw_message_targets_for_request(request: FeishuMessageRequest) -> list[OpenClawMessageTarget]:
    """按消息类型选择 OpenClaw Feishu channel account/target 路由。"""

    return [parse_openclaw_message_target(target) for target in openclaw_targets_for_message(request)]


def parse_openclaw_message_target(value: str) -> OpenClawMessageTarget:
    """解析 OpenClaw Feishu channel 路由，支持 account:target 和纯 target。"""

    account, separator, target = value.partition(":")
    if separator and account and target:
        return OpenClawMessageTarget(target=target, account=account)
    return OpenClawMessageTarget(target=value)


def openclaw_agents_for_message(request: FeishuMessageRequest) -> list[str]:
    """按消息类型选择 OpenClaw agent 收件人。"""

    if request.message_kind == "report":
        return [agent for agent in request.openclaw_report_agents if agent]
    return [agent for agent in request.openclaw_alert_agents if agent]


def delivery_recipients_for_message(request: FeishuMessageRequest) -> list[str]:
    """返回不含密钥的消息收件审计字段。"""

    if request.delivery_provider == DELIVERY_PROVIDER_OPENCLAW_AGENT:
        return openclaw_agents_for_message(request)
    if request.delivery_provider in {DELIVERY_PROVIDER_OPENCLAW, DELIVERY_PROVIDER_OPENCLAW_LEGACY}:
        return [target.audit_label() for target in openclaw_message_targets_for_request(request)]
    if request.delivery_provider == DELIVERY_PROVIDER_FEISHU_WEBHOOK:
        return ["feishu_webhook"] if request.webhook_url else []
    return []


def send_openclaw_agent_message(request: FeishuMessageRequest) -> FeishuDeliveryResult:
    """通过 OpenClaw agent session 分发报告或监控消息。"""

    agents = openclaw_agents_for_message(request)
    if not agents:
        return FeishuDeliveryResult(
            status=STATUS_FAILED,
            provider=DELIVERY_PROVIDER_OPENCLAW_AGENT,
            failure_reason="OpenClaw agent recipients are not configured",
        )
    failures: list[str] = []
    responses: list[str] = []
    for agent in agents:
        command = [
            request.openclaw_bin,
            "agent",
            "--agent",
            agent,
            "--message",
            request.text,
            "--json",
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=request.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            failures.append(f"{agent}: timed out")
            continue
        except FileNotFoundError as exc:
            return FeishuDeliveryResult(
                status=STATUS_FAILED,
                provider=DELIVERY_PROVIDER_OPENCLAW_AGENT,
                failure_reason=f"OpenClaw executable not found: {exc}",
            )
        output = (completed.stdout or completed.stderr or "").strip()
        if output:
            responses.append(f"{agent}: {output[:240]}")
        if completed.returncode != 0:
            failures.append(f"{agent}: exit {completed.returncode}")
    if failures:
        return FeishuDeliveryResult(
            status=STATUS_FAILED,
            provider=DELIVERY_PROVIDER_OPENCLAW_AGENT,
            response_code=1,
            response_status_message="; ".join(responses)[:500] if responses else None,
            failure_reason="OpenClaw agent send failed: " + "; ".join(failures),
        )
    return FeishuDeliveryResult(
        status=STATUS_PASSED,
        provider=DELIVERY_PROVIDER_OPENCLAW_AGENT,
        response_code=0,
        response_status_message="; ".join(responses)[:500] if responses else None,
    )


def run_feishu_send_stage(
    messages: list[FeishuMessageRequest],
    config: JobConfig,
    output_root: Path,
    job_dir: Path,
    sender: FeishuSender,
) -> tuple[StageResult, list[dict[str, Any]]]:
    """发送一组飞书消息，并返回聚合后的发送阶段结果。"""

    started = now_shanghai()
    started_at = iso_timestamp(started)
    log_path = job_dir / "logs" / "feishu_send.log"
    send_results: list[dict[str, Any]] = []
    for message in messages:
        message.delivery_provider = config.delivery_provider
        message.webhook_url = config.feishu_webhook_url
        message.secret = config.feishu_secret
        message.openclaw_bin = config.openclaw_bin
        message.openclaw_channel = config.openclaw_channel
        message.openclaw_target = config.openclaw_target
        message.openclaw_account = config.openclaw_account
        message.openclaw_report_targets = list(config.openclaw_report_targets)
        message.openclaw_alert_targets = list(config.openclaw_alert_targets)
        message.openclaw_report_agents = list(config.openclaw_report_agents)
        message.openclaw_alert_agents = list(config.openclaw_alert_agents)
        if message.media_path:
            media_path = Path(message.media_path).expanduser()
            if not media_path.is_absolute():
                media_path = output_root / media_path
            message.media_path = str(media_path.resolve())
        result = sender(message)
        send_results.append(
            {
                "message_kind": message.message_kind,
                "level": message.level,
                "title": message.title,
                "recipients": delivery_recipients_for_message(message),
                "media_path": message.media_path,
                **result.to_dict(),
            }
        )
    finished = now_shanghai()
    elapsed = max(0.0, (finished - started).total_seconds())
    failed = any(item["status"] != STATUS_PASSED for item in send_results)
    status = STATUS_FAILED if failed else STATUS_PASSED
    failure_reason = None
    if failed:
        failure_reason = next(
            (item.get("failure_reason") for item in send_results if item["status"] != STATUS_PASSED),
            "Feishu delivery failed",
        )
    log_payload = {
        "started_at": started_at,
        "finished_at": iso_timestamp(finished),
        "elapsed_seconds": round(elapsed, 3),
        "status": status,
        "results": send_results,
    }
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        sanitize_text(json.dumps(log_payload, ensure_ascii=False, indent=2), (config.feishu_secret,)),
        encoding="utf-8",
    )
    return (
        StageResult(
            stage="feishu_send",
            started_at=started_at,
            finished_at=iso_timestamp(finished),
            elapsed_seconds=elapsed,
            exit_code=0 if not failed else 1,
            status=status,
            log_path=status_path(log_path, output_root),
            failure_reason=failure_reason,
            soft_warning=elapsed > config.slas()["feishu_send"].soft_warning_seconds,
            timed_out=False,
        ),
        send_results,
    )


def finalize_status(
    status: dict[str, Any],
    config: JobConfig,
    output_root: Path,
    status_file: Path,
    heartbeat_path: Path,
    report_ready: bool,
    workflow_status: str,
    previous_successful_send: bool,
    sender: FeishuSender,
) -> dict[str, Any]:
    """完成质量评估、飞书发送、最终状态和人读摘要写入。"""

    metrics = status["quality_metrics"]
    evaluate_quality_alerts(status, config, workflow_status, report_ready)
    health_level = determine_health_level(status["alerts"], workflow_status)
    overall_status = determine_overall_status(workflow_status, health_level, metrics.get("daily_update_overall_status"))
    status["health_level"] = health_level
    status["health_status"] = STATUS_FAILED if health_level == STATUS_CRITICAL else STATUS_PASSED
    status["overall_status"] = overall_status
    messages: list[FeishuMessageRequest] = []
    duplicate_guard = config.send and report_ready and previous_successful_send and not config.force_send
    if duplicate_guard:
        metrics["duplicate_send_guard"] = True
        metrics["feishu_delivery_status"] = SEND_DUPLICATE
        metrics["delivery_status"] = SEND_DUPLICATE
        status["send_status"] = SEND_DUPLICATE
        append_alert(
            status["alerts"],
            STATUS_CRITICAL,
            "feishu_send",
            "same trade_date already has a successful Feishu delivery; duplicate report send blocked.",
        )
        status["health_level"] = STATUS_CRITICAL
        status["health_status"] = STATUS_FAILED
        status["overall_status"] = STATUS_FAILED
    elif config.send:
        if status["overall_status"] == STATUS_SKIPPED and config.send_skipped:
            messages.append(build_skipped_message(status))
        elif any(alert["level"] == STATUS_CRITICAL for alert in status["alerts"]):
            messages.append(build_alert_message(status, STATUS_CRITICAL))
        else:
            if any(alert["level"] == STATUS_WARNING for alert in status["alerts"]):
                messages.append(build_alert_message(status, STATUS_WARNING))
            if report_ready:
                messages.append(build_report_message(status))
        if messages:
            send_stage, send_results = run_feishu_send_stage(messages, config, output_root, output_root / "reports" / "daily-jobs" / status["trade_date"], sender)
            record_stage_result(status, send_stage, None)
            status["send_results"] = send_results
            status["send_status"] = send_stage.status
            metrics["feishu_delivery_status"] = send_stage.status
            last_response = send_results[-1] if send_results else {}
            metrics["feishu_response_code"] = last_response.get("response_code")
            metrics["delivery_status"] = send_stage.status
            metrics["delivery_response_code"] = last_response.get("response_code")
            metrics["delivery_recipients"] = [
                recipient
                for result in send_results
                for recipient in result.get("recipients", [])
            ]
            if send_stage.status != STATUS_PASSED:
                append_alert(status["alerts"], STATUS_CRITICAL, "feishu_send", send_stage.failure_reason or "Feishu send failed.")
                status["health_level"] = STATUS_CRITICAL
                status["health_status"] = STATUS_FAILED
                status["overall_status"] = STATUS_FAILED
                status["failure_reason"] = status["failure_reason"] or send_stage.failure_reason
        else:
            status["send_status"] = SEND_SKIPPED
            metrics["feishu_delivery_status"] = SEND_SKIPPED
            metrics["delivery_status"] = SEND_SKIPPED
    else:
        status["send_status"] = SEND_SKIPPED
        metrics["feishu_delivery_status"] = SEND_SKIPPED
        metrics["delivery_status"] = SEND_SKIPPED
    finished_at = iso_timestamp()
    status["finished_at"] = finished_at
    metrics["freshness_minutes"] = calculate_freshness_minutes(status["trade_date"], finished_at)
    metrics["consecutive_failures"] = compute_consecutive_failures(
        output_root,
        status["trade_date"],
        status["overall_status"] == STATUS_FAILED,
    )
    if metrics["consecutive_failures"] >= 2:
        append_alert(status["alerts"], STATUS_CRITICAL, "history", "consecutive job failures reached 2 or more.")
        status["health_level"] = STATUS_CRITICAL
        status["health_status"] = STATUS_FAILED
        status["overall_status"] = STATUS_FAILED
    write_heartbeat(heartbeat_path, status["trade_date"], "finished", None, None, output_root)
    heartbeat_payload = read_json(heartbeat_path) or {}
    metrics["current_stage"] = "finished"
    metrics["current_stage_started_at"] = None
    metrics["current_stage_elapsed_seconds"] = None
    metrics["heartbeat_updated_at"] = heartbeat_payload.get("updated_at")
    metrics["heartbeat_age_seconds"] = 0
    write_json(status_file, status)
    write_job_summary(output_root / "reports" / "daily-jobs" / status["trade_date"] / "job-summary.md", status)
    return status


def write_job_summary(path: Path, status: dict[str, Any]) -> None:
    """写入面向人工排障的每日任务摘要 Markdown。"""

    lines = [
        "# 每日 A 股报告任务摘要",
        "",
        f"- trade_date: `{status['trade_date']}`",
        f"- overall_status: `{status['overall_status']}`",
        f"- health_level: `{status['health_level']}`",
        f"- send_status: `{status['send_status']}`",
        f"- not_investment_advice: `{str(status['not_investment_advice']).lower()}`",
        "",
        "## 阶段状态",
        "",
    ]
    for stage, result in status.get("stage_results", {}).items():
        lines.append(
            f"- `{stage}`: `{result.get('status')}` exit=`{result.get('exit_code')}` elapsed=`{result.get('elapsed_seconds')}` log=`{result.get('log_path')}`"
        )
    lines.extend(["", "## Artifacts", ""])
    for name, artifact in sorted(status.get("artifacts", {}).items()):
        lines.append(f"- `{name}`: `{artifact}`")
    lines.extend(["", "## Alerts", ""])
    for alert in status.get("alerts", []) or [{"level": "info", "stage": "job", "message": "no alerts"}]:
        lines.append(f"- `{alert['level']}` `{alert['stage']}`: {alert['message']}")
    lines.extend(
        [
            "",
            "## 边界",
            "",
            "- 本任务只编排公开 CLI、Claude Code external background/sections 生成、Python validator 和飞书通知。",
            "- 本任务不直接调用采集实现，不生成交易建议、仓位建议、目标价或止盈止损指令。",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def execute_stage(
    status: dict[str, Any],
    status_file: Path,
    heartbeat_path: Path,
    output_root: Path,
    execution: StageExecution,
    runner: StageRunner,
    metric_key: str | None,
) -> StageResult:
    """执行一个阶段并立即落盘阶段状态。"""

    started_at = iso_timestamp()
    update_running_status(
        status,
        status_file,
        heartbeat_path,
        output_root,
        execution.stage,
        started_at,
        execution.job_dir / "logs" / f"{execution.stage}.log",
    )
    result = runner(execution)
    record_stage_result(status, result, metric_key)
    write_json(status_file, status)
    return result


def run_daily_report_job(
    config: JobConfig,
    stage_runner: StageRunner = run_subprocess_stage,
    feishu_sender: FeishuSender = send_feishu_message,
) -> dict[str, Any]:
    """执行一次每日定时采集、复盘、HTML 校验、健康评估和通知流程。"""

    trade_date = resolve_trade_date(config.trade_date)
    output_root = resolve_output_root(config.output_root)
    config.output_root = output_root
    job_dir, _, status_file, heartbeat_path = make_job_dirs(output_root, trade_date)
    previous_successful_send = has_previous_successful_send(status_file)
    status = build_initial_status(config, trade_date, job_dir, status_file, heartbeat_path, output_root)
    write_json(status_file, status)
    paths = {**daily_run_paths(output_root, trade_date), **daily_review_paths(output_root, trade_date)}
    status["artifacts"].update({name: status_path(path, output_root) for name, path in paths.items()})
    workflow_status = STATUS_RUNNING
    report_ready = False
    slas = config.slas()
    external_background_path = config.external_background_path

    daily_update = execute_stage(
        status,
        status_file,
        heartbeat_path,
        output_root,
        StageExecution(
            stage="daily_update",
            command=build_daily_update_command(config, trade_date),
            cwd=repo_root(),
            output_root=output_root,
            job_dir=job_dir,
            heartbeat_path=heartbeat_path,
            heartbeat_interval_seconds=config.heartbeat_interval_seconds,
            sla=slas["daily_update"],
        ),
        stage_runner,
        "daily_update_exit_code",
    )
    status["daily_update_status"] = daily_update.status
    interface_payload = load_interface_metrics(paths["interface_status"], status["quality_metrics"])
    if daily_update.status != STATUS_PASSED:
        workflow_status = STATUS_FAILED
        status["failure_reason"] = daily_update.failure_reason
    elif interface_payload is None:
        workflow_status = STATUS_FAILED
        status["daily_update_status"] = STATUS_FAILED
        status["failure_reason"] = "daily-update did not produce interface-status.json"
    elif interface_payload.get("overall_status") == STATUS_SKIPPED:
        workflow_status = STATUS_SKIPPED
        status["context_status"] = STATUS_SKIPPED
        status["llm_sections_status"] = STATUS_SKIPPED
        status["html_status"] = STATUS_SKIPPED
    elif interface_payload.get("overall_status") == STATUS_FAILED:
        workflow_status = STATUS_FAILED
        status["failure_reason"] = "daily-update returned failed status"

    if workflow_status == STATUS_RUNNING:
        context = execute_stage(
            status,
            status_file,
            heartbeat_path,
            output_root,
            StageExecution(
                stage="daily_review_context",
                command=build_daily_review_context_command(config, trade_date),
                cwd=repo_root(),
                output_root=output_root,
                job_dir=job_dir,
                heartbeat_path=heartbeat_path,
                heartbeat_interval_seconds=config.heartbeat_interval_seconds,
                sla=slas["daily_review_context"],
            ),
            stage_runner,
            "daily_review_context_exit_code",
        )
        context_payload = load_context_metrics(paths["review_context"], status["quality_metrics"])
        if context.status == STATUS_PASSED and context_payload is not None:
            status["context_status"] = STATUS_PASSED
        else:
            status["context_status"] = STATUS_FAILED
            workflow_status = STATUS_FAILED
            status["failure_reason"] = context.failure_reason or "daily-review context did not produce review-context.json"

    if workflow_status == STATUS_RUNNING and external_background_path is None and config.generate_external_background:
        external_background_path = paths["external_background"]
        prompt = build_external_background_prompt(
            paths["review_context"],
            external_background_path,
            trade_date,
            output_root,
        )
        external_command, log_command = build_claude_command(config, prompt)
        external_background = execute_stage(
            status,
            status_file,
            heartbeat_path,
            output_root,
            StageExecution(
                stage="external_background_fusion",
                command=external_command,
                cwd=repo_root(),
                output_root=output_root,
                job_dir=job_dir,
                heartbeat_path=heartbeat_path,
                heartbeat_interval_seconds=config.heartbeat_interval_seconds,
                sla=slas["external_background_fusion"],
                log_command=log_command,
            ),
            stage_runner,
            "external_background_exit_code",
        )
        status["quality_metrics"]["external_background_log_path"] = external_background.log_path
        external_payload = load_external_background_metrics(external_background_path, status["quality_metrics"], output_root)
        if external_background.status == STATUS_PASSED and external_payload is not None:
            status["quality_metrics"]["external_background_status"] = STATUS_PASSED
        else:
            workflow_status = STATUS_FAILED
            status["quality_metrics"]["external_background_status"] = STATUS_FAILED
            status["failure_reason"] = (
                external_background.failure_reason
                or "Claude Code did not produce a parseable external-background-fusion.json"
            )
    elif workflow_status == STATUS_RUNNING and external_background_path is not None:
        external_payload = load_external_background_metrics(external_background_path, status["quality_metrics"], output_root)
        if external_payload is not None:
            status["quality_metrics"]["external_background_status"] = STATUS_PASSED
        else:
            workflow_status = STATUS_FAILED
            status["quality_metrics"]["external_background_status"] = STATUS_FAILED
            status["failure_reason"] = f"external background JSON is missing or invalid: {external_background_path}"
    elif workflow_status == STATUS_RUNNING:
        status["quality_metrics"]["external_background_status"] = STATUS_SKIPPED

    if workflow_status == STATUS_RUNNING and external_background_path is not None:
        context = execute_stage(
            status,
            status_file,
            heartbeat_path,
            output_root,
            StageExecution(
                stage="daily_review_context_with_external",
                command=build_daily_review_context_command(config, trade_date, external_background_path),
                cwd=repo_root(),
                output_root=output_root,
                job_dir=job_dir,
                heartbeat_path=heartbeat_path,
                heartbeat_interval_seconds=config.heartbeat_interval_seconds,
                sla=slas["daily_review_context_with_external"],
            ),
            stage_runner,
            "daily_review_context_with_external_exit_code",
        )
        context_payload = load_context_metrics(paths["review_context"], status["quality_metrics"])
        if context.status == STATUS_PASSED and context_payload is not None:
            status["context_status"] = STATUS_PASSED
        else:
            status["context_status"] = STATUS_FAILED
            workflow_status = STATUS_FAILED
            status["failure_reason"] = context.failure_reason or "daily-review context with external background did not produce review-context.json"

    if workflow_status == STATUS_RUNNING:
        prompt = build_claude_prompt(paths["review_context"], paths["llm_sections"], trade_date, output_root)
        claude_command, log_command = build_claude_command(config, prompt)
        claude = execute_stage(
            status,
            status_file,
            heartbeat_path,
            output_root,
            StageExecution(
                stage="claude_code_sections",
                command=claude_command,
                cwd=repo_root(),
                output_root=output_root,
                job_dir=job_dir,
                heartbeat_path=heartbeat_path,
                heartbeat_interval_seconds=config.heartbeat_interval_seconds,
                sla=slas["claude_code_sections"],
                log_command=log_command,
            ),
            stage_runner,
            "claude_code_exit_code",
        )
        status["quality_metrics"]["claude_code_log_path"] = claude.log_path
        status["quality_metrics"]["llm_sections_path"] = status_path(paths["llm_sections"], output_root)
        status["quality_metrics"]["llm_sections_exists"] = paths["llm_sections"].exists()
        if claude.status == STATUS_PASSED and validate_json_file(paths["llm_sections"]):
            status["llm_sections_status"] = STATUS_PASSED
        else:
            status["llm_sections_status"] = STATUS_FAILED
            workflow_status = STATUS_FAILED
            status["failure_reason"] = claude.failure_reason or "Claude Code did not produce a parseable llm-review-sections.json"

    if workflow_status == STATUS_RUNNING:
        html = execute_stage(
            status,
            status_file,
            heartbeat_path,
            output_root,
            StageExecution(
                stage="daily_review_html",
                command=build_daily_review_html_command(config, trade_date, paths["llm_sections"], external_background_path),
                cwd=repo_root(),
                output_root=output_root,
                job_dir=job_dir,
                heartbeat_path=heartbeat_path,
                heartbeat_interval_seconds=config.heartbeat_interval_seconds,
                sla=slas["daily_review_html"],
            ),
            stage_runner,
            "daily_review_html_exit_code",
        )
        html_exists = paths["html_report"].exists()
        data_notes_exists = paths["data_notes"].exists()
        status["quality_metrics"]["html_exists"] = html_exists
        status["quality_metrics"]["data_notes_exists"] = data_notes_exists
        status["quality_metrics"]["llm_sections_validated"] = html.status == STATUS_PASSED and html_exists and data_notes_exists
        if html.status == STATUS_PASSED and html_exists and data_notes_exists:
            status["html_status"] = STATUS_PASSED
            report_ready = True
        else:
            status["html_status"] = STATUS_FAILED
            workflow_status = STATUS_FAILED
            status["failure_reason"] = html.failure_reason or "daily-review HTML validation did not produce report artifacts"

    if workflow_status == STATUS_RUNNING:
        workflow_status = STATUS_PARTIAL if status["quality_metrics"].get("daily_update_overall_status") == STATUS_PARTIAL else STATUS_PASSED
    return finalize_status(
        status,
        config,
        output_root,
        status_file,
        heartbeat_path,
        report_ready,
        workflow_status,
        previous_successful_send,
        feishu_sender,
    )


def is_expected_trading_day(trade_date: str, config: JobConfig) -> bool:
    """判断 watchdog 是否应期待当日任务状态文件。"""

    if config.watchdog_assume_trading_day:
        return True
    return parse_trade_date(trade_date).weekday() < 5


def heartbeat_age_seconds(heartbeat_path: Path) -> float | None:
    """计算 heartbeat 文件距离当前时间的秒数。"""

    if not heartbeat_path.exists():
        return None
    modified_at = datetime.fromtimestamp(heartbeat_path.stat().st_mtime, SHANGHAI_TZ)
    return max(0.0, (now_shanghai() - modified_at).total_seconds())


def run_watchdog_check(
    config: JobConfig,
    feishu_sender: FeishuSender = send_feishu_message,
) -> dict[str, Any]:
    """检查预期任务是否缺失或 heartbeat 是否停滞，并按需发送告警。"""

    trade_date = resolve_trade_date(config.trade_date)
    output_root = resolve_output_root(config.output_root)
    job_dir, _, status_file, heartbeat_path = make_job_dirs(output_root, trade_date)
    watchdog_status_path = job_dir / "watchdog-status.json"
    checked_at = iso_timestamp()
    heartbeat_payload = read_json(heartbeat_path) or {}
    age = heartbeat_age_seconds(heartbeat_path)
    expected_deadline_value = expected_job_deadline(trade_date, config)
    should_expect = is_expected_trading_day(trade_date, config)
    alerts: list[dict[str, str]] = []
    missed = False
    stale = False
    payload = read_json(status_file)
    if should_expect and now_shanghai() >= expected_deadline_value and payload is None:
        missed = True
        append_alert(alerts, STATUS_CRITICAL, "watchdog_check", "expected job-status.json is missing after deadline.")
    if payload and payload.get("overall_status") == STATUS_RUNNING:
        if age is None or age > config.watchdog_stale_seconds:
            stale = True
            append_alert(alerts, STATUS_CRITICAL, "watchdog_check", "heartbeat is missing or stale while job is running.")
        current_stage = heartbeat_payload.get("current_stage")
        elapsed = heartbeat_payload.get("current_stage_elapsed_seconds")
        stage_sla = config.slas().get(str(current_stage))
        if stage_sla and isinstance(elapsed, (int, float)) and elapsed > stage_sla.hard_timeout_seconds:
            stale = True
            append_alert(alerts, STATUS_CRITICAL, "watchdog_check", "current stage exceeded hard timeout according to heartbeat.")
    if payload and (payload.get("overall_status") == STATUS_FAILED or payload.get("health_level") == STATUS_CRITICAL):
        append_alert(
            alerts,
            STATUS_CRITICAL,
            "watchdog_check",
            "job-status.json is failed or critical.",
        )
    health_level = STATUS_CRITICAL if alerts else "info"
    status = {
        "schema_version": WATCHDOG_SCHEMA_VERSION,
        "trade_date": trade_date,
        "checked_at": checked_at,
        "overall_status": STATUS_FAILED if alerts else STATUS_PASSED,
        "health_level": health_level,
        "send_status": SEND_SKIPPED,
        "alerts": alerts,
        "quality_metrics": {
            "watchdog_checked_at": checked_at,
            "expected_job_deadline": expected_deadline_value.isoformat(),
            "missed_run_detected": missed,
            "stale_heartbeat_detected": stale,
            "heartbeat_age_seconds": None if age is None else round(age, 3),
            "heartbeat_updated_at": heartbeat_payload.get("updated_at"),
            "current_stage": heartbeat_payload.get("current_stage"),
            "current_stage_elapsed_seconds": heartbeat_payload.get("current_stage_elapsed_seconds"),
        },
        "artifacts": {
            "watchdog_status": status_path(watchdog_status_path, output_root),
            "job_status": status_path(status_file, output_root),
            "heartbeat": status_path(heartbeat_path, output_root),
        },
        "failure_reason": alerts[0]["message"] if alerts else None,
        "not_investment_advice": True,
    }
    if config.send and alerts:
        message = build_alert_message(status, STATUS_CRITICAL)
        send_stage, send_results = run_feishu_send_stage([message], config, output_root, job_dir, feishu_sender)
        status["send_status"] = send_stage.status
        status["send_results"] = send_results
        if send_stage.status != STATUS_PASSED:
            append_alert(status["alerts"], STATUS_CRITICAL, "feishu_send", send_stage.failure_reason or "Feishu send failed.")
            status["failure_reason"] = status["failure_reason"] or send_stage.failure_reason
    write_json(watchdog_status_path, status)
    return status


def build_parser() -> argparse.ArgumentParser:
    """构建每日定时报告任务脚本的命令行参数解析器。"""

    parser = argparse.ArgumentParser(description="Run or check the scheduled A-share daily report job.")
    parser.add_argument("--check-latest", action="store_true", help="Run watchdog check instead of the main job.")
    parser.add_argument("--trade-date", default=None, help="Trade date formatted as YYYY-MM-DD. Defaults to Asia/Shanghai today.")
    parser.add_argument("--output-root", default=".", help="Project output root for data, reports, logs, and status artifacts.")
    parser.add_argument("--python-bin", default=".venv/bin/python", help="Python executable used for public CLI stages.")
    parser.add_argument(
        "--claude-bin",
        default=os.environ.get("CLAUDE_CODE_BIN", "claude"),
        help="Claude Code executable used for non-interactive LLM sections generation.",
    )
    parser.add_argument("--ignore-proxy", action="store_true", help="Pass --ignore-proxy to daily-update.")
    parser.add_argument("--external-background", default=None, help="External background JSON passed consistently to context and HTML stages.")
    parser.add_argument(
        "--skip-external-background",
        action="store_true",
        help="Skip generated external background fusion and render from local A-share context only.",
    )
    parser.add_argument("--send", action="store_true", help="Send report or alert messages through Feishu.")
    parser.add_argument("--send-skipped", action="store_true", help="Send a non-market skipped summary for non-trading days.")
    parser.add_argument("--force-send", action="store_true", help="Override duplicate send guard for the same trade_date.")
    parser.add_argument(
        "--delivery-provider",
        choices=(
            DELIVERY_PROVIDER_FEISHU_WEBHOOK,
            DELIVERY_PROVIDER_OPENCLAW,
            DELIVERY_PROVIDER_OPENCLAW_LEGACY,
            DELIVERY_PROVIDER_OPENCLAW_AGENT,
        ),
        default=DELIVERY_PROVIDER_FEISHU_WEBHOOK,
        help="Message delivery provider for --send.",
    )
    parser.add_argument("--feishu-webhook-env", default="FEISHU_WEBHOOK_URL", help="Environment variable containing the Feishu webhook URL.")
    parser.add_argument("--feishu-secret-env", default="FEISHU_WEBHOOK_SECRET", help="Environment variable containing the Feishu webhook secret.")
    parser.add_argument("--openclaw-bin", default="openclaw", help="OpenClaw executable used by OpenClaw delivery providers.")
    parser.add_argument("--openclaw-channel", default="feishu", help="OpenClaw channel used when delivery-provider=openclaw_message.")
    parser.add_argument("--openclaw-target", default=None, help="OpenClaw message target; defaults to OPENCLAW_FEISHU_TARGET.")
    parser.add_argument("--openclaw-account", default=None, help="Optional OpenClaw channel account id; defaults to OPENCLAW_FEISHU_ACCOUNT.")
    parser.add_argument(
        "--openclaw-report-targets",
        default=None,
        help="Comma-separated OpenClaw Feishu channel targets that receive report messages when delivery-provider=openclaw_message. Each item may be account:target.",
    )
    parser.add_argument(
        "--openclaw-alert-targets",
        default=None,
        help="Comma-separated OpenClaw Feishu channel targets that receive alert/watchdog messages when delivery-provider=openclaw_message. Each item may be account:target.",
    )
    parser.add_argument(
        "--openclaw-report-agents",
        default=os.environ.get("OPENCLAW_REPORT_AGENTS", "main,candy"),
        help="Comma-separated OpenClaw agents that receive report messages when delivery-provider=openclaw_agent.",
    )
    parser.add_argument(
        "--openclaw-alert-agents",
        default=os.environ.get("OPENCLAW_ALERT_AGENTS", "main"),
        help="Comma-separated OpenClaw agents that receive alert/watchdog messages when delivery-provider=openclaw_agent.",
    )
    parser.add_argument("--heartbeat-interval", type=float, default=30.0, help="Seconds between heartbeat updates during subprocess stages.")
    parser.add_argument("--watchdog-stale-seconds", type=float, default=180.0, help="Seconds after which watchdog treats heartbeat as stale.")
    parser.add_argument("--expected-deadline-minutes", type=float, default=90.0, help="Minutes after 16:00 Beijing time when the job is expected to be complete.")
    parser.add_argument("--min-main-rows", type=int, default=MAIN_MIN_ROWS, help="Minimum acceptable main snapshot row count.")
    parser.add_argument("--watchdog-assume-trading-day", action="store_true", help="Force watchdog to expect a job even if the date is not a weekday.")
    return parser


def config_from_args(args: argparse.Namespace) -> JobConfig:
    """把命令行参数和飞书环境变量转换为 JobConfig。"""

    report_targets = resolve_openclaw_target_list(
        args.openclaw_report_targets,
        "OPENCLAW_REPORT_TARGETS",
        "main:oc_d0fc6f1a86e4fad2a43f7b35acaf951a,candy:oc_17f6cf4c298256bda98b2dcc571135f2",
    )
    alert_targets = resolve_openclaw_target_list(
        args.openclaw_alert_targets,
        "OPENCLAW_ALERT_TARGETS",
        "main:oc_d0fc6f1a86e4fad2a43f7b35acaf951a",
    )
    report_agents = parse_openclaw_agent_list(args.openclaw_report_agents)
    alert_agents = parse_openclaw_agent_list(args.openclaw_alert_agents)
    delivery_provider = (
        DELIVERY_PROVIDER_OPENCLAW
        if args.delivery_provider == DELIVERY_PROVIDER_OPENCLAW_LEGACY
        else args.delivery_provider
    )
    return JobConfig(
        trade_date=args.trade_date,
        output_root=Path(args.output_root),
        python_bin=args.python_bin,
        claude_bin=args.claude_bin,
        ignore_proxy=args.ignore_proxy,
        external_background_path=Path(args.external_background) if args.external_background else None,
        generate_external_background=not args.skip_external_background,
        send=args.send,
        send_skipped=args.send_skipped,
        force_send=args.force_send,
        delivery_provider=delivery_provider,
        feishu_webhook_url=os.environ.get(args.feishu_webhook_env),
        feishu_secret=os.environ.get(args.feishu_secret_env),
        openclaw_bin=args.openclaw_bin,
        openclaw_channel=args.openclaw_channel,
        openclaw_target=args.openclaw_target or os.environ.get("OPENCLAW_FEISHU_TARGET"),
        openclaw_account=args.openclaw_account or os.environ.get("OPENCLAW_FEISHU_ACCOUNT"),
        openclaw_report_targets=report_targets,
        openclaw_alert_targets=alert_targets,
        openclaw_report_agents=report_agents,
        openclaw_alert_agents=alert_agents,
        heartbeat_interval_seconds=args.heartbeat_interval,
        min_main_rows=args.min_main_rows,
        watchdog_stale_seconds=args.watchdog_stale_seconds,
        expected_deadline_minutes=args.expected_deadline_minutes,
        watchdog_assume_trading_day=args.watchdog_assume_trading_day,
    )


def parse_comma_separated_list(value: str) -> list[str]:
    """解析逗号分隔配置值，并保留 target 原始名称。"""

    return [item.strip() for item in value.split(",") if item.strip()]


def resolve_openclaw_target_list(value: str | None, env_name: str, default_value: str) -> list[str]:
    """解析 OpenClaw Feishu channel target 列表，未配置时使用生产默认值。"""

    raw_value = value if value is not None else os.environ.get(env_name, default_value)
    return parse_comma_separated_list(raw_value)


def parse_openclaw_agent_list(value: str) -> list[str]:
    """解析逗号分隔的 OpenClaw agent 列表，并兼容 main-agent 这类展示名。"""

    agents: list[str] = []
    for raw_agent in value.split(","):
        agent = raw_agent.strip()
        if not agent:
            continue
        if agent.endswith("-agent"):
            agent = agent[: -len("-agent")]
        agents.append(agent)
    return agents


def main() -> int:
    """运行每日定时报告任务或 watchdog 检查。"""

    parser = build_parser()
    args = parser.parse_args()
    config = config_from_args(args)
    status = run_watchdog_check(config) if args.check_latest else run_daily_report_job(config)
    print(json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if status.get("overall_status") in {STATUS_PASSED, STATUS_PARTIAL, STATUS_SKIPPED} else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise
    except Exception:  # noqa: BLE001 - 顶层入口需要保留 traceback 方便 cron 日志排障。
        import traceback

        traceback.print_exc()
        raise SystemExit(1)
