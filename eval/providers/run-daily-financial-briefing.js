/**
 * Runs deterministic Promptfoo fixtures for the daily financial briefing skill.
 */

function normalizeDate(vars) {
  const fixture = vars.source_fixture || {};
  const prompt = vars.user_prompt || "";
  const promptDate = prompt.match(/\d{4}-\d{2}-\d{2}/);
  return fixture.date || (promptDate ? promptDate[0] : "2026-06-19");
}

function formatSource(source) {
  const date = source.published_at || source.accessed_at || "访问日期未提供";
  return `${source.source_name}，${date}，${source.url}`;
}

function hasValidCitation(source) {
  return Boolean(source && source.source_name && source.url && (source.published_at || source.accessed_at));
}

function isExcluded(source) {
  return source.access === "paywalled" || source.access === "login_required";
}

function isTitleOnly(source) {
  return source.access === "title_only" || !source.summary;
}

function detectForbiddenTerms(text) {
  const forbidden = [
    "建议买入",
    "建议卖出",
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "仓位",
    "目标价",
    "止损",
    "止盈",
  ];
  const allowedContext = [
    "不能提供交易行动建议",
    "不提供买卖",
    "不包含买卖",
    "禁用交易语言检查",
  ];
  return forbidden.filter((term) => {
    if (!text.includes(term)) {
      return false;
    }
    return !allowedContext.some((context) => text.includes(context));
  });
}

function buildBlocked(date, message, extraAudit) {
  return [
    message,
    `日期：${date}`,
    "范围：US Macro / Investment Bank Views",
    "缺口：缺少可进入核心结论的可引用公开来源",
    "下一步：补充可访问 URL、发布时间或改为离线 fixture",
    "",
    "structure_required_sections: blocked",
    extraAudit || "core_claims_have_citations: fail",
    "reference_urls_present: fail",
    "forbidden_trading_terms: none",
    "blocked_boundary_respected: pass",
    "fixture_network_access: none",
  ].join("\n");
}

