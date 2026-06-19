"""为每日复盘外部财经背景提供本地 fixture 和 fusion 校验辅助。"""

from __future__ import annotations

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from a_share_info_hub.daily_review import (
    EXTERNAL_BACKGROUND_FUSION_SCHEMA_VERSION,
    ReviewContext,
    contains_forbidden_trading_terms,
)


LOCAL_TOPICS_SCHEMA_VERSION = "daily_review_local_topics.v1"
TOPIC_RESULT_SCHEMA_VERSION = "daily_review_external_topic_result.v1"
SOURCE_SKILL = "daily-financial-briefing"
ALLOWED_EXTERNAL_SCOPES = ["US Macro", "Investment Bank Views"]
TOPIC_KEYS = (
    "market_overview_assessment",
    "market_overview_structure",
    "market_breadth",
    "sentiment_and_events",
    "board_and_structure",
    "risk_observations",
)
TOPIC_LABELS = {
    "market_overview_assessment": "大盘定性",
    "market_overview_structure": "大盘结构",
    "market_breadth": "市场宽度",
    "sentiment_and_events": "情绪与事件",
    "board_and_structure": "板块和结构",
    "risk_observations": "风险观察",
}
EVIDENCE_BOUNDARY = (
    "外部信息只能解释风险约束、形成待验证问题或提示变量；"
    "不能覆盖、补全或改写本地 A 股快照证据，也不能形成交易行动建议。"
)


class LocalTopic(BaseModel):
    """描述从 review-context.json 抽取出的单个本地研究主题。"""

    model_config = ConfigDict(extra="forbid")

    topic_key: str
    local_summary: str
    evidence_boundary: str

    @field_validator("topic_key")
    @classmethod
    def validate_topic_key(cls, value: str) -> str:
        """确保 topic key 属于第一版固定主题集合。"""

        if value not in TOPIC_KEYS:
            raise ValueError(f"unsupported topic_key: {value}")
        return value


class LocalTopicsPackage(BaseModel):
    """保存传给外部背景 runner 的固定 6 主题包。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = LOCAL_TOPICS_SCHEMA_VERSION
    trade_date: str
    topics: list[LocalTopic]


class TopicTaskInput(BaseModel):
    """保存单个外部背景 topic runner 的完整任务输入。"""

    model_config = ConfigDict(extra="forbid")

    trade_date: str
    topic_key: str
    local_summary: str
    evidence_boundary: str
    allowed_external_scopes: list[str] = Field(default_factory=lambda: list(ALLOWED_EXTERNAL_SCOPES))
    forbidden_boundaries: list[str] = Field(
        default_factory=lambda: [
            "不得输出买入、卖出、仓位、目标价、止盈止损或实盘时点建议。",
            "不得把外部新闻或机构观点写成本地 A 股确定性结论。",
            "不得补推本地缺失的市场宽度、情绪事件、龙虎榜或板块结构。",
        ]
    )


class TopicCitation(BaseModel):
    """描述 topic result 中单条外部发现的来源引用。"""

    model_config = ConfigDict(extra="forbid")

    source_name: str
    title: str = ""
    published_at: str = ""
    accessed_at: str = ""
    url: str


class TopicFinding(BaseModel):
    """描述某个本地 topic 相关的外部事实、预期、观点或推论。"""

    model_config = ConfigDict(extra="forbid")

    text: str
    type: str
    report_usage: str
    local_relevance: str
    citations: list[TopicCitation] = Field(default_factory=list)


class TopicResult(BaseModel):
    """保存单个 topic runner 返回的外部背景结果。"""

    model_config = ConfigDict(extra="forbid")

    topic_key: str
    external_findings: list[TopicFinding] = Field(default_factory=list)
    information_gaps: list[str] = Field(default_factory=list)
    blocked: bool = False
    blocked_reason: str = ""

    @field_validator("topic_key")
    @classmethod
    def validate_topic_key(cls, value: str) -> str:
        """确保结果 topic key 属于第一版固定主题集合。"""

        if value not in TOPIC_KEYS:
            raise ValueError(f"unsupported topic_key: {value}")
        return value


class TopicResultsArtifact(BaseModel):
    """保存 6 个 topic 任务输入和 runner 原始结果，便于审计。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = TOPIC_RESULT_SCHEMA_VERSION
    trade_date: str
    tasks: list[TopicTaskInput]
    results: list[TopicResult]


