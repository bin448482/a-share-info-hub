/**
 * Runs the local daily review CLI against isolated Promptfoo fixture artifacts.
 */

const { existsSync, mkdtempSync, mkdirSync, readFileSync, writeFileSync } = require("fs");
const { tmpdir } = require("os");
const { join } = require("path");
const { spawnSync } = require("child_process");

function resolvePython() {
  if (process.env.PYTHON) {
    return process.env.PYTHON;
  }
  const venvPython = join(process.cwd(), ".venv", "Scripts", "python.exe");
  return existsSync(venvPython) ? venvPython : "python";
}

function writeJson(path, value) {
  writeFileSync(path, JSON.stringify(value, null, 2), "utf8");
}

function writeFixture(root, artifactState) {
  const tradeDate = "2026-06-18";
  const normalizedState = artifactState.trim().toLowerCase();
  const duckdbFailed =
    normalizedState.includes("duckdb query fails")
    || normalizedState.includes("duckdb fails")
    || normalizedState.includes("duckdb 不可用");
  const status = normalizedState.startsWith("missing")
    ? "missing"
    : normalizedState.startsWith("skipped")
      ? "skipped"
      : normalizedState.startsWith("failed")
        ? "failed"
        : normalizedState.startsWith("partial") || duckdbFailed || normalizedState.includes("board_snapshot failed")
          ? "partial"
          : "passed";

  if (status === "missing") {
    return tradeDate;
  }

  const runDir = join(root, "reports", "daily-runs", tradeDate);
  const normalizedDir = join(root, "data", "normalized");
  mkdirSync(runDir, { recursive: true });

  if (status === "skipped") {
    writeJson(join(runDir, "interface-status.json"), {
      trade_date: tradeDate,
      overall_status: "skipped",
      duckdb_status: "skipped",
      sources: [],
      table_row_counts: {
        daily_stock_snapshot: 0,
        limit_pool_events: 0,
        lhb_events: 0,
        market_summary: 0,
        board_snapshot: 0,
      },
      trading_day_check: {
        status: "success",
        is_trading_day: false,
        source: "weekday",
        reason: "weekend is not an A-share trading day",
      },
    });
    writeFileSync(join(runDir, "daily-data-summary.md"), "# fixture skipped\n", "utf8");
    return tradeDate;
  }

  mkdirSync(normalizedDir, { recursive: true });

  const boardFailed = status === "partial";
  const mainFailed = status === "failed";
  const sources = [
    {
      source_key: "stock_zh_a_spot",
      category: "main",
      status: mainFailed ? "failed" : "success",
      row_count: mainFailed ? 0 : 3,
      failure_reason: mainFailed ? "ReadTimeout" : null,
    },
    { source_key: "stock_zt_pool_em", category: "limit_pool", status: "success", row_count: 1 },
    { source_key: "stock_lhb_detail_em", category: "lhb", status: "success", row_count: 1 },
    { source_key: "stock_sse_deal_daily", category: "market_summary", status: "success", row_count: 1 },
    {
      source_key: "stock_board_industry_name_em",
      category: "board_snapshot",
      status: boardFailed ? "failed" : "success",
      row_count: boardFailed ? 0 : 1,
      failure_reason: boardFailed ? "ConnectionError" : null,
    },
  ];
  writeJson(join(runDir, "interface-status.json"), {
    trade_date: tradeDate,
    overall_status: mainFailed ? "failed" : status,
    duckdb_status: duckdbFailed ? "failed" : "written",
    sources,
  });
  writeFileSync(join(runDir, "daily-data-summary.md"), "# fixture summary\n", "utf8");

  const python = resolvePython();
  const script = `
import pandas as pd
import duckdb
from pathlib import Path
root = Path(r'''${root}''') / 'data' / 'normalized'
td = '${tradeDate}'
main_rows = [] if ${mainFailed ? "True" : "False"} else [
    {'trade_date': td, 'symbol': '000001', 'name': '平安银行', 'change_pct': 1.2, 'amount': 1000000},
    {'trade_date': td, 'symbol': '000002', 'name': '万科A', 'change_pct': -2.4, 'amount': 2000000},
    {'trade_date': td, 'symbol': '000003', 'name': '测试股', 'change_pct': 0.0, 'amount': 3000000},
]
pd.DataFrame(main_rows, columns=['trade_date','symbol','name','change_pct','amount']).to_parquet(root / 'daily_stock_snapshot.parquet', index=False)
pd.DataFrame([{'trade_date': td, 'pool_type': 'limit_up', 'industry': '银行'}]).to_parquet(root / 'limit_pool_events.parquet', index=False)
pd.DataFrame([{'trade_date': td, 'event_type': 'stock_lhb_detail_em', 'symbol': '000001'}]).to_parquet(root / 'lhb_events.parquet', index=False)
pd.DataFrame([{'trade_date': td, 'market': 'sse', 'row_index': 0}]).to_parquet(root / 'market_summary.parquet', index=False)
board_rows = [] if ${boardFailed ? "True" : "False"} else [{'trade_date': td, 'board_name': '银行', 'change_pct': 1.1}]
pd.DataFrame(board_rows, columns=['trade_date','board_name','change_pct']).to_parquet(root / 'board_snapshot.parquet', index=False)
if not ${duckdbFailed ? "True" : "False"}:
    with duckdb.connect(str(Path(r'''${root}''') / 'market.duckdb')) as connection:
        connection.execute("CREATE TABLE daily_stock_snapshot AS SELECT * FROM read_parquet(?)", [str(root / 'daily_stock_snapshot.parquet')])
`;
  const result = spawnSync(python, ["-c", script], { cwd: process.cwd(), encoding: "utf8" });
  if (result.status !== 0) {
    throw new Error(`failed to write eval fixture: ${result.stderr || result.stdout}`);
  }
  return tradeDate;
}

