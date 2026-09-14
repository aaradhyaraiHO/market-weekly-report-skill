/**
 * Google Apps Script — isolated WBR Review-mode service.
 *
 * This artifact must be deployed from a dedicated Apps Script project backed by
 * the dedicated Review spreadsheet. It deliberately contains only `review_*`
 * routes and Review storage. The established weekly diagnostic service is a
 * separate deployment and is never a fallback for this code.
 *
 * Required Script properties:
 *   REVIEW_SPREADSHEET_ID
 *   REVIEW_HISTORY_SPREADSHEET_ID (defaults to the authoritative Weekly Report Notes workbook)
 *   REVIEW_MODE_PROXY_SECRET
 *   REVIEW_MODE_INGEST_SECRET
 *   REVIEW_ENFORCE_ACCESS=true
 * Optional integrations:
 *   REVIEW_MODE_AI_WEBHOOK_URL
 *   REVIEW_MODE_AI_WEBHOOK_SECRET
 *   SLACK_BOT_TOKEN
 *   REVIEW_ENABLE_DIRECTORY_SYNC
 */

function ymd(v) {
  if (v == null || v === "") return "";
  if (Object.prototype.toString.call(v) === "[object Date]") {
    return Utilities.formatDate(v, "UTC", "yyyy-MM-dd");
  }
  return String(v).slice(0, 10);
}

// ── Weekly Review V2 backend ────────────────────────────────────────────────
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
      "created_at","updated_at","closed_at","deleted_at","deleted_by",
      "requester_id","owner_id","next_review_date","latest_update","expected_effect",
      "completion_evidence","measured_outcome","approval_state","approved_by","approved_at",
      "idempotency_key","duplicate_of","parent_work_id","carry_forward","archived_at"]
  },
  receipts: {
    sheet: "review_receipts",
    headers: ["receipt_id","market_slug","ce_id","ce_name","week_start","treatment",
      "reviewer","reviewed_at","next_review_date","summary","open_work_count","no_discussion_reason"]
  },
  outcomes: {
    sheet: "review_outcomes",
    headers: ["outcome_id","market_slug","ce_id","ce_name","week_start","outcome_type",
      "decision","no_discussion","approved_by","approved_at","created_at","updated_at"]
  },
  timeline: {
    sheet: "review_timeline_events",
    headers: ["event_id","market_slug","ce_id","ce_name","review_week","event_type",
      "source_type","source_ref","source_url","actor_id","actor_name","actor_role",
      "occurred_at","recorded_at","original_body","approved_body","approval_state",
      "approved_by","approved_at","related_review_id","related_work_id","supersedes_event_id","idempotency_key"]
  },
  telemetry: {
    sheet: "review_pilot_telemetry",
    headers: ["telemetry_id","market_slug","ce_id","week_start","event_type","value_number",
      "value_text","actor_name","session_id","idempotency_key","occurred_at"]
  },
  review_set: {
    sheet: "review_set",
    headers: ["market_slug","week_start","ce_id","ce_name","position","treatment",
      "reason","source","included","updated_at"]
  },
  threads: {
    sheet: "ce_threads",
    headers: ["market_slug","ce_id","ce_name","slack_channel","slack_thread_ts",
      "slack_permalink","created_at","updated_at","last_scanned_ts",
      "binding_id","binding_status","created_reason","replaced_reason",
      "predecessor_binding_id","successor_binding_id","created_by",
      "replacement_week","weekly_starter_ts","weekly_starter_week","last_post_request_id"]
  },
  weekly: {
    sheet: "review_weekly_commentary",
    headers: ["weekly_id","market_slug","ce_id","ce_name","week_start","bgm_note",
      "bgm_author","bgm_updated_at","note_deleted_at","performance_note","performance_author",
      "performance_updated_at","performance_note_deleted_at","bdm_note","bdm_author","bdm_updated_at",
      "bdm_note_deleted_at","slack_post_ts","slack_post_permalink","last_scanned_ts",
      "reply_count","contributors_json","summary_json","summary_upto_ts","summary_updated_at",
      "summary_status","summary_draft_json","summary_approved_json","summary_approved_by",
      "summary_approved_at","summary_rejected_at","summary_rejection_reason",
      "sync_status","last_error","last_post_request_id","version",
      "thread_binding_id","slack_discussion_number",
      "summary_thread_binding_id","summary_slack_discussion_number"]
  },
  suggestions: {
    sheet: "review_source_suggestions",
    headers: ["suggestion_id","market_slug","ce_id","ce_name","week_start","source_type",
      "source_author","source_ref","source_url","kind","body","proposed_owner","proposed_due_date",
      "confidence","status","created_at","decided_by","decided_at","decision_destination",
      "accepted_body","accepted_owner","accepted_due_date","idempotency_key","provider_meeting_id","access_scope","thread_binding_id"]
  },
  imports: {
    sheet: "review_meeting_imports",
    headers: ["batch_id","market_slug","week_start","items_json","created_at"]
  },
  inbox: {
    sheet: "review_source_inbox",
    headers: ["source_item_id","source_type","source_ref","source_url","source_author",
      "occurred_at","market_slug","week_start","candidate_ce_id","candidate_ce_name",
      "match_confidence","match_status","kind","body","created_at","reconciled_by","reconciled_at",
      "provider_meeting_id","access_scope","content_hash","idempotency_key"]
  },
  access: {
    sheet: "bgm_access",
    headers: ["email","display_name","market_slug","role","active","updated_at"]
  },
  people: {
    sheet: "review_slack_people",
    headers: ["slack_user_id","display_name","real_name","aliases","market_slug","active","updated_at"]
  }
};

// Read-only legacy memory source. This is deliberately outside REVIEW_TABLES:
// Review never creates, rewrites, or appends to these historical tabs.
var REVIEW_HISTORY_DEFAULT_SPREADSHEET_ID = "1hC_IAsJrlPcpFv5K49eRtcwgK6i_DkAt4ZvETxlK-s8";
var REVIEW_HISTORY_SCHEMAS = {
  actions: ["market_slug","ce_id","week_start","bucket","checkbox","note","status","owner","updated"],
  notes: ["market_slug","ce_id","ce_name","week_start","note","author","updated","slack_channel","slack_thread_ts","slack_permalink"]
};

function reviewStableCeId(value) {
  var raw = String(value == null ? "" : value).trim();
  // Google Sheets may return numeric IDs as numbers (or an exported workbook
  // may render them as `384.0`).  Normalize that representation without
  // collapsing composite CE IDs such as `18 - Paris`: the location suffix is
  // part of the stable identity and prevents history leaking across sibling
  // city entities that share the same numeric family ID.
  if (/^\d+(?:\.0+)?$/.test(raw)) return raw.replace(/\.0+$/, "");
  var composite = raw.match(/^(\d+)\s*-\s*(\S(?:.*\S)?)$/);
  return composite ? composite[1] + " - " + composite[2] : "";
}

function reviewHistoricalRows(kind, market, ceId) {
  var schema = REVIEW_HISTORY_SCHEMAS[kind];
  if (!schema) return {rows:[], unavailable:true, error:"unknown historical source"};
  try {
    var id = String(PropertiesService.getScriptProperties().getProperty("REVIEW_HISTORY_SPREADSHEET_ID") || REVIEW_HISTORY_DEFAULT_SPREADSHEET_ID).trim();
    var sh = SpreadsheetApp.openById(id).getSheetByName(kind), wanted = reviewStableCeId(ceId);
    if (!sh) return {rows:[], unavailable:true, error:"historical " + kind + " tab unavailable"};
    var last = sh.getLastRow();
    if (last < 2) return {rows:[], unavailable:false, skipped_missing_ce_id:0, duplicates:0};
    var cache = CacheService.getScriptCache(), cacheKey = "review-history-v2:" + id + ":" + kind + ":" + String(market);
    var cached = cache.get(cacheKey), payload = null;
    try { payload = cached ? JSON.parse(cached) : null; } catch (_) { payload = null; }
    if (!payload) {
      var values = sh.getRange(2, 1, last - 1, schema.length).getValues(), marketRows = [], skippedAll = 0;
      values.forEach(function(valuesRow, index) {
        var row = {_source_row:index + 2};
        schema.forEach(function(header, col) { row[header] = valuesRow[col]; });
        var stable = reviewStableCeId(row.ce_id);
        if (!stable) { skippedAll++; return; }
        if (String(row.market_slug) !== String(market)) return;
        row.ce_id = stable; row.week_start = ymd(row.week_start); row.updated = String(row.updated || "");
        marketRows.push(row);
      });
      payload = {rows:marketRows, skipped_missing_ce_id:skippedAll};
      try { cache.put(cacheKey, JSON.stringify(payload), 300); } catch (_) {}
    }
    var skipped = payload.skipped_missing_ce_id || 0, duplicates = 0, seen = {}, rows = [];
    payload.rows.forEach(function(row) {
      if (row.ce_id !== wanted) return;
      var signature = kind + "|" + [row.market_slug,row.ce_id,row.week_start,row.bucket,row.note,row.status,row.owner,row.author,row.updated].join("|");
      if (seen[signature]) { seen[signature]._duplicate_count++; duplicates++; return; }
      row._duplicate_count = 1; seen[signature] = row; rows.push(row);
    });
    return {rows:rows, unavailable:false, skipped_missing_ce_id:skipped, duplicates:duplicates};
  } catch (error) {
    return {rows:[], unavailable:true, error:"historical source unavailable"};
  }
}

var reviewSpreadsheetHandle = null;
function reviewSpreadsheet() {
  if (reviewSpreadsheetHandle) return reviewSpreadsheetHandle;
  var id = String(PropertiesService.getScriptProperties().getProperty("REVIEW_SPREADSHEET_ID") || "").trim();
  if (!id) throw new Error("REVIEW_SPREADSHEET_ID not configured");
  reviewSpreadsheetHandle = SpreadsheetApp.openById(id);
  return reviewSpreadsheetHandle;
}

var reviewSheetHandles = {};
function reviewSheet(kind) {
  if (reviewSheetHandles[kind]) return reviewSheetHandles[kind];
  var def = REVIEW_TABLES[kind];
  if (!def) throw new Error("unknown review table: " + kind);
  var ss = reviewSpreadsheet();
  var sh = ss.getSheetByName(def.sheet);
  if (!sh) {
    sh = ss.insertSheet(def.sheet);
    sh.getRange(1, 1, 1, def.headers.length).setValues([def.headers]);
    sh.getRange(1, 1, 1, def.headers.length).setFontWeight("bold");
    sh.setFrozenRows(1);
  } else {
    // Additive schema evolution: keep existing records while making newly
    // introduced audit columns visible to Sheet operators.
    var headerRange=sh.getRange(1,1,1,def.headers.length),headers=headerRange.getValues()[0];
    if(def.headers.some(function(h,i){return headers[i]!==h;})){
      headerRange.setValues([def.headers]);headerRange.setFontWeight("bold");
    }
  }
  reviewSheetHandles[kind]=sh;
  return sh;
}

var reviewRowCache = {};
function reviewRows(kind) {
  if (reviewRowCache[kind]) return reviewRowCache[kind].map(function(row){return Object.assign({},row);});
  var def = REVIEW_TABLES[kind], sh = reviewSheet(kind), last = sh.getLastRow();
  if (last < 2) return [];
  var data = sh.getRange(2, 1, last - 1, def.headers.length).getValues();
  var rows = data.map(function(row, idx) {
    var obj = {_row: idx + 2};
    def.headers.forEach(function(h, col) { obj[h] = row[col]; });
    if (obj.ce_id !== undefined) obj.ce_id = String(obj.ce_id);
    ["week_start","origin_week","review_week","replacement_week","weekly_starter_week","due_date","next_review_date","proposed_due_date","accepted_due_date"].forEach(function(h) {
      if (obj[h] !== undefined) obj[h] = Object.prototype.toString.call(obj[h])==="[object Date]"
        ? Utilities.formatDate(obj[h],reviewSpreadsheet().getSpreadsheetTimeZone(),"yyyy-MM-dd") : ymd(obj[h]);
    });
    return obj;
  });
  reviewRowCache[kind] = rows;
  return rows.map(function(row){return Object.assign({},row);});
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
    delete reviewRowCache[kind];
    var row = existing ? existing._row : sh.getLastRow() + 1;
    sh.getRange(row, 1, 1, vals.length).setValues([vals]);
    ["week_start","origin_week","review_week","replacement_week","weekly_starter_week","due_date","next_review_date","proposed_due_date","accepted_due_date","slack_thread_ts",
      "last_scanned_ts","weekly_starter_ts"].forEach(function(h) {
        var col = def.headers.indexOf(h) + 1;
        // Sheets eagerly coerces a Slack timestamp such as 1787552580.536449
        // into a number, silently dropping precision.  Store identity/time keys
        // as literal text so the persistent CE thread can always be read back
        // and used in conversations.replies.
        if (col > 0) sh.getRange(row, col).setNumberFormat("@").setValue("'" + String(record[h] || ""));
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
    if (p.source_type && String(r.source_type) !== String(p.source_type)) return false;
    if (p.week && ymd(r[weekField || "week_start"]) !== ymd(p.week)) return false;
    if (p.status && String(r.status) !== String(p.status)) return false;
    return true;
  });
}

