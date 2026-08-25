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
      "created_at","updated_at","closed_at","deleted_at","deleted_by"]
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
  weekly: {
    sheet: "review_weekly_commentary",
    headers: ["weekly_id","market_slug","ce_id","ce_name","week_start","bgm_note",
      "bgm_author","bgm_updated_at","note_deleted_at","slack_post_ts","slack_post_permalink","last_scanned_ts",
      "reply_count","contributors_json","summary_json","summary_upto_ts","summary_updated_at",
      "sync_status","last_error","last_post_request_id","version"]
  },
  suggestions: {
    sheet: "review_source_suggestions",
    headers: ["suggestion_id","market_slug","ce_id","ce_name","week_start","source_type",
      "source_author","source_ref","source_url","kind","body","proposed_owner","proposed_due_date",
      "confidence","status","created_at","decided_by","decided_at","decision_destination",
      "accepted_body","accepted_owner","accepted_due_date"]
  },
  inbox: {
    sheet: "review_source_inbox",
    headers: ["source_item_id","source_type","source_ref","source_url","source_author",
      "occurred_at","market_slug","week_start","candidate_ce_id","candidate_ce_name",
      "match_confidence","match_status","kind","body","created_at","reconciled_by","reconciled_at"]
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
  var match = String(value == null ? "" : value).trim().match(/^(\d+)(?:\s*-\s*.*)?$/);
  return match ? match[1] : "";
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

function reviewSpreadsheet() {
  var id = String(PropertiesService.getScriptProperties().getProperty("REVIEW_SPREADSHEET_ID") || "").trim();
  if (!id) throw new Error("REVIEW_SPREADSHEET_ID not configured");
  return SpreadsheetApp.openById(id);
}

function reviewSheet(kind) {
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
    sh.getRange(1, 1, 1, def.headers.length).setValues([def.headers]);
    sh.getRange(1, 1, 1, def.headers.length).setFontWeight("bold");
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

function reviewSignedActorEmail(p) {
  var email = String(p.actor_email || "").trim().toLowerCase();
  var timestamp = parseInt(p.actor_ts || "0", 10);
  var signature = String(p.actor_sig || "").toLowerCase();
  // Properties entered through the Apps Script settings UI can accidentally
  // carry a trailing newline. Keep the signed Review boundary strict while
  // normalising that transport-only whitespace on both sides.
  var secret = String(PropertiesService.getScriptProperties().getProperty("REVIEW_MODE_PROXY_SECRET") || "").trim();
  if (!email || !timestamp || !signature || !secret) return "";
  if (Math.abs(Math.floor(Date.now() / 1000) - timestamp) > 300) return "";
  var expected = reviewHex(Utilities.computeHmacSha256Signature(reviewActorCanonicalParams(p), secret));
  return reviewSafeEqual(signature, expected) ? email : "";
}

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
  if(!email)return {ok:false,error:"authenticated BGM identity required"};
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
    "review_receipt_upsert","review_set_upsert","review_source_reconcile",
    "review_suggestion_decide","review_slack_post","review_slack_scan",
    "review_granola_link_submit",
    "review_weekly_note_upsert","review_weekly_note_delete","review_weekly_slack_post","review_weekly_sync"];
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
    var rows=reviewRows(kind),existing=null;
    for(var i=0;i<rows.length;i++)if(predicate(rows[i])){existing=rows[i];break;}
    var record=buildRecord(existing),sh=reviewSheet(kind);
    var vals=def.headers.map(function(h){return record[h]==null?"":record[h];});
    var row=existing?existing._row:sh.getLastRow()+1;
    sh.getRange(row,1,1,vals.length).setValues([vals]);
    ["week_start","origin_week","due_date","next_review_date","slack_thread_ts",
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
    slack_post_ts:(existing&&existing.slack_post_ts)||"",
    slack_post_permalink:(existing&&existing.slack_post_permalink)||"",
    last_scanned_ts:(existing&&existing.last_scanned_ts)||"",reply_count:(existing&&existing.reply_count)||"0",
    contributors_json:(existing&&existing.contributors_json)||"[]",
    summary_json:(existing&&existing.summary_json)||"",summary_upto_ts:(existing&&existing.summary_upto_ts)||"",
    summary_updated_at:(existing&&existing.summary_updated_at)||"",
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
  var err=reviewRequired(p,["market_slug","ce_id","week_start","bgm_note","bgm_author"]);if(err)return err;
  var trustedAuthor=reviewTrustedAuthor(p,p.bgm_author);
  var rec=reviewUpsertBy("weekly",function(r){return r.market_slug===p.market_slug&&
    String(r.ce_id)===String(p.ce_id)&&ymd(r.week_start)===ymd(p.week_start);},function(existing){
      var next=reviewWeeklyBase(p,existing),now=reviewNow();
      next.bgm_note=p.bgm_note;next.bgm_author=trustedAuthor;next.bgm_updated_at=now;
      next.note_deleted_at="";next.sync_status=next.slack_post_ts?"sent":"saved";next.last_error="";
      next.version=String((parseInt(next.version,10)||0)+1);return next;
    });
  return jsonResp({ok:true,weekly:rec});
}

function reviewWeeklyNoteDelete(p){
  var err=reviewRequired(p,["market_slug","ce_id","week_start","deleted_by"]);if(err)return err;
  var existing=reviewWeeklyFor(p.market_slug,p.ce_id,p.week_start);
  if(!existing)return jsonResp({ok:true,action:"noop"});
  var rec=reviewWeeklyMutate(p,function(next){next.note_deleted_at=reviewNow();
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
    updated_at:now, closed_at:closed ? ((existing && existing.closed_at) || now) : "",
    deleted_at:(existing && existing.deleted_at) || "", deleted_by:(existing && existing.deleted_by) || ""
  };
  reviewWrite("work", existing, rec);
  return jsonResp({ok:true, work_item:rec});
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
    confidence:p.confidence || "", status:"pending", created_at:reviewNow(), decided_by:"", decided_at:"",
    decision_destination:"",accepted_body:"",accepted_owner:"",accepted_due_date:""
  };
  reviewWrite("suggestions", null, rec);
  return {ok:true,suggestion:rec};
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
    reconciled_by:"",reconciled_at:""};
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
  var thread = reviewFind("threads", function(r){ return r.market_slug===p.market_slug && String(r.ce_id)===String(p.ce_id); });
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
  var recentClosed=work.filter(function(r){return !!r.closed_at;}).slice(0,25);
  return jsonResp({ok:true, identity:{market_slug:p.market_slug,ce_id:String(p.ce_id)},
    counts:{comments:comments.length,weekly_commentary:weekly.length,open_work:openWork.length,receipts:receipts.length,
      source_suggestions:suggestions.length},
    weekly_commentary:weekly.slice(0,52),comments:comments.slice(0,25),work_items:openWork.concat(recentClosed),receipts:receipts.slice(0,12),
    source_suggestions:suggestions.slice(0,25),slack_thread:thread || null,
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
    "review_receipt_upsert","review_set_upsert","review_source_reconcile","review_suggestion_decide",
    "review_granola_link_submit","review_weekly_note_upsert","review_weekly_note_delete",
    "review_weekly_slack_post","review_weekly_sync","review_slack_post","review_slack_scan"];
  if(getMutations.indexOf(action)>=0)return jsonResp({ok:false,error:action+" requires POST"});
  if (action === "review_comment_list") {
    var comments = reviewFilter(reviewRows("comments"), p);
    if (!reviewBool(p.include_deleted)) comments = comments.filter(function(r){ return !r.deleted_at; });
    var commentPage=reviewPage(comments,p,"created_at",50);
    return jsonResp({ok:true,comments:commentPage.items,next_before:commentPage.next_before});
  }
  if (action === "review_work_list") {
    var work = reviewFilter(reviewRows("work"), p, "origin_week");
    if (!reviewBool(p.include_deleted)) work = work.filter(function(r){ return !r.deleted_at; });
    if (reviewBool(p.open_only)) work = work.filter(function(r){ return !r.closed_at; });
    var workPage=reviewPage(work,p,"updated_at",100);
    return jsonResp({ok:true,work_items:workPage.items,next_before:workPage.next_before});
  }
  if (action === "review_receipt_list") {
    var receiptPage=reviewPage(reviewFilter(reviewRows("receipts"),p),p,"reviewed_at",52);
    return jsonResp({ok:true,receipts:receiptPage.items,next_before:receiptPage.next_before});
  }
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
  if(action === "review_source_ingest"){
    var expected=PropertiesService.getScriptProperties().getProperty("REVIEW_MODE_INGEST_SECRET");
    if(!expected)return jsonResp({ok:false,error:"REVIEW_MODE_INGEST_SECRET not configured"});
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
  if (action === "review_granola_link_submit") return reviewGranolaLinkSubmit(payload);
  if (action === "review_suggestion_decide") return reviewSuggestionDecide(payload);
  if (action === "review_comment_upsert") return reviewCommentUpsert(payload);
  if (action === "review_comment_delete") return reviewCommentDelete(payload);
  if (action === "review_work_upsert") return reviewWorkUpsert(payload);
  if (action === "review_work_delete") return reviewWorkDelete(payload);
  if (action === "review_receipt_upsert") return reviewReceiptUpsert(payload);
  if (action === "review_set_upsert") return reviewSetUpsert(payload);
  if (action === "review_source_reconcile") return reviewSourceReconcile(payload);
  if (action === "review_weekly_note_upsert") return reviewWeeklyNoteUpsert(payload);
  if (action === "review_weekly_note_delete") return reviewWeeklyNoteDelete(payload);
  if (action === "review_weekly_slack_post") return reviewWeeklySlackPost(payload);
  if (action === "review_weekly_sync") return reviewWeeklySync(payload);
  if (action === "review_slack_post") return reviewSlackPost(payload);
  if (action === "review_slack_scan") return reviewSlackScan(payload);
  return jsonResp({ok:false,error:"unsupported POST action: " + action});
}

// ── Weekly Review CE-scoped Slack relay ─────────────────────────────────────
// This mapping is (market, CE), not (market, CE, week). Every week's questions
// and replies stay in one durable CE
// thread. The BGM supplies free-form text and may mention any Slack user.
function reviewThreadFor(market, ceId) {
  return reviewFind("threads", function(r){
    return r.market_slug === market && String(r.ce_id) === String(ceId);
  });
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
  if (existing && existing.slack_channel && existing.slack_channel !== p.channel)
    return {ok:false,error:"CE thread already belongs to another Slack channel",thread:existing};

  var header = "*Weekly Review · " + (p.ce_name || ("CE " + p.ce_id)) + "*";
  var context = "_" + p.market_slug + " · CE " + p.ce_id + " · W/C " + ymd(p.week_start) + "_";
  var body = (existing ? "" : (header + "\n" + context + "\n")) + p.text +
    "\n_— " + p.author + "_" + (p.report_url ? "\n<" + p.report_url + "|Open CE review>" : "");
  var payload = {channel:p.channel,text:body,username:"Weekly Market Review",icon_emoji:":memo:",unfurl_links:false};
  if(p.request_id)payload.client_msg_id=String(p.request_id);
  if (existing && existing.slack_thread_ts) payload.thread_ts=String(existing.slack_thread_ts);
  var resp = UrlFetchApp.fetch("https://slack.com/api/chat.postMessage",{
    method:"post",contentType:"application/json; charset=utf-8",
    headers:{Authorization:"Bearer " + token},payload:JSON.stringify(payload),muteHttpExceptions:true});
  var result = JSON.parse(resp.getContentText());
  if (!result.ok) return {ok:false,error:"slack: " + (result.error || "unknown")};
  var now=reviewNow(), anchor=(existing && String(existing.slack_thread_ts)) || String(result.ts);
  var permalink=getPermalink(token,p.channel,anchor);
  var record={market_slug:p.market_slug,ce_id:String(p.ce_id),ce_name:p.ce_name||"",
    slack_channel:p.channel,slack_thread_ts:anchor,
    slack_permalink:permalink || (existing && existing.slack_permalink) || "",
    created_at:(existing && existing.created_at)||now,updated_at:now,
    last_scanned_ts:(existing && existing.last_scanned_ts)||anchor};
  reviewWrite("threads",existing,record);
  return {ok:true,thread:record,posted_ts:String(result.ts),posted_permalink:getPermalink(token,p.channel,String(result.ts))};
}

function reviewSlackPost(p){return jsonResp(reviewSlackPostCore(p));}

function reviewWeeklySlackPost(p){
  var err=reviewRequired(p,["market_slug","ce_id","ce_name","week_start","channel","bgm_note","bgm_author","request_id"]);
  if(err)return err;
  var current=reviewWeeklyFor(p.market_slug,p.ce_id,p.week_start);
  if(current && current.last_post_request_id===p.request_id && current.slack_post_ts)
    return jsonResp({ok:true,duplicate:true,weekly:current});
  var trustedAuthor=reviewTrustedAuthor(p,p.bgm_author);
  var mentions=reviewResolveMentions(p.bgm_note,p.market_slug);
  if(mentions.ambiguous.length)return jsonResp({ok:false,error:"ambiguous Slack mentions",mentions:mentions});
  // Save the BGM note first. If Slack fails, the report still retains the note
  // and a retry reuses request_id instead of creating another weekly starter.
  var saved=reviewWeeklyMutate(p,function(next){
    next.bgm_note=p.bgm_note;next.bgm_author=trustedAuthor;next.bgm_updated_at=reviewNow();
    // A new Slack starter is also a new current-week BGM note.  It must
    // revive a previously deleted draft rather than carrying its tombstone
    // into the current record and hiding the newly posted note in Review.
    next.note_deleted_at="";next.sync_status="posting";next.last_error="";
    next.version=String((parseInt(next.version,10)||0)+1);return next;
  });
  var posted=reviewSlackPostCore({market_slug:p.market_slug,ce_id:p.ce_id,ce_name:p.ce_name,
    week_start:p.week_start,channel:p.channel,text:mentions.resolved_text,author:trustedAuthor,
    report_url:p.report_url||"",request_id:p.request_id});
  var finalState=reviewWeeklyMutate(p,function(next){
    next.last_post_request_id=p.request_id;
    if(!posted.ok){next.sync_status="post_failed";next.last_error=posted.error||"Slack post failed";return next;}
    next.slack_post_ts=posted.posted_ts;next.slack_post_permalink=posted.posted_permalink||posted.thread.slack_permalink||"";
    next.last_scanned_ts=posted.posted_ts;next.sync_status="awaiting_replies";next.last_error="";return next;
  });
  if(!posted.ok)return jsonResp({ok:false,error:posted.error,weekly:finalState,retryable:true});
  return jsonResp({ok:true,weekly:finalState,thread:posted.thread,mentions:mentions.matches});
}

function reviewJson(value,fallback){try{return value?JSON.parse(value):fallback;}catch(err){return fallback;}}

function reviewAiWeeklySummary(sourceRows,state,context){
  var endpoint=PropertiesService.getScriptProperties().getProperty("REVIEW_MODE_AI_WEBHOOK_URL");
  if(!endpoint)return {status:"source_unavailable"};
  try{
    var secret=PropertiesService.getScriptProperties().getProperty("REVIEW_MODE_AI_WEBHOOK_SECRET")||"";
    var previous=reviewJson(state.summary_json,{});
    var resp=UrlFetchApp.fetch(endpoint,{method:"post",contentType:"application/json",
      headers:secret?{"X-Review-Secret":secret}:{},
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

function reviewWeeklySyncCore(p){
  var state=reviewWeeklyFor(p.market_slug,p.ce_id,p.week_start);
  if(!state)return {ok:false,error:"weekly commentary not found"};
  if(!state.slack_post_ts)return {ok:false,error:"weekly Slack discussion has not started",weekly:state};
  var token=PropertiesService.getScriptProperties().getProperty("SLACK_BOT_TOKEN");
  if(!token)return {ok:false,error:"SLACK_BOT_TOKEN not set in Script properties",weekly:state};
  var thread=reviewThreadFor(p.market_slug,p.ce_id);
  if(!thread)return {ok:false,error:"no CE Slack thread",weekly:state};
  // A CE keeps one Slack thread for its lifetime, so each weekly cycle needs an
  // explicit upper boundary. Otherwise a late scan of W31 can also ingest W32
  // replies after the W32 starter has been posted.
  var nextCycle=reviewRows("weekly").filter(function(r){return r.market_slug===p.market_slug&&
    String(r.ce_id)===String(p.ce_id)&&ymd(r.week_start)>ymd(p.week_start)&&r.slack_post_ts;})
    .sort(function(a,b){return ymd(a.week_start).localeCompare(ymd(b.week_start));})[0];
  var latest=nextCycle?String(nextCycle.slack_post_ts):"";
  var since=String(state.last_scanned_ts||state.slack_post_ts),scan=slackThreadReplies(token,
    thread.slack_channel,thread.slack_thread_ts,since,latest);
  if(!scan.ok)return {ok:false,error:scan.error,weekly:state};
  var newest=since,created=[];
  (scan.messages||[]).forEach(function(msg){
    var ts=String(msg.ts||"");
    if(!ts||ts<=since||ts===String(thread.slack_thread_ts)||msg.bot_id||msg.subtype)return;
    newest=ts>newest?ts:newest;
    var ref=thread.slack_channel+":"+ts;
    var result=reviewSuggestionRecord({market_slug:p.market_slug,ce_id:p.ce_id,
      ce_name:p.ce_name||state.ce_name,week_start:p.week_start,source_type:"slack",
      source_author:slackUserName(token,msg.user),source_ref:ref,
      source_url:getPermalink(token,thread.slack_channel,ts),kind:"comment",body:msg.text||"",
      confidence:"source_exact"});
    if(result.ok&&!result.duplicate)created.push(result.suggestion);
  });
  var raw=reviewRows("suggestions").filter(function(r){return r.market_slug===p.market_slug&&
    String(r.ce_id)===String(p.ce_id)&&ymd(r.week_start)===ymd(p.week_start)&&
    r.source_type==="slack"&&r.kind==="comment"&&r.confidence==="source_exact";});
  var contributors=[];raw.forEach(function(r){if(r.source_author&&contributors.indexOf(r.source_author)<0)contributors.push(r.source_author);});
  var ai=raw.length?reviewAiWeeklySummary(raw,state,p):{status:"no_new_source"};
  var next=reviewWeeklyMutate(p,function(rec){
    rec.last_scanned_ts=newest;rec.reply_count=String(raw.length);rec.contributors_json=JSON.stringify(contributors);
    if(ai.status==="ok"){
      rec.summary_json=JSON.stringify(ai.summary);rec.summary_upto_ts=newest;rec.summary_updated_at=reviewNow();
      rec.sync_status="summary_current";rec.last_error="";rec.version=String((parseInt(rec.version,10)||0)+1);
    }else if(raw.length){rec.sync_status="summary_delayed";rec.last_error=ai.status;}
    else{rec.sync_status="awaiting_replies";rec.last_error="";}
    return rec;
  });
  if(ai.status==="ok"){
    (ai.summary.action_suggestions||[]).forEach(function(item,idx){if(!item||!item.text)return;
      reviewSuggestionRecord({market_slug:p.market_slug,ce_id:p.ce_id,ce_name:next.ce_name,
        week_start:p.week_start,source_type:"slack",source_author:"AI thread summary",
        source_ref:"weekly:"+next.weekly_id+":"+newest+":action:"+idx,
        source_url:next.slack_post_permalink,kind:"action",body:item.text,
        proposed_due_date:item.due_date||"",confidence:item.confidence||"summary_derived"});});
    (ai.summary.check_suggestions||[]).forEach(function(item,idx){if(!item||!item.text)return;
      reviewSuggestionRecord({market_slug:p.market_slug,ce_id:p.ce_id,ce_name:next.ce_name,
        week_start:p.week_start,source_type:"slack",source_author:"AI thread summary",
        source_ref:"weekly:"+next.weekly_id+":"+newest+":check:"+idx,
        source_url:next.slack_post_permalink,kind:"check",body:item.text,
        proposed_due_date:item.due_date||"",confidence:item.confidence||"summary_derived"});});
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
  ScriptApp.newTrigger("reviewSyncActiveThreads").timeBased().everyMinutes(5).create();
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
  north_america:["CNSHDD2H1"],central_live_entertainment:["C042A57T52Q"],italy:["C045L2WQ79P"],france:["CH64TEB71"],
  iberia:["CH2LRMJF2"],south_america:["CH2LRMJF2"],mexico_central_america:["C012949PQ81"],
  csee:["CSQ10TALA"],nordics:["CSQ10TALA"],united_kingdom:["CKTFHT4AF"],benelux:["CKTFHT4AF"],
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
      headers:secret?{"X-Review-Secret":secret}:{},
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
