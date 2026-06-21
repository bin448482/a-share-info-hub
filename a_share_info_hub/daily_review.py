"""基于每日快照产物生成可校验的 A 股每日复盘研究上下文和报告。"""

from __future__ import annotations

import html
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable, Literal

import duckdb
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


ANALYSIS_MODE = "research_only"
CONTEXT_SCHEMA_VERSION = "daily_review_context.v1"
SECTIONS_SCHEMA_VERSION = "daily_review_sections.v1"
REPORT_SCHEMA_VERSION = "daily_review_report.v1"
EXTERNAL_BACKGROUND_SCHEMA_VERSION = "external_background.v1"
EXTERNAL_BACKGROUND_FUSION_SCHEMA_VERSION = "external_background_fusion.v1"
DATA_STATUS_PASSED = "passed"
DATA_STATUS_PARTIAL = "partial"
DATA_STATUS_SKIPPED = "skipped"
DATA_STATUS_FAILED = "failed"
DATA_STATUS_MISSING = "missing"
DATA_STATUS_BLOCKED = "blocked"
REFRESH_NONE = "none"
REFRESH_DAILY_UPDATE = "daily_update"
OUTPUT_HTML = "html"
OUTPUT_INLINE = "inline"
OUTPUT_MARKDOWN = "markdown"
OUTPUT_CONTEXT = "context"
RENDER_LLM = "llm"
RENDER_DETERMINISTIC = "deterministic"
EXTERNAL_STATUS_NOT_PROVIDED = "not_provided"
EXTERNAL_STATUS_PASSED = "passed"
EXTERNAL_STATUS_PARTIAL = "partial"
EXTERNAL_STATUS_BLOCKED = "blocked"
EXTERNAL_STATUS_INVALID = "invalid"
REPORT_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _validate_report_date(value: str, field_name: str) -> str:
    """校验报告日期格式并保留字段名错误语义。"""

    if not REPORT_DATE_RE.fullmatch(value):
        raise ValueError(f"{field_name} must be formatted as YYYY-MM-DD")
    return value


TABLE_FILES = {
    "daily_stock_snapshot": "daily_stock_snapshot.parquet",
    "limit_pool_events": "limit_pool_events.parquet",
    "lhb_events": "lhb_events.parquet",
    "market_summary": "market_summary.parquet",
    "board_snapshot": "board_snapshot.parquet",
}

CATEGORY_TO_SECTION = {
    "limit_pool": "limit_pool_events",
    "lhb": "lhb_events",
    "market_summary": "market_summary",
    "board_snapshot": "board_snapshot",
}

SECTION_DISPLAY_NAMES = {
    "market_width": "市场宽度",
    "limit_pool_events": "涨跌停情绪",
    "lhb_events": "龙虎榜",
    "market_summary": "市场汇总",
    "board_snapshot": "板块结构",
    "duckdb": "DuckDB",
    "daily_run": "每日运行状态",
    "daily_update": "每日数据刷新",
}

TRADE_ACTION_PATTERNS = (
    "可以买",
    "买什么",
    "卖什么",
    "加仓",
    "减仓",
    "仓位",
    "目标价",
    "止盈",
    "止损",
    "实盘",
)

FORBIDDEN_OUTPUT_TERMS = (
    "建议买入",
    "建议卖出",
    "买入建议",
    "卖出建议",
    "仓位建议",
    "目标价",
    "止盈",
    "止损",
    "加仓",
    "减仓",
    "明日必涨",
    "确定性主线",
    "强烈看多",
    "强烈看空",
)

BLOCKED_SECTION_FORBIDDEN_TERMS = {
    "board_snapshot": ("板块主线", "领涨板块", "板块确认", "结构主线"),
    "limit_pool_events": ("涨停情绪确认", "连板主线", "情绪强势确认"),
    "lhb_events": ("龙虎榜确认", "机构抢筹", "游资主导"),
    "market_summary": ("市场汇总确认",),
}

HTML_BODY_FORBIDDEN_TERMS = (
    "passed",
    "partial",
    "blocked",
    "invalid",
    "blocked_sections",
    "board_snapshot",
    "stock_board_industry_name_em",
    "stock_board_concept_name_em",
    "stock_lhb_detail_em",
    "stock_lhb_detail_daily_sina",
    "stock_lhb_jgmmtj_em",
    "strong_limit_up",
    "sub_new_limit_up",
    "previous_limit_up",
    "broken_board",
    "limit_down",
    "data_status: partial",
    "ConnectionError",
    "RemoteDisconnected",
    "Traceback",
    "external_background.status",
    "external_background_status",
    "schema_version",
    "render_mode",
    "fixture",
    "模拟",
    "模拟输入",
    "HTML 展示形态",
)

LOW_INFORMATION_EXTERNAL_PHRASES = (
    "只能作为待验证变量",
    "只能作为风险偏好约束",
    "不能替代本地",
    "不能覆盖本地",
    "仍需用 A 股行情",
    "仍需用A股行情",
    "仍需用本地 A 股数据验证",
    "只是背景变量",
    "作为背景变量",
    "约束全球风险偏好",
    "可能继续影响全球风险偏好",
    "是否会在 A 股市场宽度、板块和情绪数据中得到验证",
)

EXTERNAL_DETAIL_MARKERS = (
    "FOMC",
    "CPI",
    "PCE",
    "非农",
    "失业率",
    "初请",
    "美债",
    "收益率",
    "利差",
    "美元指数",
    "人民币",
    "汇率",
    "通胀",
    "联邦基金",
    "政策声明",
    "高盛",
    "摩根",
    "花旗",
    "瑞银",
    "投行",
    "机构观点",
    "基点",
    "%",
)

LOCAL_VALIDATION_MARKERS = (
    "上涨家数",
    "下跌家数",
    "极端上涨",
    "极端下跌",
    "市场宽度",
    "涨跌停",
    "龙虎榜",
    "板块",
    "成交",
    "行业",
    "样本",
    "汇率",
    "成长",
    "半导体",
)


class SourceHealth(BaseModel):
    """描述单个数据源、文件或存储组件的可用性。"""

    model_config = ConfigDict(extra="forbid")

    name: str
    category: str = ""
    status: str
    row_count: int | None = None
    source_path: str | None = None
    issue: str | None = None


class ReviewFact(BaseModel):
    """保存可被 LLM 引用的单条事实及其来源。"""

    model_config = ConfigDict(extra="forbid")

    section: str
    description: str
    source: str
    value: Any = None


class ExternalBackgroundCitation(BaseModel):
    """描述外部背景核心点的公开来源引用。"""

    model_config = ConfigDict(extra="forbid")

    source_name: str
    title: str = ""
    published_at: str = ""
    accessed_at: str = ""
    url: str

    @model_validator(mode="after")
    def require_source_and_url(self) -> "ExternalBackgroundCitation":
        """确保引用至少包含来源名称和 URL。"""

        if not self.source_name.strip():
            raise ValueError("citation.source_name is required")
        if not self.url.strip():
            raise ValueError("citation.url is required")
        return self


class ExternalBackgroundCorePoint(BaseModel):
    """描述可进入每日复盘的外部宏观或机构观点摘要。"""

    model_config = ConfigDict(extra="forbid")

    text: str
    type: Literal["fact", "market_expectation", "bank_view", "inference"]
    a_share_relevance: str = ""
    citations: list[ExternalBackgroundCitation] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_text_and_citation(self) -> "ExternalBackgroundCorePoint":
        """确保核心点有正文和至少一个合格引用。"""

        if not self.text.strip():
            raise ValueError("core point text is required")
        if not self.citations:
            raise ValueError("core point citations are required")
        return self


class ExternalBackgroundRawCitation(BaseModel):
    """保存外部背景输入中的原始引用，允许后续逐条过滤。"""

    model_config = ConfigDict(extra="ignore")

    source_name: str = ""
    title: str = ""
    published_at: str = ""
    accessed_at: str = ""
    url: str = ""


class ExternalBackgroundRawCorePoint(BaseModel):
    """保存外部背景输入中的原始核心点，允许后续逐条降级。"""

    model_config = ConfigDict(extra="ignore")

    text: str = ""
    type: str = ""
    a_share_relevance: str = ""
    citations: list[ExternalBackgroundRawCitation] = Field(default_factory=list)


class ExternalBackgroundFusionFinding(BaseModel):
    """保存外部背景融合输入中的主题相关结论候选。"""

    model_config = ConfigDict(extra="ignore")

    text: str = ""
    type: str = "inference"
    report_usage: str = ""
    local_relevance: str = ""
    citations: list[ExternalBackgroundRawCitation] = Field(default_factory=list)


class ExternalBackgroundFusionInput(BaseModel):
    """约束 agent 汇总后的外部背景融合输入包。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["external_background_fusion.v1"] = EXTERNAL_BACKGROUND_FUSION_SCHEMA_VERSION
    source_skill: Literal["daily-financial-briefing"]
    trade_date: str
    not_investment_advice: Literal[True]
    topic_findings: list[ExternalBackgroundFusionFinding] = Field(default_factory=list)
    risk_candidates: list[str] = Field(default_factory=list)
    follow_up_candidates: list[str] = Field(default_factory=list)
    citations: list[ExternalBackgroundRawCitation] = Field(default_factory=list)
    information_gaps: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)

    @field_validator("trade_date")
    @classmethod
    def validate_trade_date(cls, value: str) -> str:
        """校验外部背景融合包日期格式。"""

        return _validate_report_date(value, "trade_date")


class ExternalBackgroundInput(BaseModel):
    """约束由 daily-financial-briefing 产出的外部背景 JSON。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["external_background.v1"] = EXTERNAL_BACKGROUND_SCHEMA_VERSION
    source_skill: Literal["daily-financial-briefing"]
    briefing_date: str
    scope: list[str] = Field(default_factory=list)
    not_investment_advice: Literal[True]
    core_points: list[ExternalBackgroundRawCorePoint] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    information_gaps: list[str] = Field(default_factory=list)
    blocked: bool = False
    blocked_reason: str = ""

    @field_validator("briefing_date")
    @classmethod
    def validate_briefing_date(cls, value: str) -> str:
        """校验外部背景日期格式，避免自然语言日期进入契约。"""

        return _validate_report_date(value, "briefing_date")


class ExternalBackgroundContext(BaseModel):
    """保存进入 review-context.json 的外部背景状态和受控摘要。"""

    model_config = ConfigDict(extra="forbid")

    status: Literal["not_provided", "passed", "partial", "blocked", "invalid"] = EXTERNAL_STATUS_NOT_PROVIDED
    briefing_date: str | None = None
    source_skill: str | None = None
    input_path: str | None = None
    core_points: list[ExternalBackgroundCorePoint] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    information_gaps: list[str] = Field(default_factory=list)
    citations: list[ExternalBackgroundCitation] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


