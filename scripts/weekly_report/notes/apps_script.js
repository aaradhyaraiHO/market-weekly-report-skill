/**
 * Google Apps Script — Weekly Report GM-Notes backend + Slack relay.
 *
 * Deploy as: Web app → Execute as Me → Anyone.
 * Sheet tab "notes", row 1 headers:
 *   market_slug | ce_id | ce_name | week_start | note | author | updated
 *   | slack_channel | slack_thread_ts | slack_permalink
 *
 * A note is keyed on (market_slug, ce_id, week_start) — one note per CE per week.
 * Prior weeks for the same CE become the History trail in the report drawer.
 *
 * Slack posting reads a bot token from Script Properties:
 *   Project Settings → Script properties → SLACK_BOT_TOKEN = xoxb-…
 * The bot must be invited to each market channel it posts to.
 *
 * ALL operations use GET (Apps Script mangles POST bodies across its redirect):
 *   ?action=list&market=X                                  → all notes for market (every week)
 *   ?action=upsert&market_slug=&ce_id=&week_start=&note=&author=&ce_name=
 *   ?action=post&market_slug=&ce_id=&week_start=&channel=&text=&author=&ce_name=&report_url=
 *       → posts (or threads) to Slack, stores thread_ts + permalink, returns them
 */

var SHEET_NAME = "notes";
var HEADERS = [
  "market_slug","ce_id","ce_name","week_start","note","author","updated",
  "slack_channel","slack_thread_ts","slack_permalink"
];

function getSheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) {
    sh = ss.insertSheet(SHEET_NAME);
    sh.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]);
    sh.getRange(1, 1, 1, HEADERS.length).setFontWeight("bold");
    sh.setFrozenRows(1);
  }
  return sh;
}

// Normalize a week value to YYYY-MM-DD. Sheets auto-types "2026-07-06" into a
// Date (read back as an ISO datetime), so all comparisons/output go through this.
function ymd(v) {
  if (v == null || v === "") return "";
  if (Object.prototype.toString.call(v) === "[object Date]") {
    return Utilities.formatDate(v, "UTC", "yyyy-MM-dd");
  }
  return String(v).slice(0, 10);
}

function allRows() {
  var sh = getSheet();
  var last = sh.getLastRow();
  if (last < 2) return [];
  var data = sh.getRange(2, 1, last - 1, HEADERS.length).getValues();
  var results = [];
  for (var i = 0; i < data.length; i++) {
    var obj = {};
    for (var j = 0; j < HEADERS.length; j++) obj[HEADERS[j]] = data[i][j];
    obj.ce_id = String(obj.ce_id);        // stable string keys
    obj.week_start = ymd(obj.week_start);  // normalize date → YYYY-MM-DD
    obj._row = i + 2;
    results.push(obj);
  }
  return results;
}

// A note row is unique per (market, ce, week).
function findRow(market, ceId, week) {
  var rows = allRows();
  var w = ymd(week);
  for (var i = 0; i < rows.length; i++) {
    if (rows[i].market_slug === market &&
        rows[i].ce_id === String(ceId) &&
        rows[i].week_start === w) return rows[i];
  }
  return null;
}

function writeRow(sh, existing, vals) {
  var row;
  if (existing) {
    sh.getRange(existing._row, 1, 1, HEADERS.length).setValues([vals]);
    row = existing._row;
  } else {
    sh.appendRow(vals);
    row = sh.getLastRow();
  }
  // A Slack `ts` (e.g. 1784091923.149229) must stay an EXACT string — if Sheets
  // stores it as a number it loses the last digit and threading/permalinks break.
  // Force the ts + week_start cells to plain-text format and rewrite as strings.
  var tsCol = HEADERS.indexOf("slack_thread_ts") + 1;   // 9
  var wkCol = HEADERS.indexOf("week_start") + 1;         // 4
  sh.getRange(row, tsCol).setNumberFormat("@").setValue(String(vals[tsCol - 1] || ""));
  sh.getRange(row, wkCol).setNumberFormat("@").setValue(String(vals[wkCol - 1] || ""));
  return row;
}