@dataclass
class ExternalBackgroundOrchestrationResult:
    """保存外部背景辅助 CLI 的三个落地产物路径和审计统计信息。"""

    trade_date: str
    source: str
    topics_path: Path
    topic_results_path: Path
    fusion_path: Path
    topic_count: int
    result_count: int
    fusion_schema: str


class TopicRunner(Protocol):
    """定义单个 topic 外部信息任务的可注入执行接口。"""

    def run(self, task: TopicTaskInput) -> TopicResult:
        """执行一个 topic 外部背景任务并返回结构化结果。"""


class FixtureTopicRunner:
    """为本地测试和 Promptfoo fixture smoke 生成确定性 topic 结果。"""

    def __init__(self, blocked_topic: str | None = None) -> None:
        """保存可选 blocked topic，用于验证部分失败仍能汇总。"""

        self.blocked_topic = blocked_topic
        self.calls: list[TopicTaskInput] = []

    def run(self, task: TopicTaskInput) -> TopicResult:
        """按 topic 生成确定性外部背景发现或 blocked 结果。"""

        self.calls.append(task)
        if task.topic_key == self.blocked_topic:
            return TopicResult(
                topic_key=task.topic_key,
                information_gaps=[f"{task.topic_key} 外部公开来源 fixture blocked。"],
                blocked=True,
                blocked_reason=f"{task.topic_key} fixture blocked",
            )
        topic_label = TOPIC_LABELS[task.topic_key]
        return TopicResult(
            topic_key=task.topic_key,
            external_findings=[
                TopicFinding(
                    text=f"{topic_label}相关的外部利率预期仍可能约束全球风险偏好。",
                    type="market_expectation",
                    report_usage="risk_observation",
                    local_relevance=f"{task.local_summary} 仍需用 A 股行情、板块和情绪数据验证。",
                    citations=[
                        TopicCitation(
                            source_name="Federal Reserve",
                            title="Policy statement",
                            published_at=task.trade_date,
                            accessed_at=task.trade_date,
                            url="https://www.federalreserve.gov/example",
                        )
                    ],
                )
            ],
            information_gaps=[],
        )