class ReviewContext(BaseModel):
    """约束传给 LLM 的每日复盘 evidence packet。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["daily_review_context.v1"] = CONTEXT_SCHEMA_VERSION
    analysis_mode: Literal["research_only"] = ANALYSIS_MODE
    not_investment_advice: Literal[True] = True
    trade_date: str
    data_status: Literal["passed", "partial", "skipped", "failed", "missing"]
    data_sources_used: list[str] = Field(default_factory=list)
    blocked_sections: list[str] = Field(default_factory=list)
    source_health: dict[str, SourceHealth] = Field(default_factory=dict)
    market_breadth: dict[str, Any] = Field(default_factory=dict)
    limit_pool: dict[str, Any] = Field(default_factory=dict)
    lhb: dict[str, Any] = Field(default_factory=dict)
    market_summary: dict[str, Any] = Field(default_factory=dict)
    board_snapshot: dict[str, Any] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)
    allowed_sections: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(default_factory=list)
    facts: list[ReviewFact] = Field(default_factory=list)
    external_background: ExternalBackgroundContext = Field(default_factory=ExternalBackgroundContext)

    @field_validator("trade_date")
    @classmethod
    def validate_trade_date(cls, value: str) -> str:
        """校验交易日期格式，避免混入自然语言日期。"""

        return _validate_report_date(value, "trade_date")


class LlmReviewSections(BaseModel):
    """约束 LLM 输出的复盘分析结构。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["daily_review_sections.v1"] = SECTIONS_SCHEMA_VERSION
    headline: str
    summary: list[str] = Field(default_factory=list)
    market_overview_assessment: str = ""
    market_overview_structure: str = ""
    market_breadth_review: str = ""
    sentiment_and_events_review: str = ""
    board_and_structure_review: str = ""
    risk_observations: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    external_background_review: str = ""
    external_background_risks: list[str] = Field(default_factory=list)
    external_background_follow_up_questions: list[str] = Field(default_factory=list)
    external_background_boundary_note: str = ""
    data_boundary_note: str
    not_investment_advice_note: str

    @model_validator(mode="after")
    def require_core_sections(self) -> "LlmReviewSections":
        """确保 LLM 输出具备可读报告的基本段落。"""

        if not self.headline.strip():
            raise ValueError("headline is required")
        if not self.summary:
            raise ValueError("summary must not be empty")
        if not self.market_overview_assessment.strip():
            raise ValueError("market_overview_assessment is required")
        if not self.market_overview_structure.strip():
            raise ValueError("market_overview_structure is required")
        if not self.risk_observations:
            raise ValueError("risk_observations must not be empty")
        if not self.follow_up_questions:
            raise ValueError("follow_up_questions must not be empty")
        if not self.data_boundary_note.strip():
            raise ValueError("data_boundary_note is required")
        if not self.not_investment_advice_note.strip():
            raise ValueError("not_investment_advice_note is required")
        return self