function doGet(e) {
  var p = e.parameter;
  var action = p.action || "list";

  if (action === "list") {
    var rows = allRows();
    if (p.market) rows = rows.filter(function(r){ return r.market_slug === p.market; });
    if (p.week)   rows = rows.filter(function(r){ return String(r.week_start) === String(p.week); });
    return jsonResp({ ok: true, notes: rows });
  }

  if (action === "upsert") {
    var sh = getSheet();
    var existing = findRow(p.market_slug, p.ce_id, p.week_start);
    var now = new Date().toISOString();
    var vals = [
      p.market_slug || "", String(p.ce_id || ""), p.ce_name || "",
      p.week_start || "", p.note || "", p.author || "", now,
      // preserve any existing slack linkage
      existing ? existing.slack_channel   : "",
      existing ? existing.slack_thread_ts : "",
      existing ? existing.slack_permalink : ""
    ];
    writeRow(sh, existing, vals);
    return jsonResp({ ok: true, action: existing ? "updated" : "created", updated: now });
  }

  if (action === "delete") {
    var sh2 = getSheet();
    var found = findRow(p.market_slug, p.ce_id, p.week_start);
    if (found) { sh2.deleteRow(found._row); return jsonResp({ ok: true, action: "deleted" }); }
    return jsonResp({ ok: false, error: "not found" });
  }

  if (action === "post") {
    return doPostToSlack(p);
  }

  // Diagnostic: verify the token + report its OAuth scopes (no posting).
  if (action === "auth") {
    var tok = PropertiesService.getScriptProperties().getProperty("SLACK_BOT_TOKEN");
    if (!tok) return jsonResp({ ok: false, error: "SLACK_BOT_TOKEN not set in Script properties" });
    var r = UrlFetchApp.fetch("https://slack.com/api/auth.test", {
      method: "post", headers: { Authorization: "Bearer " + tok }, muteHttpExceptions: true });
    var j = JSON.parse(r.getContentText());
    var scopes = r.getAllHeaders()["x-oauth-scopes"] || "";
    return jsonResp({ ok: j.ok, bot: j.user, team: j.team, error: j.error,
                      scopes: scopes,
                      can_post_public: String(scopes).indexOf("chat:write.public") >= 0 });
  }

  return jsonResp({ ok: false, error: "unknown action: " + action });
}

// ── Slack relay ──────────────────────────────────────────────────────────────
function doPostToSlack(p) {
  var token = PropertiesService.getScriptProperties().getProperty("SLACK_BOT_TOKEN");
  if (!token) return jsonResp({ ok: false, error: "SLACK_BOT_TOKEN not set in Script properties" });
  if (!p.channel) return jsonResp({ ok: false, error: "channel required" });

  var sh = getSheet();
  var existing = findRow(p.market_slug, p.ce_id, p.week_start);
  var now = new Date().toISOString();
  var text = p.text || "";

  // Compose the Slack message. A fresh CE/week gets a top-level post; a re-post
  // threads an update reply under the original so the discussion stays in one place.
  var threadTs = existing && existing.slack_thread_ts ? String(existing.slack_thread_ts) : "";
  var header = "📝 *" + (p.ce_name || ("CE " + p.ce_id)) + "*  ·  " + (p.market_slug || "") +
               "  ·  W/C " + (p.week_start || "");
  var body = header + "\n" + text +
             (p.author ? ("\n_— " + p.author + "_") : "") +
             (p.report_url ? ("\n<" + p.report_url + "|Open weekly report>") : "");

  var payload = {
    channel: p.channel,
    text: body,
    username: "Weekly Market Review",
    icon_emoji: ":memo:",
    unfurl_links: false
  };
  if (threadTs) payload.thread_ts = threadTs;

  var resp = UrlFetchApp.fetch("https://slack.com/api/chat.postMessage", {
    method: "post",
    contentType: "application/json; charset=utf-8",
    headers: { Authorization: "Bearer " + token },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  });
  var body2 = JSON.parse(resp.getContentText());
  if (!body2.ok) return jsonResp({ ok: false, error: "slack: " + (body2.error || "unknown") });

  var ts = body2.ts;
  // Anchor thread = the first (top-level) message's ts.
  var anchorTs = threadTs || ts;
  var permalink = getPermalink(token, p.channel, anchorTs);

  var vals = [
    p.market_slug || "", String(p.ce_id || ""), p.ce_name || "",
    p.week_start || "", text, p.author || "", now,
    p.channel, anchorTs, permalink || (existing ? existing.slack_permalink : "")
  ];
  writeRow(sh, existing, vals);

  return jsonResp({ ok: true, ts: anchorTs, permalink: permalink });
}

function getPermalink(token, channel, ts) {
  try {
    var r = UrlFetchApp.fetch(
      "https://slack.com/api/chat.getPermalink?channel=" + encodeURIComponent(channel) +
      "&message_ts=" + encodeURIComponent(ts),
      { headers: { Authorization: "Bearer " + token }, muteHttpExceptions: true });
    var j = JSON.parse(r.getContentText());
    return j.ok ? j.permalink : "";
  } catch (err) { return ""; }
}

function jsonResp(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

/**
 * ONE-TIME: run this from the editor to grant the external-request scope
 * (needed for Slack). Select `authorizeExternal` in the Run dropdown → Run →
 * Allow the "Connect to an external service" prompt. Safe to keep or delete.
 */
function authorizeExternal() {
  var r = UrlFetchApp.fetch("https://slack.com/api/auth.test", { muteHttpExceptions: true });
  Logger.log(r.getContentText());
  return r.getResponseCode();
}