function reviewPage(rows,p,dateField,defaultLimit,idField){
  var before=String(p.before||""),limit=Math.min(Math.max(parseInt(p.limit||defaultLimit,10)||defaultLimit,1),200);
  function cursor(r){return String(r[dateField]||"")+(idField?"|"+String(r[idField]||""):"");}
  rows=rows.filter(function(r){return !before||cursor(r)<before;})
    .sort(function(a,b){return cursor(a)<cursor(b)?1:cursor(a)>cursor(b)?-1:0;});
  var items=rows.slice(0,limit),next=rows.length>limit&&items.length?cursor(items[items.length-1]):"";
  return {items:items,next_before:next};
}

function reviewBool(v) { return String(v || "").toLowerCase() === "true"; }
function reviewId(prefix) { return prefix + "_" + Utilities.getUuid(); }
function reviewNow() { return new Date().toISOString(); }

function reviewActorCanonicalParams(p) {
  return Object.keys(p || {}).filter(function(key) { return key !== "actor_sig"; }).sort()
    .map(function(key) { return encodeURIComponent(key) + "=" + encodeURIComponent(String(p[key] == null ? "" : p[key])); })
    .join("\n");
}

function reviewHex(bytes) {
  return bytes.map(function(value) {
    return ("0" + ((value + 256) % 256).toString(16)).slice(-2);
  }).join("");
}

function reviewSafeEqual(a, b) {
  a = String(a || ""); b = String(b || "");
  if (!a || a.length !== b.length) return false;
  var mismatch = 0;
  for (var i = 0; i < a.length; i++) mismatch |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return mismatch === 0;
}

function reviewSignedActorStatus(p) {
  var email = String(p.actor_email || "").trim().toLowerCase();
  var timestamp = parseInt(p.actor_ts || "0", 10);
  var signature = String(p.actor_sig || "").toLowerCase();
  // Properties entered through the Apps Script settings UI can accidentally
  // carry a trailing newline. Keep the signed Review boundary strict while
  // normalising that transport-only whitespace on both sides.
  var secret = String(PropertiesService.getScriptProperties().getProperty("REVIEW_MODE_PROXY_SECRET") || "").trim();
  if (!email || !timestamp || !signature || !secret) {
    console.warn("review_signature_rejected", JSON.stringify({action:String(p.action||""),reason:"missing_field",email_present:!!email,timestamp_present:!!timestamp,signature_present:!!signature,secret_present:!!secret}));
    return {email:"",reason:"missing_field"};
  }
  var age = Math.floor(Date.now() / 1000) - timestamp;
  if (Math.abs(age) > 300) {
    console.warn("review_signature_rejected", JSON.stringify({action:String(p.action||""),reason:"expired",age_seconds:age}));
    return {email:"",reason:"expired"};
  }
  var expected = reviewHex(Utilities.computeHmacSha256Signature(reviewActorCanonicalParams(p), secret));
  if (!reviewSafeEqual(signature, expected)) {
    console.warn("review_signature_rejected", JSON.stringify({action:String(p.action||""),reason:"signature_mismatch",age_seconds:age,field_count:Object.keys(p).length}));
    return {email:"",reason:"signature_mismatch"};
  }
  return {email:email,reason:"ok"};
}

function reviewSignedActorEmail(p) { return reviewSignedActorStatus(p).email; }

function reviewActorEmail(p) {
  var email = "";
  try { email = Session.getActiveUser().getEmail() || ""; } catch (err) {}
  if (!email) email = reviewSignedActorEmail(p);
  if (!email && reviewBool(PropertiesService.getScriptProperties().getProperty("REVIEW_ALLOW_ACTOR_PARAM")))
    email = p.actor_email || "";
  return String(email).trim().toLowerCase();
}

function reviewAuthenticatedActor(p) {
  if (!reviewBool(PropertiesService.getScriptProperties().getProperty("REVIEW_ENFORCE_ACCESS")))
    return {ok:false,error:"Review access enforcement is not configured"};
  var email=reviewActorEmail(p);
  if(!email)return {ok:false,error:"authenticated BGM identity required ["+reviewSignedActorStatus(p).reason+"]"};
  return {ok:true,actor_email:email,enforcement:"on"};
}

function reviewAccessDecision(p) {
  var authenticated=reviewAuthenticatedActor(p);
  if(!authenticated.ok)return authenticated;
  var email=authenticated.actor_email;
  var market=String(p.market_slug||p.market||"");
  var allowed=reviewRows("access").filter(function(r){
    return String(r.email||"").toLowerCase()===email && reviewBool(r.active) &&
      (String(r.market_slug)==="*" || String(r.market_slug)===market) &&
      ["bgm","gm","admin"].indexOf(String(r.role||"").toLowerCase())>=0;
  })[0];
  return allowed ? {ok:true,actor_email:email,access:allowed} :
    {ok:false,error:"BGM is not allowed to change this market"};
}

function reviewTrustedAuthor(p,fallback) {
  var decision=reviewAccessDecision(p);
  return decision.ok&&decision.access&&decision.access.display_name ?
    String(decision.access.display_name) : String(fallback||"");
}

function reviewMutationGate(action,p){
  var mutations=["review_comment_upsert","review_comment_delete","review_work_upsert","review_work_delete",
    "review_receipt_upsert","review_outcome_upsert","review_timeline_event_upsert","review_telemetry_record","review_set_upsert","review_source_reconcile",
    "review_suggestion_decide","review_slack_post","review_slack_scan",
    "review_granola_link_submit",
    "review_weekly_note_upsert","review_weekly_note_delete","review_weekly_slack_post","review_weekly_sync",
    "review_summary_decide"];
  if(mutations.indexOf(action)<0)return null;
  // Verify the proxy signature against the *original* request before resolving
  // an ID-only mutation to its CE/market.  The resolver below deliberately
  // enriches `p`; verifying after that would sign a different payload and make
  // valid suggestion/delete mutations look unauthenticated.
  var authenticated=reviewAuthenticatedActor(p);
  if(!authenticated.ok)return jsonResp({ok:false,error:authenticated.error});
  // ID-only delete calls resolve their immutable Review identity before the
  // market access check. The caller cannot choose a different market.
  if(action==="review_comment_delete"&&!p.market_slug&&p.comment_id){
    var comment=reviewFind("comments",function(r){return r.comment_id===p.comment_id;});
    if(comment){p.market_slug=comment.market_slug;p.ce_id=comment.ce_id;}
  }
  if(action==="review_work_delete"&&!p.market_slug&&p.work_id){
    var work=reviewFind("work",function(r){return r.work_id===p.work_id;});
    if(work){p.market_slug=work.market_slug;p.ce_id=work.ce_id;}
  }
  // Suggestions are immutable CE-scoped records. Resolve the scope server-side
  // before authorizing a decision, so a caller cannot use an ID from another
  // market with an empty or forged market_slug.
  if(action==="review_suggestion_decide"&&!p.market_slug&&p.suggestion_id){
    var suggestion=reviewFind("suggestions",function(r){return r.suggestion_id===p.suggestion_id;});
    if(suggestion){p.market_slug=suggestion.market_slug;p.ce_id=suggestion.ce_id;}
  }
  var market=String(p.market_slug||p.market||"");
  var allowed=reviewRows("access").filter(function(r){
    return String(r.email||"").toLowerCase()===authenticated.actor_email && reviewBool(r.active) &&
      (String(r.market_slug)==="*" || String(r.market_slug)===market) &&
      ["bgm","gm","admin"].indexOf(String(r.role||"").toLowerCase())>=0;
  })[0];
  return allowed ? null : jsonResp({ok:false,error:"BGM is not allowed to change this market"});
}

function reviewUpsertBy(kind,predicate,buildRecord){
  var def=REVIEW_TABLES[kind],lock=LockService.getScriptLock();
  lock.waitLock(10000);
  try{
    delete reviewRowCache[kind]; // Re-read after acquiring the mutation lock.
    var rows=reviewRows(kind),existing=null;
    for(var i=0;i<rows.length;i++)if(predicate(rows[i])){existing=rows[i];break;}
    var prior=existing&&def.headers.map(function(h){return existing[h]==null?"":existing[h];});
    var record=buildRecord(existing);
    var vals=def.headers.map(function(h){return record[h]==null?"":record[h];});
    // An idempotent replay is a read, not another Sheet write.
    if(existing&&JSON.stringify(prior)===JSON.stringify(vals))return existing;
    var sh=reviewSheet(kind);
    var row=existing?existing._row:sh.getLastRow()+1;
    sh.getRange(row,1,1,vals.length).setValues([vals]);
    delete reviewRowCache[kind];
    ["week_start","origin_week","review_week","replacement_week","weekly_starter_week","due_date","next_review_date","proposed_due_date","accepted_due_date","slack_thread_ts",
      "slack_post_ts","last_scanned_ts","summary_upto_ts"].forEach(function(h){
      var col=def.headers.indexOf(h)+1;
      if(col>0)sh.getRange(row,col).setNumberFormat("@").setValue("'" + String(record[h]||""));
    });
    return record;
  }finally{lock.releaseLock();}
}

function reviewWeeklyFor(market,ceId,week){
  return reviewFind("weekly",function(r){return r.market_slug===market &&
    String(r.ce_id)===String(ceId) && ymd(r.week_start)===ymd(week);});
}

function reviewWeeklyBase(p,existing){
  return {
    weekly_id:(existing&&existing.weekly_id)||reviewId("wcy"),market_slug:p.market_slug,
    ce_id:String(p.ce_id),ce_name:p.ce_name||(existing&&existing.ce_name)||"",
    week_start:ymd(p.week_start),bgm_note:(existing&&existing.bgm_note)||"",
    bgm_author:(existing&&existing.bgm_author)||"",bgm_updated_at:(existing&&existing.bgm_updated_at)||"",
    note_deleted_at:(existing&&existing.note_deleted_at)||"",
    performance_note:(existing&&existing.performance_note)||"",performance_author:(existing&&existing.performance_author)||"",
    performance_updated_at:(existing&&existing.performance_updated_at)||"",
    performance_note_deleted_at:(existing&&existing.performance_note_deleted_at)||"",
    bdm_note:(existing&&existing.bdm_note)||"",bdm_author:(existing&&existing.bdm_author)||"",
    bdm_updated_at:(existing&&existing.bdm_updated_at)||"",bdm_note_deleted_at:(existing&&existing.bdm_note_deleted_at)||"",
    thread_binding_id:(existing&&existing.thread_binding_id)||"",
    slack_discussion_number:(existing&&existing.slack_discussion_number)||"",
    slack_post_ts:(existing&&existing.slack_post_ts)||"",
    slack_post_permalink:(existing&&existing.slack_post_permalink)||"",
    last_scanned_ts:(existing&&existing.last_scanned_ts)||"",reply_count:(existing&&existing.reply_count)||"0",
    contributors_json:(existing&&existing.contributors_json)||"[]",
    summary_json:(existing&&existing.summary_json)||"",summary_upto_ts:(existing&&existing.summary_upto_ts)||"",
    summary_updated_at:(existing&&existing.summary_updated_at)||"",
    summary_status:(existing&&existing.summary_status)||"",
    summary_draft_json:(existing&&existing.summary_draft_json)||"",
    summary_approved_json:(existing&&existing.summary_approved_json)||"",
    summary_approved_by:(existing&&existing.summary_approved_by)||"",
    summary_approved_at:(existing&&existing.summary_approved_at)||"",
    summary_rejected_at:(existing&&existing.summary_rejected_at)||"",
    summary_rejection_reason:(existing&&existing.summary_rejection_reason)||"",
    summary_thread_binding_id:(existing&&existing.summary_thread_binding_id)||"",
    summary_slack_discussion_number:(existing&&existing.summary_slack_discussion_number)||"",
    sync_status:(existing&&existing.sync_status)||"draft",last_error:(existing&&existing.last_error)||"",
    last_post_request_id:(existing&&existing.last_post_request_id)||"",
    version:String(parseInt((existing&&existing.version)||"0",10)||0)
  };
}

function reviewWeeklyMutate(p,mutator){
  return reviewUpsertBy("weekly",function(r){return r.market_slug===p.market_slug&&
    String(r.ce_id)===String(p.ce_id)&&ymd(r.week_start)===ymd(p.week_start);},function(existing){
      return mutator(reviewWeeklyBase(p,existing),existing);
    });
}

function reviewWeeklyNoteUpsert(p){
  var noteType=String(p.note_type||"bgm").toLowerCase();
  if(["bgm","performance","bdm"].indexOf(noteType)<0)return jsonResp({ok:false,error:"invalid note_type"});
  var noteKey=noteType+"_note",authorKey=noteType+"_author",updatedKey=noteType+"_updated_at";
  var deletedKey=noteType==="bgm"?"note_deleted_at":noteType+"_note_deleted_at";
  var noteValue=p[noteKey]!=null?p[noteKey]:p.note;
  var suppliedAuthor=p[authorKey]!=null?p[authorKey]:p.author;
  var err=reviewRequired(Object.assign({},p,{note_value:noteValue,note_author:suppliedAuthor}),["market_slug","ce_id","week_start","note_value","note_author"]);if(err)return err;
  var trustedAuthor=reviewTrustedAuthor(p,suppliedAuthor);
  var rec=reviewUpsertBy("weekly",function(r){return r.market_slug===p.market_slug&&
    String(r.ce_id)===String(p.ce_id)&&ymd(r.week_start)===ymd(p.week_start);},function(existing){
      var next=reviewWeeklyBase(p,existing),now=reviewNow();
      if(noteType==="bgm"){next.bgm_note=noteValue;next.bgm_author=trustedAuthor;next.bgm_updated_at=now;}
      else{next[noteKey]=noteValue;next[authorKey]=trustedAuthor;next[updatedKey]=now;}
      next[deletedKey]="";next.sync_status=next.slack_post_ts?"sent":"saved";next.last_error="";
      next.version=String((parseInt(next.version,10)||0)+1);return next;
    });
  return jsonResp({ok:true,weekly:rec});
}

