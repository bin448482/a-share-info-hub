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

module.exports = {
  id: () => "a-share-daily-review-local",
  callApi: async (prompt, context) => {
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
    const result = spawnSync(
      resolvePython(),
      [
        "-m",
        "a_share_info_hub",
        "daily-review",
        "--output-root",
        root,
        "--user-prompt",
        userPrompt,
        "--render-mode",
        "deterministic",
      ],
      {
        cwd: process.cwd(),
        encoding: "utf8",
        env: process.env,
      },
    );
    let output = `${result.stdout || ""}${result.stderr || ""}`.trim();
    const artifactMatch = output.match(/report_artifact:\s*(.+a-share-daily-review\.html)/);
    if (artifactMatch && existsSync(artifactMatch[1].trim())) {
      output = `${output}\n\n${readFileSync(artifactMatch[1].trim(), "utf8")}`;
    }
    output = output.replace(/\\/g, "/");
    return {
      output,
      metadata: {
        exitCode: result.status,
        caseId: vars.case_id,
      },
    };
  },
};