class AgentCommandTopicRunner:
    """legacy 诊断 runner；它不代表真实 `$daily-financial-briefing` skill 调用。"""

    def __init__(self, command: str | None = None) -> None:
        """保存可选 agent 命令模板，当前仓库默认不假设其存在。"""

        self.command = command

    def run(self, task: TopicTaskInput) -> TopicResult:
        """执行 agent 命令并解析 JSON；缺少命令或失败时返回 blocked。"""

        if not self.command:
            return TopicResult(
                topic_key=task.topic_key,
                information_gaps=["当前运行时未配置稳定的非交互 daily-financial-briefing 命令。"],
                blocked=True,
                blocked_reason="agent runner command is not configured",
            )
        completed = subprocess.run(
            [self.command],
            input=task.model_dump_json(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if completed.returncode != 0:
            return TopicResult(
                topic_key=task.topic_key,
                information_gaps=[(completed.stderr or completed.stdout or "").strip()[:400]],
                blocked=True,
                blocked_reason=f"agent command exited with {completed.returncode}",
            )
        try:
            return TopicResult.model_validate(json.loads(completed.stdout))
        except (json.JSONDecodeError, ValidationError) as exc:
            return TopicResult(
                topic_key=task.topic_key,
                information_gaps=[str(exc)],
                blocked=True,
                blocked_reason="agent command did not return valid topic result JSON",
            )


def load_review_context(path: Path) -> ReviewContext:
    """从 review-context.json 读取并校验每日复盘 evidence packet。"""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"review context is not valid JSON: {exc}") from exc
    return ReviewContext.model_validate(payload)


def extract_local_topics(context: ReviewContext) -> LocalTopicsPackage:
    """从本地 evidence packet 抽取第一版固定 6 个外部背景主题。"""

    summaries = {
        "market_overview_assessment": summarize_market_assessment(context),
        "market_overview_structure": summarize_market_structure(context),
        "market_breadth": summarize_market_breadth(context),
        "sentiment_and_events": summarize_sentiment_and_events(context),
        "board_and_structure": summarize_board_and_structure(context),
        "risk_observations": summarize_risk_observations(context),
    }
    topics = [
        LocalTopic(
            topic_key=topic_key,
            local_summary=summaries[topic_key],
            evidence_boundary=EVIDENCE_BOUNDARY,
        )
        for topic_key in TOPIC_KEYS
    ]
    return LocalTopicsPackage(trade_date=context.trade_date, topics=topics)


def build_topic_tasks(package: LocalTopicsPackage) -> list[TopicTaskInput]:
    """把本地主题包转换为可并行派发的 runner 输入。"""

    return [
        TopicTaskInput(
            trade_date=package.trade_date,
            topic_key=topic.topic_key,
            local_summary=topic.local_summary,
            evidence_boundary=topic.evidence_boundary,
        )
        for topic in package.topics
    ]


def run_topic_tasks(tasks: list[TopicTaskInput], runner: TopicRunner) -> list[TopicResult]:
    """并行执行 topic tasks，并保持输出顺序与固定 topic 顺序一致。"""

    if not tasks:
        return []
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        return list(executor.map(runner.run, tasks))


def build_fusion_payload(trade_date: str, results: list[TopicResult]) -> dict[str, Any]:
    """把 topic results 汇总为 external_background_fusion.v1 输入包。"""

    topic_findings: list[dict[str, Any]] = []
    risk_candidates: list[str] = []
    follow_up_candidates: list[str] = []
    citations: list[dict[str, str]] = []
    information_gaps: list[str] = []
    issues: list[str] = []
    seen_citations: set[tuple[str, str]] = set()
    seen_texts: set[str] = set()

    for result in results:
        if result.blocked:
            reason = result.blocked_reason.strip() or f"{result.topic_key} blocked"
            issues.append(f"{result.topic_key}: {reason}")
        information_gaps.extend(result.information_gaps)
        for finding in result.external_findings:
            if contains_forbidden_trading_terms(finding.text):
                issues.append(f"{result.topic_key}: 外部发现包含交易行动语言，已丢弃。")
                continue
            finding_payload = finding.model_dump()
            text_key = finding.text.strip()
            if text_key and text_key not in seen_texts:
                seen_texts.add(text_key)
                topic_findings.append(finding_payload)
            if finding.report_usage == "risk_observation":
                risk_candidates.append(
                    f"{finding.text} {finding.local_relevance} 外部变量不能覆盖本地 A 股证据。"
                )
            if finding.report_usage == "follow_up_question":
                follow_up_candidates.append(finding.text)
            for citation in finding.citations:
                citation_key = (citation.source_name, citation.url)
                if citation_key in seen_citations:
                    continue
                seen_citations.add(citation_key)
                citations.append(citation.model_dump())

    follow_up_candidates.extend(
        [
            "外部利率、通胀或投行观点是否会在 A 股市场宽度、板块和情绪数据中得到验证？",
        ]
    )
    return {
        "schema_version": EXTERNAL_BACKGROUND_FUSION_SCHEMA_VERSION,
        "source_skill": SOURCE_SKILL,
        "trade_date": trade_date,
        "not_investment_advice": True,
        "topic_findings": dedupe_dicts(topic_findings),
        "risk_candidates": dedupe_strings(risk_candidates),
        "follow_up_candidates": dedupe_strings(follow_up_candidates),
        "citations": citations,
        "information_gaps": dedupe_strings(information_gaps),
        "issues": dedupe_strings(issues),
    }


def orchestrate_external_background(
    context_path: Path,
    output_path: Path,
    runner: TopicRunner,
) -> ExternalBackgroundOrchestrationResult:
    """执行 review-context 到 fusion JSON 的本地辅助校验流程。"""

    context = load_review_context(context_path)
    topics_package = extract_local_topics(context)
    tasks = build_topic_tasks(topics_package)
    results = run_topic_tasks(tasks, runner)
    topic_results = TopicResultsArtifact(
        trade_date=context.trade_date,
        tasks=tasks,
        results=results,
    )
    fusion_payload = build_fusion_payload(context.trade_date, results)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    topics_path = output_path.with_name("external-background-local-topics.json")
    topic_results_path = output_path.with_name("external-background-topic-results.json")
    topics_path.write_text(topics_package.model_dump_json(indent=2), encoding="utf-8")
    topic_results_path.write_text(topic_results.model_dump_json(indent=2), encoding="utf-8")
    output_path.write_text(json.dumps(fusion_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return ExternalBackgroundOrchestrationResult(
        trade_date=context.trade_date,
        source=describe_runner_source(runner),
        topics_path=topics_path,
        topic_results_path=topic_results_path,
        fusion_path=output_path,
        topic_count=len(topics_package.topics),
        result_count=len(results),
        fusion_schema=EXTERNAL_BACKGROUND_FUSION_SCHEMA_VERSION,
    )


def describe_runner_source(runner: TopicRunner) -> str:
    """把 runner 类型转换为不会误认生产来源的审计标签。"""

    if isinstance(runner, FixtureTopicRunner):
        return "fixture_smoke"
    if isinstance(runner, AgentCommandTopicRunner):
        return "legacy_agent_command"
    return "validation_helper"


def build_runner(name: str, blocked_topic: str | None = None) -> TopicRunner:
    """按 CLI 参数构造本地辅助 runner。"""

    if name == "fixture":
        return FixtureTopicRunner(blocked_topic=blocked_topic)
    if name == "agent":
        return AgentCommandTopicRunner()
    raise ValueError(f"unsupported runner: {name}")


def render_orchestration_message(result: ExternalBackgroundOrchestrationResult) -> str:
    """生成辅助 CLI 的审计输出。"""

    return "\n".join(
        [
            f"trade_date: {result.trade_date}",
            f"external_background_source: {result.source}",
            f"external_background_orchestration_topics: {result.topic_count}",
            f"external_background_orchestration_results: {result.result_count}",
            f"external_background_schema: {result.fusion_schema}",
            f"local_topics_artifact: {result.topics_path}",
            f"topic_results_artifact: {result.topic_results_path}",
            f"fusion_artifact: {result.fusion_path}",
        ]
    )


def summarize_market_assessment(context: ReviewContext) -> str:
    """生成大盘定性 topic 的本地摘要。"""

    breadth = context.market_breadth
    if breadth.get("status") != "available":
        return "主表不可用，不能形成大盘定性。"
    return (
        f"主表覆盖 {breadth.get('sample_count')} 只证券，上涨 {breadth.get('up_count')} 只，"
        f"下跌 {breadth.get('down_count')} 只，平盘 {breadth.get('flat_count')} 只。"
    )


def summarize_market_structure(context: ReviewContext) -> str:
    """生成大盘结构 topic 的本地摘要。"""

    breadth = context.market_breadth
    if breadth.get("status") != "available":
        return "主表证据不足，不能展开大盘结构判断。"
    return (
        f"极端上涨样本 {breadth.get('extreme_up_count')} 只，"
        f"极端下跌样本 {breadth.get('extreme_down_count')} 只；"
        f"blocked_sections={context.blocked_sections}。"
    )


def summarize_market_breadth(context: ReviewContext) -> str:
    """生成市场宽度 topic 的本地摘要。"""

    return summarize_market_assessment(context)


def summarize_sentiment_and_events(context: ReviewContext) -> str:
    """生成情绪和事件 topic 的本地摘要。"""

    parts = []
    if context.limit_pool.get("status") == "available":
        parts.append(f"涨跌停情绪池记录 {context.limit_pool.get('row_count')} 条")
    if context.lhb.get("status") == "available":
        parts.append(f"龙虎榜事件记录 {context.lhb.get('row_count')} 条")
    return "；".join(parts) if parts else "情绪和事件数据不可用或为空。"


def summarize_board_and_structure(context: ReviewContext) -> str:
    """生成板块和结构 topic 的本地摘要。"""

    if "board_snapshot" in context.blocked_sections:
        return "板块快照为 blocked，本地报告不能确认板块主线或领涨结构。"
    if context.board_snapshot.get("status") != "available":
        return "板块快照不可用或为空，结构判断保持保守。"
    return f"板块快照记录 {context.board_snapshot.get('row_count')} 条。"


def summarize_risk_observations(context: ReviewContext) -> str:
    """生成风险观察 topic 的本地摘要。"""

    issues = "；".join(context.issues[:3]) if context.issues else "未记录接口诊断问题。"
    return (
        f"数据状态为 {context.data_status}；blocked sections 为 {context.blocked_sections}；"
        f"本地问题：{issues}"
    )


def dedupe_strings(values: list[str]) -> list[str]:
    """按原顺序去重字符串列表并移除空值。"""

    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def dedupe_dicts(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按 JSON 内容去重字典列表。"""

    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in values:
        key = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def main(argv: list[str] | None = None) -> int:
    """提供模块级调试入口，正式调用应走 `python -m a_share_info_hub`。"""

    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 2:
        print("usage: python -m a_share_info_hub.external_background <context> <output>")
        return 2
    result = orchestrate_external_background(Path(args[0]), Path(args[1]), FixtureTopicRunner())
    print(render_orchestration_message(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