function reviewWeeklyNoteDelete(p){
  var err=reviewRequired(p,["market_slug","ce_id","week_start","deleted_by"]);if(err)return err;
  var existing=reviewWeeklyFor(p.market_slug,p.ce_id,p.week_start);
  if(!existing)return jsonResp({ok:true,action:"noop"});
  var noteType=String(p.note_type||"bgm").toLowerCase();
  if(["bgm","performance","bdm"].indexOf(noteType)<0)return jsonResp({ok:false,error:"invalid note_type"});
  var deletedKey=noteType==="bgm"?"note_deleted_at":noteType+"_note_deleted_at";
  var rec=reviewWeeklyMutate(p,function(next){next[deletedKey]=reviewNow();
    next.sync_status=next.slack_post_ts?next.sync_status:"note_deleted";
    next.version=String((parseInt(next.version,10)||0)+1);return next;});
  return jsonResp({ok:true,weekly:rec,action:"tombstoned"});
}

function reviewRegexEscape(value){return String(value).replace(/[.*+?^${}()|[\]\\]/g,"\\$&");}

function reviewResolveMentions(text,market){
  var matches=[],ambiguous=[],people=reviewRows("people").filter(function(r){
    return reviewBool(r.active) && (String(r.market_slug||"*")==="*"||String(r.market_slug)===String(market));
  });
  var candidates={};
  people.forEach(function(person){
    var aliases=[person.display_name,person.real_name].concat(String(person.aliases||"").split(";"));
    aliases.forEach(function(alias){alias=String(alias||"").trim();if(!alias)return;
      var key=alias.toLowerCase();(candidates[key]=candidates[key]||[]).push(person);});
  });
  Object.keys(candidates).sort(function(a,b){return b.length-a.length;}).forEach(function(key){
    var alias=key,rx=new RegExp("\\b"+reviewRegexEscape(alias)+"\\b","i");
    if(!rx.test(text))return;
    var unique={},rows=candidates[key].filter(function(p){var id=String(p.slack_user_id);if(unique[id])return false;unique[id]=true;return true;});
    if(rows.length!==1){ambiguous.push({name:alias,candidates:rows.map(function(p){return {id:p.slack_user_id,name:p.display_name||p.real_name};})});return;}
    if(!matches.some(function(m){return m.slack_user_id===String(rows[0].slack_user_id);}))
      matches.push({name:rows[0].display_name||rows[0].real_name||alias,slack_user_id:String(rows[0].slack_user_id)});
  });
  var resolved=String(text||"");
  matches.forEach(function(m){
    var names=[m.name].concat(people.filter(function(p){return String(p.slack_user_id)===m.slack_user_id;})
      .reduce(function(out,p){return out.concat([p.display_name,p.real_name]).concat(String(p.aliases||"").split(";"));},[]));
    names.filter(Boolean).sort(function(a,b){return String(b).length-String(a).length;}).some(function(name){
      // Consume a user-typed @ when present. Otherwise '@Pari' becomes
      // '@<@U...>' and Slack renders it as the confusing '@@Pari'. The
      // prefix guard also avoids treating an existing Slack mention as text.
      var rx=new RegExp("(^|[^\\w<])@?"+reviewRegexEscape(String(name).trim())+"\\b","i");
      if(!rx.test(resolved))return false;
      resolved=resolved.replace(rx,function(_match,prefix){return (prefix||"")+"<@"+m.slack_user_id+">";});
      return true;
    });
  });
  return {resolved_text:resolved,matches:matches,ambiguous:ambiguous};
}

function reviewMentionResolve(p){
  var err=reviewRequired(p,["market_slug","text"]);if(err)return err;
  return jsonResp(Object.assign({ok:true},reviewResolveMentions(p.text,p.market_slug)));
}

function reviewCommentUpsert(p) {
  var err = reviewRequired(p, ["market_slug","ce_id","week_start","body","author_name"]);
  if (err) return err;
  var existing = p.comment_id ? reviewFind("comments", function(r){ return r.comment_id === p.comment_id; }) : null;
  if (p.comment_id && !existing) return jsonResp({ok:false,error:"comment not found"});
  if (existing && (existing.market_slug !== p.market_slug || String(existing.ce_id) !== String(p.ce_id) || ymd(existing.week_start)!==ymd(p.week_start)))
    return jsonResp({ok:false,error:"comment identity is immutable"});
  if(existing&&existing.deleted_at)return jsonResp({ok:false,error:"This note was deleted. Your draft has been kept."});
  if(existing&&existing.body===p.body)return jsonResp({ok:true,duplicate:true,comment:existing});
  if(existing&&p.expected_updated_at!==undefined&&String(p.expected_updated_at)!==String(existing.updated_at||existing.created_at||""))
    return jsonResp({ok:false,error:"This note has a newer edit. Your draft has been kept; reload the saved note before editing again."});
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
  if(existing){
    // Keep attribution and source identity when editing the same note.
    ["author_name","author_role","source_type","source_author","source_ref","source_url","accepted_by"].forEach(function(k){rec[k]=existing[k]||"";});
    // Archive before replacing. An interrupted save can be retried without
    // losing the previous text or duplicating its revision.
    var revisionKey="comment_revision:"+existing.comment_id+":"+reviewHash(JSON.stringify([existing.updated_at,existing.body]));
    reviewUpsertBy("timeline",function(r){return r.idempotency_key===revisionKey;},function(old){return old||{
      event_id:reviewId("evt"),market_slug:existing.market_slug,ce_id:String(existing.ce_id),ce_name:existing.ce_name,
      review_week:ymd(existing.week_start),event_type:"comment_revision",source_type:existing.source_type,
      source_ref:existing.comment_id,source_url:existing.source_url||"",actor_name:existing.author_name,
      occurred_at:existing.updated_at||existing.created_at,recorded_at:now,original_body:existing.body,
      approved_body:existing.body,approval_state:"superseded",approved_by:reviewTrustedAuthor(p,p.author_name),
      approved_at:now,idempotency_key:revisionKey
    };});
    try{
      rec=reviewUpsertBy("comments",function(r){return r.comment_id===existing.comment_id;},function(current){
        if(!current||current.deleted_at||current.body!==existing.body||String(current.updated_at)!==String(existing.updated_at))
          throw new Error("This note changed while saving. Your draft has been kept; reload the saved note before editing again.");
        return rec;
      });
    }catch(error){return jsonResp({ok:false,error:error.message});}
  }else if(p.source_type==="manual"&&p.source_ref){
    // Check AFTER taking the write lock. The first request can still complete
    // after its browser times out; a retry must not append a second note.
    var replay=false;
    try{
      rec=reviewUpsertBy("comments",function(r){return r.market_slug===p.market_slug&&String(r.ce_id)===String(p.ce_id)&&ymd(r.week_start)===ymd(p.week_start)&&r.source_ref===p.source_ref&&r.source_type==="manual";},function(current){
        if(current){
          if(current.deleted_at||current.body!==p.body)throw new Error("This save request was already used for a different or deleted note. Your draft is kept.");
          replay=true;return current;
        }
        return rec;
      });
    }catch(error){return jsonResp({ok:false,error:error.message});}
    return jsonResp({ok:true,duplicate:replay,comment:rec});
  }else reviewWrite("comments", existing, rec);
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
    "monitoring","scheduled","blocked","stale","dismissed","no_action_needed","complete","cancelled"];
  if(statuses.indexOf(p.status)<0)return jsonResp({ok:false,error:"unsupported work status"});
  if(!p.work_id&&p.idempotency_key){
    var duplicate=reviewFind("work",function(r){return r.market_slug===p.market_slug&&String(r.ce_id)===String(p.ce_id)&&r.idempotency_key===p.idempotency_key;});
    if(duplicate)return jsonResp({ok:true,duplicate:true,work_item:duplicate});
  }
  var existing = p.work_id ? reviewFind("work", function(r){ return r.work_id === p.work_id; }) : null;
  if (p.work_id && !existing) return jsonResp({ok:false,error:"work item not found"});
  if (existing && (existing.market_slug !== p.market_slug || String(existing.ce_id) !== String(p.ce_id)))
    return jsonResp({ok:false,error:"work identity is immutable"});
  var now = reviewNow(), closed = ["complete","cancelled","dismissed","no_action_needed"].indexOf(p.status) >= 0;
  var rec = {
    work_id:existing ? existing.work_id : reviewId("wrk"), market_slug:p.market_slug,
    ce_id:String(p.ce_id), ce_name:p.ce_name || (existing && existing.ce_name) || "",
    origin_week:ymd(p.origin_week), kind:p.kind, text:p.text,
    // Owner is deliberately never inferred. Empty is valid for a scheduled check.
    owner:p.owner || "", status:p.status, due_date:ymd(p.due_date || ""),
    source_type:p.source_type || (existing&&existing.source_type) || "manual",
    source_ref:p.source_ref===undefined?((existing&&existing.source_ref)||""):p.source_ref,
    source_url:p.source_url===undefined?((existing&&existing.source_url)||""):p.source_url, created_at:(existing && existing.created_at) || now,
    updated_at:now, closed_at:closed ? ((existing && existing.closed_at) || now) : "",
    deleted_at:(existing && existing.deleted_at) || "", deleted_by:(existing && existing.deleted_by) || "",
    requester_id:p.requester_id||(existing&&existing.requester_id)||"",owner_id:p.owner_id||(existing&&existing.owner_id)||"",
    next_review_date:ymd(p.next_review_date||(existing&&existing.next_review_date)||""),latest_update:p.latest_update||(existing&&existing.latest_update)||"",
    expected_effect:p.expected_effect||(existing&&existing.expected_effect)||"",completion_evidence:p.completion_evidence||(existing&&existing.completion_evidence)||"",
    measured_outcome:p.measured_outcome||(existing&&existing.measured_outcome)||"",approval_state:p.approval_state||(existing&&existing.approval_state)||"approved",
    approved_by:p.approved_by||(existing&&existing.approved_by)||reviewTrustedAuthor(p,""),approved_at:(existing&&existing.approved_at)||now,
    idempotency_key:p.idempotency_key||(existing&&existing.idempotency_key)||"",duplicate_of:p.duplicate_of||(existing&&existing.duplicate_of)||"",
    parent_work_id:p.parent_work_id||(existing&&existing.parent_work_id)||"",carry_forward:String(reviewBool(p.carry_forward===undefined?(existing&&existing.carry_forward):p.carry_forward)),
    archived_at:p.archived_at||(existing&&existing.archived_at)||""
  };
  reviewWrite("work", existing, rec);
  return jsonResp({ok:true, work_item:rec});
}

function reviewOutcomeUpsert(p){
  var err=reviewRequired(p,["market_slug","ce_id","week_start","outcome_type","decision","approved_by"]);if(err)return err;
  var existing=reviewFind("outcomes",function(r){return r.market_slug===p.market_slug&&String(r.ce_id)===String(p.ce_id)&&ymd(r.week_start)===ymd(p.week_start);});
  var now=reviewNow(),rec={outcome_id:(existing&&existing.outcome_id)||reviewId("out"),market_slug:p.market_slug,
    ce_id:String(p.ce_id),ce_name:p.ce_name||(existing&&existing.ce_name)||"",week_start:ymd(p.week_start),
    outcome_type:String(p.outcome_type),decision:String(p.decision),no_discussion:String(reviewBool(p.no_discussion)),
    approved_by:reviewTrustedAuthor(p,p.approved_by),approved_at:now,created_at:(existing&&existing.created_at)||now,updated_at:now};
  reviewWrite("outcomes",existing,rec);return jsonResp({ok:true,outcome:rec});
}

function reviewTimelineEventUpsert(p){
  var err=reviewRequired(p,["market_slug","ce_id","review_week","event_type","approved_body","approved_by","idempotency_key"]);if(err)return err;
  if(["nomination","metric_outcome","completion_evidence"].indexOf(String(p.event_type))<0)
    return jsonResp({ok:false,error:"unsupported manual timeline event type"});
  var existing=reviewFind("timeline",function(r){return r.market_slug===p.market_slug&&String(r.ce_id)===String(p.ce_id)&&String(r.idempotency_key)===String(p.idempotency_key);});
  if(existing)return jsonResp({ok:true,duplicate:true,event:existing});
  var now=reviewNow(),rec={event_id:reviewId("evt"),market_slug:p.market_slug,ce_id:String(p.ce_id),ce_name:p.ce_name||"",
    review_week:ymd(p.review_week),event_type:String(p.event_type),source_type:p.source_type||"human",source_ref:p.source_ref||"",
    source_url:p.source_url||"",actor_id:p.actor_id||"",actor_name:reviewTrustedAuthor(p,p.approved_by),actor_role:p.actor_role||"bgm",
    occurred_at:p.occurred_at||now,recorded_at:now,original_body:p.original_body||p.approved_body,approved_body:p.approved_body,
    approval_state:"approved",approved_by:reviewTrustedAuthor(p,p.approved_by),approved_at:now,related_review_id:p.related_review_id||"",
    related_work_id:p.related_work_id||"",supersedes_event_id:p.supersedes_event_id||"",idempotency_key:p.idempotency_key};
  reviewWrite("timeline",null,rec);return jsonResp({ok:true,event:rec});
}

