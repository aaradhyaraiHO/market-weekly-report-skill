/**
 * Google Apps Script — Weekly Report notes/actions + WBR review backend + Slack relay.
 *
 * Deploy as: Web app → Execute as Me → Anyone.
 *
 * Legacy tabs in the same spreadsheet (kept for current report consumers):
 *
 *   "notes"   — CE drawer notes.  Key: (market_slug, ce_id, week_start).
 *     Headers: market_slug | ce_id | ce_name | week_start | note | author | updated
 *              | slack_channel | slack_thread_ts | slack_permalink
 *
 *   "actions" — Bucket-table actions (Losing Money dropdown, Fluctuations
 *     confirm-seasonality checkbox + note).  Key: (market_slug, ce_id, week_start, bucket).
 *     Headers: market_slug | ce_id | week_start | bucket | checkbox | note | status | owner | updated
 *
 * Slack posting reads a bot token from Script Properties:
 *   Project Settings → Script properties → SLACK_BOT_TOKEN = xoxb-…
 * The bot must be invited to each market channel it posts to.
 *
 * ALL operations use GET (Apps Script mangles POST bodies across its redirect):
 *   ?action=list&market=X[&week=W]                          → notes for market (all weeks, or one)
 *   ?action=upsert&market_slug=&ce_id=&week_start=&note=&author=&ce_name=
 *   ?action=post&market_slug=&ce_id=&week_start=&channel=&text=&author=&ce_name=&report_url=
 *       → posts (or threads) to Slack, stores thread_ts + permalink, returns them
 *   ?action=action_list&market=X&week=W                     → bucket actions (market+week scoped)
 *   ?action=action_upsert&market_slug=&ce_id=&week_start=&bucket=&checkbox=&note=&status=&owner=
 *
 * Review-mode tabs (additive; see SETUP.md for the full endpoint contract):
 *   review_comments | review_work_items | review_receipts | review_set
 *   ce_threads | review_source_suggestions
 * The thread key is (market_slug, ce_id), never week, so Ask in Slack reuses one
 * persistent CE discussion. Perf history stays read-only in `ce.perf_action_hist`.
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

// A note row is unique per (market, ce, week).  Uses TextFinder to avoid
// reading the entire sheet — O(matched rows) instead of O(all rows).
function findRow(market, ceId, week) {
  var sh = getSheet();
  var w = ymd(week);
  var ceStr = String(ceId);
  // TextFinder on the ce_id column (col 2) — smallest cardinality, fastest hit
  var finder = sh.getRange(2, 2, Math.max(sh.getLastRow() - 1, 1), 1)
    .createTextFinder(ceStr).matchEntireCell(true);
  var matches = finder.findAll();
  for (var i = 0; i < matches.length; i++) {
    var r = matches[i].getRow();
    var rowData = sh.getRange(r, 1, 1, HEADERS.length).getValues()[0];
    if (rowData[0] === market && ymd(rowData[3]) === w) {
      var obj = {};
      for (var j = 0; j < HEADERS.length; j++) obj[HEADERS[j]] = rowData[j];
      obj.ce_id = String(obj.ce_id);
      obj.week_start = ymd(obj.week_start);
      obj._row = r;
      return obj;
    }
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

// ── Actions backend ─────────────────────────────────────────────────────────
// Separate "actions" tab for bucket-table actions (Losing Money dropdown,
// Fluctuations confirm-seasonality checkbox + note). Keyed on
// (market_slug, ce_id, week_start, bucket). Mirrors the notes pattern.
var ACTION_SHEET_NAME = "actions";
var ACTION_HEADERS = [
  "market_slug","ce_id","week_start","bucket","checkbox","note","status","owner","updated"
];

function getActionSheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(ACTION_SHEET_NAME);
  if (!sh) {
    sh = ss.insertSheet(ACTION_SHEET_NAME);
    sh.getRange(1, 1, 1, ACTION_HEADERS.length).setValues([ACTION_HEADERS]);
    sh.getRange(1, 1, 1, ACTION_HEADERS.length).setFontWeight("bold");
    sh.setFrozenRows(1);
  }
  return sh;
}

// Scoped read: only rows matching a market (required) + optional week filter.
// At 10 markets × 52 weeks × ~150 rows/market-week ≈ 78K rows/year, a full
// allActionRows() would be O(all rows) on every call.  This reads the full
// sheet once per request but filters server-side so the JSON response stays small.
// The week filter is strongly recommended (the client always sends it).
function actionRowsFiltered(market, week) {
  var sh = getActionSheet();
  var last = sh.getLastRow();
  if (last < 2) return [];
  var data = sh.getRange(2, 1, last - 1, ACTION_HEADERS.length).getValues();
  var w = week ? ymd(week) : null;
  var results = [];
  for (var i = 0; i < data.length; i++) {
    if (String(data[i][0]) !== market) continue;
    if (w && ymd(data[i][2]) !== w) continue;
    var obj = {};
    for (var j = 0; j < ACTION_HEADERS.length; j++) obj[ACTION_HEADERS[j]] = data[i][j];
    obj.ce_id = String(obj.ce_id);
    obj.week_start = ymd(obj.week_start);
    obj._row = i + 2;
    results.push(obj);
  }
  return results;
}

// Point lookup via TextFinder on ce_id column — avoids reading every row.
function findActionRow(market, ceId, week, bucket) {
  var sh = getActionSheet();
  var w = ymd(week);
  var ceStr = String(ceId);
  var finder = sh.getRange(2, 2, Math.max(sh.getLastRow() - 1, 1), 1)
    .createTextFinder(ceStr).matchEntireCell(true);
  var matches = finder.findAll();
  for (var i = 0; i < matches.length; i++) {
    var r = matches[i].getRow();
    var rowData = sh.getRange(r, 1, 1, ACTION_HEADERS.length).getValues()[0];
    if (rowData[0] === market && ymd(rowData[2]) === w && rowData[3] === bucket) {
      var obj = {};
      for (var j = 0; j < ACTION_HEADERS.length; j++) obj[ACTION_HEADERS[j]] = rowData[j];
      obj.ce_id = String(obj.ce_id);
      obj.week_start = ymd(obj.week_start);
      obj._row = r;
      return obj;
    }
  }
  return null;
}

function writeActionRow(sh, existing, vals) {
  var row;
  if (existing) {
    sh.getRange(existing._row, 1, 1, ACTION_HEADERS.length).setValues([vals]);
    row = existing._row;
  } else {
    sh.appendRow(vals);
    row = sh.getLastRow();
  }
  var wkCol = ACTION_HEADERS.indexOf("week_start") + 1;
  sh.getRange(row, wkCol).setNumberFormat("@").setValue(String(vals[wkCol - 1] || ""));
  return row;
}

// ── Weekly Review V2 backend ────────────────────────────────────────────────
// These tables are additive. The legacy `notes` and `actions` endpoints above
// remain unchanged because bucket alerts and the current CE drawer consume them.
// Review mode uses durable IDs so same-week entries never overwrite each other.
var REVIEW_TABLES = {
  comments: {
    sheet: "review_comments",
    headers: ["comment_id","market_slug","ce_id","ce_name","week_start","body",
      "author_name","author_role","source_type","source_author","source_ref","source_url","accepted_by",
      "created_at","updated_at","deleted_at"]
  },
  work: {
    sheet: "review_work_items",
    headers: ["work_id","market_slug","ce_id","ce_name","origin_week","kind","text",
      "owner","status","due_date","source_type","source_ref","source_url",
      "created_at","updated_at","closed_at"]
  },
  receipts: {
    sheet: "review_receipts",
    headers: ["receipt_id","market_slug","ce_id","ce_name","week_start","treatment",
      "reviewer","reviewed_at","next_review_date","summary","open_work_count"]
  },
  review_set: {
    sheet: "review_set",
    headers: ["market_slug","week_start","ce_id","ce_name","position","treatment",
      "reason","source","included","updated_at"]
  },
  threads: {
    sheet: "ce_threads",
    headers: ["market_slug","ce_id","ce_name","slack_channel","slack_thread_ts",
      "slack_permalink","created_at","updated_at","last_scanned_ts"]
  },
  suggestions: {
    sheet: "review_source_suggestions",
    headers: ["suggestion_id","market_slug","ce_id","ce_name","week_start","source_type",
      "source_author","source_ref","source_url","kind","body","proposed_owner","proposed_due_date",
      "confidence","status","created_at","decided_by","decided_at"]
  },
  inbox: {
    sheet: "review_source_inbox",
    headers: ["source_item_id","source_type","source_ref","source_url","source_author",
      "occurred_at","market_slug","week_start","candidate_ce_id","candidate_ce_name",
      "match_confidence","match_status","kind","body","created_at","reconciled_by","reconciled_at"]
  }
};

function reviewSheet(kind) {
  var def = REVIEW_TABLES[kind];
  if (!def) throw new Error("unknown review table: " + kind);
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(def.sheet);
  if (!sh) {
    sh = ss.insertSheet(def.sheet);
    sh.getRange(1, 1, 1, def.headers.length).setValues([def.headers]);
    sh.getRange(1, 1, 1, def.headers.length).setFontWeight("bold");
    sh.setFrozenRows(1);
  }
  return sh;
}

function reviewRows(kind) {
  var def = REVIEW_TABLES[kind], sh = reviewSheet(kind), last = sh.getLastRow();
  if (last < 2) return [];
  var data = sh.getRange(2, 1, last - 1, def.headers.length).getValues();
  return data.map(function(row, idx) {
    var obj = {_row: idx + 2};
    def.headers.forEach(function(h, col) { obj[h] = row[col]; });
    if (obj.ce_id !== undefined) obj.ce_id = String(obj.ce_id);
    ["week_start","origin_week","due_date","next_review_date"].forEach(function(h) {
      if (obj[h] !== undefined) obj[h] = ymd(obj[h]);
    });
    return obj;
  });
}

function reviewFind(kind, predicate) {
  var rows = reviewRows(kind);
  for (var i = 0; i < rows.length; i++) if (predicate(rows[i])) return rows[i];
  return null;
}

function reviewWrite(kind, existing, record) {
  var def = REVIEW_TABLES[kind], sh = reviewSheet(kind);
  var vals = def.headers.map(function(h) { return record[h] == null ? "" : record[h]; });
  var lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    var row = existing ? existing._row : sh.getLastRow() + 1;
    sh.getRange(row, 1, 1, vals.length).setValues([vals]);
    ["week_start","origin_week","due_date","next_review_date","slack_thread_ts",
      "last_scanned_ts"].forEach(function(h) {
        var col = def.headers.indexOf(h) + 1;
        if (col > 0) sh.getRange(row, col).setNumberFormat("@").setValue(String(record[h] || ""));
      });
    return row;
  } finally { lock.releaseLock(); }
}

function reviewRequired(p, fields) {
  var missing = fields.filter(function(k) { return p[k] == null || String(p[k]).trim() === ""; });
  return missing.length ? jsonResp({ok:false, error:"required: " + missing.join(", ")}) : null;
}

function reviewFilter(rows, p, weekField) {
  return rows.filter(function(r) {
    if (p.market && r.market_slug !== p.market) return false;
    if (p.market_slug && r.market_slug !== p.market_slug) return false;
    if (p.ce_id && String(r.ce_id) !== String(p.ce_id)) return false;
    if (p.week && ymd(r[weekField || "week_start"]) !== ymd(p.week)) return false;
    if (p.status && String(r.status) !== String(p.status)) return false;
    return true;
  });
}

function reviewPage(rows,p,dateField,defaultLimit){
  var before=String(p.before||""),limit=Math.min(Math.max(parseInt(p.limit||defaultLimit,10)||defaultLimit,1),200);
  rows=rows.filter(function(r){return !before||String(r[dateField]||"")<before;})
    .sort(function(a,b){return String(b[dateField]||"").localeCompare(String(a[dateField]||""));});
  var items=rows.slice(0,limit),next=rows.length>limit&&items.length?String(items[items.length-1][dateField]||""):"";
  return {items:items,next_before:next};
}

function reviewBool(v) { return String(v || "").toLowerCase() === "true"; }
function reviewId(prefix) { return prefix + "_" + Utilities.getUuid(); }
function reviewNow() { return new Date().toISOString(); }

function reviewCommentUpsert(p) {
  var err = reviewRequired(p, ["market_slug","ce_id","week_start","body","author_name"]);
  if (err) return err;
  var existing = p.comment_id ? reviewFind("comments", function(r){ return r.comment_id === p.comment_id; }) : null;
  if (p.comment_id && !existing) return jsonResp({ok:false,error:"comment not found"});
  if (existing && (existing.market_slug !== p.market_slug || String(existing.ce_id) !== String(p.ce_id)))
    return jsonResp({ok:false,error:"comment identity is immutable"});
  var now = reviewNow();
  var rec = {
    comment_id: existing ? existing.comment_id : reviewId("cmt"), market_slug:p.market_slug,
    ce_id:String(p.ce_id), ce_name:p.ce_name || (existing && existing.ce_name) || "",
    week_start:ymd(p.week_start), body:p.body, author_name:p.author_name,
    author_role:p.author_role || "", source_type:p.source_type || "manual",
    source_author:p.source_author || p.author_name, source_ref:p.source_ref || "", source_url:p.source_url || "",
    accepted_by:p.accepted_by || "",
    created_at:(existing && existing.created_at) || now, updated_at:now, deleted_at:""
  };
  reviewWrite("comments", existing, rec);
  return jsonResp({ok:true, comment:rec});
}

function reviewCommentDelete(p) {
  var err = reviewRequired(p, ["comment_id","deleted_by"]); if (err) return err;
  var existing = reviewFind("comments", function(r){ return r.comment_id === p.comment_id; });
  if (!existing) return jsonResp({ok:false,error:"comment not found"});
  existing.deleted_at = reviewNow(); existing.updated_at = existing.deleted_at;
  // Keep body and authorship for audit; clients render a tombstone.
  reviewWrite("comments", existing, existing);
  return jsonResp({ok:true, comment_id:p.comment_id, deleted_at:existing.deleted_at});
}

function reviewWorkUpsert(p) {
  var err = reviewRequired(p, ["market_slug","ce_id","origin_week","kind","text","status"]);
  if (err) return err;
  if (["action","check"].indexOf(p.kind) < 0) return jsonResp({ok:false,error:"kind must be action or check"});
  var statuses=["needs_action","in_progress","awaiting_reply","already_actioned","self_recovering",
    "monitoring","scheduled","no_action_needed","complete","cancelled"];
  if(statuses.indexOf(p.status)<0)return jsonResp({ok:false,error:"unsupported work status"});
  var existing = p.work_id ? reviewFind("work", function(r){ return r.work_id === p.work_id; }) : null;
  if (p.work_id && !existing) return jsonResp({ok:false,error:"work item not found"});
  if (existing && (existing.market_slug !== p.market_slug || String(existing.ce_id) !== String(p.ce_id)))
    return jsonResp({ok:false,error:"work identity is immutable"});
  var now = reviewNow(), closed = ["complete","cancelled","no_action_needed"].indexOf(p.status) >= 0;
  var rec = {
    work_id:existing ? existing.work_id : reviewId("wrk"), market_slug:p.market_slug,
    ce_id:String(p.ce_id), ce_name:p.ce_name || (existing && existing.ce_name) || "",
    origin_week:ymd(p.origin_week), kind:p.kind, text:p.text,
    // Owner is deliberately never inferred. Empty is valid for a scheduled check.
    owner:p.owner || "", status:p.status, due_date:ymd(p.due_date || ""),
    source_type:p.source_type || "manual", source_ref:p.source_ref || "",
    source_url:p.source_url || "", created_at:(existing && existing.created_at) || now,
    updated_at:now, closed_at:closed ? ((existing && existing.closed_at) || now) : ""
  };
  reviewWrite("work", existing, rec);
  return jsonResp({ok:true, work_item:rec});
}

function reviewReceiptUpsert(p) {
  var err = reviewRequired(p, ["market_slug","ce_id","week_start","treatment","reviewer"]);
  if (err) return err;
  var existing = reviewFind("receipts", function(r){
    return r.market_slug === p.market_slug && String(r.ce_id) === String(p.ce_id) &&
      ymd(r.week_start) === ymd(p.week_start);
  });
  var now = reviewNow();
  var rec = {
    receipt_id:(existing && existing.receipt_id) || reviewId("rcp"), market_slug:p.market_slug,
    ce_id:String(p.ce_id), ce_name:p.ce_name || (existing && existing.ce_name) || "",
    week_start:ymd(p.week_start), treatment:p.treatment, reviewer:p.reviewer,
    reviewed_at:now, next_review_date:ymd(p.next_review_date || ""), summary:p.summary || "",
    open_work_count:String(p.open_work_count || "0")
  };
  reviewWrite("receipts", existing, rec);
  return jsonResp({ok:true, receipt:rec});
}

function reviewSetUpsert(p) {
  var err = reviewRequired(p, ["market_slug","week_start","ce_id"]); if (err) return err;
  var existing = reviewFind("review_set", function(r){
    return r.market_slug === p.market_slug && ymd(r.week_start) === ymd(p.week_start) &&
      String(r.ce_id) === String(p.ce_id);
  });
  var rec = {
    market_slug:p.market_slug, week_start:ymd(p.week_start), ce_id:String(p.ce_id),
    ce_name:p.ce_name || (existing && existing.ce_name) || "", position:p.position || "",
    treatment:p.treatment || "", reason:p.reason || "", source:p.source || "manual",
    included:p.included === undefined ? "true" : String(reviewBool(p.included)), updated_at:reviewNow()
  };
  reviewWrite("review_set", existing, rec);
  return jsonResp({ok:true, review_set_item:rec});
}

function reviewSuggestionRecord(p) {
  if (["slack","granola"].indexOf(String(p.source_type).toLowerCase()) < 0)
    return {ok:false,error:"source_type must be slack or granola"};
  var duplicate = reviewFind("suggestions", function(r){
    return r.source_type === p.source_type && r.source_ref === p.source_ref && r.kind === p.kind;
  });
  if (duplicate) return {ok:true,duplicate:true,suggestion:duplicate};
  var rec = {
    suggestion_id:reviewId("sgg"), market_slug:p.market_slug, ce_id:String(p.ce_id),
    ce_name:p.ce_name || "", week_start:ymd(p.week_start), source_type:p.source_type,
    source_author:p.source_author || "", source_ref:p.source_ref, source_url:p.source_url || "", kind:p.kind, body:p.body,
    proposed_owner:p.proposed_owner || "", proposed_due_date:ymd(p.proposed_due_date || ""),
    confidence:p.confidence || "", status:"pending", created_at:reviewNow(), decided_by:"", decided_at:""
  };
  reviewWrite("suggestions", null, rec);
  return {ok:true,suggestion:rec};
}

function reviewSourceIngestRecord(p) {
  var missing=["market_slug","week_start","source_type","source_ref","kind","body"]
    .filter(function(k){return p[k]==null||String(p[k]).trim()==="";});
  if(missing.length)return {ok:false,error:"required: "+missing.join(", ")};
  p.source_type=String(p.source_type).toLowerCase();
  if(p.source_type!=="granola" && !p.ce_id)
    return {ok:false,error:"ce_id required for non-Granola source"};
  var matched=!!p.ce_id && ["unmatched","ambiguous"].indexOf(p.match_status)<0;
  if(matched)return reviewSuggestionRecord(p);
  var duplicate=reviewFind("inbox",function(r){return r.source_type===p.source_type&&r.source_ref===p.source_ref;});
  if(duplicate)return {ok:true,duplicate:true,inbox_item:duplicate};
  var rec={source_item_id:reviewId("src"),source_type:p.source_type,source_ref:p.source_ref,
    source_url:p.source_url||"",source_author:p.source_author||"",occurred_at:p.occurred_at||"",
    market_slug:p.market_slug,week_start:ymd(p.week_start),candidate_ce_id:String(p.candidate_ce_id||""),
    candidate_ce_name:p.candidate_ce_name||"",match_confidence:p.match_confidence||"",
    match_status:p.match_status||"unmatched",kind:p.kind,body:p.body,created_at:reviewNow(),
    reconciled_by:"",reconciled_at:""};
  reviewWrite("inbox",null,rec);
  return {ok:true,queued_for_reconciliation:true,inbox_item:rec};
}

function reviewSuggestionIngest(p) {
  return jsonResp(reviewSourceIngestRecord(p));
}

function reviewSourceReconcile(p){
  var err=reviewRequired(p,["source_item_id","market_slug","ce_id","week_start","decided_by"]);if(err)return err;
  var inbox=reviewFind("inbox",function(r){return r.source_item_id===p.source_item_id;});
  if(!inbox)return jsonResp({ok:false,error:"source inbox item not found"});
  if(inbox.reconciled_at)return jsonResp({ok:false,error:"source inbox item already reconciled"});
  var result=reviewSuggestionRecord({market_slug:p.market_slug,ce_id:p.ce_id,ce_name:p.ce_name||"",
    week_start:p.week_start,source_type:inbox.source_type,source_author:inbox.source_author,
    source_ref:inbox.source_ref,source_url:inbox.source_url,kind:inbox.kind,body:inbox.body,
    confidence:inbox.match_confidence});
  if(!result.ok)return jsonResp(result);
  inbox.match_status="matched";inbox.candidate_ce_id=String(p.ce_id);inbox.candidate_ce_name=p.ce_name||"";
  inbox.reconciled_by=p.decided_by;inbox.reconciled_at=reviewNow();reviewWrite("inbox",inbox,inbox);
  return jsonResp({ok:true,inbox_item:inbox,suggestion:result.suggestion});
}

function reviewSuggestionDecide(p) {
  var err = reviewRequired(p, ["suggestion_id","decision","decided_by"]); if (err) return err;
  if (["approved","rejected"].indexOf(p.decision) < 0)
    return jsonResp({ok:false,error:"decision must be approved or rejected"});
  var existing = reviewFind("suggestions", function(r){ return r.suggestion_id === p.suggestion_id; });
  if (!existing) return jsonResp({ok:false,error:"suggestion not found"});
  existing.status=p.decision; existing.decided_by=p.decided_by; existing.decided_at=reviewNow();
  reviewWrite("suggestions", existing, existing);
  // Approval is explicit: the caller chooses the destination and can edit the text first.
  if (p.decision === "approved" && p.destination === "comment") {
    return reviewCommentUpsert({market_slug:existing.market_slug,ce_id:existing.ce_id,
      ce_name:existing.ce_name,week_start:existing.week_start,body:p.body || existing.body,
      author_name:existing.source_author || p.decided_by,author_role:p.author_role || "",
      source_type:existing.source_type,source_author:existing.source_author || "",accepted_by:p.decided_by,
      source_ref:existing.source_ref,source_url:existing.source_url});
  }
  if (p.decision === "approved" && (p.destination === "action" || p.destination === "check")) {
    return reviewWorkUpsert({market_slug:existing.market_slug,ce_id:existing.ce_id,
      ce_name:existing.ce_name,origin_week:existing.week_start,kind:p.destination,
      text:p.body || existing.body,owner:p.owner || "",status:p.work_status || "needs_action",
      due_date:p.due_date || existing.proposed_due_date,source_type:existing.source_type,
      source_ref:existing.source_ref,source_url:existing.source_url});
  }
  return jsonResp({ok:true, suggestion:existing});
}

function reviewMemory(p) {
  var err = reviewRequired(p, ["market_slug","ce_id"]); if (err) return err;
  var f = {market_slug:p.market_slug,ce_id:String(p.ce_id)};
  var comments = reviewFilter(reviewRows("comments"), f).sort(function(a,b){ return String(b.created_at).localeCompare(String(a.created_at)); });
  var work = reviewFilter(reviewRows("work"), f, "origin_week").sort(function(a,b){ return String(b.updated_at).localeCompare(String(a.updated_at)); });
  var receipts = reviewFilter(reviewRows("receipts"), f).sort(function(a,b){ return String(b.week_start).localeCompare(String(a.week_start)); });
  var suggestions = reviewFilter(reviewRows("suggestions"), f).sort(function(a,b){ return String(b.created_at).localeCompare(String(a.created_at)); });
  var thread = reviewFind("threads", function(r){ return r.market_slug===p.market_slug && String(r.ce_id)===String(p.ce_id); });
  // Existing notes/actions remain visible during migration, but stay clearly
  // labelled and are never rewritten into the new tables implicitly.
  var legacyNotes = allRows().filter(function(r){
    return r.market_slug===p.market_slug && String(r.ce_id)===String(p.ce_id) && r.note;
  }).map(function(r){return {legacy:true,market_slug:r.market_slug,ce_id:r.ce_id,
    ce_name:r.ce_name,week_start:r.week_start,body:r.note,author_name:r.author,
    source_type:"legacy_notes_sheet",source_url:r.slack_permalink||"",updated_at:r.updated};});
  var legacyActions = actionRowsFiltered(p.market_slug,"").filter(function(r){
    return String(r.ce_id)===String(p.ce_id) && (r.status||r.note||r.checkbox);
  });
  var openWork=work.filter(function(r){return !r.closed_at;});
  var recentClosed=work.filter(function(r){return !!r.closed_at;}).slice(0,25);
  return jsonResp({ok:true, identity:{market_slug:p.market_slug,ce_id:String(p.ce_id)},
    counts:{comments:comments.length,open_work:openWork.length,receipts:receipts.length,
      source_suggestions:suggestions.length,legacy_notes:legacyNotes.length},
    comments:comments.slice(0,25),work_items:openWork.concat(recentClosed),receipts:receipts.slice(0,12),
    source_suggestions:suggestions.slice(0,25),slack_thread:thread || null,
    legacy_notes:legacyNotes.slice(0,52),legacy_bucket_actions:legacyActions.slice(0,52),
    perf_history_contract:"read ce.perf_action_hist from the report snapshot; no review-store write"});
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

  if (action === "action_list") {
    if (!p.market) return jsonResp({ ok: false, error: "market required" });
    var aRows = actionRowsFiltered(p.market, p.week || "");
    return jsonResp({ ok: true, actions: aRows });
  }

  if (action === "action_delete") {
    if (!p.market_slug || !p.ce_id || !p.week_start || !p.bucket)
      return jsonResp({ ok: false, error: "market_slug, ce_id, week_start, bucket required" });
    var adSh = getActionSheet();
    var adFound = findActionRow(p.market_slug, p.ce_id, p.week_start, p.bucket);
    if (adFound) { adSh.deleteRow(adFound._row); return jsonResp({ ok: true, action: "deleted" }); }
    return jsonResp({ ok: true, action: "noop" });
  }

  if (action === "action_upsert") {
    var ash = getActionSheet();
    var aExisting = findActionRow(p.market_slug, p.ce_id, p.week_start, p.bucket);
    var aNow = new Date().toISOString();
    var aVals = [
      p.market_slug || "", String(p.ce_id || ""), p.week_start || "",
      p.bucket || "", p.checkbox || "", p.note || "", p.status || "",
      p.owner || "", aNow
    ];
    writeActionRow(ash, aExisting, aVals);
    return jsonResp({ ok: true, action: aExisting ? "updated" : "created", updated: aNow });
  }

  // Weekly Review V2. GET mutations are retained because the deployed Apps
  // Script already uses redirect-safe query requests; webhook/batch ingestion
  // can use doPost below.
  if (action === "review_comment_list") {
    var comments = reviewFilter(reviewRows("comments"), p);
    if (!reviewBool(p.include_deleted)) comments = comments.filter(function(r){ return !r.deleted_at; });
    var commentPage=reviewPage(comments,p,"created_at",50);
    return jsonResp({ok:true,comments:commentPage.items,next_before:commentPage.next_before});
  }
  if (action === "review_comment_upsert") return reviewCommentUpsert(p);
  if (action === "review_comment_delete") return reviewCommentDelete(p);
  if (action === "review_work_list") {
    var work = reviewFilter(reviewRows("work"), p, "origin_week");
    if (reviewBool(p.open_only)) work = work.filter(function(r){ return !r.closed_at; });
    var workPage=reviewPage(work,p,"updated_at",100);
    return jsonResp({ok:true,work_items:workPage.items,next_before:workPage.next_before});
  }
  if (action === "review_work_upsert") return reviewWorkUpsert(p);
  if (action === "review_receipt_list") {
    var receiptPage=reviewPage(reviewFilter(reviewRows("receipts"),p),p,"reviewed_at",52);
    return jsonResp({ok:true,receipts:receiptPage.items,next_before:receiptPage.next_before});
  }
  if (action === "review_receipt_upsert") return reviewReceiptUpsert(p);
  if (action === "review_set_list") {
    var setRows = reviewFilter(reviewRows("review_set"), p);
    return jsonResp({ok:true,review_set:setRows.filter(function(r){ return String(r.included) !== "false"; })});
  }
  if (action === "review_set_upsert") return reviewSetUpsert(p);
  if (action === "review_suggestion_list") {
    var sg = reviewFilter(reviewRows("suggestions"), p);
    if (!reviewBool(p.include_decided)) sg = sg.filter(function(r){ return r.status === "pending"; });
    var suggestionPage=reviewPage(sg,p,"created_at",50);
    return jsonResp({ok:true,suggestions:suggestionPage.items,next_before:suggestionPage.next_before});
  }
  if (action === "review_source_inbox") {
    var inbox=reviewFilter(reviewRows("inbox"),p);
    if(!reviewBool(p.include_reconciled))inbox=inbox.filter(function(r){return !r.reconciled_at;});
    return jsonResp({ok:true,inbox:inbox});
  }
  // External source ingestion is POST-only so its shared secret is never put in a URL.
  if (action === "review_source_ingest") return jsonResp({ok:false,error:"review_source_ingest requires POST"});
  if (action === "review_source_reconcile") return reviewSourceReconcile(p);
  if (action === "review_suggestion_decide") return reviewSuggestionDecide(p);
  if (action === "review_memory") return reviewMemory(p);
  if (action === "review_slack_post") return reviewSlackPost(p);
  if (action === "review_slack_scan") return reviewSlackScan(p);

  return jsonResp({ ok: false, error: "unknown action: " + action });
}

// JSON entry point for Granola/Slack adapters and future trusted automations.
// A single payload may be supplied, or `{items:[...]}` for source ingestion.
function doPost(e) {
  var payload = {};
  try { payload = JSON.parse((e.postData && e.postData.contents) || "{}"); }
  catch (err) { return jsonResp({ok:false,error:"invalid JSON"}); }
  var action = payload.action || "review_source_ingest";
  if(action === "review_source_ingest"){
    var expected=PropertiesService.getScriptProperties().getProperty("REVIEW_INGEST_SECRET");
    if(!expected)return jsonResp({ok:false,error:"REVIEW_INGEST_SECRET not configured"});
    if(String(payload.ingest_secret||"")!==String(expected))return jsonResp({ok:false,error:"unauthorized source ingestion"});
  }
  if (action === "review_source_ingest" && payload.items) {
    var results = payload.items.map(function(item) {
      item.source_type = item.source_type || payload.source_type;
      item.market_slug = item.market_slug || payload.market_slug;
      item.week_start = item.week_start || payload.week_start;
      return reviewSourceIngestRecord(item);
    });
    return jsonResp({ok:true,results:results});
  }
  if (action === "review_source_ingest") return reviewSuggestionIngest(payload);
  if (action === "review_suggestion_decide") return reviewSuggestionDecide(payload);
  return jsonResp({ok:false,error:"unsupported POST action: " + action});
}

// ── Weekly Review CE-scoped Slack relay ─────────────────────────────────────
// Unlike the legacy note relay below, this mapping is (market, CE), not
// (market, CE, week). Every week's questions and replies stay in one durable CE
// thread. The BGM supplies free-form text and may mention any Slack user.
function reviewThreadFor(market, ceId) {
  return reviewFind("threads", function(r){
    return r.market_slug === market && String(r.ce_id) === String(ceId);
  });
}

function reviewSlackPost(p) {
  var err = reviewRequired(p,["market_slug","ce_id","week_start","channel","text","author"]);
  if (err) return err;
  var token = PropertiesService.getScriptProperties().getProperty("SLACK_BOT_TOKEN");
  if (!token) return jsonResp({ok:false,error:"SLACK_BOT_TOKEN not set in Script properties"});
  var existing = reviewThreadFor(p.market_slug,p.ce_id);
  if (existing && existing.slack_channel && existing.slack_channel !== p.channel)
    return jsonResp({ok:false,error:"CE thread already belongs to another Slack channel",thread:existing});

  var header = "*Weekly Review · " + (p.ce_name || ("CE " + p.ce_id)) + "*";
  var context = "_" + p.market_slug + " · CE " + p.ce_id + " · W/C " + ymd(p.week_start) + "_";
  var body = (existing ? "" : (header + "\n" + context + "\n")) + p.text +
    "\n_— " + p.author + "_" + (p.report_url ? "\n<" + p.report_url + "|Open CE review>" : "");
  var payload = {channel:p.channel,text:body,username:"Weekly Market Review",icon_emoji:":memo:",unfurl_links:false};
  if (existing && existing.slack_thread_ts) payload.thread_ts=String(existing.slack_thread_ts);
  var resp = UrlFetchApp.fetch("https://slack.com/api/chat.postMessage",{
    method:"post",contentType:"application/json; charset=utf-8",
    headers:{Authorization:"Bearer " + token},payload:JSON.stringify(payload),muteHttpExceptions:true});
  var result = JSON.parse(resp.getContentText());
  if (!result.ok) return jsonResp({ok:false,error:"slack: " + (result.error || "unknown")});
  var now=reviewNow(), anchor=(existing && String(existing.slack_thread_ts)) || String(result.ts);
  var permalink=getPermalink(token,p.channel,anchor);
  var record={market_slug:p.market_slug,ce_id:String(p.ce_id),ce_name:p.ce_name||"",
    slack_channel:p.channel,slack_thread_ts:anchor,
    slack_permalink:permalink || (existing && existing.slack_permalink) || "",
    created_at:(existing && existing.created_at)||now,updated_at:now,
    last_scanned_ts:(existing && existing.last_scanned_ts)||anchor};
  reviewWrite("threads",existing,record);
  return jsonResp({ok:true,thread:record,posted_ts:String(result.ts)});
}

function reviewSlackScan(p) {
  var err=reviewRequired(p,["market_slug","ce_id","week_start"]); if(err)return err;
  var token=PropertiesService.getScriptProperties().getProperty("SLACK_BOT_TOKEN");
  if(!token)return jsonResp({ok:false,error:"SLACK_BOT_TOKEN not set in Script properties"});
  var thread=reviewThreadFor(p.market_slug,p.ce_id);
  if(!thread)return jsonResp({ok:false,error:"no CE Slack thread"});
  var since=String(thread.last_scanned_ts||thread.slack_thread_ts||"0");
  var result=slackThreadReplies(token,thread.slack_channel,thread.slack_thread_ts,since);
  if(!result.ok)return jsonResp(result);
  var created=[],newest=since;
  (result.messages||[]).forEach(function(msg){
    var ts=String(msg.ts||"");
    if(!ts||ts<=since||ts===String(thread.slack_thread_ts)||msg.bot_id||msg.subtype)return;
    newest=ts>newest?ts:newest;
    var ref=thread.slack_channel+":"+ts;
    var duplicate=reviewFind("suggestions",function(r){return r.source_type==="slack"&&r.source_ref===ref;});
    if(duplicate)return;
    var rec={suggestion_id:reviewId("sgg"),market_slug:p.market_slug,ce_id:String(p.ce_id),
      ce_name:p.ce_name||thread.ce_name||"",week_start:ymd(p.week_start),source_type:"slack",
      source_author:slackUserName(token,msg.user),source_ref:ref,
      source_url:getPermalink(token,thread.slack_channel,ts),kind:"comment",
      // Raw reply is the fail-closed suggestion. AI may propose a better summary below,
      // but the source text and author ID remain attached and approval is still required.
      body:msg.text||"",proposed_owner:"",proposed_due_date:"",confidence:"source_exact",
      status:"pending",created_at:reviewNow(),decided_by:"",decided_at:""};
    reviewWrite("suggestions",null,rec); created.push(rec);
  });
  thread.last_scanned_ts=newest; thread.updated_at=reviewNow(); reviewWrite("threads",thread,thread);
  var ai=reviewAiSuggestions("slack",created,p);
  return jsonResp({ok:true,new_replies:created,ai:ai,thread:thread});
}

function slackThreadReplies(token,channel,threadTs,oldest){
  var messages=[],cursor="",pages=0;
  do{
    var url="https://slack.com/api/conversations.replies?channel="+encodeURIComponent(channel)+
      "&ts="+encodeURIComponent(String(threadTs))+"&limit=200&inclusive=false"+
      (oldest?"&oldest="+encodeURIComponent(oldest):"")+
      (cursor?"&cursor="+encodeURIComponent(cursor):"");
    var resp=UrlFetchApp.fetch(url,{headers:{Authorization:"Bearer "+token},muteHttpExceptions:true});
    var body=JSON.parse(resp.getContentText());
    if(!body.ok)return {ok:false,error:"slack: "+(body.error||"unknown")};
    messages=messages.concat(body.messages||[]);
    cursor=((body.response_metadata||{}).next_cursor)||"";pages++;
  }while(cursor&&pages<20); // 4,000 replies per scan; cursor retained by last_scanned_ts next run.
  return {ok:true,messages:messages,truncated:!!cursor};
}

// Optional adapter: set REVIEW_AI_WEBHOOK_URL to a trusted service that returns
// `{suggestions:[{source_ref,kind,body,proposed_owner,proposed_due_date,confidence}]}`.
// With no adapter or a bad response, raw source suggestions remain pending and
// the API explicitly reports source_unavailable; it never invents a summary.
function reviewAiSuggestions(sourceType, sourceRows, context) {
  if(!sourceRows.length)return {status:"no_new_source",suggestions:[]};
  var endpoint=PropertiesService.getScriptProperties().getProperty("REVIEW_AI_WEBHOOK_URL");
  if(!endpoint)return {status:"source_unavailable",suggestions:[]};
  try{
    var resp=UrlFetchApp.fetch(endpoint,{method:"post",contentType:"application/json",
      payload:JSON.stringify({source_type:sourceType,identity:{market_slug:context.market_slug,
        ce_id:String(context.ce_id),week_start:ymd(context.week_start)},records:sourceRows}),muteHttpExceptions:true});
    var body=JSON.parse(resp.getContentText());
    if(!body||!body.suggestions)return {status:"invalid_response",suggestions:[]};
    var out=[];
    body.suggestions.forEach(function(s){
      var source=sourceRows.filter(function(r){return r.source_ref===s.source_ref;})[0];
      if(!source||!s.body)return; // fail closed: AI output must point to ingested source
      var rec={suggestion_id:reviewId("sgg"),market_slug:source.market_slug,ce_id:source.ce_id,
        ce_name:source.ce_name,week_start:source.week_start,source_type:source.source_type,
        source_author:source.source_author||"",source_ref:source.source_ref+":ai:"+(s.kind||"comment"),source_url:source.source_url,
        kind:s.kind||"comment",body:s.body,proposed_owner:s.proposed_owner||"",
        proposed_due_date:ymd(s.proposed_due_date||""),confidence:s.confidence||"",
        status:"pending",created_at:reviewNow(),decided_by:"",decided_at:""};
      reviewWrite("suggestions",null,rec);out.push(rec);
    });
    return {status:"ok",suggestions:out};
  }catch(ex){return {status:"source_unavailable",suggestions:[]};}
}

function slackUserName(token,userId){
  if(!userId)return "";
  try{
    var r=UrlFetchApp.fetch("https://slack.com/api/users.info?user="+encodeURIComponent(userId),
      {headers:{Authorization:"Bearer "+token},muteHttpExceptions:true});
    var j=JSON.parse(r.getContentText()),u=j.user||{},profile=u.profile||{};
    return profile.display_name||profile.real_name||u.real_name||u.name||userId;
  }catch(ex){return userId;}
}

// ── Legacy CE/week Slack relay ──────────────────────────────────────────────
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