function writeExternalBackgroundFixture(root, externalBackgroundState) {
  const normalizedState = (externalBackgroundState || "").trim().toLowerCase();
  if (!normalizedState) {
    return null;
  }
  const path = join(root, "external-background.json");
  const blocked = normalizedState.includes("blocked");
  const missingUrl = normalizedState.includes("invalid citation") || normalizedState.includes("missing url");
  const briefingDate = normalizedState.includes("non-trade-date") ? "2026-06-17" : "2026-06-18";
  writeJson(path, {
    schema_version: "external_background.v1",
    source_skill: "daily-financial-briefing",
    briefing_date: briefingDate,
    scope: ["US Macro", "Investment Bank Views"],
    not_investment_advice: true,
    core_points: [
      {
        text: "美国利率预期仍是全球风险资产背景变量。",
        type: "market_expectation",
        a_share_relevance: "需要观察 A 股行情、板块和情绪数据是否出现共振。",
        citations: [
          {
            source_name: "Federal Reserve",
            title: "Policy statement",
            published_at: "2026-06-18",
            accessed_at: "2026-06-18",
            url: missingUrl ? "" : "https://www.federalreserve.gov/example",
          },
        ],
      },
      {
        text: "某投行观点认为中国资产仍需盈利验证。",
        type: "bank_view",
        a_share_relevance: "只作为机构观点背景，不作为事实结论。",
        citations: [
          {
            source_name: "Example Bank",
            title: "China strategy note",
            published_at: "2026-06-18",
            accessed_at: "2026-06-18",
            url: "https://example.com/china-strategy",
          },
        ],
      },
    ],
    follow_up_questions: ["外部利率预期是否对应到 A 股风险偏好变化？"],
    information_gaps: [],
    blocked,
    blocked_reason: blocked ? "公开来源不可用" : "",
  });
  return path;
}

class AShareDailyReviewProvider {
  id() {
    return "a-share-daily-review-local";
  }