function reviewTelemetryRecord(p){
  var err=reviewRequired(p,["market_slug","week_start","event_type","idempotency_key"]);if(err)return err;
  var existing=reviewFind("telemetry",function(r){return r.market_slug===p.market_slug&&String(r.idempotency_key)===String(p.idempotency_key);});
  if(existing)return jsonResp({ok:true,duplicate:true,telemetry:existing});
  var rec={telemetry_id:reviewId("tel"),market_slug:p.market_slug,ce_id:String(p.ce_id||""),week_start:ymd(p.week_start),
    event_type:String(p.event_type),value_number:p.value_number==null?"":String(p.value_number),value_text:String(p.value_text||""),
    actor_name:reviewTrustedAuthor(p,p.actor_name||""),session_id:String(p.session_id||""),idempotency_key:String(p.idempotency_key),occurred_at:p.occurred_at||reviewNow()};
  reviewWrite("telemetry",null,rec);return jsonResp({ok:true,telemetry:rec});
}

function reviewTimeline(p, fullHistory){
  var market=p.market_slug,ce=String(p.ce_id),events=reviewFilter(reviewRows("timeline"),{market_slug:market,ce_id:ce}).slice();
  function add(type,week,when,body,source,ref,url,actor,reviewId,workId){events.push({event_id:"projection:"+type+":"+String(ref||week||when),market_slug:market,ce_id:ce,review_week:ymd(week),event_type:type,occurred_at:when||week,recorded_at:when||week,approved_body:body||"",approval_state:"approved",source_type:source||"review",source_ref:ref||"",source_url:url||"",actor_name:actor||"",related_review_id:reviewId||"",related_work_id:workId||"",read_only:true});}
  reviewFilter(reviewRows("review_set"),{market_slug:market,ce_id:ce}).forEach(function(r){add(r.treatment&&r.treatment!=="not_scheduled"?"shortlist_selected":"candidate_created",r.week_start,r.updated_at,r.reason,"weekly_report",r.source);});
  reviewFilter(reviewRows("weekly"),{market_slug:market,ce_id:ce}).forEach(function(r){if(r.bgm_note&&!r.note_deleted_at)add("bgm_observation",r.week_start,r.bgm_updated_at,r.bgm_note,"review",r.weekly_id,"",r.bgm_author);if(r.slack_post_ts)add("slack_discussion",r.week_start,r.slack_post_ts,"Slack discussion started or continued","slack",r.slack_post_ts,r.slack_post_permalink,r.bgm_author);if(String(r.summary_status)==="approved"&&(r.summary_approved_json||r.summary_json))add("slack_summary",r.week_start,r.summary_approved_at||r.summary_updated_at,r.summary_approved_json||r.summary_json,"slack",r.summary_upto_ts,r.slack_post_permalink,r.summary_approved_by||"BGM");});
  reviewFilter(reviewRows("outcomes"),{market_slug:market,ce_id:ce}).forEach(function(r){add("outcome_approved",r.week_start,r.approved_at,r.decision,"review",r.outcome_id,"",r.approved_by,r.outcome_id);});
  reviewFilter(reviewRows("work"),{market_slug:market,ce_id:ce}).filter(function(r){return !r.deleted_at;}).forEach(function(r){add(r.closed_at?"work_completed":"work_opened",r.origin_week,r.updated_at,r.text,"review",r.source_ref,r.source_url,r.approved_by,"",r.work_id);});
  reviewFilter(reviewRows("receipts"),{market_slug:market,ce_id:ce}).forEach(function(r){add("review_finished",r.week_start,r.reviewed_at,r.summary,"review",r.receipt_id,"",r.reviewer,r.receipt_id);});
  return events.sort(function(a,b){return String(b.occurred_at||b.recorded_at||"").localeCompare(String(a.occurred_at||a.recorded_at||""));}).slice(0,fullHistory?undefined:250);
}

function reviewBacklog(p){
  var market=p.market_slug,now=ymd(new Date()),actor=String(p.actor_name||"").toLowerCase();
  var work=reviewRows("work").filter(function(r){return r.market_slug===market&&!r.deleted_at;});
  var suggestions=reviewRows("suggestions").filter(function(r){return r.market_slug===market&&(!r.status||r.status==="pending");});
  return {needs_approval:suggestions,open:work.filter(function(r){return !r.closed_at&&!r.archived_at;}),mine:work.filter(function(r){return !r.closed_at&&actor&&String(r.owner||r.owner_id||"").toLowerCase()===actor;}),
    blocked_overdue:work.filter(function(r){return !r.closed_at&&(r.status==="blocked"||(r.due_date&&ymd(r.due_date)<now));}),stale:work.filter(function(r){return !r.closed_at&&r.status==="stale";}),
    recently_completed:work.filter(function(r){return !!r.closed_at&&!r.archived_at;}).sort(function(a,b){return String(b.closed_at).localeCompare(String(a.closed_at));}).slice(0,100),
    archived:work.filter(function(r){return !!r.archived_at||r.status==="dismissed";})};
}

function reviewReconciliation(p){
  var market=String(p.market_slug||""),week=ymd(p.week_start||p.week),start=new Date(week+"T00:00:00Z");
  if(isNaN(start.getTime()))start=new Date();
  var prior=new Date(start.getTime());prior.setUTCDate(prior.getUTCDate()-7);var priorWeek=ymd(prior),now=ymd(new Date());
  var work=reviewRows("work").filter(function(r){return r.market_slug===market&&!r.deleted_at;});
  function open(r){return !r.closed_at&&!r.archived_at;}
  return {week_start:week,prior_cycle_start:priorWeek,
    completed_since_prior:work.filter(function(r){return r.closed_at&&ymd(r.closed_at)>=priorWeek;}),
    open:work.filter(open),
    blocked_overdue:work.filter(function(r){return open(r)&&(r.status==="blocked"||(r.due_date&&ymd(r.due_date)<now));}),
    carried_forward:work.filter(function(r){return open(r)&&reviewBool(r.carry_forward);}),
    evidence_suggesting_completion:work.filter(function(r){return open(r)&&String(r.completion_evidence||"").trim();}),
    revisit_required:work.filter(function(r){return open(r)&&(reviewBool(r.carry_forward)||r.status==="stale"||(r.next_review_date&&ymd(r.next_review_date)<=week));}),
    later_economic_outcome:{status:"unavailable",reason:"An approved comparison contract is not configured; Review does not infer metric attribution."}};
}

function reviewWorkDelete(p) {
  var err = reviewRequired(p, ["work_id","deleted_by"]); if (err) return err;
  var existing = reviewFind("work", function(r){ return r.work_id === p.work_id; });
  if (!existing) return jsonResp({ok:false,error:"work item not found"});
  existing.deleted_at = existing.deleted_at || reviewNow();
  existing.deleted_by = existing.deleted_by || reviewTrustedAuthor(p,p.deleted_by);
  existing.updated_at = existing.deleted_at;
  reviewWrite("work", existing, existing);
  return jsonResp({ok:true, work_id:p.work_id, deleted_at:existing.deleted_at});
}