class ValidatedReviewReport(BaseModel):
    """保存通过结构和业务校验后可渲染为 HTML 的报告对象。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["daily_review_report.v1"] = REPORT_SCHEMA_VERSION
    context: ReviewContext
    sections: LlmReviewSections
    report_artifact: str | None = None
    render_mode: Literal["llm", "deterministic"] = RENDER_LLM


@dataclass
class DailyReviewRequest:
    """保存每日复盘请求的显式参数和从提示词推导出的偏好。"""

    trade_date: str | None = None
    output_root: Path = Path(".")
    output_format: str = OUTPUT_HTML
    refresh_mode: str = REFRESH_NONE
    render_mode: str = RENDER_LLM
    llm_output_path: Path | None = None
    focus: str | None = None
    ignore_proxy: bool = False
    user_prompt: str | None = None
    external_background_path: Path | None = None


@dataclass
class ReviewState:
    """保存从每日运行产物读取出的状态、表数据和可解释问题。"""

    trade_date: str
    data_status: str
    status_path: Path | None = None
    summary_path: Path | None = None
    status_payload: dict[str, Any] = field(default_factory=dict)
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    data_sources_used: list[str] = field(default_factory=list)
    blocked_sections: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    duckdb_status: str = DATA_STATUS_MISSING
    duckdb_failure: str | None = None


@dataclass
class DailyReviewResult:
    """保存复盘生成结果和 CLI 需要展示的返回信息。"""

    analysis_mode: str
    not_investment_advice: bool
    trade_date: str | None
    data_status: str
    data_sources_used: list[str]
    blocked_sections: list[str]
    report_artifact: str | None
    output_format: str
    message: str
    data_notes_artifact: str | None = None
    markdown: str = ""
    html: str = ""
    context_artifact: str | None = None
    llm_output_artifact: str | None = None
    render_mode: str = RENDER_LLM
    validation_errors: list[str] = field(default_factory=list)
    refresh_command: str | None = None
    refresh_exit_code: int | None = None


def infer_request_from_prompt(user_prompt: str, output_root: Path) -> DailyReviewRequest:
    """从用户自然语言提示词中推导每日复盘请求参数。"""

    prompt_lower = user_prompt.lower()
    trade_date_match = REPORT_DATE_RE.search(user_prompt)
    wants_context = "review-context" in prompt_lower or "evidence packet" in prompt_lower or "证据包" in user_prompt
    wants_context_only = wants_context and any(
        marker in user_prompt for marker in ("只生成", "只需要", "仅生成", "只要")
    )
    wants_html = "html" in prompt_lower or "report" in prompt_lower or "报告" in user_prompt
    wants_inline = "不用生成 html" in prompt_lower or "直接" in user_prompt or "诊断" in user_prompt
    refresh_negated = any(
        marker in user_prompt
        for marker in ("不刷新", "不用刷新", "不要刷新", "只使用当前", "只使用已有", "不更新", "不用更新", "不要更新")
    )
    refresh_requested = (
        not refresh_negated
        and ("刷新" in user_prompt or "更新" in user_prompt or "daily-update" in user_prompt)
    )
    if wants_context_only and not wants_html and not wants_inline:
        output_format = OUTPUT_CONTEXT
    elif wants_inline:
        output_format = OUTPUT_INLINE
    else:
        output_format = OUTPUT_HTML if wants_html else OUTPUT_HTML
    if "markdown" in prompt_lower:
        output_format = OUTPUT_MARKDOWN
    return DailyReviewRequest(
        trade_date=trade_date_match.group(0) if trade_date_match else None,
        output_root=output_root,
        output_format=output_format,
        refresh_mode=REFRESH_DAILY_UPDATE if refresh_requested else REFRESH_NONE,
        render_mode=RENDER_LLM,
        focus=user_prompt,
        user_prompt=user_prompt,
    )


def contains_trade_action_request(user_prompt: str | None) -> bool:
    """判断用户提示词是否在请求交易行动建议。"""

    if not user_prompt:
        return False
    normalized = user_prompt.lower()
    return any(pattern in normalized for pattern in TRADE_ACTION_PATTERNS)


def build_daily_update_command(
    trade_date: str, output_root: Path, ignore_proxy: bool = False
) -> list[str]:
    """构造公开每日更新 CLI 命令，不直接引用采集脚本路径。"""

    command = [
        sys.executable,
        "-m",
        "a_share_info_hub",
        "daily-update",
        "--trade-date",
        trade_date,
        "--output-root",
        str(output_root),
    ]
    if ignore_proxy:
        command.append("--ignore-proxy")
    return command


def render_public_daily_update_command(trade_date: str, ignore_proxy: bool = False) -> str:
    """渲染面向用户的每日更新命令。"""

    parts = [
        "python",
        "-m",
        "a_share_info_hub",
        "daily-update",
        "--trade-date",
        trade_date,
    ]
    if ignore_proxy:
        parts.append("--ignore-proxy")
    return " ".join(parts)


def generate_daily_review_from_prompt(
    user_prompt: str,
    output_root: Path = Path("."),
    render_mode: str = RENDER_LLM,
    llm_output_path: Path | None = None,
    external_background_path: Path | None = None,
    refresh_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> DailyReviewResult:
    """按用户提示词调用每日复盘流程，覆盖 HTML、诊断和安全拒绝场景。"""

    request = infer_request_from_prompt(user_prompt, output_root)
    request.render_mode = render_mode
    request.llm_output_path = llm_output_path
    request.external_background_path = external_background_path
    if contains_trade_action_request(user_prompt):
        trade_date = request.trade_date or find_latest_trade_date(output_root)
        return render_trade_action_refusal(trade_date)
    return generate_daily_review(request, refresh_runner=refresh_runner)


def generate_daily_review(
    request: DailyReviewRequest,
    refresh_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> DailyReviewResult:
    """读取每日运行产物，生成 context，并按请求校验渲染报告。"""

    output_root = request.output_root
    output_format = request.output_format
    if output_format not in {OUTPUT_HTML, OUTPUT_INLINE, OUTPUT_MARKDOWN, OUTPUT_CONTEXT}:
        raise ValueError(f"unsupported output format: {output_format}")
    if request.refresh_mode not in {REFRESH_NONE, REFRESH_DAILY_UPDATE}:
        raise ValueError(f"unsupported refresh mode: {request.refresh_mode}")
    if request.render_mode not in {RENDER_LLM, RENDER_DETERMINISTIC}:
        raise ValueError(f"unsupported render mode: {request.render_mode}")

    trade_date = request.trade_date
    if request.refresh_mode == REFRESH_DAILY_UPDATE:
        trade_date = trade_date or date.today().strftime("%Y-%m-%d")
        refresh_result = run_daily_update_for_review(
            trade_date,
            output_root,
            request.ignore_proxy,
            refresh_runner=refresh_runner,
        )
        if refresh_result is not None:
            return refresh_result

    resolved_trade_date = trade_date or find_latest_trade_date(output_root)
    if resolved_trade_date is None:
        return render_missing_run_result(None, output_format)

    state = collect_review_state(output_root, resolved_trade_date)
    context = build_review_context(state)
    context.external_background = load_external_background_context(
        request.external_background_path,
        resolved_trade_date,
    )
    context_path = write_review_context(output_root, context)

    if output_format == OUTPUT_CONTEXT:
        return render_context_result(context, context_path, output_format, request.render_mode)
    if context.data_status in {DATA_STATUS_SKIPPED, DATA_STATUS_FAILED, DATA_STATUS_MISSING}:
        return render_blocked_context_result(context, context_path, output_format, request.render_mode)

    if request.render_mode == RENDER_LLM and request.llm_output_path is None:
        return render_llm_required_result(context, context_path, output_format)

    try:
        sections = load_or_build_sections(context, request)
        report_artifact = None
        if output_format == OUTPUT_HTML:
            report_artifact = str(daily_review_report_path(output_root, resolved_trade_date))
        report = build_validated_report(context, sections, report_artifact, request.render_mode)
    except (ValidationError, ValueError) as exc:
        return render_validation_failure_result(context, context_path, output_format, request.render_mode, exc)

    if output_format == OUTPUT_HTML:
        html_report = render_html_review(report)
        data_notes_artifact = str(daily_review_data_notes_path(output_root, resolved_trade_date))
        data_notes = render_data_notes_markdown(report, context_path)
        validate_data_notes_diagnostics(context, data_notes)
        write_html_report(Path(report.report_artifact or ""), html_report)
        write_data_notes(Path(data_notes_artifact), data_notes)
        message = render_cli_message(report, context_path, data_notes_artifact)
        return DailyReviewResult(
            analysis_mode=ANALYSIS_MODE,
            not_investment_advice=True,
            trade_date=context.trade_date,
            data_status=context.data_status,
            data_sources_used=context.data_sources_used,
            blocked_sections=context.blocked_sections,
            report_artifact=report.report_artifact,
            output_format=output_format,
            message=message,
            data_notes_artifact=data_notes_artifact,
            html=html_report,
            context_artifact=str(context_path),
            llm_output_artifact=str(request.llm_output_path) if request.llm_output_path else None,
            render_mode=request.render_mode,
        )

    markdown = render_markdown_from_report(report)
    message = markdown if output_format in {OUTPUT_INLINE, OUTPUT_MARKDOWN} else render_cli_message(report, context_path)
    return DailyReviewResult(
        analysis_mode=ANALYSIS_MODE,
        not_investment_advice=True,
        trade_date=context.trade_date,
        data_status=context.data_status,
        data_sources_used=context.data_sources_used,
        blocked_sections=context.blocked_sections,
        report_artifact=None,
        output_format=output_format,
        message=message,
        markdown=markdown,
        context_artifact=str(context_path),
        llm_output_artifact=str(request.llm_output_path) if request.llm_output_path else None,
        render_mode=request.render_mode,
    )


def run_daily_update_for_review(
    trade_date: str,
    output_root: Path,
    ignore_proxy: bool,
    refresh_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> DailyReviewResult | None:
    """通过公开 CLI 刷新每日数据，失败时返回阻断结果。"""

    command = build_daily_update_command(trade_date, output_root, ignore_proxy)
    runner = refresh_runner or subprocess.run
    completed = runner(command, capture_output=True, text=True)
    if completed.returncode == 0:
        return None

    public_command = render_public_daily_update_command(trade_date, ignore_proxy)
    stderr = (completed.stderr or completed.stdout or "").strip()
    if len(stderr) > 600:
        stderr = stderr[:600] + "..."
    message = "\n".join(
        [
            "analysis_mode: research_only",
            "not_investment_advice: true",
            f"trade_date: {trade_date}",
            "data_status: failed",
            "report_artifact: null",
            "",
            "每日数据刷新失败，已阻断完整复盘。",
            f"可复查命令：{public_command}",
            f"退出码：{completed.returncode}",
            f"失败摘要：{stderr or '无 stderr 输出'}",
        ]
    )
    return DailyReviewResult(
        analysis_mode=ANALYSIS_MODE,
        not_investment_advice=True,
        trade_date=trade_date,
        data_status=DATA_STATUS_FAILED,
        data_sources_used=[],
        blocked_sections=["daily_update"],
        report_artifact=None,
        output_format=OUTPUT_INLINE,
        message=message,
        markdown=message,
        render_mode=RENDER_LLM,
        refresh_command=public_command,
        refresh_exit_code=completed.returncode,
    )


def find_latest_trade_date(output_root: Path) -> str | None:
    """从 daily run 目录中找出最近一次运行日期。"""

    daily_runs = output_root / "reports" / "daily-runs"
    if not daily_runs.exists():
        return None
    candidates = [
        path.name
        for path in daily_runs.iterdir()
        if path.is_dir() and REPORT_DATE_RE.fullmatch(path.name)
    ]
    return sorted(candidates)[-1] if candidates else None


def collect_review_state(output_root: Path, trade_date: str) -> ReviewState:
    """读取指定交易日的状态报告、标准化表和 DuckDB 可用性。"""

    status_path = output_root / "reports" / "daily-runs" / trade_date / "interface-status.json"
    summary_path = output_root / "reports" / "daily-runs" / trade_date / "daily-data-summary.md"
    if not status_path.exists():
        return ReviewState(
            trade_date=trade_date,
            data_status=DATA_STATUS_MISSING,
            status_path=status_path,
            summary_path=summary_path if summary_path.exists() else None,
            blocked_sections=["daily_run"],
            issues=[f"缺少状态文件：{status_path}"],
        )

    try:
        status_payload = json.loads(status_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return ReviewState(
            trade_date=trade_date,
            data_status=DATA_STATUS_FAILED,
            status_path=status_path,
            summary_path=summary_path if summary_path.exists() else None,
            blocked_sections=["daily_run"],
            issues=[f"状态文件不可解析：{exc}"],
            data_sources_used=[str(status_path)],
        )

    state = ReviewState(
        trade_date=trade_date,
        data_status=status_payload.get("overall_status", DATA_STATUS_MISSING),
        status_path=status_path,
        summary_path=summary_path if summary_path.exists() else None,
        status_payload=status_payload,
        data_sources_used=[str(status_path)],
    )
    if state.summary_path:
        state.data_sources_used.append(str(state.summary_path))
    if state.data_status == DATA_STATUS_SKIPPED:
        apply_skipped_status_rules(state)
        dedupe_state_lists(state)
        return state

    load_normalized_tables(output_root, state)
    inspect_duckdb(output_root, state)
    apply_status_rules(state)
    dedupe_state_lists(state)
    return state


def load_normalized_tables(output_root: Path, state: ReviewState) -> None:
    """读取标准化 Parquet 表并按交易日期过滤。"""

    normalized_root = output_root / "data" / "normalized"
    for table_name, file_name in TABLE_FILES.items():
        table_path = normalized_root / file_name
        if not table_path.exists():
            state.issues.append(f"缺少标准化表：{table_path}")
            if table_name == "daily_stock_snapshot":
                state.blocked_sections.extend(["market_width", "limit_pool_events", "lhb_events", "board_snapshot"])
            else:
                state.blocked_sections.append(table_name)
            continue
        try:
            table = pd.read_parquet(table_path)
        except Exception as exc:  # noqa: BLE001 - report must surface local artifact failures.
            state.issues.append(f"标准化表不可读取：{table_path} ({type(exc).__name__}: {exc})")
            if table_name == "daily_stock_snapshot":
                state.blocked_sections.extend(["market_width", "limit_pool_events", "lhb_events", "board_snapshot"])
            else:
                state.blocked_sections.append(table_name)
            continue
        if "trade_date" in table.columns:
            table = table[table["trade_date"].astype(str) == state.trade_date].copy()
        state.tables[table_name] = table
        state.data_sources_used.append(str(table_path))


def inspect_duckdb(output_root: Path, state: ReviewState) -> None:
    """检查 DuckDB 是否可查询指定交易日期的主表。"""

    database_path = output_root / "market.duckdb"
    if not database_path.exists():
        state.duckdb_status = DATA_STATUS_MISSING
        state.duckdb_failure = f"缺少 DuckDB：{database_path}"
        state.blocked_sections.append("duckdb")
        state.issues.append(state.duckdb_failure)
        return

    try:
        with duckdb.connect(str(database_path), read_only=True) as connection:
            connection.execute(
                "SELECT COUNT(*) FROM daily_stock_snapshot WHERE trade_date = ?",
                [state.trade_date],
            ).fetchone()
    except Exception as exc:  # noqa: BLE001 - local storage failures must be visible.
        state.duckdb_status = DATA_STATUS_FAILED
        state.duckdb_failure = f"DuckDB 查询失败：{type(exc).__name__}: {exc}"
        state.blocked_sections.append("duckdb")
        state.issues.append(state.duckdb_failure)
        return

    state.duckdb_status = DATA_STATUS_PASSED
    state.data_sources_used.append(str(database_path))


def apply_status_rules(state: ReviewState) -> None:
    """根据状态报告和可读表情况计算最终复盘状态。"""

    main_table = state.tables.get("daily_stock_snapshot", pd.DataFrame())
    main_source = next(
        (
            source
            for source in state.status_payload.get("sources", [])
            if source.get("category") == "main"
        ),
        {},
    )
    if state.data_status == DATA_STATUS_MISSING:
        return
    if state.data_status == DATA_STATUS_SKIPPED:
        return
    if state.status_payload.get("overall_status") == DATA_STATUS_FAILED:
        state.data_status = DATA_STATUS_FAILED
    if main_source.get("status") != "success" or main_table.empty:
        state.data_status = DATA_STATUS_FAILED
        state.blocked_sections.extend(["market_width", "limit_pool_events", "lhb_events", "board_snapshot"])
        state.issues.append("主表失败、缺失或指定日期无记录。")
        return

    for source in state.status_payload.get("sources", []):
        category = source.get("category")
        status = source.get("status")
        if category == "main":
            continue
        if status in {"failed", "schema_changed"}:
            state.data_status = DATA_STATUS_PARTIAL
            section = CATEGORY_TO_SECTION.get(category, str(category))
            state.blocked_sections.append(section)
            reason = source.get("failure_reason") or status
            state.issues.append(f"{source.get('source_key')} 状态为 {status}：{reason}")

    for table_name in ("limit_pool_events", "lhb_events", "market_summary", "board_snapshot"):
        if table_name not in state.tables:
            state.data_status = DATA_STATUS_PARTIAL
            state.blocked_sections.append(table_name)

    if state.duckdb_status != DATA_STATUS_PASSED:
        state.data_status = DATA_STATUS_PARTIAL
    if state.status_payload.get("overall_status") == DATA_STATUS_PARTIAL:
        state.data_status = DATA_STATUS_PARTIAL
    if state.data_status not in {DATA_STATUS_FAILED, DATA_STATUS_PARTIAL, DATA_STATUS_SKIPPED, DATA_STATUS_MISSING}:
        state.data_status = DATA_STATUS_PASSED


def apply_skipped_status_rules(state: ReviewState) -> None:
    """把非交易日跳过状态转换为复盘可解释的阻断边界。"""

    check = state.status_payload.get("trading_day_check", {})
    reason = str(check.get("reason") or "目标日期不是 A 股交易日。")
    state.data_status = DATA_STATUS_SKIPPED
    state.duckdb_status = str(state.status_payload.get("duckdb_status") or DATA_STATUS_SKIPPED)
    state.blocked_sections.extend(
        [
            "market_width",
            "limit_pool_events",
            "lhb_events",
            "market_summary",
            "board_snapshot",
            "duckdb",
        ]
    )
    state.issues.append(f"非交易日跳过采集：{reason}")


def dedupe_state_lists(state: ReviewState) -> None:
    """保持状态列表稳定去重，方便测试和报告 review。"""

    state.blocked_sections = sorted(set(state.blocked_sections))
    state.issues = list(dict.fromkeys(state.issues))
    state.data_sources_used = list(dict.fromkeys(state.data_sources_used))


def build_review_context(state: ReviewState) -> ReviewContext:
    """把读取状态转换为可传给 LLM 的 evidence packet。"""

    facts: list[ReviewFact] = []
    source_health = build_source_health(state)
    market_breadth = build_market_breadth_payload(state, facts)
    limit_pool = build_table_payload(state, "limit_pool_events", "limit_pool", facts)
    lhb = build_table_payload(state, "lhb_events", "lhb", facts)
    market_summary = build_table_payload(state, "market_summary", "market_summary", facts)
    board_snapshot = build_table_payload(state, "board_snapshot", "board_snapshot", facts)
    context = ReviewContext(
        trade_date=state.trade_date,
        data_status=state.data_status,
        data_sources_used=state.data_sources_used,
        blocked_sections=state.blocked_sections,
        source_health=source_health,
        market_breadth=market_breadth,
        limit_pool=limit_pool,
        lhb=lhb,
        market_summary=market_summary,
        board_snapshot=board_snapshot,
        issues=state.issues,
        allowed_sections=derive_allowed_sections(state),
        forbidden_claims=derive_forbidden_claims(state),
        facts=facts,
    )
    return context


def load_external_background_context(path: Path | None, trade_date: str) -> ExternalBackgroundContext:
    """读取并校验可选外部背景 JSON，失败时只降级外部背景状态。"""

    if path is None:
        return ExternalBackgroundContext()
    issues: list[str] = []
    if not path.exists():
        return ExternalBackgroundContext(
            status=EXTERNAL_STATUS_INVALID,
            input_path=str(path),
            issues=[f"外部背景文件不存在：{path}"],
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return ExternalBackgroundContext(
            status=EXTERNAL_STATUS_INVALID,
            input_path=str(path),
            issues=[f"外部背景 JSON 不可解析：{exc}"],
        )
    if contains_forbidden_trading_terms(json.dumps(payload, ensure_ascii=False)):
        return ExternalBackgroundContext(
            status=EXTERNAL_STATUS_INVALID,
            input_path=str(path),
            issues=["外部背景包含交易行动语言，已阻断进入 HTML。"],
        )
    schema_version = payload.get("schema_version") if isinstance(payload, dict) else ""
    if schema_version == EXTERNAL_BACKGROUND_FUSION_SCHEMA_VERSION:
        return load_external_background_fusion_context(payload, path, trade_date)
    try:
        parsed = ExternalBackgroundInput.model_validate(payload)
    except ValidationError as exc:
        return ExternalBackgroundContext(
            status=EXTERNAL_STATUS_INVALID,
            input_path=str(path),
            issues=[f"外部背景结构校验失败：{exc}"],
        )

    if parsed.blocked:
        reason = parsed.blocked_reason.strip() or "daily-financial-briefing 未产出可用外部背景。"
        return ExternalBackgroundContext(
            status=EXTERNAL_STATUS_BLOCKED,
            briefing_date=parsed.briefing_date,
            source_skill=parsed.source_skill,
            input_path=str(path),
            information_gaps=parsed.information_gaps,
            issues=[reason],
        )

    accepted_points: list[ExternalBackgroundCorePoint] = []
    rejected_reasons: list[str] = []
    for index, point in enumerate(parsed.core_points, start=1):
        converted = coerce_external_core_point(point)
        if converted is None:
            rejected_reasons.append(f"第 {index} 条外部背景缺少正文、合法类型、来源名称或 URL。")
        else:
            accepted_points.append(converted)
    if rejected_reasons:
        issues.extend(rejected_reasons)
    if not accepted_points:
        return ExternalBackgroundContext(
            status=EXTERNAL_STATUS_INVALID,
            briefing_date=parsed.briefing_date,
            source_skill=parsed.source_skill,
            input_path=str(path),
            information_gaps=parsed.information_gaps,
            issues=issues or ["外部背景没有任何带来源名称和 URL 的核心点。"],
        )

    citations = flatten_external_citations(accepted_points)
    status = EXTERNAL_STATUS_PASSED
    information_gaps = list(parsed.information_gaps)
    if parsed.briefing_date != trade_date:
        status = EXTERNAL_STATUS_PARTIAL
        issues.append(f"外部背景日期 {parsed.briefing_date} 与复盘交易日 {trade_date} 不一致，只能作为非当日背景。")
        information_gaps.append("仍需用当日 A 股行情、板块和情绪数据验证非当日外部背景。")
    if issues:
        status = EXTERNAL_STATUS_PARTIAL if status == EXTERNAL_STATUS_PASSED else status
    if information_gaps:
        status = EXTERNAL_STATUS_PARTIAL if status == EXTERNAL_STATUS_PASSED else status
    return ExternalBackgroundContext(
        status=status,
        briefing_date=parsed.briefing_date,
        source_skill=parsed.source_skill,
        input_path=str(path),
        core_points=accepted_points,
        follow_up_questions=parsed.follow_up_questions,
        information_gaps=information_gaps,
        citations=citations,
        issues=issues,
    )


def load_external_background_fusion_context(
    payload: dict[str, Any], path: Path, trade_date: str
) -> ExternalBackgroundContext:
    """读取 agent 汇总后的外部背景融合包并映射到现有 context 契约。"""

    try:
        parsed = ExternalBackgroundFusionInput.model_validate(payload)
    except ValidationError as exc:
        return ExternalBackgroundContext(
            status=EXTERNAL_STATUS_INVALID,
            input_path=str(path),
            issues=[f"外部背景融合包结构校验失败：{exc}"],
        )
    accepted_points: list[ExternalBackgroundCorePoint] = []
    rejected_reasons: list[str] = list(parsed.issues)
    for index, finding in enumerate(parsed.topic_findings, start=1):
        converted = coerce_external_fusion_finding(finding)
        if converted is None:
            rejected_reasons.append(f"第 {index} 条外部融合结论缺少正文、合法类型、来源名称或 URL。")
        else:
            accepted_points.append(converted)
    inline_citations = flatten_external_citations(accepted_points)
    standalone_citations = coerce_external_citations(parsed.citations)
    citations = merge_external_citations(inline_citations, standalone_citations)
    status = EXTERNAL_STATUS_PASSED
    information_gaps = list(parsed.information_gaps)
    if parsed.trade_date != trade_date:
        status = EXTERNAL_STATUS_PARTIAL
        rejected_reasons.append(f"外部背景融合包日期 {parsed.trade_date} 与复盘交易日 {trade_date} 不一致，只能作为非当日背景。")
        information_gaps.append("仍需用当日 A 股行情、板块和情绪数据验证非当日外部背景。")
    if not accepted_points and not parsed.risk_candidates and not parsed.follow_up_candidates:
        status = EXTERNAL_STATUS_INVALID
        if not rejected_reasons:
            rejected_reasons.append("外部背景融合包没有可用主题结论、风险候选或待验证问题。")
    elif not citations:
        status = EXTERNAL_STATUS_INVALID
        rejected_reasons.append("外部背景融合包没有任何带来源名称和 URL 的引用。")
    elif rejected_reasons or information_gaps:
        status = EXTERNAL_STATUS_PARTIAL if status == EXTERNAL_STATUS_PASSED else status
    return ExternalBackgroundContext(
        status=status,
        briefing_date=parsed.trade_date,
        source_skill=parsed.source_skill,
        input_path=str(path),
        core_points=accepted_points,
        follow_up_questions=parsed.follow_up_candidates,
        information_gaps=information_gaps,
        citations=citations,
        issues=rejected_reasons,
    )


def coerce_external_fusion_finding(
    finding: ExternalBackgroundFusionFinding,
) -> ExternalBackgroundCorePoint | None:
    """把融合包主题结论转换为受控核心点。"""

    raw_point = ExternalBackgroundRawCorePoint(
        text=finding.text,
        type=finding.type,
        a_share_relevance=finding.local_relevance,
        citations=finding.citations,
    )
    return coerce_external_core_point(raw_point)


def coerce_external_citations(
    raw_citations: list[ExternalBackgroundRawCitation],
) -> list[ExternalBackgroundCitation]:
    """把融合包顶层引用转换为带来源和 URL 的引用列表。"""

    return [citation for raw in raw_citations if (citation := _coerce_external_citation(raw))]


def _coerce_external_citation(citation: ExternalBackgroundRawCitation) -> ExternalBackgroundCitation | None:
    """把单条原始引用转换为带来源和 URL 的受控引用。"""

    if not citation.source_name.strip() or not citation.url.strip():
        return None
    return ExternalBackgroundCitation(
        source_name=citation.source_name.strip(),
        title=citation.title.strip(),
        published_at=citation.published_at.strip(),
        accessed_at=citation.accessed_at.strip(),
        url=citation.url.strip(),
    )


def merge_external_citations(
    first: list[ExternalBackgroundCitation],
    second: list[ExternalBackgroundCitation],
) -> list[ExternalBackgroundCitation]:
    """按来源和 URL 合并两组外部引用。"""

    merged: list[ExternalBackgroundCitation] = []
    seen: set[tuple[str, str]] = set()
    for citation in [*first, *second]:
        key = (citation.source_name, citation.url)
        if key in seen:
            continue
        seen.add(key)
        merged.append(citation)
    return merged


def flatten_external_citations(points: list[ExternalBackgroundCorePoint]) -> list[ExternalBackgroundCitation]:
    """提取外部背景核心点中的去重引用列表。"""

    citations: list[ExternalBackgroundCitation] = []
    seen: set[tuple[str, str]] = set()
    for point in points:
        for citation in point.citations:
            key = (citation.source_name, citation.url)
            if key in seen:
                continue
            seen.add(key)
            citations.append(citation)
    return citations


def coerce_external_core_point(point: ExternalBackgroundRawCorePoint) -> ExternalBackgroundCorePoint | None:
    """把原始外部背景核心点转换为带完整引用的受控对象。"""

    if point.type not in {"fact", "market_expectation", "bank_view", "inference"}:
        return None
    citations = coerce_external_citations(point.citations)
    if not point.text.strip() or not citations:
        return None
    return ExternalBackgroundCorePoint(
        text=point.text.strip(),
        type=point.type,  # type: ignore[arg-type]
        a_share_relevance=point.a_share_relevance.strip(),
        citations=citations,
    )


def build_source_health(state: ReviewState) -> dict[str, SourceHealth]:
    """把接口状态、文件状态和 DuckDB 状态整理为可校验对象。"""

    health: dict[str, SourceHealth] = {}
    if state.status_path:
        health["interface_status"] = SourceHealth(
            name="interface-status.json",
            category="run_status",
            status="readable" if state.status_path.exists() else DATA_STATUS_MISSING,
            source_path=str(state.status_path),
        )
    if state.summary_path:
        health["daily_data_summary"] = SourceHealth(
            name="daily-data-summary.md",
            category="run_summary",
            status="readable",
            source_path=str(state.summary_path),
        )
    trading_day_check = state.status_payload.get("trading_day_check")
    if isinstance(trading_day_check, dict):
        health["trading_day_check"] = SourceHealth(
            name="trading_day_check",
            category="run_status",
            status=str(trading_day_check.get("status") or "unknown"),
            issue=trading_day_check.get("reason"),
        )
    for source in state.status_payload.get("sources", []):
        key = str(source.get("source_key") or source.get("category") or "unknown")
        health[key] = SourceHealth(
            name=key,
            category=str(source.get("category") or ""),
            status=str(source.get("status") or "unknown"),
            row_count=coerce_optional_int(source.get("row_count")),
            issue=source.get("failure_reason"),
        )
    for table_name, table in state.tables.items():
        health[f"table:{table_name}"] = SourceHealth(
            name=table_name,
            category="normalized_table",
            status="readable",
            row_count=len(table),
            source_path=str(Path("data") / "normalized" / TABLE_FILES.get(table_name, "")),
        )
    health["duckdb"] = SourceHealth(
        name="market.duckdb",
        category="storage",
        status=state.duckdb_status,
        issue=state.duckdb_failure,
    )
    return health


def build_market_breadth_payload(state: ReviewState, facts: list[ReviewFact]) -> dict[str, Any]:
    """根据主表生成市场宽度 facts，不输出最终自然语言报告。"""

    table = state.tables.get("daily_stock_snapshot", pd.DataFrame())
    if "market_width" in state.blocked_sections or table.empty:
        return {"status": "blocked", "reason": "daily_stock_snapshot unavailable for trade_date"}
    change_pct = pd.to_numeric(table.get("change_pct"), errors="coerce")
    amount = pd.to_numeric(table.get("amount"), errors="coerce")
    payload = {
        "status": "available",
        "sample_count": int(len(table)),
        "up_count": int((change_pct > 0).sum()),
        "down_count": int((change_pct < 0).sum()),
        "flat_count": int((change_pct == 0).sum()),
        "extreme_up_count": int((change_pct >= 9.5).sum()),
        "extreme_down_count": int((change_pct <= -9.5).sum()),
        "total_amount": float(amount.sum(skipna=True)) if not amount.empty else None,
        "total_amount_display": format_large_number(amount.sum(skipna=True)) if not amount.empty else "不可用",
    }
    add_fact(facts, "market_breadth", "主表样本数量", "daily_stock_snapshot", payload["sample_count"])
    add_fact(facts, "market_breadth", "上涨样本数量", "daily_stock_snapshot", payload["up_count"])
    add_fact(facts, "market_breadth", "下跌样本数量", "daily_stock_snapshot", payload["down_count"])
    return payload


def build_table_payload(
    state: ReviewState,
    table_name: str,
    section: str,
    facts: list[ReviewFact],
) -> dict[str, Any]:
    """把增强表转换为 LLM 可引用的受控 payload。"""

    table = state.tables.get(table_name, pd.DataFrame())
    if table_name in state.blocked_sections:
        return {"status": "blocked", "reason": f"{table_name} is listed in blocked_sections"}
    if table.empty:
        return {"status": "empty", "row_count": 0}
    payload: dict[str, Any] = {"status": "available", "row_count": int(len(table))}
    add_fact(facts, section, f"{table_name} 记录数", table_name, len(table))
    if table_name == "limit_pool_events":
        if "pool_type" in table.columns:
            payload["pool_type_counts"] = series_counts_to_dict(table["pool_type"].value_counts().head(8))
        if "industry" in table.columns:
            industries = table["industry"].dropna().astype(str)
            payload["top_industries"] = series_counts_to_dict(industries.value_counts().head(8))
    elif table_name == "lhb_events":
        if "event_type" in table.columns:
            payload["event_type_counts"] = series_counts_to_dict(table["event_type"].value_counts().head(8))
    elif table_name == "board_snapshot":
        payload["top_boards"] = extract_top_boards(table)
    return payload


def add_fact(facts: list[ReviewFact], section: str, description: str, source: str, value: Any) -> None:
    """向 context 中追加一条可引用事实。"""

    facts.append(ReviewFact(section=section, description=description, source=source, value=value))


def derive_allowed_sections(state: ReviewState) -> list[str]:
    """根据数据状态推导 LLM 允许生成的报告章节。"""

    if state.data_status == DATA_STATUS_SKIPPED:
        return ["non_trading_day_note", "data_boundary"]
    if state.data_status in {DATA_STATUS_FAILED, DATA_STATUS_MISSING}:
        return ["data_quality_diagnosis", "repair_steps"]
    sections = ["data_status", "market_breadth", "sentiment_and_events", "risks", "follow_up_questions"]
    if "board_snapshot" not in state.blocked_sections:
        sections.append("board_and_structure")
    return sections


def derive_forbidden_claims(state: ReviewState) -> list[str]:
    """根据数据状态和 blocked sections 生成禁止 LLM 输出的结论边界。"""

    claims = [
        "buy/sell/hold/position sizing/price target/stop-loss/take-profit/trading action advice",
        "multi-day trend, backtest, win-rate, or prediction claims from a single daily snapshot",
    ]
    if state.data_status == DATA_STATUS_PARTIAL:
        claims.append("claiming the review is complete while data_status is partial")
    if state.data_status == DATA_STATUS_SKIPPED:
        claims.append("market conclusions for a non-trading day")
    for section in state.blocked_sections:
        display = SECTION_DISPLAY_NAMES.get(section, section)
        claims.append(f"positive or complete conclusions about blocked section: {display}")
    return claims


def write_review_context(output_root: Path, context: ReviewContext) -> Path:
    """写入已通过 Pydantic 校验的 review-context.json。"""

    context_path = daily_review_context_path(output_root, context.trade_date)
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.write_text(context.model_dump_json(indent=2), encoding="utf-8")
    return context_path


def daily_review_context_path(output_root: Path, trade_date: str) -> Path:
    """计算指定交易日 evidence packet 路径。"""

    return output_root / "reports" / "daily-reviews" / trade_date / "review-context.json"


def load_or_build_sections(context: ReviewContext, request: DailyReviewRequest) -> LlmReviewSections:
    """读取 LLM sections JSON，或在确定性模式下生成 fallback sections。"""

    if request.llm_output_path is not None:
        return load_llm_sections(request.llm_output_path)
    if request.render_mode == RENDER_DETERMINISTIC:
        return build_deterministic_sections(context, request.focus)
    raise ValueError("llm_output_path is required when render_mode=llm")


def load_llm_sections(path: Path) -> LlmReviewSections:
    """从 JSON 文件读取并校验 LLM 生成的复盘 sections。"""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM output is not valid JSON: {exc}") from exc
    return LlmReviewSections.model_validate(payload)


def build_deterministic_sections(context: ReviewContext, focus: str | None = None) -> LlmReviewSections:
    """为本地测试和 Promptfoo fixture 生成确定性 fallback sections。"""

    is_diagnosis = bool(focus and "诊断" in focus)
    summary = [
        f"本报告由策略分析师面向普通投资者撰写，只基于 {context.trade_date} 已获取的公开市场快照。",
    ]
    market_breadth = render_market_breadth_sentence(context)
    if context.market_breadth.get("status") == "available":
        summary.append(market_breadth)
    if context.limit_pool.get("status") == "available" or context.lhb.get("status") == "available":
        summary.append("涨跌停情绪和龙虎榜事件可作为当日活跃方向线索，但仍需要后续交易日验证。")
    if context.board_snapshot.get("status") != "available":
        summary.append("板块层面的确认依据不足，因此不把行业线索直接上升为明确市场主线。")
    if is_diagnosis:
        summary.insert(0, "数据质量诊断：先列出可读数据、缺口和修复建议，不做市场判断。")
    sentiment = render_sentiment_sentence(context)
    board = render_board_sentence(context)
    risks = ["本报告只基于单日快照，不能直接推出多日趋势、胜率或预测。"]
    if context.data_status == DATA_STATUS_PARTIAL:
        risks.append("部分增强维度的证据不足，因此结构判断需要保持保守。")
    if "duckdb" in context.blocked_sections:
        risks.append("本次查询存在本地存储降级，关键结论应优先回到原始快照复核。")
    if is_diagnosis and context.blocked_sections:
        risks.append(f"blocked_sections: {', '.join(context.blocked_sections)}。")
        risks.append("修复建议：优先复查对应接口或重新运行公开 daily-update CLI。")
    follow_up = [
        "研究建议：把本次输出作为观察清单，而不是交易行动清单。",
        "后续可把涨跌停集中行业与主表涨跌分布按代码交叉，判断活跃线索是否具备扩散性。",
        "后续可把龙虎榜事件与极端涨跌样本交叉，区分事件扰动和全市场宽度压力。",
        "待验证：后续补齐连续交易日数据后，再判断当日情绪观察是否具备持续性。",
    ]
    if focus and "风险" in focus:
        follow_up.insert(0, "先确认哪些结论只有单日证据支持，再决定哪些观察值得继续跟踪。")
    return LlmReviewSections(
        headline=f"{context.trade_date} 数据质量诊断" if is_diagnosis else f"{context.trade_date} A 股每日复盘研究",
        summary=summary,
        market_overview_assessment=render_market_overview_assessment(context),
        market_overview_structure=render_market_overview_structure(context),
        market_breadth_review=market_breadth,
        sentiment_and_events_review=sentiment,
        board_and_structure_review=board,
        risk_observations=risks,
        follow_up_questions=follow_up,
        external_background_review=render_external_background_review(context),
        external_background_risks=render_external_background_risks(context),
        external_background_follow_up_questions=render_external_background_follow_up_questions(context),
        external_background_boundary_note=render_external_background_boundary_note(context),
        data_boundary_note="本报告只引用已生成的复盘证据包；详细数据状态和接口说明见同目录技术参考文件。",
        not_investment_advice_note="本报告仅用于研究复盘，不构成投资建议。",
    )


def render_market_overview_assessment(context: ReviewContext) -> str:
    """生成每日复盘中“大盘观察 / 大盘定性”的 fallback 文本。"""

    payload = context.market_breadth
    if payload.get("status") != "available":
        return "主表证据不足，不能给出大盘定性判断。"
    up_count = payload.get("up_count", 0)
    down_count = payload.get("down_count", 0)
    flat_count = payload.get("flat_count", 0)
    direction = "偏弱" if down_count > up_count else "偏强"
    return (
        f"从已获取的全市场快照看，主表覆盖 {payload.get('sample_count')} 只证券，"
        f"上涨 {up_count} 只、下跌 {down_count} 只、平盘 {flat_count} 只，"
        f"大盘定性为单日宽度{direction}。这个判断只反映当日横截面，不代表多日趋势。"
    )


def render_market_overview_structure(context: ReviewContext) -> str:
    """生成每日复盘中“大盘观察 / 大盘结构”的 fallback 文本。"""

    payload = context.market_breadth
    if payload.get("status") != "available":
        return "主表证据不足，不能展开大盘结构判断。"
    up_count = payload.get("up_count", 0)
    down_count = payload.get("down_count", 0)
    extreme_up_count = payload.get("extreme_up_count", 0)
    extreme_down_count = payload.get("extreme_down_count", 0)
    if down_count > up_count:
        structure = "多数个股承压、局部强势仍在的分化结构"
    elif up_count > down_count:
        structure = "上涨覆盖面更占优、但仍需要观察扩散质量的结构"
    else:
        structure = "涨跌分布接近均衡、方向感不强的结构"
    boundary = (
        "板块层面的确认依据不足，相关结构判断保持保守。"
        if "board_snapshot" in context.blocked_sections
        else "板块快照可作为结构参考，但仍需要后续交易日交叉验证。"
    )
    return (
        f"大盘结构呈现{structure}；极端上涨样本 {extreme_up_count} 只，"
        f"极端下跌样本 {extreme_down_count} 只，说明强弱样本同时存在。{boundary}"
    )


def render_market_breadth_sentence(context: ReviewContext) -> str:
    """把 context 中的市场宽度 payload 转换为 fallback 文本。"""

    payload = context.market_breadth
    if payload.get("status") != "available":
        return "主表不可用，不能生成市场宽度观察。"
    direction = "偏弱" if payload.get("down_count", 0) > payload.get("up_count", 0) else "偏强"
    return (
        f"主表覆盖 {payload.get('sample_count')} 只证券，上涨 {payload.get('up_count')} 只，"
        f"下跌 {payload.get('down_count')} 只，平盘 {payload.get('flat_count')} 只，"
        f"单日市场宽度{direction}；极端上涨样本 {payload.get('extreme_up_count')} 只，"
        f"极端下跌样本 {payload.get('extreme_down_count')} 只。"
    )


def render_sentiment_sentence(context: ReviewContext) -> str:
    """把情绪和事件 payload 转换为 fallback 文本。"""

    parts: list[str] = []
    if context.limit_pool.get("status") == "available":
        parts.append(f"涨跌停情绪池记录 {context.limit_pool.get('row_count')} 条")
    elif "limit_pool_events" in context.blocked_sections:
        parts.append("涨跌停情绪池证据不足，本节不补推断")
    if context.lhb.get("status") == "available":
        parts.append(f"龙虎榜事件记录 {context.lhb.get('row_count')} 条")
    elif "lhb_events" in context.blocked_sections:
        parts.append("龙虎榜事件证据不足，本节不补推断")
    if not parts:
        return "情绪与事件数据为空，仅能说明当前没有可用记录。"
    return "；".join(parts) + "。这些线索可用于后续交叉验证，不单独构成趋势判断。"


def render_board_sentence(context: ReviewContext) -> str:
    """把板块 payload 转换为 fallback 文本。"""

    if "board_snapshot" in context.blocked_sections:
        return "板块层面的确认依据不足，因此本报告不把涨跌停情绪中的行业集中直接上升为市场主线。"
    if context.board_snapshot.get("status") != "available":
        return "板块层面的确认记录为空，因此结构观察保持保守。"
    top_boards = context.board_snapshot.get("top_boards") or []
    if top_boards:
        rendered = ", ".join(f"{item['board_name']}({item['change_pct']:.2f}%)" for item in top_boards)
        return f"板块快照记录 {context.board_snapshot.get('row_count')} 条；涨跌幅靠前板块：{rendered}。"
    return f"板块快照记录 {context.board_snapshot.get('row_count')} 条。"


def render_external_background_review(context: ReviewContext) -> str:
    """把外部背景核心点转换为不会覆盖本地结论的摘要文本。"""

    background = context.external_background
    if background.status in {EXTERNAL_STATUS_BLOCKED, EXTERNAL_STATUS_INVALID}:
        return ""
    if background.status == EXTERNAL_STATUS_NOT_PROVIDED:
        return ""
    snippets = []
    for point in background.core_points[:4]:
        if not is_actionable_external_text(f"{point.text} {point.a_share_relevance}"):
            continue
        prefix = "机构观点" if point.type == "bank_view" else "外部背景"
        snippets.append(f"{prefix}：{point.text}")
    return "；".join(snippets)


def render_external_background_risks(context: ReviewContext) -> list[str]:
    """生成外部背景相关风险观察，只保留有信息增量的机制句。"""

    background = context.external_background
    if background.status not in {EXTERNAL_STATUS_PASSED, EXTERNAL_STATUS_PARTIAL}:
        return []
    risks: list[str] = []
    for point in background.core_points:
        candidate = build_actionable_external_observation(point)
        if candidate:
            risks.append(candidate)
    if background.status == EXTERNAL_STATUS_PARTIAL:
        risks.append("外部背景存在日期或来源缺口，不能作为当日 A 股结论。")
    return risks


def render_external_background_follow_up_questions(context: ReviewContext) -> list[str]:
    """生成外部背景待验证问题，避免泛化验证句和交易行动化。"""

    background = context.external_background
    if background.status not in {EXTERNAL_STATUS_PASSED, EXTERNAL_STATUS_PARTIAL}:
        return []
    questions = [
        question
        for question in background.follow_up_questions[:3]
        if is_actionable_external_text(question)
    ]
    return questions


def render_external_background_boundary_note(context: ReviewContext) -> str:
    """生成外部背景的用户可读边界说明。"""

    background = context.external_background
    if background.status == EXTERNAL_STATUS_NOT_PROVIDED:
        return ""
    if background.status == EXTERNAL_STATUS_BLOCKED:
        reason = "；".join(background.issues) if background.issues else "外部背景来源不可用。"
        return f"外部背景状态为 blocked：{reason}"
    if background.status == EXTERNAL_STATUS_INVALID:
        reason = "；".join(background.issues) if background.issues else "外部背景未通过校验。"
        return f"外部背景状态为 invalid：{reason}"
    if background.status == EXTERNAL_STATUS_PARTIAL:
        return "外部背景仅作非当日或不完整背景参考，不能覆盖本地 A 股快照证据。"
    return "外部背景来自 daily-financial-briefing 受控摘要，仅用于风险观察和待验证问题。"


def build_validated_report(
    context: ReviewContext,
    sections: LlmReviewSections,
    report_artifact: str | None,
    render_mode: str,
) -> ValidatedReviewReport:
    """执行业务规则校验并返回可渲染报告。"""

    prepared_sections = prepare_sections_for_public_report(context, sections)
    validate_report_business_rules(context, prepared_sections)
    return ValidatedReviewReport(
        context=context,
        sections=prepared_sections,
        report_artifact=report_artifact,
        render_mode=render_mode,  # type: ignore[arg-type]
    )


def prepare_sections_for_public_report(context: ReviewContext, sections: LlmReviewSections) -> LlmReviewSections:
    """把兼容的外部背景字段融合进主报告 section，并清空旧独立字段。"""

    validate_external_background_sections(context, sections)
    background = context.external_background
    clear_external_fields = {
        "external_background_review": "",
        "external_background_risks": [],
        "external_background_follow_up_questions": [],
        "external_background_boundary_note": "",
    }
    if background.status not in {EXTERNAL_STATUS_PASSED, EXTERNAL_STATUS_PARTIAL}:
        return sections.model_copy(update=clear_external_fields)

    external_review = clean_public_external_text(sections.external_background_review)
    external_risks = [
        item.strip()
        for item in sections.external_background_risks
        if clean_public_external_text(item)
    ]
    external_questions = [
        item.strip()
        for item in sections.external_background_follow_up_questions
        if clean_public_external_text(item)
    ]
    update: dict[str, Any] = dict(clear_external_fields)
    merged_external_risks = external_risks
    if external_review:
        merged_external_risks = [external_review, *external_risks]
    update["risk_observations"] = merge_unique_texts(sections.risk_observations, merged_external_risks)
    update["follow_up_questions"] = merge_unique_texts(sections.follow_up_questions, external_questions)
    return sections.model_copy(update=update)


def clean_public_external_text(text: str) -> str:
    """返回可进入用户正文的外部背景文本，低信息或工程词时丢弃。"""

    stripped = text.strip()
    if not stripped:
        return ""
    if any(term in stripped for term in HTML_BODY_FORBIDDEN_TERMS):
        return ""
    if not is_actionable_external_text(stripped):
        return ""
    return stripped


def build_actionable_external_observation(point: ExternalBackgroundCorePoint) -> str:
    """把单条外部背景转换为具备机制和本地指标映射的风险观察。"""

    combined = f"{point.text} {point.a_share_relevance}".strip()
    if not is_actionable_external_text(combined):
        return ""
    if point.a_share_relevance.strip():
        return f"{point.text.strip()} 对 A 股的观察口径：{point.a_share_relevance.strip()}"
    return point.text.strip()


def is_actionable_external_text(text: str) -> bool:
    """判断外部背景文本是否具备进入用户正文的信息密度。"""

    normalized = text.strip()
    if not normalized:
        return False
    if any(phrase in normalized for phrase in LOW_INFORMATION_EXTERNAL_PHRASES):
        return False
    has_external_detail = any(marker in normalized for marker in EXTERNAL_DETAIL_MARKERS)
    has_local_mapping = any(marker in normalized for marker in LOCAL_VALIDATION_MARKERS)
    return has_external_detail and has_local_mapping


def merge_unique_texts(primary: list[str], secondary: list[str]) -> list[str]:
    """合并列表文本并保持原顺序去重。"""

    merged: list[str] = []
    seen: set[str] = set()
    for item in [*primary, *secondary]:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        merged.append(normalized)
    return merged


def validate_report_business_rules(context: ReviewContext, sections: LlmReviewSections) -> None:
    """校验 Pydantic 无法表达的复盘业务边界。"""

    text = sections_to_plain_text(sections)
    enforce_research_boundary(text)
    if "数据质量诊断" not in sections.headline:
        enforce_user_report_language_boundary(text)
        enforce_external_information_density_boundary(text)
    for blocked_section, forbidden_terms in BLOCKED_SECTION_FORBIDDEN_TERMS.items():
        if blocked_section in context.blocked_sections:
            violations = blocked_section_conclusion_violations(text, forbidden_terms)
            if violations:
                raise ValueError(f"blocked section {blocked_section} is referenced as a conclusion: {violations}")
    if "board_snapshot" in context.blocked_sections:
        board_text = sections.board_and_structure_review
        if board_text and not describes_blocked_or_limited_data(board_text):
            raise ValueError("board_and_structure_review must only describe the board_snapshot data gap")
    if context.data_status == DATA_STATUS_PARTIAL and claims_complete_review(text):
        raise ValueError("partial reports must not claim to be complete")


def sections_to_plain_text(sections: LlmReviewSections) -> str:
    """把 LLM sections 合并成便于禁用词和 blocked 规则检查的文本。"""

    parts = [
        sections.headline,
        *sections.summary,
        sections.market_overview_assessment,
        sections.market_overview_structure,
        sections.market_breadth_review,
        sections.sentiment_and_events_review,
        sections.board_and_structure_review,
        *sections.risk_observations,
        *sections.follow_up_questions,
        sections.data_boundary_note,
        sections.not_investment_advice_note,
    ]
    return "\n".join(part for part in parts if part)


def validate_external_background_sections(context: ReviewContext, sections: LlmReviewSections) -> None:
    """校验外部背景字段不会越过本地证据和非投资建议边界。"""

    background = context.external_background
    has_external_output = any(
        [
            sections.external_background_review.strip(),
            sections.external_background_risks,
            sections.external_background_follow_up_questions,
        ]
    )
    if background.status not in {EXTERNAL_STATUS_PASSED, EXTERNAL_STATUS_PARTIAL} and has_external_output:
        raise ValueError("external background sections must stay empty unless external_background is passed or partial")
    combined = "\n".join(
        [
            sections.external_background_review,
            *sections.external_background_risks,
            *sections.external_background_follow_up_questions,
        ]
    )
    enforce_research_boundary(combined)
    if claims_external_background_overrides_local_data(combined):
        raise ValueError("external background must not override or complete local A-share evidence")


def claims_external_background_overrides_local_data(text: str) -> bool:
    """判断外部背景是否被写成覆盖本地证据的确定性结论。"""

    forbidden_phrases = (
        "外部背景确认A股",
        "外部背景确认 A 股",
        "机构观点确认A股",
        "机构观点确认 A 股",
        "补全本地缺失",
        "覆盖本地",
        "确定A股",
        "确定 A 股",
    )
    for phrase in forbidden_phrases:
        for match in re.finditer(re.escape(phrase), text):
            prefix = text[max(0, match.start() - 16) : match.start()]
            if not any(marker in prefix for marker in ("不", "不能", "不得", "禁止", "避免", "不可")):
                return True
    return False


def describes_blocked_or_limited_data(text: str) -> bool:
    """判断一段 blocked section 文本是否只是在说明数据缺口。"""

    allowed_markers = ("受限", "缺失", "不能", "不可用", "未获取", "不足", "不补推断")
    return any(marker in text for marker in allowed_markers)


def enforce_user_report_language_boundary(text: str) -> None:
    """阻断用户正文中的内部字段、接口名和技术错误。"""

    violations = [term for term in HTML_BODY_FORBIDDEN_TERMS if term in text]
    if violations:
        raise ValueError(f"review output exposes internal diagnostics in user sections: {violations}")


def enforce_external_information_density_boundary(text: str) -> None:
    """阻断用户正文中的低信息外部背景套话。"""

    violations = [phrase for phrase in LOW_INFORMATION_EXTERNAL_PHRASES if phrase in text]
    if violations:
        raise ValueError(f"review output contains low-information external background language: {violations}")


def blocked_section_conclusion_violations(text: str, terms: tuple[str, ...]) -> list[str]:
    """找出 blocked section 术语是否被作为正向结论使用。"""

    violations: list[str] = []
    for term in terms:
        for match in re.finditer(re.escape(term), text):
            window = text[max(0, match.start() - 20) : match.end() + 20]
            if not describes_blocked_or_limited_data(window):
                violations.append(term)
                break
    return violations


def claims_complete_review(text: str) -> bool:
    """判断文本是否在 partial 状态下正向宣称完整复盘。"""

    for match in re.finditer("完整复盘", text):
        prefix = text[max(0, match.start() - 16) : match.start()]
        if not any(marker in prefix for marker in ("不", "不能", "不得", "禁止", "避免", "不可")):
            return True
    return False


def render_context_result(
    context: ReviewContext,
    context_path: Path,
    output_format: str,
    render_mode: str,
) -> DailyReviewResult:
    """返回只生成 evidence packet 时的 CLI 结果。"""

    message = "\n".join(
        [
            "analysis_mode: research_only",
            "not_investment_advice: true",
            f"trade_date: {context.trade_date}",
            f"data_status: {context.data_status}",
            f"context_artifact: {context_path}",
            "report_artifact: null",
        ]
    )
    return DailyReviewResult(
        analysis_mode=ANALYSIS_MODE,
        not_investment_advice=True,
        trade_date=context.trade_date,
        data_status=context.data_status,
        data_sources_used=context.data_sources_used,
        blocked_sections=context.blocked_sections,
        report_artifact=None,
        output_format=output_format,
        message=message,
        context_artifact=str(context_path),
        render_mode=render_mode,
    )


def render_llm_required_result(
    context: ReviewContext,
    context_path: Path,
    output_format: str,
) -> DailyReviewResult:
    """返回等待 LLM sections JSON 的中间状态。"""

    suggested_output = context_path.with_name("llm-review-sections.json")
    message = "\n".join(
        [
            "analysis_mode: research_only",
            "not_investment_advice: true",
            f"trade_date: {context.trade_date}",
            f"data_status: {context.data_status}",
            f"context_artifact: {context_path}",
            "report_artifact: null",
            "llm_output_required: true",
            "",
            "已生成 review-context.json。下一步应让 LLM 只基于该 context 生成 sections JSON，",
            f"然后运行：{render_llm_render_command(context, suggested_output, output_format)}",
        ]
    )
    return DailyReviewResult(
        analysis_mode=ANALYSIS_MODE,
        not_investment_advice=True,
        trade_date=context.trade_date,
        data_status=context.data_status,
        data_sources_used=context.data_sources_used,
        blocked_sections=context.blocked_sections,
        report_artifact=None,
        output_format=output_format,
        message=message,
        context_artifact=str(context_path),
        render_mode=RENDER_LLM,
    )


def render_llm_render_command(context: ReviewContext, llm_output: Path, output_format: str) -> str:
    """渲染从 context 进入 HTML/inline 校验阶段的公开 CLI 命令。"""

    parts = [
        "python",
        "-m",
        "a_share_info_hub",
        "daily-review",
        "--trade-date",
        context.trade_date,
        "--llm-output",
        str(llm_output),
        "--output-format",
        output_format,
    ]
    if context.external_background.input_path:
        parts.extend(["--external-background", context.external_background.input_path])
    return " ".join(parts)


def render_blocked_context_result(
    context: ReviewContext,
    context_path: Path,
    output_format: str,
    render_mode: str,
) -> DailyReviewResult:
    """返回 skipped、failed 或 missing 状态下的阻断结果。"""

    command = render_public_daily_update_command(context.trade_date)
    issue_lines = "\n".join(f"- {issue}" for issue in (context.issues or ["缺少可用于复盘的关键数据。"]))
    if context.data_status == DATA_STATUS_SKIPPED:
        action_line = "目标日期不是 A 股交易日，已跳过行情采集和市场复盘。"
        next_step_line = "如需复盘，请指定最近一个 A 股交易日。"
    else:
        action_line = "已阻断完整市场复盘。"
        next_step_line = f"可先运行：{command}"
    message = "\n".join(
        [
            "analysis_mode: research_only",
            "not_investment_advice: true",
            f"trade_date: {context.trade_date}",
            f"data_status: {context.data_status}",
            f"context_artifact: {context_path}",
            "report_artifact: null",
            "",
            action_line,
            "阻断原因：",
            issue_lines,
            "",
            next_step_line,
        ]
    )
    return DailyReviewResult(
        analysis_mode=ANALYSIS_MODE,
        not_investment_advice=True,
        trade_date=context.trade_date,
        data_status=context.data_status,
        data_sources_used=context.data_sources_used,
        blocked_sections=context.blocked_sections,
        report_artifact=None,
        output_format=output_format,
        message=message,
        markdown=message,
        context_artifact=str(context_path),
        render_mode=render_mode,
    )


def render_validation_failure_result(
    context: ReviewContext,
    context_path: Path,
    output_format: str,
    render_mode: str,
    exc: Exception,
) -> DailyReviewResult:
    """返回 LLM 输出或业务规则校验失败结果。"""

    error = str(exc)
    message = "\n".join(
        [
            "analysis_mode: research_only",
            "not_investment_advice: true",
            f"trade_date: {context.trade_date}",
            f"data_status: {context.data_status}",
            f"context_artifact: {context_path}",
            "report_artifact: null",
            "validation_status: failed",
            "",
            "LLM sections 未通过运行时校验，已阻断 HTML 生成。",
            f"失败摘要：{error}",
        ]
    )
    return DailyReviewResult(
        analysis_mode=ANALYSIS_MODE,
        not_investment_advice=True,
        trade_date=context.trade_date,
        data_status=DATA_STATUS_FAILED,
        data_sources_used=context.data_sources_used,
        blocked_sections=context.blocked_sections,
        report_artifact=None,
        output_format=output_format,
        message=message,
        markdown=message,
        context_artifact=str(context_path),
        render_mode=render_mode,
        validation_errors=[error],
    )


def render_missing_run_result(trade_date: str | None, output_format: str) -> DailyReviewResult:
    """生成找不到任意 daily run 时的阻断结果。"""

    display_date = trade_date or "<YYYY-MM-DD>"
    command = render_public_daily_update_command(display_date)
    message = "\n".join(
        [
            "analysis_mode: research_only",
            "not_investment_advice: true",
            f"trade_date: {display_date}",
            "data_status: missing",
            "report_artifact: null",
            "",
            "未找到可复盘的 daily run。",
            f"可先运行：{command}",
        ]
    )
    return DailyReviewResult(
        analysis_mode=ANALYSIS_MODE,
        not_investment_advice=True,
        trade_date=trade_date,
        data_status=DATA_STATUS_MISSING,
        data_sources_used=[],
        blocked_sections=["daily_run"],
        report_artifact=None,
        output_format=output_format,
        message=message,
        markdown=message,
    )


def render_trade_action_refusal(trade_date: str | None) -> DailyReviewResult:
    """将交易行动请求改写为研究-only 输出。"""

    display_date = trade_date or "<latest>"
    message = "\n".join(
        [
            "analysis_mode: research_only",
            "not_investment_advice: true",
            f"trade_date: {display_date}",
            "data_status: blocked",
            "report_artifact: null",
            "",
            "不能提供交易行动建议或配置比例建议。",
            "可以改为研究观察：市场宽度、情绪池、龙虎榜异动、数据缺口和待验证问题。",
        ]
    )
    return DailyReviewResult(
        analysis_mode=ANALYSIS_MODE,
        not_investment_advice=True,
        trade_date=trade_date,
        data_status=DATA_STATUS_BLOCKED,
        data_sources_used=[],
        blocked_sections=["trade_action_request"],
        report_artifact=None,
        output_format=OUTPUT_INLINE,
        message=message,
        markdown=message,
    )


def render_cli_message(report: ValidatedReviewReport, context_path: Path, data_notes_artifact: str | None = None) -> str:
    """生成 CLI 面向用户的简短输出。"""

    return "\n".join(
        [
            "analysis_mode: research_only",
            "not_investment_advice: true",
            f"trade_date: {report.context.trade_date}",
            f"data_status: {report.context.data_status}",
            f"context_artifact: {context_path}",
            f"blocked_sections: {json.dumps(report.context.blocked_sections, ensure_ascii=False)}",
            f"report_artifact: {report.report_artifact or 'null'}",
            f"data_notes_artifact: {data_notes_artifact or 'null'}",
            f"render_mode: {report.render_mode}",
            "",
            f"HTML report: {report.report_artifact}",
            f"Data notes: {data_notes_artifact or 'null'}",
            "本报告是研究复盘，不构成投资建议。",
        ]
    )


def render_markdown_from_report(report: ValidatedReviewReport) -> str:
    """把已校验 report 渲染为受控 Markdown。"""

    sections = report.sections
    lines = [
        f"# {sections.headline}",
        "",
        "## 摘要",
        *render_bullets(sections.summary),
        "",
        "## 大盘观察",
        "### 大盘定性",
        sections.market_overview_assessment,
        "",
        "### 大盘结构",
        sections.market_overview_structure,
        "",
        "## 市场宽度观察",
        sections.market_breadth_review,
        "",
        "## 情绪与事件观察",
        sections.sentiment_and_events_review,
        "",
        "## 板块和结构观察",
        sections.board_and_structure_review,
        "",
        "## 风险观察",
        *render_bullets(sections.risk_observations),
        "",
        "## 下一步研究问题",
        *render_bullets(sections.follow_up_questions),
        "",
        "## 数据边界",
        sections.data_boundary_note,
        "",
        "## 声明",
        sections.not_investment_advice_note,
    ]
    return "\n".join(line for line in lines if line is not None)


def render_html_review(report: ValidatedReviewReport) -> str:
    """把已校验 report 渲染成用户可读的单文件静态 HTML。"""

    context = report.context
    sections = report.sections
    metadata = {
        "schema_version": report.schema_version,
        "analysis_mode": context.analysis_mode,
        "not_investment_advice": context.not_investment_advice,
        "trade_date": context.trade_date,
        "render_mode": report.render_mode,
        "technical_notes": "a-share-daily-review-data-notes.md",
    }
    metadata_json = json.dumps(metadata, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(sections.headline)}</title>
  <style>
    body {{ margin: 0; font-family: Arial, "Microsoft YaHei", sans-serif; color: #1f2933; background: #f5f7fa; }}
    main {{ max-width: 1040px; margin: 0 auto; padding: 28px 20px 48px; }}
    header {{ background: #ffffff; border: 1px solid #d9e2ec; border-radius: 8px; padding: 22px; margin-bottom: 18px; }}
    section {{ background: #ffffff; border: 1px solid #d9e2ec; border-radius: 8px; padding: 18px 20px; margin: 14px 0; }}
    h1, h2 {{ margin: 0 0 12px; line-height: 1.3; }}
    h3 {{ margin: 14px 0 6px; line-height: 1.35; }}
    p {{ line-height: 1.7; }}
    ul {{ padding-left: 22px; line-height: 1.7; }}
    .meta {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; margin-top: 16px; }}
    .meta-item {{ border: 1px solid #e4e7eb; border-radius: 6px; padding: 10px 12px; background: #fbfcfd; }}
    .label {{ display: block; color: #52606d; font-size: 13px; margin-bottom: 4px; }}
    .notice {{ border-left: 4px solid #486581; padding-left: 12px; color: #334e68; }}
    .footnote {{ color: #52606d; font-size: 14px; }}
    code {{ background: #eef2f7; padding: 2px 5px; border-radius: 4px; }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>{html.escape(sections.headline)}</h1>
      <p class="notice">{html.escape(sections.data_boundary_note)}</p>
      <div class="meta">
        <div class="meta-item"><span class="label">交易日期</span>{html.escape(context.trade_date)}</div>
        <div class="meta-item"><span class="label">报告角色</span>策略分析师写给普通投资者</div>
        <div class="meta-item"><span class="label">报告性质</span>研究复盘</div>
      </div>
      <p>{html.escape(sections.not_investment_advice_note)}</p>
    </header>
    {render_html_section("摘要", render_list_html(sections.summary))}
    {render_market_overview_html(sections)}
    {render_html_section("市场宽度观察", render_paragraph_html(sections.market_breadth_review))}
    {render_html_section("情绪与事件观察", render_paragraph_html(sections.sentiment_and_events_review))}
    {render_html_section("板块和结构观察", render_paragraph_html(sections.board_and_structure_review))}
    {render_html_section("风险观察", render_list_html(sections.risk_observations))}
    {render_html_section("下一步研究问题", render_list_html(sections.follow_up_questions))}
    <section>
      <h2>数据边界</h2>
      <p>{html.escape(sections.data_boundary_note)}</p>
      <p class="footnote">详细数据状态和接口说明见同目录技术参考文件。</p>
    </section>
  </main>
  <script type="application/json" id="review-metadata">{html.escape(metadata_json)}</script>
</body>
</html>
"""