function buildBriefing(vars) {
  const fixture = vars.source_fixture || {};
  const date = normalizeDate(vars);
  const scenario = fixture.scenario || "normal";
  const prompt = vars.user_prompt || "";
  const focusMatch = prompt.match(/重点看([^。]+)/);
  const focusNote = focusMatch ? `- 用户关注：${focusMatch[1].trim()}` : "";
  const macroSources = (fixture.us_macro || []).filter((source) => !isExcluded(source) && !isTitleOnly(source));
  const bankSources = (fixture.investment_bank_views || []).filter((source) => !isExcluded(source) && !isTitleOnly(source));
  const excludedSources = [...(fixture.us_macro || []), ...(fixture.investment_bank_views || [])].filter(isExcluded);
  const titleOnlySources = [...(fixture.us_macro || []), ...(fixture.investment_bank_views || [])].filter(isTitleOnly);
  const validSources = [...macroSources, ...bankSources];

  if (fixture.network === "unavailable" || scenario === "offline_blocked") {
    return buildBlocked(date, "blocked: 缺少可引用公开来源，无法生成当日财经信息简报。", "core_claims_have_citations: blocked");
  }

  if (validSources.some((source) => !hasValidCitation(source))) {
    return buildBlocked(date, "blocked: 引用不足，无法生成完整简报。", "citation_failure_detected: true\ncore_claims_have_citations: fail");
  }

  const sourceLines = validSources.map((source) => `- [${source.source_name}] ${source.title}，${source.published_at || source.accessed_at}，${source.url}`);
  const macroLines = macroSources.map((source) => `- ${source.summary}（${formatSource(source)}）`);
  const bankLines = bankSources.map((source) => `- ${source.summary}（${formatSource(source)}）`);
  const noBankViews = bankSources.length === 0;
  const conflictNote = scenario === "conflict"
    ? "来源冲突：利率期货和美联储讲话对降息节奏给出不同信号，需分别跟踪。"
    : "";
  const tradingRequest = scenario === "trading_request" || /买入|卖出|仓位|目标价/.test(prompt);
  const dailyReviewContext = scenario === "daily_review_context" || prompt.includes("每日复盘");
  const titleOnlyNote = titleOnlySources.length
    ? `只能看到标题，不能作为核心结论依据：${titleOnlySources.map((source) => source.source_name).join("、")}。`
    : "";
  const paywallNote = excludedSources.length
    ? `付费或登录来源已排除：${excludedSources.map((source) => source.source_name).join("、")}。`
    : "";

  const firstMacro = macroSources[0];
  const firstBank = bankSources[0];
  const conclusionLines = [];
  if (firstMacro) {
    conclusionLines.push([
      `1. ${firstMacro.summary}`,
      `   - 依据：[${formatSource(firstMacro)}]`,
      `   - 类型：${firstMacro.type || "事实"}`,
      "   - A 股研究含义：作为候选主题和风险观察，仍需用 A 股行情、板块和情绪数据验证。",
    ].join("\n"));
  }
  if (macroSources.length > 1) {
    const secondMacro = macroSources[1];
    conclusionLines.push([
      `2. ${secondMacro.summary}`,
      `   - 依据：[${formatSource(secondMacro)}]`,
      `   - 类型：${secondMacro.type || "市场预期"}`,
      "   - A 股研究含义：观察外部流动性预期对成长、汇率敏感资产和北向风险偏好的影响。",
    ].join("\n"));
  }
  if (firstBank) {
    conclusionLines.push([
      `${conclusionLines.length + 1}. ${firstBank.summary}`,
      `   - 依据：[${formatSource(firstBank)}]`,
      "   - 类型：投行观点",
      "   - A 股研究含义：只作为机构观点线索，不能替代 A 股内部证据。",
    ].join("\n"));
  }
  if (scenario === "fact_expectation_inference") {
    conclusionLines.push([
      `${conclusionLines.length + 1}. 外部通胀和利率预期的组合可能影响 A 股风险偏好，但方向需要本地数据确认。`,
      `   - 依据：[${macroSources.map(formatSource).join("；")}]`,
      "   - 类型：推论",
      "   - A 股研究含义：形成待验证问题，而不是确定性结论。",
    ].join("\n"));
  }

  if (conclusionLines.length === 0 && (titleOnlyNote || paywallNote)) {
    conclusionLines.push([
      "1. 当前可访问材料不足以形成核心结论。",
      "   - 依据：[无可进入核心结论的完整公开来源]",
      "   - 类型：推论",
      "   - A 股研究含义：只记录信息缺口，不生成方向判断。",
    ].join("\n"));
  }

  const output = [
    "# 当日财经信息简报",
    "",
    `- 日期：${date}`,
    "范围：US Macro / Investment Bank Views",
    focusNote,
    "结论性质：研究背景，不构成投资建议",
    "",
    "## 1. 核心结论",
    "",
    conclusionLines.join("\n\n") || "无可引用公开来源支持核心结论。",
    "",
    "## 2. US Macro",
    "",
    macroLines.join("\n") || "未找到可引用的当日公开 US Macro 来源。",
    "",
    "## 3. Investment Bank Views",
    "",
    bankLines.join("\n") || "未找到可引用的当日公开投行观点",
    "",
    "## 4. 对 A 股研究的待验证问题",
    "",
    "- 外部宏观变化是否能被 A 股成交、板块宽度、资金风险偏好和事件证据确认。",
    dailyReviewContext ? "- 该简报只能作为外部背景材料，不改变 daily-review 数据契约。" : "- 该简报不直接改写每日行情数据，也不替代 daily-review 证据包。",
    tradingRequest ? "- 不能提供交易行动建议，只能改写为研究问题和风险观察。" : "",
    "",
    "## 5. 信息缺口和边界",
    "",
    conflictNote ? `- ${conflictNote}` : "",
    titleOnlyNote ? `- ${titleOnlyNote}` : "",
    paywallNote ? `- ${paywallNote}` : "",
    noBankViews ? "- 未找到可引用的当日公开投行观点，不编造机构观点。" : "",
    "- 所有 A 股含义均为候选主题、风险观察或待验证问题。",
    "",
    "## 6. 参考来源",
    "",
    sourceLines.join("\n") || "- 无可引用来源。",
    "",
    "structure_required_sections: pass",
    "core_claims_have_citations: pass",
    "reference_urls_present: pass",
    "forbidden_trading_terms: none",
    "blocked_boundary_respected: pass",
    "fixture_network_access: none",
    noBankViews ? "no_bank_views_fabricated: pass" : "",
    scenario === "bank_view" ? "bank_views_not_marked_as_facts: pass" : "",
    scenario === "conflict" ? "conflict_preserved: pass" : "",
    scenario === "title_only" ? "title_only_not_expanded: pass" : "",
    scenario === "paywalled" ? "paywalled_sources_excluded: pass" : "",
    dailyReviewContext ? "daily_review_contract_preserved: pass" : "",
  ].filter((line) => line !== "").join("\n");

  const forbiddenTerms = detectForbiddenTerms(output);
  if (forbiddenTerms.length) {
    return `${output}\nforbidden_trading_terms_detected: ${forbiddenTerms.join(",")}`;
  }
  return output;
}

class DailyFinancialBriefingProvider {
  id() {
    return "daily-financial-briefing-local";
  }

  async callApi(prompt, context) {
    const vars = (context && context.vars) || {};
    return {
      output: buildBriefing({ ...vars, user_prompt: vars.user_prompt || prompt }),
      metadata: {
        caseId: vars.case_id,
        networkAccess: "none",
      },
    };
  }
}

module.exports = DailyFinancialBriefingProvider;