function reviewReceiptUpsert(p) {
  var err = reviewRequired(p, ["market_slug","ce_id","week_start","treatment","reviewer"]);
  if (err) return err;
  if(p.treatment==="not_scheduled")return jsonResp({ok:false,error:"review treatment is required"});
  var weekly=reviewWeeklyFor(p.market_slug,p.ce_id,p.week_start);
  var noDiscussionReason=String(p.no_discussion_reason||"").trim();
  if(!(weekly&&weekly.slack_post_ts)&&!noDiscussionReason)return jsonResp({ok:false,error:"Slack discussion or concise no-discussion reason is required"});
  var pending=reviewFilter(reviewRows("suggestions"),{market_slug:p.market_slug,ce_id:String(p.ce_id)}).filter(function(r){return ymd(r.week_start)===ymd(p.week_start)&&(!r.status||r.status==="pending");});
  if(pending.length)return jsonResp({ok:false,error:"pending suggestions must be triaged before completion"});
  var unresolved=reviewFilter(reviewRows("work"),{market_slug:p.market_slug,ce_id:String(p.ce_id)}).filter(function(r){return !r.deleted_at&&!r.closed_at;});
  var unmanaged=unresolved.filter(function(r){return !(reviewBool(r.carry_forward)||(r.owner&&(r.due_date||r.next_review_date))||(r.kind==="check"&&(r.due_date||r.next_review_date)));});
  if(unmanaged.length)return jsonResp({ok:false,error:"unresolved work needs an owner/date or explicit carry-forward"});
  var existing = reviewFind("receipts", function(r){
    return r.market_slug === p.market_slug && String(r.ce_id) === String(p.ce_id) &&
      ymd(r.week_start) === ymd(p.week_start);
  });
  var now = reviewNow();
  var rec = {
    receipt_id:(existing && existing.receipt_id) || reviewId("rcp"), market_slug:p.market_slug,
    ce_id:String(p.ce_id), ce_name:p.ce_name || (existing && existing.ce_name) || "",
    week_start:ymd(p.week_start), treatment:p.treatment, reviewer:p.reviewer,
    reviewed_at:now, next_review_date:ymd(p.next_review_date || ""),
    summary:p.summary||"",open_work_count:String(unresolved.length),
    no_discussion_reason:noDiscussionReason||(existing&&existing.no_discussion_reason)||""
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
  var stableKey=String(p.idempotency_key||[p.source_type,p.source_ref,p.ce_id,p.kind,String(p.body||"").toLowerCase().replace(/\s+/g," ").trim()].join(":"));
  var duplicate = reviewFind("suggestions", function(r){
    return String(r.idempotency_key||"")===stableKey||(r.source_type === p.source_type && r.source_ref === p.source_ref && String(r.ce_id)===String(p.ce_id) && r.kind === p.kind);
  });
  if (duplicate) return {ok:true,duplicate:true,suggestion:duplicate};
  var rec = {
    suggestion_id:reviewId("sgg"), market_slug:p.market_slug, ce_id:String(p.ce_id),
    ce_name:p.ce_name || "", week_start:ymd(p.week_start), source_type:p.source_type,
    source_author:p.source_author || "", source_ref:p.source_ref, source_url:p.source_url || "", kind:p.kind, body:p.body,
    proposed_owner:p.proposed_owner || "", proposed_due_date:ymd(p.proposed_due_date || ""),
    confidence:p.confidence || "", status:"pending", created_at:reviewNow(), decided_by:"", decided_at:"",
    decision_destination:"",accepted_body:"",accepted_owner:"",accepted_due_date:"",idempotency_key:stableKey,
    provider_meeting_id:p.provider_meeting_id||"",access_scope:p.access_scope||"",thread_binding_id:p.thread_binding_id||""
  };
  var saved=reviewUpsertBy("suggestions",function(r){
    return String(r.idempotency_key||"")===stableKey||(r.source_type===p.source_type&&r.source_ref===p.source_ref&&String(r.ce_id)===String(p.ce_id)&&r.kind===p.kind);
  },function(old){return old||rec;});
  return {ok:true,duplicate:saved.suggestion_id!==rec.suggestion_id,suggestion:saved};
}

// Freeze the first extraction before saving suggestions. Retries (including
// concurrent requests with different model wording) replay that exact batch.
function reviewImportBatch(p){
  if(!p.batch_id||!p.market_slug||!p.week_start)return jsonResp({ok:false,error:"batch identity required"});
  var key=function(r){return r.batch_id===p.batch_id&&r.market_slug===p.market_slug&&ymd(r.week_start)===ymd(p.week_start);};
  var existing=reviewFind("imports",key);
  if(!existing&&!Array.isArray(p.items))return jsonResp({ok:true,found:false});
  var encoded=JSON.stringify(p.items||[]);
  if(!existing&&encoded.length>45000)return jsonResp({ok:false,error:"Meeting extraction is too large; split the transcript"});
  var batch=existing||reviewUpsertBy("imports",key,function(old){return old||{
    batch_id:p.batch_id,market_slug:p.market_slug,week_start:ymd(p.week_start),items_json:encoded,created_at:reviewNow()
  };});
  var results=JSON.parse(batch.items_json).map(function(item){return reviewSourceIngestRecord(item);});
  return jsonResp({ok:true,found:true,results:results,replayed:!!existing});
}

function reviewSourceIngestRecord(p) {
  var missing=["market_slug","week_start","source_type","source_ref","kind","body"]
    .filter(function(k){return p[k]==null||String(p[k]).trim()==="";});
  if(missing.length)return {ok:false,error:"required: "+missing.join(", ")};
  p.source_type=String(p.source_type).toLowerCase();
  if(["granola","slack"].indexOf(p.source_type)<0)
    return {ok:false,error:"source_type must be slack or granola"};
  if(["comment","action","check"].indexOf(String(p.kind))<0)
    return {ok:false,error:"kind must be comment, action, or check"};
  if(p.source_type!=="granola" && !p.ce_id)
    return {ok:false,error:"ce_id required for non-Granola source"};
  // Granola is only allowed into a CE when the upstream matcher explicitly
  // says exact. Candidate IDs on ambiguous/retry records are evidence for the
  // reconciliation queue, never permission to attach to a CE.
  var matched=!!p.ce_id && (p.source_type!=="granola" || String(p.match_status)==="exact");
  if(matched)return reviewSuggestionRecord(p);
  var duplicate=reviewFind("inbox",function(r){return r.source_type===p.source_type&&r.source_ref===p.source_ref;});
  if(duplicate)return {ok:true,duplicate:true,inbox_item:duplicate};
  var rec={source_item_id:reviewId("src"),source_type:p.source_type,source_ref:p.source_ref,
    source_url:p.source_url||"",source_author:p.source_author||"",occurred_at:p.occurred_at||"",
    market_slug:p.market_slug,week_start:ymd(p.week_start),candidate_ce_id:String(p.candidate_ce_id||""),
    candidate_ce_name:p.candidate_ce_name||"",match_confidence:p.match_confidence||"",
    match_status:p.match_status||"unmatched",kind:p.kind,body:p.body,created_at:reviewNow(),
    reconciled_by:"",reconciled_at:"",provider_meeting_id:p.provider_meeting_id||"",access_scope:p.access_scope||"",
    content_hash:p.content_hash||"",idempotency_key:p.idempotency_key||[p.source_type,p.source_ref,p.kind].join(":")};
  var saved=reviewUpsertBy("inbox",function(r){return r.source_type===p.source_type&&r.source_ref===p.source_ref;},function(old){return old||rec;});
  return {ok:true,duplicate:saved.source_item_id!==rec.source_item_id,queued_for_reconciliation:true,inbox_item:saved};
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

function reviewGranolaPullLink(p,url){
  var endpoint=String(PropertiesService.getScriptProperties().getProperty("REVIEW_GRANOLA_PULL_URL")||"").trim();
  var secret=String(PropertiesService.getScriptProperties().getProperty("REVIEW_GRANOLA_PULL_SECRET")||"").trim();
  if(!endpoint||!secret)return {status:"queued",reason:"Granola pull service is not configured"};
  // Use the Review set as the bounded catalogue for this market/week. A meeting
  // may produce suggestions for more than the CE that was used to attach it,
  // but only an exact CE-name match can leave the source inbox.
  var seen={},ces=[];reviewRows("review_set").filter(function(r){return r.market_slug===p.market_slug&&
    ymd(r.week_start)===ymd(p.week_start)&&reviewBool(r.included);}).forEach(function(r){
      if(!seen[String(r.ce_id)]){seen[String(r.ce_id)]=true;ces.push({ce_id:String(r.ce_id),ce_name:r.ce_name||""});}});
  if(!seen[String(p.ce_id)])ces.push({ce_id:String(p.ce_id),ce_name:p.ce_name||""});
  try{
    var resp=UrlFetchApp.fetch(endpoint,{method:"post",contentType:"application/json",
      headers:{"X-Review-Secret":secret},payload:JSON.stringify({market_slug:p.market_slug,
        week_start:ymd(p.week_start),source_url:url,ces:ces}),muteHttpExceptions:true});
    var body=JSON.parse(resp.getContentText());
    return resp.getResponseCode()>=200&&resp.getResponseCode()<300&&body&&body.ok?
      {status:"submitted",items_queued:body.items_queued||0}:{status:"queued",reason:(body&&body.error)||("Granola pull returned "+resp.getResponseCode())};
  }catch(ex){return {status:"queued",reason:String(ex)};}
}

// A pasted Granola meeting is stored first, then the isolated pull service is
// asked to extract it. Failure never drops the source: it remains visibly
// queued and can be retried after credentials or the link are corrected.
function reviewGranolaLinkSubmit(p){
  var err=reviewRequired(p,["market_slug","ce_id","ce_name","week_start","source_url","submitted_by"]);if(err)return err;
  var url=String(p.source_url||"").trim();
  if(!/^https:\/\/([a-z0-9-]+\.)*granola\.ai\//i.test(url))
    return jsonResp({ok:false,error:"Paste a valid Granola meeting link"});
  var existing=reviewFind("inbox",function(r){return r.source_type==="granola"&&r.source_url===url&&
    r.market_slug===p.market_slug&&String(r.candidate_ce_id)===String(p.ce_id)&&ymd(r.week_start)===ymd(p.week_start);});
  if(existing)return jsonResp({ok:true,duplicate:true,inbox_item:existing});
  var ref="granola-link:"+Utilities.base64EncodeWebSafe(url).slice(0,48);
  var rec={source_item_id:reviewId("src"),source_type:"granola",source_ref:ref,source_url:url,
    source_author:p.submitted_by,occurred_at:p.occurred_at||"",market_slug:p.market_slug,
    week_start:ymd(p.week_start),candidate_ce_id:String(p.ce_id),candidate_ce_name:p.ce_name,
    match_confidence:"bgm_attached",match_status:"awaiting_import",kind:"comment",
    body:"Granola meeting attached by "+p.submitted_by+"; awaiting source extraction.",created_at:reviewNow(),
    reconciled_by:"",reconciled_at:"",provider_meeting_id:p.provider_meeting_id||"",access_scope:p.access_scope||"",
    content_hash:p.content_hash||"",idempotency_key:ref};
  reviewWrite("inbox",null,rec);
  var pull=reviewGranolaPullLink(p,url);
  return jsonResp({ok:true,inbox_item:rec,pull:pull});
}

function reviewSuggestionDecide(p) {
  var err = reviewRequired(p, ["suggestion_id","decision","decided_by"]); if (err) return err;
  if (["approved","rejected"].indexOf(p.decision) < 0)
    return jsonResp({ok:false,error:"decision must be approved or rejected"});
  var existing = reviewFind("suggestions", function(r){ return r.suggestion_id === p.suggestion_id; });
  if (!existing) return jsonResp({ok:false,error:"suggestion not found"});
  if (existing.status && existing.status !== "pending")
    return jsonResp({ok:true,duplicate:true,suggestion:existing});
  if (p.decision === "approved" && ["comment","action","check"].indexOf(p.destination) < 0)
    return jsonResp({ok:false,error:"approved suggestion requires comment, action, or check destination"});
  existing.status=p.decision; existing.decided_by=p.decided_by; existing.decided_at=reviewNow();
  existing.decision_destination=p.decision === "approved" ? p.destination : "ignored";
  existing.accepted_body=p.body || existing.body;
  existing.accepted_owner=p.owner || "";
  existing.accepted_due_date=ymd(p.due_date || existing.proposed_due_date || "");
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
  var work = reviewFilter(reviewRows("work"), f, "origin_week").filter(function(r){return !r.deleted_at;})
    .sort(function(a,b){ return String(b.updated_at).localeCompare(String(a.updated_at)); });
  var receipts = reviewFilter(reviewRows("receipts"), f).sort(function(a,b){ return String(b.week_start).localeCompare(String(a.week_start)); });
  var weekly = reviewFilter(reviewRows("weekly"), f).sort(function(a,b){ return String(b.week_start).localeCompare(String(a.week_start)); });
  var suggestions = reviewFilter(reviewRows("suggestions"), f).sort(function(a,b){ return String(b.created_at).localeCompare(String(a.created_at)); });
  var threads = reviewThreadsFor(p.market_slug,p.ce_id);
  var historicalActions=reviewHistoricalRows("actions",p.market_slug,p.ce_id);
  var historicalComments=reviewHistoricalRows("notes",p.market_slug,p.ce_id);
  var perfHistory=historicalActions.rows.map(function(row){return {
    ce_id:row.ce_id,week_start:row.week_start,bucket:String(row.bucket||""),action_text:String(row.note||""),
    owner:String(row.owner||""),status:String(row.status||""),outcome:"",updated_at:row.updated,
    duplicate_count:row._duplicate_count,source_row:row._source_row,read_only:true
  };});
  var legacyComments=historicalComments.rows.map(function(row){return {
    ce_id:row.ce_id,ce_name:String(row.ce_name||""),week_start:row.week_start,body:String(row.note||""),
    author_name:String(row.author||""),created_at:row.updated,slack_channel:String(row.slack_channel||""),
    slack_thread_ts:String(row.slack_thread_ts||""),slack_permalink:String(row.slack_permalink||""),
    duplicate_count:row._duplicate_count,source_row:row._source_row,read_only:true
  };});
  var openWork=work.filter(function(r){return !r.closed_at;});
  var recentClosed=work.filter(function(r){return !!r.closed_at;});
  var timeline=reviewTimeline(p,true);
  perfHistory.forEach(function(r){timeline.push({event_id:"history:perf:"+String(r.source_row||r.week_start),market_slug:p.market_slug,ce_id:String(p.ce_id),review_week:r.week_start,event_type:"performance_history",source_type:"historical_sheet",occurred_at:r.updated_at||r.week_start,approved_body:r.action_text,actor_name:r.owner,approval_state:"read_only",read_only:true});});
  legacyComments.forEach(function(r){timeline.push({event_id:"history:comment:"+String(r.source_row||r.week_start),market_slug:p.market_slug,ce_id:String(p.ce_id),review_week:r.week_start,event_type:"historical_comment",source_type:"historical_sheet",source_url:r.slack_permalink,occurred_at:r.created_at||r.week_start,approved_body:r.body,actor_name:r.author_name,approval_state:"read_only",read_only:true});});
  timeline.sort(function(a,b){return String(b.occurred_at||b.recorded_at||"").localeCompare(String(a.occurred_at||a.recorded_at||""));});
  return jsonResp({ok:true, identity:{market_slug:p.market_slug,ce_id:String(p.ce_id)},
    counts:{comments:comments.length,weekly_commentary:weekly.length,open_work:openWork.length,receipts:receipts.length,
      source_suggestions:suggestions.length},
    weekly_commentary:weekly,comments:comments,work_items:openWork.concat(recentClosed),receipts:receipts,
    source_suggestions:suggestions.slice(0,25),slack_thread:reviewThreadFor(p.market_slug,p.ce_id),slack_threads:threads,timeline:timeline,
    perf_history:perfHistory,historical_comments:legacyComments,
    historical_source_status:{actions:{unavailable:historicalActions.unavailable,skipped_missing_ce_id:historicalActions.skipped_missing_ce_id||0,duplicates:historicalActions.duplicates||0},
      comments:{unavailable:historicalComments.unavailable,skipped_missing_ce_id:historicalComments.skipped_missing_ce_id||0,duplicates:historicalComments.duplicates||0}},
    diagnostic_history_contract:"read-only report snapshot or dedicated GET-only adapter; no Review-store write",
    perf_history_contract:"read ce.perf_action_hist from the report snapshot; no review-store write"});
}

function doGet(e) {
  var p = e.parameter;
  var action = p.action || "";
  var denied=reviewMutationGate(action,p);if(denied)return denied;
  var readAccess=reviewAccessDecision(p);
  if(!readAccess.ok)return jsonResp({ok:false,error:readAccess.error});

  // Do not put notes, work, author names, or Slack text in a URL.  The Review
  // browser client uses doPost for every mutation.  This is also a hard split
  // from the legacy diagnostic Apps Script, whose GET action contract remains
  // unchanged in apps_script.js.
  var getMutations=["review_comment_upsert","review_comment_delete","review_work_upsert","review_work_delete",
    "review_receipt_upsert","review_outcome_upsert","review_timeline_event_upsert","review_telemetry_record","review_set_upsert","review_source_reconcile","review_suggestion_decide",
    "review_granola_link_submit","review_weekly_note_upsert","review_weekly_note_delete",
    "review_weekly_slack_post","review_weekly_sync","review_summary_decide","review_slack_post","review_slack_scan"];
  if(getMutations.indexOf(action)>=0)return jsonResp({ok:false,error:action+" requires POST"});
  if (action === "review_comment_list") {
    var comments = reviewFilter(reviewRows("comments"), p);
    if(p.comment_id)comments=comments.filter(function(r){return r.comment_id===p.comment_id;});
    if(p.source_ref)comments=comments.filter(function(r){return r.source_ref===p.source_ref;});
    if (!reviewBool(p.include_deleted)) comments = comments.filter(function(r){ return !r.deleted_at; });
    var commentPage=reviewPage(comments,p,"created_at",50);
    return jsonResp({ok:true,comments:commentPage.items,next_before:commentPage.next_before});
  }
  if (action === "review_work_list") {
    var work = reviewFilter(reviewRows("work"), p, "origin_week");
    if (!reviewBool(p.include_deleted)) work = work.filter(function(r){ return !r.deleted_at; });
    if (reviewBool(p.open_only)) work = work.filter(function(r){ return !r.closed_at; });
    var workPage=reviewPage(work,p,"updated_at",100,"work_id");
    return jsonResp({ok:true,work_items:workPage.items,next_before:workPage.next_before});
  }
  if (action === "review_receipt_list") {
    var receiptPage=reviewPage(reviewFilter(reviewRows("receipts"),p),p,"reviewed_at",52);
    return jsonResp({ok:true,receipts:receiptPage.items,next_before:receiptPage.next_before});
  }
  if(action==="review_outcome_list"){
    return jsonResp({ok:true,outcomes:reviewFilter(reviewRows("outcomes"),p).sort(function(a,b){return String(b.updated_at||"").localeCompare(String(a.updated_at||""));})});
  }
  if(action==="review_timeline")return jsonResp({ok:true,timeline:reviewTimeline(p)});
  if(action==="review_backlog")return jsonResp(Object.assign({ok:true},reviewBacklog(Object.assign({},p,{actor_name:readAccess.access&&readAccess.access.display_name||""}))));
  if(action==="review_reconciliation")return jsonResp(Object.assign({ok:true},reviewReconciliation(p)));
  if (action === "review_set_list") {
    var setRows = reviewFilter(reviewRows("review_set"), p);
    return jsonResp({ok:true,review_set:setRows.filter(function(r){ return String(r.included) !== "false"; })});
  }
  if (action === "review_suggestion_list") {
    var sg = reviewFilter(reviewRows("suggestions"), p);
    if (!reviewBool(p.include_decided)) sg = sg.filter(function(r){ return r.status === "pending"; });
    var suggestionPage=reviewPage(sg,p,"created_at",50);
    return jsonResp({ok:true,suggestions:suggestionPage.items,next_before:suggestionPage.next_before});
  }
  if (action === "review_source_inbox") {
    var inboxFilter=Object.assign({},p);delete inboxFilter.ce_id;
    var inbox=reviewFilter(reviewRows("inbox"),inboxFilter);
    if(p.ce_id)inbox=inbox.filter(function(r){return String(r.candidate_ce_id)===String(p.ce_id);});
    if(!reviewBool(p.include_reconciled))inbox=inbox.filter(function(r){return !r.reconciled_at;});
    return jsonResp({ok:true,inbox:inbox});
  }
  // External source ingestion is POST-only so its shared secret is never put in a URL.
  if (action === "review_source_ingest") return jsonResp({ok:false,error:"review_source_ingest requires POST"});
  if (action === "review_weekly_list") {
    var weekly=reviewFilter(reviewRows("weekly"),p);
    var weeklyPage=reviewPage(weekly,p,"week_start",26);
    return jsonResp({ok:true,weekly:weeklyPage.items,next_before:weeklyPage.next_before});
  }
  if (action === "review_mention_resolve") return reviewMentionResolve(p);
  if (action === "review_thread_list") return jsonResp({ok:true,active_thread:reviewThreadFor(p.market_slug,p.ce_id),threads:reviewThreadsFor(p.market_slug,p.ce_id)});
  if (action === "review_memory") return reviewMemory(p);

  return jsonResp({ ok: false, error: "unknown action: " + action });
}

// JSON entry point for Granola/Slack adapters and future trusted automations.
// A single payload may be supplied, or `{items:[...]}` for source ingestion.
function doPost(e) {
  var payload = {};
  try { payload = JSON.parse((e.postData && e.postData.contents) || "{}"); }
  catch (err) { return jsonResp({ok:false,error:"invalid JSON"}); }
  var action = payload.action || "review_source_ingest";
  var denied=reviewMutationGate(action,payload);if(denied)return denied;
  if(action === "review_source_ingest" || action === "review_import_batch"){
    var expected=PropertiesService.getScriptProperties().getProperty("REVIEW_MODE_INGEST_SECRET");
    if(!expected)return jsonResp({ok:false,error:"REVIEW_MODE_INGEST_SECRET not configured"});
    if(String(payload.ingest_secret||"")!==String(expected))return jsonResp({ok:false,error:"unauthorized source ingestion"});
  }
  if (action === "review_import_batch") return reviewImportBatch(payload);
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
  if (action === "review_granola_link_submit") return reviewGranolaLinkSubmit(payload);
  if (action === "review_suggestion_decide") return reviewSuggestionDecide(payload);
  if (action === "review_comment_upsert") return reviewCommentUpsert(payload);
  if (action === "review_comment_delete") return reviewCommentDelete(payload);
  if (action === "review_work_upsert") return reviewWorkUpsert(payload);
  if (action === "review_work_delete") return reviewWorkDelete(payload);
  if (action === "review_receipt_upsert") return reviewReceiptUpsert(payload);
  if (action === "review_outcome_upsert") return reviewOutcomeUpsert(payload);
  if (action === "review_timeline_event_upsert") return reviewTimelineEventUpsert(payload);
  if (action === "review_telemetry_record") return reviewTelemetryRecord(payload);
  if (action === "review_set_upsert") return reviewSetUpsert(payload);
  if (action === "review_source_reconcile") return reviewSourceReconcile(payload);
  if (action === "review_weekly_note_upsert") return reviewWeeklyNoteUpsert(payload);
  if (action === "review_weekly_note_delete") return reviewWeeklyNoteDelete(payload);
  if (action === "review_weekly_slack_post") return reviewWeeklySlackPost(payload);
  if (action === "review_weekly_sync") return reviewWeeklySync(payload);
  if (action === "review_summary_decide") return reviewSummaryDecide(payload);
  if (action === "review_slack_post") return reviewSlackPost(payload);
  if (action === "review_slack_scan") return reviewSlackScan(payload);
  return jsonResp({ok:false,error:"unsupported POST action: " + action});
}

// ── Weekly Review CE-scoped Slack relay ─────────────────────────────────────
// This mapping is (market, CE), not (market, CE, week). Every week's questions
// and replies stay in one durable CE
// thread. The BGM supplies free-form text and may mention any Slack user.
function reviewThreadsFor(market, ceId) {
  return reviewRows("threads").filter(function(r){
    return r.market_slug === market && String(r.ce_id) === String(ceId);
  }).sort(function(a,b){return String(b.created_at||"").localeCompare(String(a.created_at||""));});
}

function reviewThreadFor(market, ceId) {
  // Blank status is a legacy active binding. Identity is stable market + CE ID.
  return reviewThreadsFor(market,ceId).filter(function(r){
    return !r.binding_status || String(r.binding_status)==="active";
  })[0] || null;
}

// Immutable Slack provenance, independent of the latest weekly starter on a
// reusable thread. Invalid or contradictory legacy evidence never picks active.
function reviewSlackLocation(value) {
  var text=String(value||"").replace(/&amp;/g,"&"),match=text.match(/^https:\/\/[a-z0-9-]+\.slack\.com\/archives\/([CG][A-Z0-9]+)\/p(\d+)(?:[?#]|$)/i);
  if(!match||match[2].length<=6)return null;
  var message=match[2].slice(0,-6)+"."+match[2].slice(-6),parent=text.match(/[?&]thread_ts=(\d+\.\d+)(?:&|#|$)/);
  return {channel:match[1],parent:parent?parent[1]:message,message:message,hasParent:!!parent};
}

function reviewResolveWeeklyThread(state,threads) {
  if(!state)return null;
  var explicit=String(state.thread_binding_id||""),post=String(state.slack_post_ts||""),location=reviewSlackLocation(state.slack_post_permalink);
  var matches=threads.filter(function(thread){
    if(explicit)return String(thread.binding_id||"")===explicit&&(!location||
      (location.channel===String(thread.slack_channel)&&(!location.hasParent||location.parent===String(thread.slack_thread_ts))));
    if(location)return location.channel===String(thread.slack_channel)&&
      (location.hasParent?location.parent===String(thread.slack_thread_ts):
        (location.message===String(thread.slack_thread_ts)||location.message===String(thread.weekly_starter_ts)))&&
      (!post||post===location.message||post===location.parent);
    // A nonempty unparseable link is not evidence for a legacy multi-thread CE.
    if(state.slack_post_permalink)return false;
    return !!post&&(post===String(thread.slack_thread_ts)||post===String(thread.weekly_starter_ts));
  });
  return matches.length===1?matches[0]:null;
}

function reviewThreadNumber(thread,threads) {
  return String(threads.length-threads.findIndex(function(t){return String(t.binding_id||"")===String(thread.binding_id||"");}));
}

function reviewSummarySourceMatches(row,thread,state,latest) {
  var explicit=String(row.thread_binding_id||""),location=reviewSlackLocation(row.source_url),ref=String(row.source_ref||"").match(/^([CG][A-Z0-9]+):(\d+\.\d+)$/);
  if(explicit&&explicit!==String(thread.binding_id||""))return false;
  if(!explicit){
    if(!location||!ref||location.channel!==ref[1]||location.channel!==String(thread.slack_channel)||
      location.parent!==String(thread.slack_thread_ts))return false;
    if(location.message!==location.parent&&location.message!==ref[2])return false;
  }
  // The caller has already matched market + CE + exact week. An immutable
  // binding proves these stored records belong to this discussion, even when
  // an older relay moved slack_post_ts forward on every same-week reply.
  // Legacy unbound records still require both permalink proof and the boundary.
  var ts=ref?ref[2]:"";
  return !ts||((!!explicit||!state.slack_post_ts||ts>=String(state.slack_post_ts))&&(!latest||ts<latest));
}

function reviewSummaryDecide(p){
  var err=reviewRequired(p,["market_slug","ce_id","week_start","decision","decided_by","thread_binding_id","slack_discussion_number"]);if(err)return err;
  var state=reviewWeeklyFor(p.market_slug,p.ce_id,p.week_start);
  if(!state)return jsonResp({ok:false,error:"weekly commentary not found"});
  if(!state.thread_binding_id||!state.slack_discussion_number)
    return jsonResp({ok:false,error:"weekly summary is not bound to an exact Slack discussion"});
  if(String(state.thread_binding_id)!==String(p.thread_binding_id)||
      String(state.slack_discussion_number)!==String(p.slack_discussion_number))
    return jsonResp({ok:false,error:"stale Slack discussion summary binding"});
  if(String(state.summary_thread_binding_id||"")!==String(state.thread_binding_id)||
      String(state.summary_slack_discussion_number||"")!==String(state.slack_discussion_number))
    return jsonResp({ok:false,error:"summary belongs to a different Slack discussion"});
  var decision=String(p.decision||"").toLowerCase();
  if(["approved","rejected","regenerate"].indexOf(decision)<0)return jsonResp({ok:false,error:"invalid summary decision"});
  var trusted=reviewTrustedAuthor(p,p.decided_by),now=reviewNow(),draft=String(p.summary_json||state.summary_draft_json||"");
  if(decision==="approved"){
    var parsed=reviewJson(draft,null);if(!parsed)return jsonResp({ok:false,error:"approved summary must be valid JSON"});
  }
  var next=reviewWeeklyMutate(p,function(rec){
    if(String(rec.thread_binding_id||"")!==String(state.thread_binding_id||"")||String(rec.slack_discussion_number||"")!==String(state.slack_discussion_number||""))throw new Error("CE thread changed before summary save");
    if(decision==="approved"){
      rec.summary_status="approved";rec.summary_draft_json=draft;rec.summary_approved_json=draft;rec.summary_json=draft;
      rec.summary_approved_by=trusted;rec.summary_approved_at=now;rec.summary_rejected_at="";rec.summary_rejection_reason="";rec.sync_status="summary_approved";
    }else if(decision==="rejected"){
      rec.summary_status="rejected";rec.summary_rejected_at=now;rec.summary_rejection_reason=String(p.reason||"");rec.sync_status="summary_rejected";
    }else{
      rec.summary_status="regenerate_requested";rec.summary_draft_json="";rec.summary_rejected_at="";rec.summary_rejection_reason="";rec.sync_status="summary_regenerate_requested";
    }
    rec.version=String((parseInt(rec.version,10)||0)+1);return rec;
  });
  return jsonResp({ok:true,weekly:next,decision:decision});
}

function reviewSlackPostCore(p) {
  var err = reviewRequired(p,["market_slug","ce_id","week_start","channel","text","author"]);
  if (err) return {ok:false,error:"required Slack fields missing"};
  var expectedChannel=reviewPrimarySlackChannel(p.market_slug);
  if(!expectedChannel)return {ok:false,error:"no Review Slack channel configured for market"};
  if(String(p.channel)!==expectedChannel)return {ok:false,error:"Slack channel does not match Review market routing"};
  var token = PropertiesService.getScriptProperties().getProperty("SLACK_BOT_TOKEN");
  if (!token) return {ok:false,error:"SLACK_BOT_TOKEN not set in Script properties"};
  var existing = reviewThreadFor(p.market_slug,p.ce_id);
  var operation=String(p.thread_operation||(existing?"continue":"start"));
  if(["start","continue","new_parent"].indexOf(operation)<0)
    return {ok:false,error:"invalid Slack thread operation"};
  if(!existing&&operation==="continue")
    return {ok:false,error:"no existing CE thread to continue"};
  if(existing&&operation==="start")operation="new_parent";
  if(existing&&operation==="new_parent"&&!String(p.replacement_reason||"").trim())
    return {ok:false,error:"replacement reason is required to start a new CE discussion",thread:existing};
  if (existing && existing.slack_channel && existing.slack_channel !== p.channel && operation!=="new_parent")
    return {ok:false,error:"CE thread already belongs to another Slack channel",thread:existing};
  if(existing&&p.request_id&&String(existing.last_post_request_id||"")===String(p.request_id))
    return {ok:true,duplicate:true,operation:operation,thread:existing,
      posted_ts:String(existing.weekly_starter_ts||existing.slack_thread_ts||""),
      posted_permalink:getPermalink(token,p.channel,String(existing.weekly_starter_ts||existing.slack_thread_ts||""))};
  var reuse=!!existing&&operation==="continue";
  if(existing&&!existing.binding_id)existing.binding_id=reviewId("thb");

  var header = "*Weekly Review · " + (p.ce_name || ("CE " + p.ce_id)) + "*";
  var context = "_" + p.market_slug + " · CE " + p.ce_id + " · W/C " + ymd(p.week_start) + "_";
  var body = (reuse ? "" : (header + "\n" + context + "\n")) + p.text +
    "\n_— " + p.author + "_" + (p.report_url ? "\n<" + p.report_url + "|Open CE review>" : "");
  var payload = {channel:p.channel,text:body,username:"Weekly Market Review",icon_emoji:":memo:",unfurl_links:false};
  if(p.request_id)payload.client_msg_id=String(p.request_id);
  if (reuse && existing.slack_thread_ts) payload.thread_ts=String(existing.slack_thread_ts);
  var resp = UrlFetchApp.fetch("https://slack.com/api/chat.postMessage",{
    method:"post",contentType:"application/json; charset=utf-8",
    headers:{Authorization:"Bearer " + token},payload:JSON.stringify(payload),muteHttpExceptions:true});
  var result = JSON.parse(resp.getContentText());
  if (!result.ok) return {ok:false,error:"slack: " + (result.error || "unknown")};
  var now=reviewNow(),bindingId=reuse?(existing.binding_id||reviewId("thb")):reviewId("thb");
  var anchor=reuse?String(existing.slack_thread_ts):String(result.ts);
  var permalink=getPermalink(token,p.channel,anchor);
  var record={market_slug:p.market_slug,ce_id:String(p.ce_id),ce_name:p.ce_name||"",
    slack_channel:p.channel,slack_thread_ts:anchor,
    slack_permalink:permalink || (reuse && existing.slack_permalink) || "",
    created_at:(reuse && existing.created_at)||now,updated_at:now,
    last_scanned_ts:(reuse && existing.last_scanned_ts)||anchor,
    binding_id:bindingId,binding_status:"active",
    created_reason:reuse?(existing.created_reason||"legacy"):String(p.replacement_reason||"first_discussion"),
    replaced_reason:"",predecessor_binding_id:reuse?(existing.predecessor_binding_id||""):(existing&&existing.binding_id||""),
    successor_binding_id:"",created_by:p.author||"",replacement_week:reuse?(existing.replacement_week||""):ymd(p.week_start),
    weekly_starter_ts:String(result.ts),weekly_starter_week:ymd(p.week_start),last_post_request_id:String(p.request_id||"")};
  if(reuse)reviewWrite("threads",existing,record);
  else{
    reviewWrite("threads",null,record);
    if(existing){
      existing.binding_status="replaced";
      existing.replaced_reason=String(p.replacement_reason||"");existing.successor_binding_id=bindingId;
      existing.updated_at=now;reviewWrite("threads",existing,existing);
    }
  }
  return {ok:true,operation:operation,thread:record,posted_ts:String(result.ts),posted_permalink:getPermalink(token,p.channel,String(result.ts))};
}

function reviewSlackPost(p){return jsonResp(reviewSlackPostCore(p));}

function reviewArchiveApprovedSummary(state){
  if(!state||!(state.summary_approved_json||(String(state.summary_status||"")==="approved"&&state.summary_json)))return null;
  var binding=String(state.summary_thread_binding_id||state.thread_binding_id||"");
  var number=String(state.summary_slack_discussion_number||state.slack_discussion_number||"");
  var key="slack_summary:"+String(state.weekly_id||"")+":"+binding+":"+number;
  var existing=reviewFind("timeline",function(r){return String(r.idempotency_key||"")===key;});
  if(existing)return existing;
  var rec={event_id:reviewId("evt"),market_slug:state.market_slug,ce_id:String(state.ce_id),
    ce_name:state.ce_name||"",review_week:ymd(state.week_start),event_type:"slack_summary",
    source_type:"slack",source_ref:binding||state.summary_upto_ts||"",
    source_url:state.slack_post_permalink||"",actor_id:"",actor_name:state.summary_approved_by||"BGM",
    actor_role:"bgm",occurred_at:state.summary_approved_at||state.summary_updated_at||reviewNow(),
    recorded_at:reviewNow(),original_body:state.summary_approved_json||state.summary_json,
    approved_body:state.summary_approved_json||state.summary_json,approval_state:"approved",
    approved_by:state.summary_approved_by||"BGM",approved_at:state.summary_approved_at||state.summary_updated_at||reviewNow(),
    related_review_id:state.weekly_id||"",related_work_id:"",supersedes_event_id:"",idempotency_key:key};
  reviewWrite("timeline",null,rec);return rec;
}

function reviewWeeklySlackPost(p){
  var discussionText=p.discussion_text!=null?p.discussion_text:p.bgm_note;
  var discussionAuthor=p.discussion_author!=null?p.discussion_author:p.bgm_author;
  var err=reviewRequired(Object.assign({},p,{discussion_text:discussionText,discussion_author:discussionAuthor}),["market_slug","ce_id","ce_name","week_start","channel","discussion_text","discussion_author","request_id"]);
  if(err)return err;
  var current=reviewWeeklyFor(p.market_slug,p.ce_id,p.week_start);
  // A weekly record can already point at the active CE thread and still accept
  // additional BGM replies. Only the same request is a duplicate; treating all
  // continuations as duplicates makes the UI report success without posting.
  if(current && current.slack_post_ts && current.sync_status!=="post_failed" && p.request_id &&
      String(current.last_post_request_id||"")===String(p.request_id))
    return jsonResp({ok:true,duplicate:true,weekly:current});
  var trustedAuthor=reviewTrustedAuthor(p,discussionAuthor);
  var mentions=reviewResolveMentions(discussionText,p.market_slug);
  if(mentions.ambiguous.length)return jsonResp({ok:false,error:"ambiguous Slack mentions",mentions:mentions});
  // Slack composition is deliberately independent from all role notes. A
  // retry reuses request_id without overwriting BGM/Performance/BDM memory.
  var saved=reviewWeeklyMutate(p,function(next){
    next.sync_status="posting";next.last_error="";
    next.version=String((parseInt(next.version,10)||0)+1);return next;
  });
  var posted=reviewSlackPostCore({market_slug:p.market_slug,ce_id:p.ce_id,ce_name:p.ce_name,
    week_start:p.week_start,channel:p.channel,text:mentions.resolved_text,author:trustedAuthor,
    report_url:p.report_url||"",request_id:p.request_id,thread_operation:p.thread_operation||"",
    replacement_reason:p.replacement_reason||""});
  if(posted.ok&&posted.operation==="new_parent")reviewArchiveApprovedSummary(current);
  var finalState=reviewWeeklyMutate(p,function(next){
    next.last_post_request_id=p.request_id;
    if(!posted.ok){next.sync_status="post_failed";next.last_error=posted.error||"Slack post failed";return next;}
    // Same-week replies append to the discussion, not a new weekly boundary.
    // Keep the first post so historical summaries retain earlier source text.
    if(posted.operation==="new_parent"||!next.slack_post_ts||
        String(next.thread_binding_id||"")!==String(posted.thread.binding_id||"")){
      next.slack_post_ts=posted.posted_ts;next.slack_post_permalink=posted.posted_permalink||posted.thread.slack_permalink||"";
    }
    next.thread_binding_id=String(posted.thread.binding_id||"");
    next.slack_discussion_number=String(reviewThreadsFor(p.market_slug,p.ce_id).length||1);
    if(posted.operation==="new_parent"){
      next.summary_json="";next.summary_upto_ts="";next.summary_updated_at="";next.summary_status="";
      next.summary_draft_json="";next.summary_approved_json="";next.summary_approved_by="";next.summary_approved_at="";
      next.summary_rejected_at="";next.summary_rejection_reason="";
      next.summary_thread_binding_id="";next.summary_slack_discussion_number="";
      next.reply_count="0";next.contributors_json="[]";
    }
    if(posted.operation==="new_parent"||!next.last_scanned_ts)next.last_scanned_ts=posted.posted_ts;next.sync_status="awaiting_replies";next.last_error="";return next;
  });
  if(!posted.ok)return jsonResp({ok:false,error:posted.error,weekly:finalState,retryable:true});
  reviewSuggestionRecord({market_slug:p.market_slug,ce_id:p.ce_id,ce_name:p.ce_name,week_start:p.week_start,
    source_type:"slack",source_author:trustedAuthor,source_ref:p.channel+":"+posted.posted_ts,
    source_url:posted.posted_permalink||posted.thread.slack_permalink,kind:"comment",body:discussionText,
    confidence:"source_exact",thread_binding_id:posted.thread.binding_id});
  return jsonResp({ok:true,operation:posted.operation,weekly:finalState,thread:posted.thread,mentions:mentions.matches});
}

function reviewJson(value,fallback){try{return value?JSON.parse(value):fallback;}catch(err){return fallback;}}

function reviewAiHeaders(context,secret){
  var props=PropertiesService.getScriptProperties(),headers=secret?{"X-Review-Secret":secret}:{};
  var automation=props.getProperty("REVIEW_MODE_VERCEL_AUTOMATION_SECRET")||"";
  // Accept transport configuration only from a fresh, HMAC-signed server
  // request. Retain it for scheduled syncs, which have no browser session.
  if(context&&context.review_ai_protection_bypass&&reviewSignedActorEmail(context)){
    var supplied=String(context.review_ai_protection_bypass);
    if(supplied!==automation){props.setProperty("REVIEW_MODE_VERCEL_AUTOMATION_SECRET",supplied);automation=supplied;}
  }
  if(automation)headers["x-vercel-protection-bypass"]=automation;
  return headers;
}

function reviewAiWeeklySummary(sourceRows,state,context){
  var endpoint=PropertiesService.getScriptProperties().getProperty("REVIEW_MODE_AI_WEBHOOK_URL");
  if(!endpoint)return {status:"source_unavailable"};
  try{
    var secret=PropertiesService.getScriptProperties().getProperty("REVIEW_MODE_AI_WEBHOOK_SECRET")||"";
    var previous=reviewJson(state.summary_json,{});
    var resp=UrlFetchApp.fetch(endpoint,{method:"post",contentType:"application/json",
      headers:reviewAiHeaders(context,secret),
      payload:JSON.stringify({mode:"weekly_thread_summary",identity:{market_slug:context.market_slug,
        ce_id:String(context.ce_id),week_start:ymd(context.week_start)},previous_summary:previous,
        records:sourceRows.map(function(r){return {source_ref:r.source_ref,source_url:r.source_url,
          author:r.source_author,body:r.body,created_at:r.created_at};})}),muteHttpExceptions:true});
    var body=JSON.parse(resp.getContentText()),summary=body&&body.summary;
    if(!summary)return {status:"invalid_response"};
    ["findings","decisions","open_points","action_suggestions","check_suggestions"].forEach(function(key){
      if(!Array.isArray(summary[key]))summary[key]=[];
    });
    var allowed={};sourceRows.forEach(function(r){allowed[r.source_ref]=true;});
    summary.source_refs=(summary.source_refs||sourceRows.map(function(r){return r.source_ref;}))
      .filter(function(ref){return allowed[ref];});
    if(!summary.source_refs.length)return {status:"invalid_response"};
    return {status:"ok",summary:summary};
  }catch(ex){return {status:"source_unavailable",error:String(ex)};}
}

function reviewHash(text){var value=2166136261;for(var i=0;i<text.length;i++){value^=text.charCodeAt(i);value=Math.imul(value,16777619);}return (value>>>0).toString(16);}

function reviewWeeklySyncCore(p){
  var state=reviewWeeklyFor(p.market_slug,p.ce_id,p.week_start);
  var threads=reviewThreadsFor(p.market_slug,p.ce_id),active=reviewThreadFor(p.market_slug,p.ce_id);
  var wanted=String(p.thread_binding_id||""),hasHistory=state&&(state.thread_binding_id||state.slack_post_ts||state.slack_post_permalink);
  var thread=hasHistory?reviewResolveWeeklyThread(state,threads):(wanted?threads.filter(function(t){return String(t.binding_id)===wanted;})[0]:active);
  if(hasHistory&&!thread)return {ok:false,error:"Cannot establish this week's Slack thread from saved history.",weekly:state};
  if(!thread)return {ok:false,error:"no matching CE Slack thread",weekly:state};
  if(wanted&&String(thread.binding_id||"")!==wanted)return {ok:false,error:"CE thread changed. Refresh before summarizing."};
  var recoverBinding=state&&(!state.thread_binding_id||!state.slack_discussion_number);
  if(!state||!state.slack_post_ts||recoverBinding){
    var expectedBinding=String((state||{}).thread_binding_id||""),expectedPost=String((state||{}).slack_post_ts||"");
    state=reviewWeeklyMutate(p,function(rec){
      if(String(rec.thread_binding_id||"")!==expectedBinding||String(rec.slack_post_ts||"")!==expectedPost)throw new Error("CE thread changed before legacy binding recovery");
      rec.thread_binding_id=rec.thread_binding_id||thread.binding_id||"";
      rec.slack_discussion_number=rec.slack_discussion_number||reviewThreadNumber(thread,threads);
      rec.slack_post_ts=rec.slack_post_ts||thread.slack_thread_ts;rec.slack_post_permalink=rec.slack_post_permalink||thread.slack_permalink;rec.last_scanned_ts=rec.last_scanned_ts||rec.slack_post_ts;return rec;
    });
  }
  if(wanted&&String(state.thread_binding_id||"")!==wanted)return {ok:false,error:"CE thread changed. Refresh before summarizing."};
  var token=PropertiesService.getScriptProperties().getProperty("SLACK_BOT_TOKEN");
  if(!token)return {ok:false,error:"SLACK_BOT_TOKEN not set in Script properties",weekly:state};
  // A CE may reuse its active Slack thread, so each weekly cycle needs an
  // explicit upper boundary. Otherwise a late scan of W31 can also ingest W32
  // replies after the W32 starter has been posted.
  var nextCycle=reviewRows("weekly").filter(function(r){return r.market_slug===p.market_slug&&
    String(r.ce_id)===String(p.ce_id)&&ymd(r.week_start)>ymd(p.week_start)&&r.slack_post_ts&&
    String((reviewResolveWeeklyThread(r,threads)||{}).binding_id||"")===String(thread.binding_id||"");})
    .sort(function(a,b){return ymd(a.week_start).localeCompare(ymd(b.week_start));})[0];
  var latest=nextCycle?String(nextCycle.slack_post_ts):"";
  var since=String(state.last_scanned_ts||state.slack_post_ts),scan=slackThreadReplies(token,
    thread.slack_channel,thread.slack_thread_ts,since,latest);
  if(!scan.ok)return {ok:false,error:scan.error,weekly:state};
  var newest=since,created=[];
  (scan.messages||[]).forEach(function(msg){
    var ts=String(msg.ts||"");
    if(!ts||ts<=since||(latest&&ts>=latest)||ts===String(thread.slack_thread_ts)||msg.bot_id||msg.subtype)return;
    newest=ts>newest?ts:newest;
    var ref=thread.slack_channel+":"+ts;
    var result=reviewSuggestionRecord({market_slug:p.market_slug,ce_id:p.ce_id,
      ce_name:p.ce_name||state.ce_name,week_start:p.week_start,source_type:"slack",
      source_author:slackUserName(token,msg.user),source_ref:ref,
      source_url:getPermalink(token,thread.slack_channel,ts),kind:"comment",body:msg.text||"",
      confidence:"source_exact",thread_binding_id:thread.binding_id||""});
    if(result.ok&&!result.duplicate)created.push(result.suggestion);
  });
  var raw=reviewRows("suggestions").filter(function(r){return r.market_slug===p.market_slug&&
    String(r.ce_id)===String(p.ce_id)&&ymd(r.week_start)===ymd(p.week_start)&&
    r.source_type==="slack"&&r.kind==="comment"&&r.confidence==="source_exact"&&
    reviewSummarySourceMatches(r,thread,state,latest);});
  var contributors=[];raw.forEach(function(r){if(r.source_author&&contributors.indexOf(r.source_author)<0)contributors.push(r.source_author);});
  // App-relayed replies have already been stored as exact sources, but Slack
  // identifies them as bot messages. Include their timestamps in the summary
  // freshness check without advancing the human scan cursor past unread pages.
  var summaryNewest=newest;
  raw.forEach(function(r){var ref=String(r.source_ref||"").match(/^([CG][A-Z0-9]+):(\d+\.\d+)$/);
    if(ref&&ref[2]>summaryNewest)summaryNewest=ref[2];});
  if(!created.length && Number(state.reply_count||0)===raw.length && state.summary_upto_ts===summaryNewest && ["pending","approved"].indexOf(String(state.summary_status))>=0)
    return {ok:true,weekly:state,new_replies:[],ai_status:"current"};
  var ai=raw.length?reviewAiWeeklySummary(raw,state,p):{status:"no_new_source"};
  var latestState=reviewWeeklyFor(p.market_slug,p.ce_id,p.week_start);
  if(String((latestState||{}).thread_binding_id||"")!==String(state.thread_binding_id||""))return {ok:false,error:"CE thread changed while summarizing. Refresh to summarize the new thread."};
  var next=reviewWeeklyMutate(p,function(rec){
    if(String(rec.thread_binding_id||"")!==String(state.thread_binding_id||""))throw new Error("CE thread changed while summarizing");
    rec.last_scanned_ts=newest;rec.reply_count=String(raw.length);rec.contributors_json=JSON.stringify(contributors);
    if(ai.status==="ok"){
      rec.summary_draft_json=JSON.stringify(ai.summary);rec.summary_status="pending";rec.summary_upto_ts=summaryNewest;rec.summary_updated_at=reviewNow();
      rec.summary_thread_binding_id=String(state.thread_binding_id||"");
      rec.summary_slack_discussion_number=String(state.slack_discussion_number||"");
      rec.sync_status="summary_pending_approval";rec.last_error="";rec.version=String((parseInt(rec.version,10)||0)+1);
    }else if(raw.length){rec.sync_status="summary_delayed";rec.last_error=ai.status;}
    else{rec.sync_status="awaiting_replies";rec.last_error="";}
    return rec;
  });
  if(ai.status==="ok"){
    (ai.summary.action_suggestions||[]).forEach(function(item,idx){if(!item||!item.text)return;
      reviewSuggestionRecord({market_slug:p.market_slug,ce_id:p.ce_id,ce_name:next.ce_name,
        week_start:p.week_start,source_type:"slack",source_author:"AI thread summary",
        thread_binding_id:thread.binding_id||"",
        source_ref:"weekly:"+next.weekly_id+":"+String(thread.binding_id||"")+":action:"+reviewHash(item.text.toLowerCase().replace(/\s+/g," ").trim()),
        source_url:next.slack_post_permalink,kind:"action",body:item.text,
        proposed_owner:item.owner||"",proposed_due_date:item.due_date||"",confidence:item.confidence||"summary_derived"});});
    (ai.summary.check_suggestions||[]).forEach(function(item,idx){if(!item||!item.text)return;
      reviewSuggestionRecord({market_slug:p.market_slug,ce_id:p.ce_id,ce_name:next.ce_name,
        week_start:p.week_start,source_type:"slack",source_author:"AI thread summary",
        thread_binding_id:thread.binding_id||"",
        source_ref:"weekly:"+next.weekly_id+":"+String(thread.binding_id||"")+":check:"+reviewHash(item.text.toLowerCase().replace(/\s+/g," ").trim()),
        source_url:next.slack_post_permalink,kind:"check",body:item.text,
        proposed_owner:item.owner||"",proposed_due_date:item.due_date||"",confidence:item.confidence||"summary_derived"});});
  }
  return {ok:true,weekly:next,new_replies:created,ai_status:ai.status,truncated:scan.truncated};
}

function reviewWeeklySync(p){return jsonResp(reviewWeeklySyncCore(p));}

function reviewSyncActiveThreads(){
  var cutoff=new Date();cutoff.setUTCDate(cutoff.getUTCDate()-21);var cutoffYmd=ymd(cutoff);
  reviewRows("weekly").filter(function(r){return r.slack_post_ts&&ymd(r.week_start)>=cutoffYmd;})
    .slice(0,80).forEach(function(r){try{reviewWeeklySyncCore(r);}catch(err){}});
}

function installReviewSyncTrigger(){
  ScriptApp.getProjectTriggers().filter(function(t){return t.getHandlerFunction()==="reviewSyncActiveThreads";})
    .forEach(function(t){ScriptApp.deleteTrigger(t);});
  // Manual summaries only. Retain this installer as a cleanup entry point.
  return {ok:true,mode:"manual"};
}

function installReviewAutomation(){
  installReviewStorage();
  installReviewSyncTrigger();
  ScriptApp.getProjectTriggers().filter(function(t){return t.getHandlerFunction()==="reviewSyncSlackPeople";})
    .forEach(function(t){ScriptApp.deleteTrigger(t);});
  if(reviewBool(PropertiesService.getScriptProperties().getProperty("REVIEW_ENABLE_DIRECTORY_SYNC"))){
    ScriptApp.newTrigger("reviewSyncSlackPeople").timeBased().everyDays(1).atHour(2).create();
    reviewSyncSlackPeople();
  }
}

function installReviewStorage(){
  Object.keys(REVIEW_TABLES).forEach(function(kind){reviewSheet(kind);});
  return Object.keys(REVIEW_TABLES).map(function(kind){return REVIEW_TABLES[kind].sheet;});
}

// Review mentions are market-scoped. These are channel IDs, not names, so a
// rename in Slack cannot silently broaden who can be tagged. Keep this list in
// lockstep with docs/weekly-review/MARKET_CHANNEL_MAPPING.md.
var REVIEW_MARKET_SLACK_CHANNELS={
  north_america:["C0BQHT29WMB"],central_live_entertainment:["C042A57T52Q"],italy:["C045L2WQ79P"],france:["CH64TEB71"],
  iberia:["CH2LRMJF2"],south_america:["CH2LRMJF2"],mexico_central_america:["C012949PQ81"],
  csee:["CSQ10TALA"],nordics:["CSQ10TALA"],united_kingdom:["CKTFHT4AF"],benelux:["CL13UPZ6V"],
  east_asia:["CQD6220VB","C01C4NPLYN6","C01CARUM1CL","C0809DN93DH"],oceania:["CHKRLFDPU","C039TMH0GEP","C097DVBLHGS"],
  sea:["C5WFYN82H","C03R4UJ4DHC","C01CHADFPAM","C03US4WRHB6","C05D50N5BQW"],
  uae:["C046622L80Z"],gcc:["C0889D22PM5"],north_africa:["C0889D22PM5"],rest_of_mea:["C0889D22PM5"],
  headout:["C0975BGAX0B"]
};

function reviewPrimarySlackChannel(market){
  var channels=REVIEW_MARKET_SLACK_CHANNELS[String(market)]||[];
  return channels.length ? String(channels[0]) : "";
}

function reviewSlackApi(token,url){
  var resp=UrlFetchApp.fetch(url,{headers:{Authorization:"Bearer "+token},muteHttpExceptions:true});
  var body=JSON.parse(resp.getContentText());if(!body.ok)throw new Error(body.error||"Slack API failed");return body;
}

function reviewSlackDirectoryUsers(token){
  var cursor="",users={},pages=0;
  do{var body=reviewSlackApi(token,"https://slack.com/api/users.list?limit=200"+(cursor?"&cursor="+encodeURIComponent(cursor):""));
    (body.members||[]).forEach(function(u){if(!u.deleted&&!u.is_bot&&u.id!=="USLACKBOT")users[String(u.id)]=u;});
    cursor=((body.response_metadata||{}).next_cursor)||"";pages++;
  }while(cursor&&pages<20);
  return users;
}

function reviewSlackChannelMemberIds(token,channel){
  var cursor="",ids=[],pages=0;
  do{var body=reviewSlackApi(token,"https://slack.com/api/conversations.members?limit=200&channel="+encodeURIComponent(channel)+
      (cursor?"&cursor="+encodeURIComponent(cursor):""));
    ids=ids.concat(body.members||[]);cursor=((body.response_metadata||{}).next_cursor)||"";pages++;
  }while(cursor&&pages<20);
  return ids;
}

function reviewAliasJoin(values){
  var seen={};return values.map(function(v){return String(v||"").trim();}).filter(function(v){
    var key=v.toLowerCase();if(!v||seen[key])return false;seen[key]=true;return true;}).join(";");
}

function reviewSyncSlackPeople(){
  var token=PropertiesService.getScriptProperties().getProperty("SLACK_BOT_TOKEN");
  if(!token)throw new Error("SLACK_BOT_TOKEN not set");
  var users=reviewSlackDirectoryUsers(token),existing={};
  reviewRows("people").forEach(function(r){existing[String(r.market_slug)+"|"+String(r.slack_user_id)]=r;});
  var records={},now=reviewNow();
  Object.keys(REVIEW_MARKET_SLACK_CHANNELS).forEach(function(market){
    var ids={};REVIEW_MARKET_SLACK_CHANNELS[market].forEach(function(channel){
      reviewSlackChannelMemberIds(token,channel).forEach(function(id){ids[String(id)]=true;});});
    Object.keys(ids).forEach(function(id){var u=users[id];if(!u)return;var profile=u.profile||{},prior=existing[market+"|"+id]||{};
      var display=profile.display_name||u.name||profile.real_name||u.real_name||id;
      records[market+"|"+id]=[id,display,profile.real_name||u.real_name||"",
        reviewAliasJoin([prior.aliases,u.name,profile.display_name,profile.real_name,u.real_name]),market,"true",now];});
  });
  var sh=reviewSheet("people"),def=REVIEW_TABLES.people,values=Object.keys(records).sort().map(function(k){return records[k];});
  if(sh.getLastRow()>1)sh.getRange(2,1,sh.getLastRow()-1,def.headers.length).clearContent();
  if(values.length)sh.getRange(2,1,values.length,def.headers.length).setValues(values);
  return values.length;
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

function slackThreadReplies(token,channel,threadTs,oldest,latest){
  var messages=[],cursor="",pages=0;
  do{
    var url="https://slack.com/api/conversations.replies?channel="+encodeURIComponent(channel)+
      "&ts="+encodeURIComponent(String(threadTs))+"&limit=200&inclusive=false"+
      (oldest?"&oldest="+encodeURIComponent(oldest):"")+
      (latest?"&latest="+encodeURIComponent(latest):"")+
      (cursor?"&cursor="+encodeURIComponent(cursor):"");
    var resp=UrlFetchApp.fetch(url,{headers:{Authorization:"Bearer "+token},muteHttpExceptions:true});
    var body=JSON.parse(resp.getContentText());
    if(!body.ok)return {ok:false,error:"slack: "+(body.error||"unknown")};
    messages=messages.concat((body.messages||[]).filter(function(msg){
      return !latest||String(msg.ts||"")<String(latest);
    }));
    cursor=((body.response_metadata||{}).next_cursor)||"";pages++;
  }while(cursor&&pages<20); // 4,000 replies per scan; cursor retained by last_scanned_ts next run.
  return {ok:true,messages:messages,truncated:!!cursor};
}

// Optional adapter: set REVIEW_MODE_AI_WEBHOOK_URL to a trusted service that returns
// `{suggestions:[{source_ref,kind,body,proposed_owner,proposed_due_date,confidence}]}`.
// With no adapter or a bad response, raw source suggestions remain pending and
// the API explicitly reports source_unavailable; it never invents a summary.
function reviewAiSuggestions(sourceType, sourceRows, context) {
  if(!sourceRows.length)return {status:"no_new_source",suggestions:[]};
  var endpoint=PropertiesService.getScriptProperties().getProperty("REVIEW_MODE_AI_WEBHOOK_URL");
  if(!endpoint)return {status:"source_unavailable",suggestions:[]};
  try{
    var secret=PropertiesService.getScriptProperties().getProperty("REVIEW_MODE_AI_WEBHOOK_SECRET")||"";
    var resp=UrlFetchApp.fetch(endpoint,{method:"post",contentType:"application/json",
      headers:reviewAiHeaders(context,secret),
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