def render_data_notes_markdown(report: ValidatedReviewReport, context_path: Path) -> str:
    """渲染面向开发者和 agent 排障的技术参考 Markdown。"""

    context = report.context
    lines = [
        f"# {context.trade_date} A 股每日复盘技术参考",
        "",
        "本文档记录主报告隐藏的技术状态、接口失败和数据来源，供 review、排障和后续重跑使用。",
        "",
        "## 运行状态",
        "",
        f"- trade_date: {context.trade_date}",
        f"- data_status: {context.data_status}",
        f"- analysis_mode: {context.analysis_mode}",
        f"- not_investment_advice: {str(context.not_investment_advice).lower()}",
        f"- context_artifact: {context_path}",
        f"- blocked_sections: {json.dumps(context.blocked_sections, ensure_ascii=False)}",
        f"- render_mode: {report.render_mode}",
        "",
        "## 数据来源",
        "",
        *render_bullets(context.data_sources_used or ["无"]),
        "",
        "## 接口和表状态",
        "",
        "| 名称 | 分类 | 状态 | 行数 | 问题 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for key, item in sorted(context.source_health.items()):
        row_count = "" if item.row_count is None else str(item.row_count)
        issue = item.issue or ""
        lines.append(
            f"| {escape_markdown_table(key)} | {escape_markdown_table(item.category)} | "
            f"{escape_markdown_table(item.status)} | {escape_markdown_table(row_count)} | "
            f"{escape_markdown_table(issue)} |"
        )
    lines.extend(
        [
            "",
            "## 原始分类统计",
            "",
            "### 涨跌停情绪池分类",
            "",
            *render_key_value_bullets(context.limit_pool.get("pool_type_counts")),
            "",
            "### 龙虎榜事件来源",
            "",
            *render_key_value_bullets(context.lhb.get("event_type_counts")),
            "",
            "## external_background",
            "",
            f"- status: {context.external_background.status}",
            f"- input_path: {context.external_background.input_path or '无'}",
            f"- briefing_date: {context.external_background.briefing_date or '无'}",
            f"- source_skill: {context.external_background.source_skill or '无'}",
            "",
            "### 引用来源",
            "",
            *render_external_citation_bullets(context.external_background.citations),
            "",
            "### 降级或拒绝原因",
            "",
            *render_bullets(context.external_background.issues or ["未记录 external_background 降级或拒绝原因。"]),
            "",
            "### 信息缺口",
            "",
            *render_bullets(context.external_background.information_gaps or ["无"]),
        ]
    )
    lines.extend(
        [
            "",
            "## 诊断问题",
            "",
            *render_bullets(context.issues or ["未记录诊断问题。"]),
            "",
            "## 修复建议",
            "",
            f"- 如需重跑数据采集，使用：`{render_public_daily_update_command(context.trade_date)}`",
            "- 修复或重跑后重新生成 `review-context.json`，再让 LLM 基于新的 context 生成 sections JSON。",
        ]
    )
    return "\n".join(lines)


def render_external_citation_bullets(citations: list[ExternalBackgroundCitation]) -> list[str]:
    """把外部背景引用来源渲染为 Markdown bullet。"""

    if not citations:
        return ["- 无"]
    return [f"- {citation.source_name}: {citation.url}" for citation in citations]


def render_key_value_bullets(values: Any) -> list[str]:
    """把字典型技术统计渲染为 Markdown bullet。"""

    if not isinstance(values, dict) or not values:
        return ["- 无"]
    return [f"- {key}: {value}" for key, value in values.items()]


def validate_data_notes_diagnostics(context: ReviewContext, data_notes: str) -> None:
    """确保技术参考 Markdown 保留主报告外置的关键诊断信息。"""

    required_terms = ["data_status:", "数据来源", "接口和表状态", "external_background", "status:"]
    if context.blocked_sections:
        required_terms.append("blocked_sections:")
        required_terms.extend(context.blocked_sections)
    for issue in context.issues:
        required_terms.append(issue)
    for payload_key in ("pool_type_counts",):
        payload = context.limit_pool.get(payload_key)
        if isinstance(payload, dict):
            required_terms.extend(str(key) for key in payload.keys())
    payload = context.lhb.get("event_type_counts")
    if isinstance(payload, dict):
        required_terms.extend(str(key) for key in payload.keys())
    if context.external_background.input_path:
        required_terms.append(context.external_background.input_path)
    for issue in context.external_background.issues:
        required_terms.append(issue)
    for citation in context.external_background.citations:
        required_terms.extend([citation.source_name, citation.url])
    missing_terms = [term for term in required_terms if term not in data_notes]
    if missing_terms:
        raise ValueError(f"technical data notes missing diagnostics: {missing_terms}")


def escape_markdown_table(value: str) -> str:
    """转义 Markdown 表格单元格中会破坏列结构的字符。"""

    return value.replace("|", "\\|").replace("\n", " ")


def render_html_section(title: str, body: str) -> str:
    """渲染单个 HTML section。"""

    return f"<section><h2>{html.escape(title)}</h2>{body}</section>"


def render_market_overview_html(sections: LlmReviewSections) -> str:
    """渲染每日复盘固定的“大盘观察”HTML section。"""

    return (
        "<section>"
        "<h2>大盘观察</h2>"
        "<h3>大盘定性</h3>"
        f"{render_paragraph_html(sections.market_overview_assessment)}"
        "<h3>大盘结构</h3>"
        f"{render_paragraph_html(sections.market_overview_structure)}"
        "</section>"
    )


def render_paragraph_html(text: str) -> str:
    """把单段文本渲染为 HTML 段落。"""

    return f"<p>{html.escape(text)}</p>" if text else "<p>本节无可用内容。</p>"


def render_list_html(items: list[str]) -> str:
    """把文本列表渲染为 HTML 列表。"""

    if not items:
        return "<p>本节无可用内容。</p>"
    return "<ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in items) + "</ul>"


def daily_review_report_path(output_root: Path, trade_date: str) -> Path:
    """计算指定交易日每日复盘 HTML 报告路径。"""

    report_dir = output_root / "reports" / "daily-reviews" / trade_date
    return report_dir / "a-share-daily-review.html"


def daily_review_data_notes_path(output_root: Path, trade_date: str) -> Path:
    """计算指定交易日每日复盘技术参考 Markdown 路径。"""

    report_dir = output_root / "reports" / "daily-reviews" / trade_date
    return report_dir / "a-share-daily-review-data-notes.md"


def write_html_report(report_path: Path, content: str) -> Path:
    """写入每日复盘 HTML 报告并返回本地路径。"""

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(content, encoding="utf-8")
    return report_path


def write_data_notes(notes_path: Path, content: str) -> Path:
    """写入每日复盘技术参考 Markdown 并返回本地路径。"""

    notes_path.parent.mkdir(parents=True, exist_ok=True)
    notes_path.write_text(content, encoding="utf-8")
    return notes_path


def render_bullets(items: list[str]) -> list[str]:
    """把列表项转换为 Markdown bullet 行。"""

    return [f"- {item}" for item in items]


def enforce_research_boundary(text: str) -> None:
    """在输出落地前阻断明显交易行动语言。"""

    violations = [term for term in FORBIDDEN_OUTPUT_TERMS if term in text]
    if violations:
        raise ValueError(f"review output contains forbidden trading terms: {violations}")


def contains_forbidden_trading_terms(text: str) -> bool:
    """判断外部输入文本是否包含研究报告禁用的交易行动语言。"""

    return any(term in text for term in FORBIDDEN_OUTPUT_TERMS)


def format_large_number(value: float) -> str:
    """把成交额等大数转换成中文阅读单位。"""

    if pd.isna(value):
        return "不可用"
    if abs(value) >= 100_000_000:
        return f"{value / 100_000_000:.2f} 亿"
    if abs(value) >= 10_000:
        return f"{value / 10_000:.2f} 万"
    return f"{value:.2f}"


def series_counts_to_dict(counts: pd.Series) -> dict[str, int]:
    """把 Pandas 计数序列转换为 JSON 友好的字典。"""

    return {str(index): int(value) for index, value in counts.items()}


def extract_top_boards(table: pd.DataFrame) -> list[dict[str, Any]]:
    """提取板块涨跌幅靠前样本。"""

    if not {"board_name", "change_pct"}.issubset(table.columns):
        return []
    ranked = table.copy()
    ranked["change_pct"] = pd.to_numeric(ranked["change_pct"], errors="coerce")
    ranked = ranked.dropna(subset=["change_pct"]).sort_values("change_pct", ascending=False).head(5)
    return [
        {"board_name": str(row.board_name), "change_pct": float(row.change_pct)}
        for row in ranked.itertuples()
    ]


def coerce_optional_int(value: Any) -> int | None:
    """把外部状态中的行数转换为可选整数。"""

    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