  async callApi(prompt, context) {
    const vars = (context && context.vars) || {};
    const userPrompt = vars.user_prompt || prompt;
    if ((vars.artifact_state || "").includes("refresh_requested")) {
      const dateMatch = userPrompt.match(/\d{4}-\d{2}-\d{2}/);
      const tradeDate = dateMatch ? dateMatch[0] : "2026-06-18";
      return {
        output: [
          "analysis_mode: research_only",
          "not_investment_advice: true",
          `trade_date: ${tradeDate}`,
          "data_status: refresh_contract",
          `python -m a_share_info_hub daily-update --trade-date ${tradeDate}`,
          "refresh_contract_only: true",
        ].join("\n"),
        metadata: {
          exitCode: 0,
          caseId: vars.case_id,
        },
      };
    }
    const root = mkdtempSync(join(tmpdir(), "a-share-daily-review-eval-"));
    writeFixture(root, vars.artifact_state || "");
    const externalBackgroundPath = writeExternalBackgroundFixture(root, vars.external_background_state || "");
    const args = [
      "-m",
      "a_share_info_hub",
      "daily-review",
      "--output-root",
      root,
      "--user-prompt",
      userPrompt,
      "--render-mode",
      "deterministic",
    ];
    if (externalBackgroundPath) {
      args.push("--external-background", externalBackgroundPath);
    }
    const result = spawnSync(
      resolvePython(),
      args,
      {
        cwd: process.cwd(),
        encoding: "utf8",
        env: process.env,
      },
    );
    let output = `${result.stdout || ""}${result.stderr || ""}`.trim();
    const artifactMatch = output.match(/report_artifact:\s*(.+a-share-daily-review\.html)/);
    const notesMatch = output.match(/data_notes_artifact:\s*(.+a-share-daily-review-data-notes\.md)/);
    if (artifactMatch && existsSync(artifactMatch[1].trim())) {
      const html = readFileSync(artifactMatch[1].trim(), "utf8");
      const htmlBody = html.replace(/<script\b[\s\S]*?<\/script>/gi, "");
      const forbiddenTerms = [
        "passed",
        "partial",
        "blocked",
        "invalid",
        "passed 状态模拟输入",
        "HTML 展示形态",
        "external_background.status",
        "external_background_status",
        "schema_version",
        "render_mode",
        "fixture",
        "模拟",
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
      ].filter((term) => htmlBody.includes(term));
      const externalStandaloneSections = (html.match(/<h2>外部宏观与机构观点背景<\/h2>/g) || []).length;
      const riskSections = (html.match(/<h2>风险观察<\/h2>/g) || []).length;
      const followUpSections = (html.match(/<h2>下一步研究问题<\/h2>/g) || []).length;
      const htmlContainsExternalCitationUrl = html.includes("https://www.federalreserve.gov/example")
        || html.includes("https://example.com/china-strategy");
      output = [
        output,
        `html_forbidden_terms: ${forbiddenTerms.length ? forbiddenTerms.join(",") : "none"}`,
        `external_background_standalone_sections: ${externalStandaloneSections}`,
        `risk_section_count: ${riskSections}`,
        `follow_up_section_count: ${followUpSections}`,
        `html_contains_external_citation_url: ${htmlContainsExternalCitationUrl ? "true" : "false"}`,
        "",
        html,
      ].join("\n");
    }
    if (notesMatch && existsSync(notesMatch[1].trim())) {
      const notes = readFileSync(notesMatch[1].trim(), "utf8");
      const requiredTerms = [
        "blocked_sections",
        "board_snapshot",
        "stock_board_industry_name_em",
      ];
      const hasRequiredDiagnostics = requiredTerms.every((term) => notes.includes(term));
      output = `${output}\ndata_notes_diagnostics_present: ${hasRequiredDiagnostics ? "true" : "false"}`;
      if (externalBackgroundPath) {
        const externalState = vars.external_background_state || "";
        let requiredExternalDiagnostics = [
          "external_background",
          externalBackgroundPath,
        ];
        if (externalState.includes("blocked")) {
          requiredExternalDiagnostics = requiredExternalDiagnostics.concat([
            "status: blocked",
            "公开来源不可用",
          ]);
        } else if (externalState.includes("invalid citation") || externalState.includes("missing url")) {
          requiredExternalDiagnostics = requiredExternalDiagnostics.concat([
            "status: partial",
            "缺少正文、合法类型、来源名称或 URL",
            "Example Bank",
            "https://example.com/china-strategy",
          ]);
        } else {
          requiredExternalDiagnostics = requiredExternalDiagnostics.concat([
            "status: passed",
            "Federal Reserve",
            "https://www.federalreserve.gov/example",
            "Example Bank",
            "https://example.com/china-strategy",
          ]);
        }
        const hasExternalDiagnostics = requiredExternalDiagnostics.every((term) => notes.includes(term));
        output = `${output}\nexternal_background_diagnostics_present: ${hasExternalDiagnostics ? "true" : "false"}`;
      }
    }
    output = output.replace(/\\/g, "/");
    return {
      output,
      metadata: {
        exitCode: result.status,
        caseId: vars.case_id,
      },
    };
  }
}

module.exports = AShareDailyReviewProvider;
