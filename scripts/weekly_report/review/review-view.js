/* Mini Audit — the report's live /api/review workspace.
 * One writeup, shared actions, and CE memory alongside the existing CE drawer.
 * No standalone mockup runtime is included. Rebuild with inject_review_view.py.
 */
(function (global) {
  "use strict";

  function summaryThreadFor(weekly,registry) {
    weekly=weekly||{};registry=registry||{};
    // A pinned week's summary follows its saved discussion, independently of
    // the active thread used by the writeup's Continue control.
    if(weekly.thread_binding_id)return (registry.threads||[]).find(function(t){return String(t.binding_id)===String(weekly.thread_binding_id);})||null;
    if(weekly.slack_post_ts||weekly.slack_post_permalink)return null; // Backend resolves legacy provenance; never guess active here.
    return registry.active||null;
  }

  // Read-only projection of the shared CE records. Never create a second task store.
  function ceMemoryEntries(memory, live) {
    memory=memory||{};live=live||{};
    var rows=[],seen={},weeklyIds={},workIds={},receiptIds={};
    function merge(base,updates,key){var map={};(base||[]).concat(updates||[]).forEach(function(r,i){map[r[key]||('row:'+i)]=r;});return Object.keys(map).map(function(k){return map[k];});}
    function date(value){var s=String(value||'');return /^\d{10}\.\d+$/.test(s)?new Date(Number(s)*1000).toISOString():s;}
    function text(value){return typeof value==='string'?value:(value&&(value.text||value.body||value.decision))||'';}
    function summary(raw){try{var s=typeof raw==='string'?JSON.parse(raw):raw;return ['findings','decisions','open_points'].map(function(k){return {label:{findings:'Findings',decisions:'Decisions',open_points:'Open questions'}[k],points:(s[k]||[]).map(text).filter(Boolean)};}).filter(function(s){return s.points.length;});}catch(_){return [];}}
    function add(r){if(seen[r.id]||(!r.body&&!r.status&&!(r.sections||[]).length))return;seen[r.id]=true;r.date=date(r.date);rows.push(r);}
    function source(s){return s==='granola'?'Meeting':s==='slack'?'Slack':s==='historical_sheet'?'Historical record':s||'Review';}
    merge(memory.comments,live.comments,'comment_id').forEach(function(c){if(!c.deleted_at)add({id:'comment:'+c.comment_id,label:c.source_type==='granola'?'Meeting note':'Note',body:c.body,week:c.week_start,date:c.created_at,author:c.source_author||c.author_name,source:source(c.source_type),url:c.source_url,approvedBy:c.accepted_by});});
    merge(memory.weekly_commentary||memory.weekly,live.weekly,'weekly_id').forEach(function(w){
      weeklyIds[w.weekly_id]=w;
      ['bgm','bdm','performance'].forEach(function(role){if(w[role+'_note']&&!(role==='bgm'?w.note_deleted_at:w[role+'_note_deleted_at']))add({id:'weekly:'+w.weekly_id+':'+role,label:role==='bgm'?'BGM observation':role==='bdm'?'BDM note':'Performance diagnosis',body:w[role+'_note'],week:w.week_start,date:w[role+'_updated_at']||w.week_start,author:w[role+'_author'],source:'Original note'});});
      if(w.summary_approved_json||w.summary_status==='approved')add({id:'summary:'+w.weekly_id,label:'Slack summary'+(w.summary_slack_discussion_number?' · Discussion '+w.summary_slack_discussion_number:''),sections:summary(w.summary_approved_json||w.summary_json),week:w.week_start,date:w.summary_approved_at||w.summary_updated_at||w.week_start,workPrefix:w.summary_thread_binding_id?'weekly:'+w.weekly_id+':'+w.summary_thread_binding_id+':':'',author:w.summary_approved_by,source:'Slack',url:w.slack_post_permalink});
    });
    (memory.historical_comments||[]).forEach(function(c,i){add({id:'historical-comment:'+(c.source_row||i),label:'Earlier CE comment',body:c.body,week:c.week_start,date:c.created_at||c.week_start,author:c.author_name,source:'Historical record · read-only',url:c.slack_permalink,duplicate_count:c.duplicate_count});});
    (memory.perf_history||memory.perf_actions||[]).forEach(function(p,i){add({id:'performance:'+(p.source_row||i),label:'Performance action',body:p.action_text||p.text||p.action||p.comment,week:p.week_start||p.week,date:p.updated_at||p.week_start,author:p.owner,status:p.status,bucket:p.bucket,outcome:p.outcome,duplicate_count:p.duplicate_count,source:'Historical record · read-only'});});
    (memory.work_items||[]).forEach(function(w){workIds[w.work_id]=true;});
    // A successful work fetch is authoritative, including deletions. Memory is a read fallback.
    (live.work!==undefined?live.work:(memory.work_items||[])).forEach(function(w){workIds[w.work_id]=true;if(!w.deleted_at)add({id:'work:'+w.work_id,label:w.kind==='check'?'Follow-up':'Action',body:w.text,week:w.origin_week,date:w.updated_at||w.created_at||w.origin_week,author:w.owner,status:w.status,due:w.due_date,outcome:w.measured_outcome,evidence:w.completion_evidence,source:source(w.source_type),url:w.source_url,workId:w.work_id});});
    (memory.receipts||[]).forEach(function(r){receiptIds[r.receipt_id]=true;add({id:'receipt:'+r.receipt_id,label:'Review completed',body:r.summary||'Review recorded',week:r.week_start,date:r.reviewed_at,author:r.reviewer,source:'Review'});});
    (memory.timeline||[]).forEach(function(e){
      var type=e.event_type,projected=String(e.event_id||'').indexOf('projection:')===0;
      if(type==='performance_history'&&(memory.perf_history||[]).length)return;
      if(type==='historical_comment'&&(memory.historical_comments||[]).length)return;
      if((type==='work_opened'||type==='work_completed')&&workIds[e.related_work_id])return;
      if(type==='review_finished'&&receiptIds[e.source_ref||e.related_review_id])return;
      if(type==='bgm_observation'&&weeklyIds[e.source_ref])return;
      if(type==='slack_summary'&&projected&&Object.keys(weeklyIds).some(function(k){var w=weeklyIds[k];return (w.summary_approved_json||w.summary_status==='approved')&&String(w.week_start)===String(e.review_week);}))return;
      add({id:e.event_id,label:{slack_summary:'Slack summary',historical_comment:'Earlier CE comment',performance_history:'Performance action',outcome_approved:'Decision',metric_outcome:'Measured outcome',completion_evidence:'Completion evidence'}[type]||String(type||'Activity').replace(/_/g,' '),body:type==='slack_summary'?'':e.approved_body||e.original_body,sections:type==='slack_summary'?summary(e.approved_body||e.original_body):[],week:e.review_week,date:e.occurred_at||e.recorded_at||e.review_week,author:e.actor_name,source:source(e.source_type),url:e.source_url,workId:e.related_work_id,approvedBy:e.approved_by,workPrefix:type==='slack_summary'&&e.related_review_id&&e.source_ref?'weekly:'+e.related_review_id+':'+e.source_ref+':':''});
    });
    rows.forEach(function(r){if(!r.workPrefix)return;r.relatedWork=(live.work!==undefined?live.work:(memory.work_items||[])).filter(function(w){return !w.deleted_at&&String(w.source_ref||'').indexOf(r.workPrefix)===0;}).map(function(w){return {id:w.work_id,text:w.text,status:w.status};});});
    return rows.sort(function(a,b){return b.date.localeCompare(a.date)||a.id.localeCompare(b.id);});
  }
  global.weeklyCeMemoryEntries=ceMemoryEntries;

  // Week ownership comes from the review record, never its last-edited timestamp.
  function ceMemoryWeeks(entries, threads) {
    var groups={};
    function group(week){var key=/^\d{4}-\d{2}-\d{2}$/.test(String(week||''))?week:'undated';return groups[key]||(groups[key]={week:key,paragraphs:[],work:[],sources:[]});}
    (entries||[]).slice().sort(function(a,b){return String(a.date||'').localeCompare(String(b.date||''));}).forEach(function(r){
      var g=group(r.week);g.sources.push(r);
      if(r.workId&&(r.label==='Action'||r.label==='Follow-up'||r.label==='work opened'||r.label==='work completed')){if(!g.work.some(function(w){return w.workId===r.workId;}))g.work.push(r);return;}
      // Operational events remain in Sources; they are not a diagnosis or conclusion.
      if(['candidate created','shortlist selected','slack discussion','Review completed','review finished','nomination','comment revision'].indexOf(r.label)>=0)return;
      var parts=r.body?[r.body]:[];
      (r.sections||[]).forEach(function(s){if(s.points.length)parts.push((s.label==='Open questions'?'Still unresolved: ':'')+s.points.join(' '));});
      var body=parts.join(' ').trim();if(!body&&r.label!=='Performance action')return;
      var existing=g.paragraphs.find(function(p){return p.text===body;});
      if(existing)existing.sourceIds.push(r.id);else g.paragraphs.push({text:body,sourceIds:[r.id]});
    });
    (threads||[]).forEach(function(t,i){
      // A thread is listed once in the week it started, even when reused later.
      var linked=(entries||[]).find(function(r){return t.slack_permalink&&r.url===t.slack_permalink;});
      var g=group(t.replacement_week||(linked&&linked.week));
      g.sources.push({id:'thread:'+(t.binding_id||i),label:'Slack discussion',body:t.created_reason||'CE discussion',author:t.created_by,date:t.created_at,url:t.slack_permalink,status:t.binding_status,source:'Slack'});
    });
    return Object.keys(groups).sort(function(a,b){if(a==='undated')return 1;if(b==='undated')return -1;return b.localeCompare(a);}).map(function(k){return groups[k];});
  }
  global.weeklyCeMemoryWeeks=ceMemoryWeeks;

  var TREATMENT_LABELS = {
    not_scheduled: "Not scheduled", live: "Review live", async: "Review async",
    follow_up: "Follow-up only", skip: "Skip this week"
  };
  var TREATMENT_ORDER = ["not_scheduled", "live", "async", "follow_up", "skip"];
  var WORK_STATUS = [
    ["needs_action", "Needs action"], ["already_actioned", "Already actioned"],
    ["self_recovering", "Self-recovering"], ["monitoring", "Monitoring"],
    ["blocked", "Blocked"], ["stale", "Stale"], ["no_action_needed", "No action needed"],
    ["complete", "Complete"], ["dismissed", "Archived / dismissed"]
  ];
  var CHECK_STATUS = [
    ["scheduled", "Scheduled"], ["monitoring", "Monitoring"],
    ["self_recovering", "Self-recovering"], ["complete", "Complete"]
  ];
  var CLOSED = ["complete", "cancelled", "dismissed", "no_action_needed"];
  var MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];
  // Primary posting routes mirror alert/market_channels.json. Alternate market
  // channels remain read/mention sources; one discussion must have one stable home.
  var MARKET_CHANNELS = {
    north_america:{id:"C0BQHT29WMB",name:"adhoc-north-america"},italy:{id:"C045L2WQ79P",name:"mkt-italy-switzerland-malta"},
    oceania:{id:"CHKRLFDPU",name:"mkt-australia"},france:{id:"CH64TEB71",name:"mkt-france"},
    united_kingdom:{id:"CKTFHT4AF",name:"mkt-uk"},iberia:{id:"CH2LRMJF2",name:"mkt-iberia"},
    csee:{id:"CSQ10TALA",name:"mkt-csee"},east_asia:{id:"CQD6220VB",name:"mkt-japan"},
    sea:{id:"C5WFYN82H",name:"mkt-singapore"},uae:{id:"C046622L80Z",name:"mkt-mena"},
    gcc:{id:"C0889D22PM5",name:"mkt-mena-expansion-internal"},north_africa:{id:"C0889D22PM5",name:"mkt-mena-expansion-internal"},
    rest_of_mea:{id:"C0889D22PM5",name:"mkt-mena-expansion-internal"},benelux:{id:"CL13UPZ6V",name:"mkt-netherlands"},
    nordics:{id:"CSQ10TALA",name:"mkt-csee"},south_america:{id:"CH2LRMJF2",name:"mkt-iberia"},
    mexico_central_america:{id:"C012949PQ81",name:"mkt-mexico"}
  };

  global.initReviewView = function initReviewView(ctx) {
    var root = ctx.root;
    if (!root) return null;
    var H = ctx.helpers || {};
    var esc = H.escapeHtml || function (v) {
      return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) {
        return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
      });
    };
    var api = global.createWeeklyReviewApi ? global.createWeeklyReviewApi("/api/review") : null;

    var S = {
      headline: null, market: "", market_slug: "", week_start: "", week_end: "", channel: null,
      queue: [], byId: {}, selected: null, loaded: false,
      receipts: {}, outcomes: {}, weekly: {}, weeklyHist: {}, threadRegistry: {}, threadRegistryLoaded:{}, threadRegistryError:{}, work: {}, suggestions: {}, comments: {}, setRows: {}, setRowsList: [],
      loadingCe: {}, editingNote: false, editingRole: "", confirmDelete: false, adding: false, compose: "",
      processing: false, processSummary: "", noteDraft: null, roleDrafts: {}, slackDrafts: {}, composeDrafts: {}, composeByCe: {}, queueQuery: "", queueFilter: "all", queueReason: "", queueCategory: "", queueOwner: "", queueTaskForce: "", queueBrowse: false, expandedSuggestion: "", workTab: "open", mentionPreview: null, mentionBusy: false,
      editingWork: null, confirmDeleteWork: null, editingComment: null, confirmDeleteComment: null,
      threadOperation: "", threadOperationByCe: {}, newThreadReason: "", newThreadReasonDrafts: {}, backlogView: "open", reconciliation: null, finishReasonOpen:false, showAllSuggestions:false,
      drafts: {}, writeupEditors: {}, outcomeDrafts: {}, noDiscussionDrafts:{}, ceLoadedAt: {}, ceRequestSeq: {}, ceControllers: {}, memoryCache: {}, memoryInflight: {}, asyncBusy: {}, resourceErrors: {}, auditStatus: {}, queueOpen: false, sendRequests: {}
    };

    // Review mutations are BGM-only.  The server already has the authenticated
    // Google identity, so hydrate the local display name once instead of
    // blocking meeting imports/actions behind an unrelated manual name field.
    if (api && api.whoami) {
      api.whoami().then(function (identity) {
        if (identity && identity.actor_name && !author()) {
          setAuthor(identity.actor_name);
          if (S.loaded) render();
        }
      }).catch(function () {
        // The normal mutation path will give the user the actionable auth error.
      });
    }

    // ---- small helpers ---------------------------------------------------
    function author() { try { return localStorage.getItem("wr_author") || ""; } catch (e) { return ""; } }
    function setAuthor(v) { try { localStorage.setItem("wr_author", String(v || "").trim()); } catch (e) {} }
    function sessionId(){try{var id=sessionStorage.getItem("wr_review_session");if(!id){id="rvs_"+Date.now()+"_"+Math.random().toString(36).slice(2);sessionStorage.setItem("wr_review_session",id);}return id;}catch(e){return "session";}}
    function track(event,fields){if(!api||typeof api.recordTelemetry!=="function")return;var f=fields||{},key=[event,S.market_slug,S.week_start,f.ce_id||S.selected||"",f.value_text||"",sessionId()].join(":");api.recordTelemetry({market_slug:S.market_slug,ce_id:String(f.ce_id||S.selected||""),week_start:S.week_start,event_type:event,value_number:f.value_number,value_text:f.value_text||"",actor_name:author(),session_id:sessionId(),idempotency_key:f.idempotency_key||key}).catch(function(){});}
    function ident(ceId) {
      var ce = S.byId[String(ceId)] || {};
      return { market_slug: S.market_slug, ce_id: String(ceId), ce_name: ce.ce_name || "", week_start: S.week_start };
    }
    function syncUrl(ceId) {
      try {
        var url = new URL(location.href);
        url.searchParams.set("view", "review");
        url.searchParams.set("market", S.market_slug);
        url.searchParams.set("week", S.week_start);
        if (ceId) url.searchParams.set("ce_id", String(ceId)); else url.searchParams.delete("ce_id");
        history.replaceState(history.state, "", url.toString());
      } catch (e) {}
    }
    function ensureLocalCe(ceId) {
      var id=String(ceId), ce=(S.headline.all_ces||[]).find(function(row){return String(row.ce_id)===id;});
      if (!ce) return null;
      if (!S.byId[id]) { var q={ce_id:id,ce_name:ce.ce_name||("CE "+id),reason:"Opened from CE drawer",source:"drawer"}; S.queue.push(q); S.byId[id]=q; }
      return ce;
    }
    function revealQueueSelection(ceId) {
      var panel = root.querySelector("#rv-queue-review");
      var active = root.querySelector('[data-select-ce="' + String(ceId).replace(/"/g, '\\"') + '"]');
      if (!panel || !active) return;
      var rowRect = active.getBoundingClientRect();
      var panelRect = panel.getBoundingClientRect();
      if (rowRect.top < panelRect.top) panel.scrollTop += rowRect.top - panelRect.top;
      else if (rowRect.bottom > panelRect.bottom) panel.scrollTop += rowRect.bottom - panelRect.bottom;
      if (active.focus) active.focus({ preventScroll: true });
    }
    function captureVisibleDrafts() {
      var draftCe=S.renderedCe||S.selected;
      S.memoryDisclosures=S.memoryDisclosures||{};

      root.querySelectorAll("[data-role-input]").forEach(function (el) {
        S.roleDrafts[roleDraftKey(el.dataset.roleInput)] = el.value;
      });
      var note = root.querySelector("#rv-note");
      if (note) { S.noteDraft = note.value; S.drafts[String(draftCe)] = note.value; }
      var meeting=root.querySelector("#rv-process-text");if(meeting)S.meetingDraft=meeting.value;
      var slack = root.querySelector("#rv-slack-message");
      if (slack) S.slackDrafts[String(draftCe)] = slack.value;
      var reason = root.querySelector("#rv-new-thread-reason");
      if (reason) S.newThreadReasonDrafts[String(draftCe)] = reason.value;
      if (S.threadOperation) S.threadOperationByCe[String(draftCe)] = S.threadOperation;
      if (S.compose) {
        var composeKey=composeDraftKey(draftCe,S.compose);
        S.composeByCe[String(draftCe)]=S.compose;
        S.composeDrafts[composeKey]={
          text:(root.querySelector("#rv-c-text")||{}).value||"",
          owner:(root.querySelector("#rv-c-owner")||{}).value||"",
          due:(root.querySelector("#rv-c-due")||{}).value||"",
          status:(root.querySelector("#rv-c-status")||{}).value||(S.compose==="check"?"scheduled":"needs_action")
        };
      }
    }
    function openAnalyticsDrawer(ceId) {
      captureVisibleDrafts();
      var ce=ensureLocalCe(ceId);
      if (ce && ctx.openCeDrawer) ctx.openCeDrawer(String(ce.ce_id)); else toast("CE analytics drawer unavailable for this CE");
    }
    function toast(msg) {
      var t = document.getElementById("rv-toast");
      if (!t) return;
      t.textContent = msg; t.hidden = false;
      clearTimeout(global.__rvToast); global.__rvToast = setTimeout(function () { t.hidden = true; }, 2800);
    }
    function initials(name) {
      var p = String(name || "").trim().split(/\s+/).filter(Boolean);
      if (!p.length) return "?";
      return (p[0][0] + (p.length > 1 ? p[p.length - 1][0] : "")).toUpperCase();
    }
    function avatar(name, cls) {
      var n = String(name || "").trim();
      if (!n) return '<span class="rv-av ' + (cls || "") + ' none">–</span>';
      return '<span class="rv-av ' + (cls || "") + '" title="' + esc(n) + '">' + esc(initials(n)) + "</span>";
    }
    function parseDate(s) { if (!s) return null; var d = new Date(String(s).length <= 10 ? s + "T00:00:00Z" : s); return isNaN(d) ? null : d; }
    function fmtWhen(iso) {
      var d = parseDate(iso); if (!d) return "";
      var now = new Date(), same = d.getUTCFullYear() === now.getFullYear() && d.getUTCMonth() === now.getMonth() && d.getUTCDate() === now.getDate();
      var hh = String(d.getHours()).padStart(2, "0"), mm = String(d.getMinutes()).padStart(2, "0");
      return same ? "Today, " + hh + ":" + mm : d.getUTCDate() + " " + MONTHS[d.getUTCMonth()][0] + MONTHS[d.getUTCMonth()].slice(1).toLowerCase();
    }
    function fmtDue(s) { var d = parseDate(s); return d ? d.getUTCDate() + " " + MONTHS[d.getUTCMonth()][0] + MONTHS[d.getUTCMonth()].slice(1).toLowerCase() : ""; }
    function optionList(options, value) {
      var list = options.slice();
      if (value && !list.some(function (o) { return o[0] === value; })) list.push([value, value]);
      return list.map(function (o) { return '<option value="' + esc(o[0]) + '"' + (o[0] === value ? " selected" : "") + ">" + esc(o[1]) + "</option>"; }).join("");
    }
    function sourceName(item) {
      var source = String((item && item.source_type) || "").toLowerCase();
      return source === "slack" ? "Slack" : source === "granola" ? "Meeting" : "Imported";
    }
    function flaggedRows(h) {
      var b = (h && h.diagnostic_buckets) || {}, lm = b.losing_money || {}, fx = b.fluctuations || {}, out = [];
      (lm.existing || []).forEach(function (r) { out.push({ ce_id: r.ce_id, ce_name: r.ce_name, reason: "Losing money", bucket: "losing_money" }); });
      (lm.new || []).forEach(function (r) { out.push({ ce_id: r.ce_id, ce_name: r.ce_name, reason: "Losing money · new", bucket: "losing_money" }); });
      (fx.down || []).forEach(function (r) { out.push({ ce_id: r.ce_id, ce_name: r.ce_name, reason: "RPC / CM1 drop", bucket: "flux_down" }); });
      (fx.up || []).forEach(function (r) { out.push({ ce_id: r.ce_id, ce_name: r.ce_name, reason: "RPC / CM1 spike", bucket: "flux_up" }); });
      return out;
    }
    function buildQueue() {
      var h = S.headline, all = h.all_ces || [], nameById = {};
      all.forEach(function (ce) { nameById[String(ce.ce_id)] = ce.ce_name; });
      var seen = {}, queue = [];
      flaggedRows(h).forEach(function (r) {
        var id = String(r.ce_id); if (!id || seen[id]) return; seen[id] = true;
        queue.push({ ce_id: id, ce_name: r.ce_name || nameById[id] || ("CE " + id), reason: r.reason, source: "flag" });
      });
      (S.setRowsList || []).forEach(function (r) {
        var id = String(r.ce_id); if (!id || seen[id]) return; seen[id] = true;
        queue.push({ ce_id: id, ce_name: r.ce_name || nameById[id] || ("CE " + id), reason: r.reason || "Added to review", source: "manual" });
      });
      S.queue = queue; S.byId = {};
      queue.forEach(function (q) { S.byId[q.ce_id] = q; });
    }
    function treatmentFor(ceId) { var r = S.setRows[String(ceId)]; return (r && r.treatment) || "not_scheduled"; }
    function reviewedFor(ceId) { return !!S.receipts[String(ceId)]; }
    function workFor(ceId) { return (S.work[String(ceId)] || []); }
    function openWorkFor(ceId) { return workFor(ceId).filter(function (w) { return CLOSED.indexOf(w.status) < 0; }); }
    function shortlistState(q) {
      if (reviewedFor(q.ce_id)) return "reviewed";
      var treatment = treatmentFor(q.ce_id);
      if (["live", "async", "follow_up"].indexOf(treatment) >= 0) return "selected";
      if (treatment === "skip") return "skipped";
      return "candidate";
    }
    function refreshHeadline() {
      var h = ctx.getHeadline ? ctx.getHeadline() : null;
      if (!h) return false;
      var changed = h.market_slug !== S.market_slug || h.week_start !== S.week_start;
      if(changed){
        captureVisibleDrafts();S.reportDrafts=S.reportDrafts||{};
        if(S.market_slug)S.reportDrafts[S.market_slug+"|"+S.week_start]={writeups:S.slackDrafts,threads:S.threadOperationByCe};
        var saved=S.reportDrafts[(h.market_slug||h.market)+"|"+h.week_start]||{};
        S.slackDrafts=saved.writeups||{};S.threadOperationByCe=saved.threads||{};S.threadOperation="";
        S.renderedCe=null;S.selected=null;S.loaded=false;S.loadingCe={};S.weekly={};S.weeklyHist={};S.comments={};S.suggestions={};S.work={};S.workLoaded=false;S.ceLoadedAt={};S.resourceErrors={};S.threadRegistry={};S.threadRegistryLoaded={};S.threadRegistryError={};S.auditStatus={};S.meetingResults=[];S.meetingUnmatched=[];S.processSummary="";S.compose="";S.noteDraft=null;
      }
      S.headline = h; S.market = h.market || h.market_slug || ""; S.market_slug = h.market_slug || h.market || "";
      S.week_start = h.week_start || ""; S.week_end = h.week_end || "";
      var ch = (h.notes_channels || (ctx.getBaseHeadline && ctx.getBaseHeadline().notes_channels) || {})[S.market_slug];
      // North America Review discussions intentionally use the dedicated
      // ad-hoc room; weekly alerts continue to use the report payload's mkt-usa route.
      S.channel = S.market_slug === "north_america" ? MARKET_CHANNELS.north_america : (ch || MARKET_CHANNELS[S.market_slug] || null);
      return changed;
    }
    function loadQueue() {
      refreshHeadline();
      if (!api) { S.setRowsList = []; buildQueue(); render(); return Promise.resolve(); }
      // Paint the snapshot-backed queue immediately. Remote review state then
      // enriches it without delaying tab navigation.
      if (!S.loaded) {
        buildQueue();
        if (!S.selected || !S.byId[S.selected]) S.selected = (S.queue[0] || {}).ce_id || null;
        S.loaded = true; render();
        if (S.selected) loadCe(S.selected);
      }
      var market=S.market_slug,week=S.week_start,id={market_slug:market,week:week};
      function current(){return S.market_slug===market&&S.week_start===week;}
      return Promise.all([
        api.reviewSet(id).then(function(res){if(!current())return;S.setRowsList=res.review_set||[];S.setRows={};S.setRowsList.forEach(function(r){S.setRows[String(r.ce_id)]=r;});var selected=S.selected;buildQueue();if(selected)ensureLocalCe(selected);render();}).catch(function(){}),
        api.receipts(id).then(function(res){if(!current())return;S.receipts={};(res.receipts||[]).forEach(function(r){S.receipts[String(r.ce_id)]=r;});render();}).catch(function(){}),
        reloadWork()
      ]);
    }

    function loadCe(ceId, force) {
      ceId=String(ceId);
      if (!api) return Promise.resolve();
      if (S.loadingCe[ceId]) {
        if (!force) return S.loadingCe[ceId];
        var pending=S.loadingCe[ceId],pendingMarket=S.market_slug,pendingWeek=S.week_start;
        return pending.then(function(){if(S.market_slug===pendingMarket&&S.week_start===pendingWeek)return loadCe(ceId,true);});
      }
      if (!force && S.ceLoadedAt[ceId] && Date.now()-S.ceLoadedAt[ceId]<60000) return Promise.resolve();
      var market=S.market_slug, week=S.week_start, seq=(S.ceRequestSeq[ceId]||0)+1;
      var commentVersion=(S.commentVersions||{})[ceId]||0;
      S.ceRequestSeq[ceId]=seq;
      var options={refresh:!!force,timeoutMs:45000}, errors=S.resourceErrors[ceId]=S.resourceErrors[ceId]||{};
      function current(){return S.market_slug===market&&S.week_start===week&&S.ceRequestSeq[ceId]===seq;}
      function resource(name,call,apply){return call.then(function(res){if(!current())return;apply(res);delete errors[name];if(String(S.selected)===ceId)render();}).catch(function(error){if(!current())return;errors[name]=error.message||"Unavailable";if(name==="threads")S.threadRegistryError[ceId]=true;if(String(S.selected)===ceId)render();});}
      var calls=[
        resource("notes",api.weeklyCommentary({market_slug:market,ce_id:ceId,week:week},"",8,options),function(res){var rows=res.weekly||[];S.weeklyHist[ceId]=rows;S.weekly[ceId]=rows.find(function(r){return String(r.week_start)===week;})||null;}),
        resource("suggestions",api.suggestions({market_slug:market,ce_id:ceId,week:week},false,options),function(res){S.suggestions[ceId]=res.suggestions||[];}),
        resource("comments",api.comments({market_slug:market,ce_id:ceId,week:week},false,options),function(res){if(((S.commentVersions||{})[ceId]||0)===commentVersion)S.comments[ceId]=res.comments||[];}),
        resource("threads",api.threads({market_slug:market,ce_id:ceId},options),function(res){S.threadRegistry[ceId]={active:res.active_thread||null,threads:res.threads||[]};S.threadRegistryLoaded[ceId]=true;delete S.threadRegistryError[ceId];})
      ];
      S.loadingCe[ceId]=Promise.all(calls).finally(function(){if(current()){delete S.loadingCe[ceId];S.ceLoadedAt[ceId]=Object.keys(errors).length?0:Date.now();}});
      if((S.memoryDisclosures||{})[market+"|"+ceId+"|memory"])loadMemoryInline(ceId,force);
      return S.loadingCe[ceId];
    }
    function loadMemoryInline(ceId,force){
      if(!api)return;
      var market=S.market_slug,week=S.week_start,key=market+"|"+week+"|"+ceId;
      if(S.memoryInflight[key])return force?S.memoryInflight[key].then(function(){if(S.market_slug===market&&S.week_start===week)return loadMemoryInline(ceId,true);}):S.memoryInflight[key];
      if(!force&&S.memoryCache[key])return Promise.resolve();
      S.memoryInflight[key]=api.memory({market_slug:market,ce_id:ceId},!!force).then(function(res){S.memoryCache[key]=res;if(S.market_slug===market&&S.week_start===week&&String(S.selected)===String(ceId))render();}).catch(function(error){S.memoryCache[key]=Object.assign({},S.memoryCache[key]||{},{error:error.message||"Memory unavailable"});if(String(S.selected)===String(ceId))render();}).finally(function(){delete S.memoryInflight[key];});
    }

    function select(ceId) {
      captureVisibleDrafts();
      if (S.selected && S.noteDraft != null) S.drafts[String(S.selected)] = S.noteDraft;

      S.selected = String(ceId); S.confirmDelete = false; S.compose = S.composeByCe[S.selected]||""; S.editingRole = ""; S.memoryOpen = false; S.queueBrowse = false; S.expandedSuggestion = ""; S.finishReasonOpen=false; S.showAllSuggestions=false;
      S.noteDraft = Object.prototype.hasOwnProperty.call(S.drafts, S.selected) ? S.drafts[S.selected] : null;
      S.editingNote = S.noteDraft != null;
      S.mentionPreview = null; S.threadOperation = S.threadOperationByCe[S.selected]||""; S.newThreadReason = S.newThreadReasonDrafts[S.selected]||""; S.editingWork = null; S.confirmDeleteWork = null; S.editingComment = null; S.confirmDeleteComment = null;
      syncUrl(S.selected);
      render();
      loadCe(S.selected);
    }

    // ---- render: shell ---------------------------------------------------
    function render() {
      if (!S.headline) { root.innerHTML=""; return; }
      if(S.renderedCe===S.selected)captureVisibleDrafts();
      var focus=document.activeElement, focusId=S.renderedCe===S.selected&&focus&&root.contains(focus)?focus.id:"", caret=focus&&focus.selectionStart;
      var audit=root.querySelector(".rv-main"),scroll=S.renderedCe===S.selected&&audit?audit.scrollTop:0;
      if(ctx.releaseAnalytics)ctx.releaseAnalytics();
      root.innerHTML='<div class="rv-audit-toolbar"><button class="rv-btn" id="rv-audit-queue" type="button">☰ Mini Audit queue</button><span>'+esc(S.market)+' · '+esc(S.week_start)+'</span><button class="rv-btn" id="rv-meeting" type="button">Add meeting notes</button></div>'+
        (S.processing?renderMeetingInput():"")+'<div class="rv-layout rv-mini-audit"><section class="rv-data-pane" id="rv-data-pane" aria-label="CE data"></section>'+renderMain()+'</div>'+
        (S.queueOpen?'<div class="rv-queue-overlay" role="dialog" aria-modal="true" aria-label="Choose a CE">'+renderSide()+'</div>':"")+'<div class="rv-toast" id="rv-toast" role="status" hidden></div>';
      S.renderedCe=S.selected;
      if(!root.hidden&&S.selected&&ctx.mountAnalytics)ctx.mountAnalytics(root.querySelector("#rv-data-pane"),S.selected);
      wire();
      audit=root.querySelector(".rv-main");if(audit)audit.scrollTop=scroll;
      var next=focusId&&document.getElementById(focusId);if(next){next.focus({preventScroll:true});if(typeof caret==="number"&&next.setSelectionRange)next.setSelectionRange(caret,caret);}
    }

    function renderAuditQueueRows(){
      var needle=String(S.queueQuery||"").trim().toLowerCase();
      var rows=needle?(S.headline.all_ces||[]).filter(function(ce){return [ce.ce_id,ce.ce_name,ce.city].join(" ").toLowerCase().indexOf(needle)>=0;}):S.queue;
      return rows.length?rows.slice(0,100).map(function(q){var count=openWorkFor(String(q.ce_id)).length;return '<button class="rv-ce-row'+(String(q.ce_id)===S.selected?' active':'')+'" type="button" data-select-ce="'+esc(q.ce_id)+'"><span class="rv-ce-copy"><strong>'+esc(q.ce_name)+'</strong><small>CE '+esc(q.ce_id)+(q.reason?' · '+esc(q.reason):'')+(count?' · '+count+' open actions':'')+'</small></span></button>';}).join(""):'<p class="rv-subtle">'+(needle?'No matching CEs.':'Search for any CE to begin.')+'</p>';
    }
    function renderSide(){
      return '<aside class="rv-side" aria-label="Mini Audit queue"><div class="rv-summary-heading"><h2>Choose a CE</h2><button class="rv-close" id="rv-close-queue" type="button" aria-label="Close CE browser">×</button></div><label class="rv-search"><span class="sr-only">Search CE</span><input id="rv-search-ce" aria-label="Search CE" type="search" placeholder="Search all CEs by name or ID" value="'+esc(S.queueQuery||"")+'"><button id="rv-clear-search" type="button" aria-label="Clear CE search">×</button></label><div class="rv-queue-panel" id="rv-queue-review">'+renderAuditQueueRows()+'</div></aside>';
    }
    function renderPickerResults() {
      var all = (S.headline.all_ces || []);
      var q = (S.pickerQuery || "").toLowerCase();
      if (!q) return '<div class="rv-picker-empty">Type a CE name, id or city…</div>';
      var matches = all.filter(function (ce) {
        if (S.byId[String(ce.ce_id)]) return false;
        return (String(ce.ce_name || "") + " " + String(ce.ce_id) + " " + String(ce.city || "")).toLowerCase().indexOf(q) >= 0;
      }).slice(0, 20);
      if (!matches.length) return '<div class="rv-picker-empty">No unadded CE matches “' + esc(S.pickerQuery) + "”.</div>";
      return matches.map(function (ce) {
        return '<button class="rv-picker-item" type="button" data-pick-ce="' + esc(ce.ce_id) + '"><strong>' + esc(ce.ce_name || ("CE " + ce.ce_id)) +
          "</strong><small>CE " + esc(ce.ce_id) + (ce.city ? " · " + esc(ce.city) : "") + (ce.category ? " · " + esc(ce.category) : "") + "</small></button>";
      }).join("");
    }

    // ---- render: workspace ----------------------------------------------
    function renderMain() {
      var q=S.byId[S.selected];
      if(!q)return '<main class="rv-main"><div class="rv-empty-state">Choose a CE to start a Mini Audit.</div></main>';
      return '<main class="rv-main" aria-label="Mini Audit"><header class="rv-detail-head"><div class="rv-eyebrow">Mini Audit · CE '+esc(q.ce_id)+'</div><h2>'+esc(q.ce_name)+'</h2></header><div class="rv-workspace">'+renderCommentaryCard(q)+renderActionsCard(q)+renderMemoryRail(q)+'</div></main>';
    }

    function completionBlockers(q){
      var blockers=[],weekly=S.weekly[q.ce_id]||{},pending=dedupeSuggestions((S.suggestions[q.ce_id]||[]).filter(function(s){return (!s.decided_at&&(!s.status||s.status==="pending"))&&(s.kind==="action"||s.kind==="check"||s.kind==="comment"||!s.kind); }));
      if(treatmentFor(q.ce_id)==="not_scheduled")blockers.push({key:"treatment",label:"Choose a review path"});
      if(!weekly.slack_post_ts&&!String(S.noDiscussionDrafts[q.ce_id]||"").trim())blockers.push({key:"discussion",label:"Start Slack or add a no-discussion reason"});
      if(pending.length)blockers.push({key:"suggestions",label:"Triage "+pending.length+" pending suggestion"+(pending.length===1?"":"s")});
      var unmanaged=openWorkFor(q.ce_id).filter(function(w){return !(String(w.carry_forward)==="true"||(w.owner&&(w.due_date||w.next_review_date))||(w.kind==="check"&&(w.due_date||w.next_review_date)));});
      if(unmanaged.length)blockers.push({key:"work",label:"Assign/date or carry forward "+unmanaged.length+" open item"+(unmanaged.length===1?"":"s")});
      return blockers;
    }
    function roleMeta(role) {
      return role === "performance" ? {label:"Performance note",key:"performance_note",author:"performance_author",updated:"performance_updated_at",deleted:"performance_note_deleted_at"} :
        role === "bdm" ? {label:"BDM note",key:"bdm_note",author:"bdm_author",updated:"bdm_updated_at",deleted:"bdm_note_deleted_at"} :
        {label:"BGM note",key:"bgm_note",author:"bgm_author",updated:"bgm_updated_at",deleted:"note_deleted_at"};
    }
    function roleDraftKey(role){return String(S.selected)+":"+role;}
    function composeDraftKey(ceId,kind){return [S.market_slug,S.week_start,String(ceId),String(kind)].join(":");}
    function renderWeeklySummary(weekly,currentDiscussionNumber){
      if(!weekly||!weekly.slack_post_ts)return "";
      var discussionNumber=String(weekly.slack_discussion_number||currentDiscussionNumber||""),discussionLabel=discussionNumber?"Slack discussion #"+discussionNumber:"Current Slack discussion";
      var explicitSummaryBinding=!!(weekly.summary_thread_binding_id||weekly.summary_slack_discussion_number);
      var legacySingleDiscussion=!explicitSummaryBinding&&(!discussionNumber||discussionNumber==="1");
      var summaryBound=legacySingleDiscussion||(String(weekly.summary_thread_binding_id||"")===String(weekly.thread_binding_id||"")&&String(weekly.summary_slack_discussion_number||"")===discussionNumber);
      var approved=summaryBound&&String(weekly.summary_status||"")==="approved",raw=summaryBound?(approved?(weekly.summary_approved_json||weekly.summary_json):(weekly.summary_draft_json||"")):"",summary=null;try{summary=raw?JSON.parse(raw):null;}catch(e){}
      function group(label,rows){return rows&&rows.length?rows.map(function(row){return '<li><strong>'+label+':</strong> '+esc(typeof row==="string"?row:(row.text||row.body||""))+'</li>';}).join(""):"";}
      var delayed=summaryBound&&weekly.sync_status==="summary_delayed",pending=summaryBound&&String(weekly.summary_status)==="pending",rejected=summaryBound&&String(weekly.summary_status)==="rejected",status=!summaryBound?"Summary pending for "+discussionLabel:
        (delayed?"Summary delayed · Slack replies remain available":
        (approved?"Approved by "+(weekly.summary_approved_by||"BGM")+" · "+fmtWhen(weekly.summary_approved_at||weekly.summary_updated_at):(pending?"Draft summary awaiting BGM approval":(rejected?"Draft summary rejected":"Waiting for replies"))));
      if(!summary&&!pending)return '<p class="rv-subtle">No summary yet for '+esc(discussionLabel)+'.</p>';
      if(approved)return '<div class="rv-saved-summary"><div class="rv-source-meta">'+esc(discussionLabel)+(weekly.summary_approved_at||weekly.summary_updated_at?' · Updated '+esc(fmtWhen(weekly.summary_approved_at||weekly.summary_updated_at)):'')+'</div>'+['findings','decisions','open_points'].map(function(k){return (summary[k]||[]).map(function(row){return '<p>'+(k==='open_points'?'<strong>Still unresolved:</strong> ':'')+esc(typeof row==='string'?row:(row.text||row.body||''))+'</p>';}).join('');}).join('')+'</div>';
      var content=summary?'<ul class="rv-summary-bullets">'+(group("Finding",summary.findings)+group("Decision",summary.decisions)+group("Open question",summary.open_points))+'</ul>':"";
      var finding=summary&&summary.findings&&summary.findings.length?(typeof summary.findings[0]==="string"?summary.findings[0]:(summary.findings[0].text||summary.findings[0].body||"")):"";
      return '<div class="rv-summary-surface'+(approved?' approved':'')+'" data-thread-binding-id="'+esc(weekly.thread_binding_id||"")+'" data-slack-discussion-number="'+esc(discussionNumber)+'"><div class="rv-summary-title"><div><span class="rv-origin slack">Slack</span><strong>'+esc(discussionLabel)+' · '+(approved?'Approved summary':(pending?'Draft summary':'Summary pending'))+'</strong></div><span class="rv-attention-chip '+(approved?'approved':'')+'">'+(approved?'Approved':(pending?'Needs BGM approval':'Preparing'))+'</span></div>'+
        '<div class="rv-sync-status'+(delayed?' delayed':'')+'"><span class="rv-live-dot"></span>'+esc(status)+'</div>'+
        (approved?'<div class="rv-summary-principal"><strong>Finding</strong><span>'+esc(finding||"Approved summary available")+'</span></div><details class="rv-summary-details"><summary>View details</summary><div class="rv-summary">'+content+'</div></details>':(content?'<div class="rv-summary">'+content+'</div>':'<div class="rv-summary rv-summary-empty">'+esc(!summaryBound?'This discussion has no summary yet. The previous discussion remains in CE Memory.':'No summary is available yet. Slack replies remain available at source.')+'</div>'))+
        (pending?'<div class="rv-summary-actions"><button class="rv-btn small primary" id="rv-summary-approve" type="button">Save summary to memory</button><button class="rv-link" id="rv-summary-reject" type="button">Dismiss</button></div>':'')+'</div>';
    }
    function writeupEditorKey(ceId){return composeDraftKey(ceId,"writeup-editor");}
    function currentWeekComments(ceId){
      return (S.comments[ceId]||[]).filter(function(c){return !c.deleted_at&&String(c.week_start)===S.week_start;});
    }
    function openWriteup(mode,commentId){
      captureVisibleDrafts();
      var c=currentWeekComments(S.selected).find(function(c){return c.comment_id===commentId;}),key=writeupEditorKey(S.selected);
      S.writeupEditors[key]={mode:mode,comment:c?Object.assign({},c):null,previousDraft:S.slackDrafts[S.selected]||""};
      S.slackDrafts[S.selected]=c?c.body:(S.slackDrafts[S.selected]||"");
      var box=root.querySelector("#rv-slack-message");if(box)box.value=S.slackDrafts[S.selected];
      S.mentionPreview=null;render();box=root.querySelector("#rv-slack-message");if(box)box.focus();
    }
    function closeWriteup(ceId){
      var key=writeupEditorKey(ceId),editor=S.writeupEditors[key];
      S.slackDrafts[ceId]=editor?editor.previousDraft||"":"";delete S.writeupEditors[key];
      if(String(S.selected)===String(ceId)){var box=root.querySelector("#rv-slack-message");if(box)box.value=S.slackDrafts[ceId];}
      S.mentionPreview=null;
    }
    function renderWriteup(q,busy,loaded,summaryBusy,operation){
      var notes=currentWeekComments(q.ce_id),editor=S.writeupEditors[writeupEditorKey(q.ce_id)],editing=editor&&editor.mode==='edit',replying=editor&&editor.mode==='reply';
      var compose=!!editor||!notes.length||!!S.slackDrafts[q.ce_id];
      var cards=notes.filter(function(c){return !editing||!editor.comment||c.comment_id!==editor.comment.comment_id;}).map(function(c){
        return '<article class="rv-saved-note" data-saved-note="'+esc(c.comment_id)+'"><div class="rv-note-content"><div class="rv-source-meta">'+esc(c.source_author||c.author_name||'Reviewer')+' · '+esc(fmtWhen(c.updated_at||c.created_at))+(c.updated_at&&c.created_at!==c.updated_at?' · Edited':'')+'</div><p>'+esc(c.body)+'</p>'+(c.source_url?'<a class="rv-source-link" href="'+esc(c.source_url)+'" target="_blank" rel="noopener">'+(c.source_type==='slack'?'View in Slack':'View source')+' ↗</a>':'')+'</div><div class="rv-note-actions">'+(c.source_type==='manual'?'<button class="rv-link" type="button" data-edit-writeup="'+esc(c.comment_id)+'"'+(busy||editor?' disabled':'')+'>Edit</button>':'')+'<button class="rv-link rv-note-discuss" type="button" data-discuss-writeup="'+esc(c.comment_id)+'"'+(busy||editor?' disabled':'')+'>Discuss in Slack</button></div></article>';
      }).join('');
      var warning=(S.resourceErrors[q.ce_id]||{}).comments?'<p class="rv-subtle" role="status">Saved notes could not load. <button class="rv-link" id="rv-retry-notes" type="button">Retry</button></p>':'';
      if(!compose)return '<div class="rv-field-label">This week’s notes</div>'+warning+cards+'<button class="rv-btn rv-new-writeup" id="rv-new-writeup" type="button"'+(busy?' disabled':'')+'><span aria-hidden="true">＋</span> Add a note or reply</button>';
      return (cards?'<div class="rv-field-label">This week’s notes</div>'+cards:'')+warning+'<label class="rv-field-label" for="rv-slack-message">'+(editing?'Edit note':replying?'Slack message':'Your writeup')+'</label><textarea id="rv-slack-message"'+(busy?' disabled':'')+' placeholder="What did you notice? Write a note or @mention someone to discuss it in Slack.">'+esc(S.slackDrafts[String(q.ce_id)]||'')+'</textarea><div class="rv-composer-actions">'+(editor?'<button class="rv-btn" id="rv-cancel-writeup" type="button"'+(busy?' disabled':'')+'>Cancel</button>':'')+(!replying?'<button class="rv-btn" id="rv-save-writeup" type="button"'+(busy?' disabled':'')+'>'+(S.asyncBusy['note:'+q.ce_id]?'Saving…':editing?'Save changes':'Save note')+'</button>':'')+(!editing?'<div class="rv-slack-send">'+renderSendDestination(q,loaded,busy,operation)+'<button class="rv-btn primary" id="rv-send-writeup" type="button"'+(!loaded||busy||summaryBusy?' disabled':'')+'>'+(S.asyncBusy['send:'+q.ce_id]?'Sending…':operation==='continue'?'Reply in Slack':'Start Slack thread')+'</button></div>':'')+'</div>';
    }
    function renderSendDestination(q,loaded,busy,operation){
      var registry=S.threadRegistry[q.ce_id]||{},hasThread=!!registry.active,activeNumber=String((registry.threads||[]).length||1);
      if(!loaded)return '<span class="rv-subtle">'+(S.threadRegistryError[q.ce_id]?'Slack unavailable':'Finding CE thread…')+'</span>'+(S.threadRegistryError[q.ce_id]?'<button class="rv-link" id="rv-retry-threads" type="button">Retry</button>':'');
      return '<label class="rv-thread-select">Send to<select id="rv-thread-choice" aria-label="Slack thread"'+(busy?' disabled':'')+'>'+(hasThread?'<option value="continue"'+(operation==='continue'?' selected':'')+'>Continue discussion #'+esc(activeNumber)+'</option>':'')+'<option value="new_parent"'+(operation==='new_parent'?' selected':'')+'>Start a new thread</option></select></label>'+(operation==='new_parent'?'<span class="rv-send-hint">Creates a new Slack thread when you send.</span>':'');
    }
    function renderCommentaryCard(q){
      var weekly=S.weekly[q.ce_id]||{}, registry=S.threadRegistry[q.ce_id]||{}, binding=registry.active||null, loaded=!!S.threadRegistryLoaded[q.ce_id];
      var weeklyError=(S.resourceErrors[q.ce_id]||{}).notes,weeklyLoading=!Object.prototype.hasOwnProperty.call(S.weekly,q.ce_id)&&!weeklyError;
      var weeklyStatus=weeklyError?'<p class="rv-subtle" role="status">Saved discussion could not load. Existing notes and summaries have not been removed. <button class="rv-link" id="rv-retry-discussion" type="button">Retry discussion</button></p>':weeklyLoading?'<p class="rv-subtle" role="status">Loading saved discussion…</p>':'';
      var hasThread=!!binding, operation=S.threadOperation==="new_parent"?"new_parent":(hasThread?"continue":"new_parent");
      var summaryBinding=summaryThreadFor(weekly,registry),number=String(weekly.slack_discussion_number||(summaryBinding?(registry.threads||[]).length-(registry.threads||[]).findIndex(function(t){return t.binding_id===summaryBinding.binding_id;}):""));
      var busy=!!(S.asyncBusy["send:"+q.ce_id]||S.asyncBusy["note:"+q.ce_id]),summaryBusy=!!S.asyncBusy["summary:"+q.ce_id],status=S.auditStatus[q.ce_id]||"";
      // The grouped discussion link follows the displayed week's summary,
      // independently of the active thread selected for the next message.
      var url=weekly.slack_post_permalink||(summaryBinding&&summaryBinding.slack_permalink)||(!weekly.slack_post_ts&&binding?binding.slack_permalink:"");
      var discussion=hasThread||weekly.slack_post_ts||weeklyError||weeklyLoading?'<section class="rv-discussion-group" aria-label="Slack discussion"><div class="rv-discussion-heading"><h3>Slack discussion</h3>'+(url?'<a class="rv-source-link" href="'+esc(url)+'" target="_blank" rel="noopener">Open in Slack ↗</a>':'')+'</div>'+weeklyStatus+'<div class="rv-discussion-tools"><button class="rv-btn small" id="rv-sync-thread" type="button"'+(summaryBusy||busy||weeklyError||weeklyLoading?' disabled':'')+'>'+(summaryBusy?'Summarizing…':'Summarize discussion')+'</button></div>'+renderWeeklySummary(weekly,number)+'</section>':'';
      return '<section id="rv-discussion-section" class="rv-flow-section">'+renderWriteup(q,busy,loaded,summaryBusy,operation)+renderMentionPreview()+(status?'<p class="rv-audit-status" role="status">'+esc(status)+'</p>':'')+discussion+'</section>';
    }

    function normalizedSuggestionBody(s) {
      return String((s && s.body) || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim().replace(/\s+/g, " ");
    }
    function dedupeSuggestions(rows) {
      var seen = {}, out = [];
      rows.forEach(function (s) {
        var key = String(s.kind || "action") + "|" + normalizedSuggestionBody(s);
        if (!normalizedSuggestionBody(s)) key += "|" + String(s.suggestion_id || s.source_ref || "");
        if (seen[key]) {
          seen[key]._trace = seen[key]._trace || [];
          seen[key]._trace.push({ suggestion_id:s.suggestion_id || "", source_ref:s.source_ref || "", source_type:s.source_type || "" });
          return;
        }
        var copy = Object.assign({}, s);
        copy._trace = [{ suggestion_id:s.suggestion_id || "", source_ref:s.source_ref || "", source_type:s.source_type || "" }];
        seen[key] = copy; out.push(copy);
      });
      return out;
    }

    function renderMentionPreview() {
      var preview=S.mentionPreview;if(!preview)return "";
      var matches=preview.matches||[],ambiguous=preview.ambiguous||[];
      return '<div class="rv-mention-status" aria-live="polite">'+matches.map(function(m){return '<span class="rv-person-chip">@'+esc(m.name||m.slack_user_id)+'</span>';}).join("")+ambiguous.map(function(a){return '<span>Use a full Slack name for @'+esc(a.name)+': '+esc((a.candidates||[]).map(function(c){return c.name;}).join(", "))+'</span>';}).join("")+'</div>';
    }
    function resolveWriteupMentions(text){
      clearTimeout(S.mentionTimer);S.mentionPreview=null;
      if(!api||text.indexOf("@")<0)return;
      var ceId=S.selected,market=S.market_slug;
      S.mentionTimer=setTimeout(function(){api.resolveMentions(ident(ceId),text).then(function(res){if(S.selected!==ceId||S.market_slug!==market||S.slackDrafts[ceId]!==text)return;S.mentionPreview=res;render();}).catch(function(){});},450);
    }
    function renderActionsCard(q) {
      var sugg = (S.suggestions[q.ce_id] || []).filter(function (s) { return s.confidence!=="source_exact" && (s.kind === "action" || s.kind === "check" || s.kind === "comment" || !s.kind); });
      var pending = dedupeSuggestions(sugg.filter(function (s) { return !s.decided_at && (s.status || "pending") === "pending"; }));
      var allWork = workFor(q.ce_id),openAll=allWork.filter(function(w){return CLOSED.indexOf(w.status)<0&&!w.archived_at;}),doneAll=allWork.filter(function(w){return CLOSED.indexOf(w.status)>=0&&!w.archived_at;});
      var laterItems=[],openItems=openAll,visibleSuggestions=S.showAllSuggestions?pending:pending.slice(0,3);
      var nextCheck=laterItems.filter(function(w){return w.due_date||w.next_review_date;}).sort(function(a,b){return String(a.due_date||a.next_review_date).localeCompare(String(b.due_date||b.next_review_date));})[0];
      var focus=[pending.length?pending.length+" suggestion"+(pending.length===1?"":"s")+" need review":"No suggestions waiting",openItems.length?openItems.length+" open action"+(openItems.length===1?"":"s"):"no open actions",nextCheck?"next check "+fmtDue(nextCheck.due_date||nextCheck.next_review_date):(laterItems.length?laterItems.length+" item"+(laterItems.length===1?"":"s")+" for later":"nothing scheduled")].join(" · ")+".";
      var suggHtml = visibleSuggestions.map(function (s) {
        var isCheck = s.kind === "check", isComment = s.kind === "comment" || !s.kind, expanded = String(S.expandedSuggestion) === String(s.suggestion_id), trace = s._trace || [];
        var owner=s.proposed_owner||"",due=s.proposed_due_date||"",needsFields=!isComment&&((!isCheck&&!owner)|| (isCheck&&!due));
        var sourceLine=(isComment?'Observation':(isCheck?'Check':'Action'))+' suggested from '+sourceName(s)+(s.created_at?' · '+fmtWhen(s.created_at):'')+(trace.length>1?' · '+trace.length+' matching sources':'');
        var proposal=[owner?'Owner '+owner:'',due?(isCheck?'Next check ':'Due ')+fmtDue(due):''].filter(Boolean).join(' · ');
        return '<div class="rv-sugg" data-suggestion="' + esc(s.suggestion_id) + '" data-duplicate-ids="'+esc(trace.slice(1).map(function(t){return t.suggestion_id;}).filter(Boolean).join(','))+'" data-kind="' + esc(isComment?"comment":s.kind) + '" data-body="'+esc(s.body||'')+'" data-owner="'+esc(owner)+'" data-due="'+esc(due)+'">' +
          '<div class="rv-suggestion-main"><div class="rv-sugg-meta">'+esc(sourceLine)+'</div><div class="rv-suggestion-text">'+esc(s.body||'Untitled suggestion')+'</div>'+(proposal?'<div class="rv-suggestion-proposal">'+esc(proposal)+'</div>':'')+'</div>'+
          '<div class="rv-inline-actions"><button class="rv-btn small primary" type="button" data-sugg-accept>'+(isComment?'Approve observation':(isCheck?'Approve check':'Approve action'))+'</button><button class="rv-btn small" type="button" data-sugg-edit="'+esc(s.suggestion_id)+'" aria-expanded="'+(expanded?'true':'false')+'">Edit</button><button class="rv-link" type="button" data-sugg-ignore>Dismiss</button></div>'+
          (expanded?'<div class="rv-sugg-detail"><textarea class="rv-sugg-edit" data-sugg-body aria-label="Edit suggested ' + (isComment ? "observation" : (isCheck ? "check" : "action")) + '">' + esc(s.body || "") + "</textarea>" +
          (isComment?'':'<div class="rv-work-controls" style="display:grid;grid-template-columns:1fr 1fr auto;gap:8px;margin-bottom:10px">' +
          '<input type="text" data-w-owner placeholder="' + (isCheck ? "Owner (optional)" : "Owner") + '" value="' + esc(owner) + '" style="min-height:38px;padding:8px 10px;border:1px solid var(--rv-g400);border-radius:10px">' +
          '<input type="date" data-w-due value="' + esc(due) + '" style="min-height:38px;padding:8px 10px;border:1px solid var(--rv-g400);border-radius:10px">' +
          '<select data-w-status class="rv-select">' + optionList(isCheck ? CHECK_STATUS : WORK_STATUS, isCheck ? "scheduled" : "needs_action") + "</select></div>") +
          '<div class="rv-sugg-actions"><button class="rv-btn small primary" type="button" data-sugg-accept>'+(needsFields?'Complete &amp; approve':'Save &amp; approve')+'</button><button class="rv-btn small" type="button" data-sugg-edit="">Cancel</button></div><details class="rv-trace"><summary>Source details</summary><ul>'+trace.map(function(t){return '<li>'+esc(sourceName(t))+' · '+esc(t.source_ref||'source reference unavailable')+' · '+esc(t.suggestion_id||'suggestion ID unavailable')+'</li>';}).join('')+'</ul></details></div>':'')+'</div>';
      }).join("");
      var openHtml = openItems.map(workRow).join("");
      var laterHtml=laterItems.map(workRow).join("");
      var doneHtml = doneAll.length ? '<details class="rv-done"><summary>Completed · ' + doneAll.length + "</summary>" +
        '<div class="rv-done-list">' + doneAll.map(workRow).join("") + "</div></details>" : "";

      var composer = S.compose ? renderCompose(S.compose) : "";
      var count = openAll.length ? openAll.length + " active" : (pending.length ? pending.length+" suggested" : (allWork.length ? "All done" : "No open actions"));
      var tabs=[['needs','Needs review',pending.length],['open','Open',openItems.length],['completed','Completed',doneAll.length]];
      if((S.resourceErrors[q.ce_id]||{}).suggestions){count='Suggestions unavailable';tabs[0][2]='—';}
      if(S.workError){count='Actions unavailable';tabs[1][2]='—';tabs[2][2]='—';}
      var active=S.workTab||'needs',panel=active==='needs'?(suggHtml+(pending.length>3?'<button class="rv-link rv-see-more" type="button" id="rv-more-suggestions">'+(S.showAllSuggestions?'Show fewer':'See '+(pending.length-3)+' more')+'</button>':'')):active==='open'?(openHtml||'<div class="rv-empty-state"><strong>No open work</strong><span>Approved actions will appear here.</span></div>'):active==='later'?(laterHtml||'<div class="rv-empty-state"><strong>Nothing scheduled</strong><span>Checks and explicit carry-forward items will appear here.</span></div>'):(doneHtml||'<div class="rv-empty-state"><strong>No completed work</strong><span>Recent completed items will appear here.</span></div>');
      if(S.workError)panel='<p role="status" class="rv-audit-status">Could not load actions. Existing work has not been removed. '+esc(S.workError)+'</p><button class="rv-btn" type="button" id="rv-retry-work"'+(S.workLoading?' disabled':'')+'>'+(S.workLoading?'Retrying actions…':'Retry actions')+'</button>'+openHtml;
      else if(S.workLoading&&!allWork.length)panel='<p role="status" class="rv-subtle">Loading open work…</p>';
      if((S.resourceErrors[q.ce_id]||{}).suggestions)panel='<p class="rv-subtle">Suggested actions could not load. <button class="rv-link" type="button" id="rv-retry-threads">Retry</button></p>'+panel;
      return '<section class="rv-flow-section rv-actions-module" id="rv-actions-section"><div class="rv-module-head"><span class="rv-module-icon attention" aria-hidden="true">✓</span><div class="rv-card-headings"><div class="rv-card-title">Actions</div><div class="rv-card-sub">Open work across all weeks.</div></div><span class="rv-card-count">'+count+'</span></div>' +
        '<div class="rv-source-bridge"><span aria-hidden="true">↓</span><strong>'+pending.length+' follow-up'+(pending.length===1?'':'s')+' suggested from '+esc((S.weekly[q.ce_id]||{}).slack_discussion_number?'Slack discussion #'+(S.weekly[q.ce_id]||{}).slack_discussion_number:'the active Slack discussion')+'</strong></div><div class="rv-action-surface"><p class="rv-focus-summary">'+esc(focus)+'</p><div class="rv-action-tabs" role="tablist">'+tabs.map(function(t){return '<button type="button" role="tab" class="rv-action-tab'+(active===t[0]?' active':'')+'" aria-selected="'+(active===t[0]?'true':'false')+'" data-work-tab="'+t[0]+'">'+t[1]+' <span>'+t[2]+'</span></button>';}).join('')+'</div><div class="rv-action-panel">'+panel+'</div>' +
        '<div class="rv-add-row"><button class="rv-btn ghost small" type="button" id="rv-add-action">＋ Add action</button></div>'+composer+'</div></section>';
    }
    function workRow(w) {
      var done = CLOSED.indexOf(w.status) >= 0, isCheck = w.kind === "check";
      var src = w.source_type === "granola" ? "Meeting" : w.source_type === "slack" ? "Slack" : w.source_type === "bgm_manual" ? "Manual" : (w.source_type || "");
      var srcLink = w.source_url ? '<a href="' + esc(w.source_url) + '" target="_blank" rel="noopener">' + esc(src || "source") + " ↗</a>" : esc(src);
      var meta = [w.owner ? esc(w.owner) : (isCheck ? "" : "no owner"), w.due_date ? (isCheck ? "returns " : "due ") + esc(fmtDue(w.due_date)) : "", srcLink].filter(Boolean).join(" · ");
      var unmanaged=!done&&!w._pending&&!(String(w.carry_forward)==="true"||(w.owner&&(w.due_date||w.next_review_date))||(isCheck&&(w.due_date||w.next_review_date)));
      var left = isCheck && w.due_date
        ? '<span class="rv-datebadge"><span class="m">' + MONTHS[(parseDate(w.due_date) || new Date()).getUTCMonth()] + '</span><span class="d">' + (parseDate(w.due_date) || new Date()).getUTCDate() + "</span></span>"
        : '<button class="rv-check' + (done ? " on" : "") + '" type="button" data-work-toggle="' + esc(w.work_id) + '" title="' + (done ? "Reopen" : "Mark complete") + '">' + (done ? "✓" : "") + "</button>";
      var right = w.owner ? avatar(w.owner, "sm") : '<span class="rv-av sm none">–</span>';
      if (String(S.editingWork || "") === String(w.work_id)) return renderWorkEdit(w);
      return '<div class="rv-work' + (done ? " done" : "") + (w._pending ? " pending" : "") + '" data-work="' + esc(w.work_id) + '" data-pending="'+(w._pending?"true":"false")+'">' + left +
        '<div class="rv-work-main">' + (w._pending?'<div class="rv-work-kicker">Saving…</div>':(isCheck ? '<div class="rv-work-kicker">Next review check</div>' : "")) +
        '<div class="rv-work-title">' + esc(w.text) + "</div>" +
        '<div class="rv-work-meta">' + meta + "</div>" +
        '<div class="rv-work-status"><select class="rv-select" data-work-status="' + esc(w.work_id) + '">' + optionList(isCheck ? CHECK_STATUS : WORK_STATUS, w.status) + "</select>" +
        (String(S.confirmDeleteWork || "") === String(w.work_id)
          ? '<span class="rv-delete-confirm">Remove this item?<button class="rv-link danger" type="button" data-work-delete-confirm="' + esc(w.work_id) + '">Delete</button><button class="rv-link" type="button" data-work-delete-cancel>Cancel</button></span>'
          : '<button class="rv-link" type="button" data-work-edit="' + esc(w.work_id) + '">Edit</button><button class="rv-link danger" type="button" data-work-delete="' + esc(w.work_id) + '">Delete</button>') + "</div>" +
        "</div>" + right + "</div>";
    }
    function renderWorkEdit(w) {
      var isCheck = w.kind === "check";
      return '<div class="rv-work rv-work-edit" data-work="' + esc(w.work_id) + '"><div class="rv-work-main">' +
        '<div class="rv-work-kicker">Edit ' + (isCheck ? "scheduled check" : "action") + "</div>" +
        '<input type="text" data-edit-text value="' + esc(w.text || "") + '" aria-label="Work item">' +
        '<div class="rv-work-edit-grid"><input type="text" data-edit-owner value="' + esc(w.owner || "") + '" placeholder="Owner' + (isCheck ? " (optional)" : "") + '">' +
        '<input type="date" data-edit-due value="' + esc(w.due_date || "") + '">' +
        '<select class="rv-select" data-edit-status>' + optionList(isCheck ? CHECK_STATUS : WORK_STATUS, w.status) + "</select></div>" +
        '<div class="rv-work-edit-actions"><button class="rv-btn small" type="button" data-work-edit-cancel>Cancel</button>' +
        '<button class="rv-btn small primary" type="button" data-work-edit-save="' + esc(w.work_id) + '">Save changes</button></div></div></div>';
    }
    function renderCompose(kind) {
      var isCheck = kind === "check",draft=S.composeDrafts[composeDraftKey(S.selected,kind)]||{},defaultStatus=isCheck?"scheduled":"needs_action";
      return '<div class="rv-compose" style="display:block"><div class="row1"><input type="text" id="rv-c-text" value="'+esc(draft.text||'')+'" placeholder="' + (isCheck ? "What should we revisit next week?" : "What needs to happen?") + '"></div>' +
        '<div class="row2"><input type="text" id="rv-c-owner" value="'+esc(draft.owner||'')+'" placeholder="' + (isCheck ? "Owner (optional)" : "Owner") + '">' +
        '<input type="date" id="rv-c-due" value="'+esc(draft.due||'')+'">' +
        '<select class="rv-select" id="rv-c-status">' + optionList(isCheck ? CHECK_STATUS : WORK_STATUS, draft.status||defaultStatus) + "</select></div>" +
        '<div class="foot"><button class="rv-btn small" type="button" id="rv-c-cancel">Cancel</button>' +
        '<button class="rv-btn small primary" type="button" id="rv-c-save">' + (isCheck ? "Schedule check" : "Create action") + "</button></div></div>";
    }
    function renderMemoryRail(q){
      var key=S.market_slug+"|"+S.week_start+"|"+q.ce_id,memory=S.memoryCache[key],errors=(memory||{}).historical_source_status||{};
      var rows=ceMemoryEntries(memory,{comments:S.comments[q.ce_id],weekly:S.weeklyHist[q.ce_id],work:S.workError||!S.workLoaded?undefined:(S.work[q.ce_id]||[])});
      var visibleNotes=currentWeekComments(q.ce_id).map(function(c){return 'comment:'+c.comment_id;}),activeWeekly=S.weekly[q.ce_id]||{};
      var summaryInline=renderCommentaryCard(q).indexOf('class="rv-saved-summary"')>=0;
      // Suppress only the summary actually rendered inline. A saved summary
      // with a missing or changed discussion binding must remain in memory.
      // Other current-week context (including earlier discussions) stays accessible.
      rows=rows.filter(function(r){return String(r.week)!==S.week_start||(visibleNotes.indexOf(r.id)<0&&(!summaryInline||r.id!=='summary:'+activeWeekly.weekly_id)&&!r.workId);});
      function card(r){
        var sections=(r.sections||[]).map(function(s){return '<strong>'+esc(s.label)+'</strong><ul>'+s.points.map(function(p){return '<li>'+esc(p)+'</li>';}).join('')+'</ul>';}).join('');
        var meta=[r.author,r.week?'w/c '+r.week:'',r.date?fmtWhen(r.date)||r.date:'',r.source,r.duplicate_count>1?r.duplicate_count+' identical source rows':'' ].filter(Boolean).map(esc).join(' · ');
        var status=[r.status?String(r.status).replace(/_/g,' '):'',r.due?'Due '+fmtDue(r.due):'',r.bucket].filter(Boolean).map(esc).join(' · ');
        return '<article class="rv-memory-entry"><strong>'+esc(r.label)+'</strong><div class="rv-source-meta">'+meta+'</div>'+(status?'<div class="rv-memory-status">'+status+'</div>':'')+(r.body?'<p>'+esc(r.body)+'</p>':'')+sections+(r.evidence?'<p><strong>Completion evidence:</strong> '+esc(r.evidence)+'</p>':'')+(r.outcome?'<p><strong>Outcome:</strong> '+esc(r.outcome)+'</p>':'')+(r.relatedWork||[]).filter(function(w){return findWork(w.id)&&!findWork(w.id).archived_at;}).map(function(w){return '<p><button class="rv-link" type="button" data-memory-work="'+esc(w.id)+'">Action: '+esc(w.text)+' →</button></p>';}).join('')+(r.url?'<a class="rv-source-link" href="'+esc(r.url)+'" target="_blank" rel="noopener">Open source ↗</a>':'')+(r.workId&&findWork(r.workId)&&!findWork(r.workId).archived_at?' <button class="rv-link" type="button" data-memory-work="'+esc(r.workId)+'">View action →</button>':'')+'</article>';
      }
      var threads=(S.threadRegistry[q.ce_id]||{}).threads||(memory||{}).slack_threads||[],allWeeks=ceMemoryWeeks(rows,threads),weeks=allWeeks.filter(function(w){return w.week!==S.week_start;});
      var currentContext=allWeeks.filter(function(w){return w.week===S.week_start&&w.sources.some(function(r){return r.label!=='Slack discussion';});});
      function disclosure(key,defaultOpen){var saved=(S.memoryDisclosures||{})[S.market_slug+'|'+q.ce_id+'|'+key];return saved===undefined?defaultOpen:!!saved;}
      function weekCard(w,index){
        var key='week:'+w.week,title=w.week==='undated'?'Week unavailable':'Week of '+fmtDue(w.week);
        if(w.week!=='undated')title+=' '+w.week.slice(0,4);
        function sourceNumber(id){return w.sources.findIndex(function(r){return r.id===id;})+1;}
        var prose=w.paragraphs.map(function(p){var perf=w.sources.filter(function(r){return p.sourceIds.indexOf(r.id)>=0&&r.label==='Performance action';});var perfMeta=perf.map(function(r){return '<div class="rv-memory-perf-meta">'+['Performance history',r.author,r.status?'Recorded status: '+String(r.status).replace(/_/g,' '):'',r.date?'Updated '+(fmtWhen(r.date)||r.date):''].filter(Boolean).map(esc).join(' · ')+(r.outcome?'<p>Recorded outcome: '+esc(r.outcome)+'</p>':'')+'</div>';}).join('');return '<div class="rv-memory-passage"><p>'+esc(p.text||(perf.length?'No action description recorded.':''))+' <button type="button" class="rv-memory-citation" data-memory-source="'+esc(w.week)+'" aria-label="Show original sources for '+esc(title)+'">'+p.sourceIds.map(function(id){return '['+sourceNumber(id)+']';}).join(' ')+'</button></p>'+perfMeta+'</div>';}).join('');
        var work=w.work.length?'<div class="rv-memory-followthrough"><strong>Follow-through</strong>'+w.work.map(function(r){return '<div class="rv-memory-work-ref">'+(findWork(r.workId)&&!findWork(r.workId).archived_at?'<button class="rv-link" type="button" data-memory-work="'+esc(r.workId)+'">'+esc(r.body)+' →</button>':'<span>'+esc(r.body)+'</span>')+'<div class="rv-source-meta">'+[r.author,r.status?String(r.status).replace(/_/g,' '):'',r.due?'Due '+fmtDue(r.due):''].filter(Boolean).map(esc).join(' · ')+'</div>'+(r.evidence?'<p>'+esc(r.evidence)+'</p>':'')+(r.outcome?'<p>'+esc(r.outcome)+'</p>':'')+'</div>';}).join('')+'</div>':'';
        var sourceKey='sources:'+w.week;
        return '<details class="rv-memory-week" data-memory-details="'+esc(key)+'"'+(disclosure(key,index===0)?' open':'')+'><summary><strong>'+esc(title)+'</strong></summary><div class="rv-memory-week-body"><div class="rv-memory-account">'+prose+'</div>'+work+'<details class="rv-memory-originals" data-memory-details="'+esc(sourceKey)+'" data-memory-source-week="'+esc(w.week)+'"'+(disclosure(sourceKey,false)?' open':'')+'><summary>Sources · '+w.sources.length+'</summary>'+w.sources.map(function(r,i){return '<div class="rv-memory-original"><span class="rv-source-meta">['+(i+1)+']</span>'+card(r)+'</div>';}).join('')+'</details></div></details>';
      }
      var warning=(!memory?'Loading CE history…':memory.error?'History could not refresh. Previously loaded records remain below.':'');
      if((errors.comments||{}).unavailable)warning+=' Earlier comments source is unavailable.';
      if((errors.actions||{}).unavailable)warning+=' Performance history source is unavailable.';
      return currentContext.map(weekCard).join('')+'<details class="rv-flow-section rv-memory-shell" data-memory-details="memory"'+(disclosure('memory',false)?' open':'')+'><summary><h3>CE memory</h3></summary><div class="rv-memory-shell-body"><div class="rv-summary-heading"><span>Other weeks</span><button class="rv-link" id="rv-memory-refresh" type="button">Refresh</button></div>'+(warning?'<p role="status" class="rv-subtle">'+esc(warning)+'</p>':'')+weeks.map(weekCard).join('')+(!weeks.length&&!warning?'<p class="rv-subtle">No earlier CE history recorded yet.</p>':'')+'</div></details>';
    }

    function renderMeetingInput(){return '<section class="rv-meeting-input"><div class="rv-summary-heading"><strong>Weekly meeting notes</strong><button class="rv-link" id="rv-process-cancel" type="button">Close</button></div><label class="rv-field-label" for="rv-process-text">Paste the meeting transcript</label><textarea id="rv-process-text" placeholder="Paste meeting notes or transcript">'+esc(S.meetingDraft||"")+'</textarea><button class="rv-btn primary" id="rv-process-run" type="button"'+(S.meetingBusy?' disabled':'')+'>'+(S.meetingBusy?'Extracting…':'Find CE summaries &amp; actions')+'</button>'+(S.processSummary?'<p role="status">'+esc(S.processSummary)+'</p>':'')+(S.meetingUnmatched||[]).map(function(item){return '<blockquote>'+esc(item.body)+'</blockquote>';}).join('')+(S.meetingResults||[]).filter(function(c){return (c.suggestions||[]).length;}).map(function(c){return '<button class="rv-btn small" type="button" data-meeting-ce="'+esc(c.ce_id)+'">'+esc(c.ce_name)+' · '+(c.suggestions||[]).length+' to review →</button>';}).join('')+'</section>';}
    function sameReport(id){return S.market_slug===id.market_slug&&S.week_start===(id.week_start||id.week);}
    function saveWriteup(){
      if(!api||!ensureAuthor())return;
      var id=ident(S.selected),key="note:"+id.ce_id,text=(root.querySelector("#rv-slack-message")||{}).value||"";
      if(!text.trim()||S.asyncBusy[key])return;
      captureVisibleDrafts();
      var editor=S.writeupEditors[writeupEditorKey(id.ce_id)],existing=editor&&editor.mode==='edit'&&editor.comment;
      var draftKey=composeDraftKey(id.ce_id,"note:"+(existing?existing.comment_id+":":"")+text),request=S.sendRequests[draftKey]||(S.sendRequests[draftKey]="note_"+Date.now()+"_"+hash(draftKey));
      S.asyncBusy[key]=true;S.auditStatus[id.ce_id]="Saving note…";render();
      function progress(message){
        if(!sameReport(id)||!S.asyncBusy[key])return;
        S.auditStatus[id.ce_id]=message;
        if(String(S.selected)===String(id.ce_id)){var status=root.querySelector("#rv-discussion-section .rv-audit-status");if(status)status.textContent=message;}
      }
      var slowTimer=setTimeout(function(){progress("Still saving your note… Your text is kept here. Please don’t submit it again.");},8000);
      var payload=Object.assign({},id,{source_ref:request,body:text,author_name:author(),source_type:"manual"});
      if(existing)payload=Object.assign({},id,{comment_id:existing.comment_id,body:text,author_name:author(),expected_updated_at:existing.updated_at||existing.created_at||""});
      api.saveComment(payload,function(message){clearTimeout(slowTimer);progress(message);}).then(function(res){
        if(!sameReport(id))return;
        var c=res.comment;
        if(!c||!c.comment_id)throw new Error("Could not confirm the save. Your writeup is preserved.");
        S.commentVersions=S.commentVersions||{};S.commentVersions[id.ce_id]=(S.commentVersions[id.ce_id]||0)+1;
        S.comments[id.ce_id]=[c].concat((S.comments[id.ce_id]||[]).filter(function(x){return x.comment_id!==c.comment_id;}));
        closeWriteup(id.ce_id);delete S.sendRequests[draftKey];S.auditStatus[id.ce_id]=existing?"Note updated.":"Note saved.";
      }).catch(function(error){if(!sameReport(id))return;S.auditStatus[id.ce_id]=error.message||"Could not save. Your writeup is preserved.";}).finally(function(){clearTimeout(slowTimer);delete S.asyncBusy[key];if(sameReport(id)&&S.selected===id.ce_id){var box=root.querySelector("#rv-slack-message");if(box)box.value=S.slackDrafts[id.ce_id]||"";render();}});
    }
    function sendWriteup(){
      if(!api||!ensureAuthor()||!S.threadRegistryLoaded[S.selected])return;
      captureVisibleDrafts();var id=ident(S.selected),text=String(S.slackDrafts[id.ce_id]||"").trim(),key="send:"+id.ce_id;
      if(!text||S.asyncBusy[key])return;
      var binding=(S.threadRegistry[id.ce_id]||{}).active,op=S.threadOperation==="new_parent"||!binding?"new_parent":"continue";
      var requestKey=composeDraftKey(id.ce_id,[op,binding&&binding.binding_id||"",text].join(":"));
      var requestId=S.sendRequests[requestKey]||(S.sendRequests[requestKey]="audit_"+Date.now()+"_"+hash(requestKey));
      S.asyncBusy[key]=true;S.auditStatus[id.ce_id]="Sending to Slack…";render();
      api.startSlackDiscussion(Object.assign({},id,{channel:S.channel&&S.channel.id,discussion_text:text,discussion_author:author(),request_id:requestId,report_url:location.href,thread_operation:op,replacement_reason:op==="new_parent"?text.slice(0,180):""})).then(function(res){
        if(!sameReport(id))return;
        S.weekly[id.ce_id]=res.weekly;if(res.thread){var old=(S.threadRegistry[id.ce_id]||{}).threads||[];S.threadRegistry[id.ce_id]={active:res.thread,threads:[res.thread].concat(old.filter(function(t){return t.binding_id!==res.thread.binding_id;}))};}
        closeWriteup(id.ce_id);delete S.sendRequests[requestKey];delete S.threadOperationByCe[id.ce_id];if(S.selected===id.ce_id)S.threadOperation="";
        S.auditStatus[id.ce_id]=op==="continue"?"Reply sent to Slack.":"New Slack thread created. Previous discussions stay in CE memory.";
      }).catch(function(error){if(!sameReport(id))return;S.auditStatus[id.ce_id]=(error.message||"Send failed")+" Your writeup is preserved; retry uses the same request.";}).finally(function(){delete S.asyncBusy[key];if(sameReport(id)&&S.selected===id.ce_id){var box=root.querySelector("#rv-slack-message");if(box)box.value=S.slackDrafts[id.ce_id]||"";render();}});
    }

    function bind(sel, fn) { var el = root.querySelector(sel); if (el) el.onclick = fn; }
    function wirePickerResults() {
      root.querySelectorAll("[data-pick-ce]").forEach(function (b) { b.onclick = function () { addCe(b.dataset.pickCe); }; });
    }
    function wire() {
      bind("#rv-retry-work",reloadWork);
      bind("#rv-audit-queue",function(){S.queueOpen=!S.queueOpen;render();var input=root.querySelector("#rv-search-ce");if(input)input.focus();});
      root.onkeydown=function(e){if(e.key==="Escape"&&S.queueOpen){e.preventDefault();S.queueOpen=false;render();root.querySelector("#rv-audit-queue").focus();}};
      var overlay=root.querySelector(".rv-queue-overlay");if(overlay){
        overlay.onclick=function(e){if(e.target===overlay){S.queueOpen=false;render();root.querySelector("#rv-audit-queue").focus();}};
        overlay.onkeydown=function(e){if(e.key!=="Tab")return;var items=Array.from(overlay.querySelectorAll("button,input,select,a[href]")).filter(function(el){return !el.disabled&&el.offsetParent!==null;});if(!items.length)return;var first=items[0],last=items[items.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}};
      }
      bind("#rv-meeting",function(){S.processing=!S.processing;render();});
      bind("#rv-save-writeup",saveWriteup);bind("#rv-send-writeup",sendWriteup);
      bind("#rv-new-writeup",function(){openWriteup('new');});
      bind("#rv-cancel-writeup",function(){closeWriteup(S.selected);render();});
      bind("#rv-retry-notes",function(){loadCe(S.selected,true);});
      bind("#rv-retry-discussion",function(){loadCe(S.selected,true);});
      root.querySelectorAll("[data-edit-writeup]").forEach(function(b){b.onclick=function(){openWriteup('edit',b.dataset.editWriteup);};});
      root.querySelectorAll("[data-discuss-writeup]").forEach(function(b){b.onclick=function(){openWriteup('reply',b.dataset.discussWriteup);};});
      bind("#rv-memory-refresh",function(){loadCe(S.selected,true);reloadWork();});
      root.querySelectorAll("[data-memory-details]").forEach(function(el){var summary=el.querySelector("summary");if(summary)summary.onclick=function(){S.memoryDisclosures=S.memoryDisclosures||{};S.memoryDisclosures[S.market_slug+"|"+S.selected+"|"+el.dataset.memoryDetails]=!el.open;if(el.dataset.memoryDetails==="memory"&&!el.open)loadMemoryInline(S.selected);};});
      root.querySelectorAll("[data-memory-source]").forEach(function(b){b.onclick=function(){var target=Array.prototype.find.call(root.querySelectorAll("[data-memory-source-week]"),function(el){return el.dataset.memorySourceWeek===b.dataset.memorySource;});if(target){target.open=true;S.memoryDisclosures=S.memoryDisclosures||{};S.memoryDisclosures[S.market_slug+"|"+S.selected+"|"+target.dataset.memoryDetails]=true;var summary=target.querySelector("summary");summary.focus();summary.scrollIntoView({block:"nearest",behavior:"smooth"});}};});
      root.querySelectorAll("[data-memory-work]").forEach(function(b){b.onclick=function(){var w=findWork(b.dataset.memoryWork);if(!w)return;S.workTab=CLOSED.indexOf(w.status)>=0?"completed":"open";render();var target=Array.prototype.find.call(root.querySelectorAll("[data-work-status]"),function(el){return el.dataset.workStatus===w.work_id;});if(target){var details=target.closest("details");if(details)details.open=true;target.scrollIntoView({block:"center",behavior:"smooth"});target.focus({preventScroll:true});}};});
      var threadChoice=root.querySelector("#rv-thread-choice");if(threadChoice)threadChoice.onchange=function(){captureVisibleDrafts();S.threadOperation=threadChoice.value;S.threadOperationByCe[S.selected]=threadChoice.value;render();};
      var meeting=root.querySelector("#rv-process-text");if(meeting)meeting.oninput=function(){S.meetingDraft=meeting.value;};
      root.querySelectorAll("[data-meeting-ce]").forEach(function(b){b.onclick=function(){S.workTab="needs";select(b.dataset.meetingCe);};});
      root.querySelectorAll("[data-select-ce]").forEach(function (b) { b.onclick = function () { S.queueOpen=false;ensureLocalCe(b.dataset.selectCe);select(b.dataset.selectCe); }; });
      root.querySelectorAll("[data-open-drawer-ce]").forEach(function (b) {
        b.onclick=function(e){e.preventDefault();e.stopPropagation();openAnalyticsDrawer(b.dataset.openDrawerCe);};
        b.onkeydown=function(e){if(e.key==="Enter"||e.key===" "){e.preventDefault();e.stopPropagation();openAnalyticsDrawer(b.dataset.openDrawerCe);}};
      });
      root.querySelectorAll("[data-open-ce]").forEach(function (b) { b.onclick = function () { select(b.dataset.openCe); }; });
      root.querySelectorAll("[data-remove-ce]").forEach(function (b) { b.onclick = function (e) { e.stopPropagation(); removeCe(b.dataset.removeCe); }; });
      bind("#rv-add-ce", function () { S.adding = !S.adding; S.pickerQuery = ""; render(); var i = root.querySelector("#rv-picker-input"); if (i) i.focus(); });
      bind("#rv-browse-ces", function () { captureVisibleDrafts(); S.queueBrowse = true; render(); var i=root.querySelector("#rv-search-ce");if(i)i.focus({preventScroll:true}); });
      bind("#rv-close-queue", function () { S.queueBrowse = false; S.queueOpen=false; render(); var b=root.querySelector("#rv-audit-queue");if(b)b.focus({preventScroll:true}); });
      root.querySelectorAll("[data-queue-filter]").forEach(function(b){b.onclick=function(){S.queueFilter=b.dataset.queueFilter;render();};});
      var reasonFilter=root.querySelector("#rv-reason-filter");if(reasonFilter)reasonFilter.onchange=function(){S.queueReason=reasonFilter.value;render();};
      var categoryFilter=root.querySelector("#rv-category-filter");if(categoryFilter)categoryFilter.onchange=function(){S.queueCategory=categoryFilter.value;render();};
      var pick = root.querySelector("#rv-picker-input");
      if (pick) pick.oninput = function () {
        S.pickerQuery = pick.value;
        var res = root.querySelector("#rv-picker-results");
        if (res) { res.innerHTML = renderPickerResults(); wirePickerResults(); }
      };
      wirePickerResults();
      var search=root.querySelector("#rv-search-ce");
      if(search)search.oninput=function(){S.queueQuery=search.value;var panel=root.querySelector("#rv-queue-review");if(panel){panel.innerHTML=renderAuditQueueRows();wire();}};
      bind("#rv-clear-search",function(){S.queueQuery="";render();var el=root.querySelector("#rv-search-ce");if(el)el.focus();});
      [["#rv-owner-filter","queueOwner"],["#rv-task-force-filter","queueTaskForce"]].forEach(function(pair){var el=root.querySelector(pair[0]);if(el)el.onchange=function(){S[pair[1]]=el.value;render();};});

      var treatment = root.querySelector("#rv-treatment");
      if (treatment) treatment.onchange = function () { setTreatment(treatment.value); };
      bind("#rv-open-drawer", function () {
        openAnalyticsDrawer(S.selected);
      });
      bind("#rv-edit-note", function () { S.editingNote = true; S.noteDraft = Object.prototype.hasOwnProperty.call(S.drafts,S.selected)?S.drafts[S.selected]:((S.weekly[S.selected] || {}).bgm_note || ""); S.mentionPreview = null; render(); var n = root.querySelector("#rv-note"); if (n) { n.focus(); n.setSelectionRange(n.value.length, n.value.length); } });
      bind("#rv-cancel-note", function () { S.editingNote = false; delete S.drafts[S.selected]; S.noteDraft = null; S.mentionPreview = null; render(); });
      bind("#rv-delete-note", function () { S.confirmDelete = true; render(); });
      bind("#rv-del-no", function () { S.confirmDelete = false; render(); });
      bind("#rv-del-yes", deleteNote);
      bind("#rv-save-note", saveNote);
      root.querySelectorAll("[data-role-edit]").forEach(function(b){b.onclick=function(){S.editingRole=b.dataset.roleEdit;render();var el=root.querySelector('[data-role-input="'+S.editingRole+'"]');if(el)el.focus();};});
      root.querySelectorAll("[data-role-open]").forEach(function(b){b.onclick=function(){S.editingRole=b.dataset.roleOpen;render();var el=root.querySelector('[data-role-input="'+S.editingRole+'"]');if(el)el.focus();};});
      root.querySelectorAll("[data-role-cancel]").forEach(function(b){b.onclick=function(){delete S.roleDrafts[roleDraftKey(b.dataset.roleCancel)];S.editingRole="";render();};});
      root.querySelectorAll("[data-role-save]").forEach(function(b){b.onclick=function(){saveRoleNote(b.dataset.roleSave,b);};});
      root.querySelectorAll("[data-role-delete]").forEach(function(b){b.onclick=function(){deleteRoleNote(b.dataset.roleDelete);};});
      root.querySelectorAll("[data-role-input]").forEach(function(el){el.oninput=function(){S.roleDrafts[roleDraftKey(el.dataset.roleInput)]=el.value;};});
      bind("#rv-start-slack", startSlack);
      bind("#rv-retry-threads",function(){delete S.ceLoadedAt[S.selected];delete S.threadRegistryError[S.selected];loadCe(S.selected);render();});
      root.querySelectorAll("[data-resolve]").forEach(function(b){b.onclick=function(){focusRequirement(b.dataset.resolve);};});
      bind("#rv-save-finish-reason",function(){var input=root.querySelector("#rv-no-discussion-reason"),value=String(input?input.value:"").trim();if(!value){if(input)input.focus();toast("Add a concise reason");return;}S.noDiscussionDrafts[S.selected]=value;S.finishReasonOpen=false;render();toast("No-discussion reason ready for the review receipt");});
      var finishReason=root.querySelector("#rv-no-discussion-reason");if(finishReason)finishReason.oninput=function(){S.noDiscussionDrafts[S.selected]=finishReason.value;};
      bind("#rv-continue-slack", function(){S.threadOperation="continue";S.threadOperationByCe[String(S.selected)]="continue";S.mentionPreview=null;render();var message=root.querySelector("#rv-slack-message");if(message)message.focus({preventScroll:true});});
      bind("#rv-new-slack", function(){S.threadOperation="new_parent";S.threadOperationByCe[String(S.selected)]="new_parent";S.newThreadReason=S.newThreadReasonDrafts[String(S.selected)]||"";S.mentionPreview=null;render();var reason=root.querySelector("#rv-new-thread-reason");if(reason)reason.focus();});
      bind("#rv-new-thread-cancel", function(){S.threadOperation="";S.newThreadReason="";delete S.threadOperationByCe[String(S.selected)];delete S.newThreadReasonDrafts[String(S.selected)];S.mentionPreview=null;render();});
      bind("#rv-confirm-slack", postSlack);
      bind("#rv-mention-cancel", function () { S.mentionPreview = null; render(); var n = root.querySelector("#rv-slack-message"); if (n) n.focus(); });
      var noteInput = root.querySelector("#rv-note");
      if (noteInput) noteInput.oninput = function () { S.noteDraft = noteInput.value; S.drafts[S.selected]=S.noteDraft; S.mentionPreview = null; };
      var slackInput=root.querySelector("#rv-slack-message");if(slackInput)slackInput.oninput=function(){S.slackDrafts[String(S.selected)]=slackInput.value;resolveWriteupMentions(slackInput.value);};
      var threadReason=root.querySelector("#rv-new-thread-reason");if(threadReason)threadReason.oninput=function(){S.newThreadReason=threadReason.value;S.newThreadReasonDrafts[String(S.selected)]=threadReason.value;S.mentionPreview=null;};
      bind("#rv-sync-thread", syncThread);
      bind("#rv-summary-approve", function(){decideSummary("approved");});
      bind("#rv-summary-reject", function(){decideSummary("rejected");});
      bind("#rv-summary-regenerate", function(){decideSummary("regenerate");});
      bind("#rv-process-cancel", function () { S.processing = false; render(); });
      bind("#rv-process-run", runExtract);
      root.querySelectorAll(".rv-sugg").forEach(function (card) {
        card.querySelectorAll("[data-sugg-accept]").forEach(function(acc){acc.onclick=function(){acceptSuggestion(card);};});
        card.querySelectorAll("[data-sugg-ignore]").forEach(function(ig){ig.onclick=function(){decideSuggestionGroup(card,"rejected",{});};});
        if(S.asyncBusy["suggestion:"+card.dataset.suggestion])card.querySelectorAll("button").forEach(function(b){b.disabled=true;});
      });
      root.querySelectorAll("[data-sugg-edit]").forEach(function(b){b.onclick=function(){S.expandedSuggestion=b.dataset.suggEdit&&String(S.expandedSuggestion)!==String(b.dataset.suggEdit)?b.dataset.suggEdit:"";render();var active=root.querySelector('[data-sugg-edit="'+String(S.expandedSuggestion).replace(/"/g,'')+'"]');if(active)active.focus({preventScroll:true});};});
      root.querySelectorAll("[data-work-tab]").forEach(function(b){b.onclick=function(){S.workTab=b.dataset.workTab||"needs";render();};});
      bind("#rv-more-suggestions",function(){S.showAllSuggestions=!S.showAllSuggestions;render();var heading=root.querySelector('#rv-actions-section [data-work-tab="needs"]');if(heading&&heading.focus)heading.focus({preventScroll:true});});
      root.querySelectorAll("[data-backlog-view]").forEach(function(b){b.onclick=function(){S.backlogView=b.dataset.backlogView||"open";render();};});
      root.querySelectorAll("[data-comment-edit]").forEach(function (b) { b.onclick = function () { S.editingComment = b.dataset.commentEdit; render(); }; });
      root.querySelectorAll("[data-comment-edit-cancel]").forEach(function (b) { b.onclick = function () { S.editingComment = null; render(); }; });
      root.querySelectorAll("[data-comment-save]").forEach(function (b) { b.onclick = function () { saveImportedComment(b.dataset.commentSave); }; });
      root.querySelectorAll("[data-comment-delete]").forEach(function (b) { b.onclick = function () { S.confirmDeleteComment = b.dataset.commentDelete; render(); }; });
      root.querySelectorAll("[data-comment-delete-confirm]").forEach(function (b) { b.onclick = function () { deleteImportedComment(b.dataset.commentDeleteConfirm); }; });
      root.querySelectorAll("[data-comment-delete-cancel]").forEach(function (b) { b.onclick = function () { S.confirmDeleteComment = null; render(); }; });
      root.querySelectorAll("[data-work-toggle]").forEach(function (b) { b.onclick = function () { toggleWork(b.dataset.workToggle); }; });
      root.querySelectorAll("[data-work-status]").forEach(function (sel) { sel.onchange = function () { setWorkStatus(sel.dataset.workStatus, sel.value); }; });
      root.querySelectorAll("[data-work-edit]").forEach(function (b) { b.onclick = function () { S.editingWork = b.dataset.workEdit; render(); }; });
      root.querySelectorAll("[data-work-delete]").forEach(function (b) { b.onclick = function () { S.confirmDeleteWork = b.dataset.workDelete; render(); }; });
      root.querySelectorAll("[data-work-delete-confirm]").forEach(function (b) { b.onclick = function () { deleteWork(b.dataset.workDeleteConfirm); }; });
      root.querySelectorAll("[data-work-delete-cancel]").forEach(function (b) { b.onclick = function () { S.confirmDeleteWork = null; render(); }; });
      root.querySelectorAll("[data-work-edit-save]").forEach(function (b) { b.onclick = function () { saveWorkEdit(b.dataset.workEditSave); }; });
      root.querySelectorAll("[data-work-edit-cancel]").forEach(function (b) { b.onclick = function () { S.editingWork = null; render(); }; });
      bind("#rv-add-action", function () { captureVisibleDrafts();S.compose = S.compose === "action" ? "" : "action";if(S.compose)S.composeByCe[String(S.selected)]=S.compose;else delete S.composeByCe[String(S.selected)];render(); var i = root.querySelector("#rv-c-text"); if (i) i.focus({preventScroll:true}); });
      bind("#rv-add-check", function () { captureVisibleDrafts();S.compose = S.compose === "check" ? "" : "check";if(S.compose)S.composeByCe[String(S.selected)]=S.compose;else delete S.composeByCe[String(S.selected)];render(); var i = root.querySelector("#rv-c-text"); if (i) i.focus({preventScroll:true}); });
      ["#rv-c-text","#rv-c-owner","#rv-c-due","#rv-c-status"].forEach(function(sel){var el=root.querySelector(sel);if(el)el.oninput=el.onchange=function(){captureVisibleDrafts();};});
      bind("#rv-c-cancel", function () { delete S.composeDrafts[composeDraftKey(S.selected,S.compose)];delete S.composeByCe[String(S.selected)];S.compose = ""; render(); });
      bind("#rv-c-save", saveCompose);
      bind("#rv-next-ce", nextCe);
      bind("#rv-finish", finishReview);
    }
    function ensureAuthor() {
      var el = root.querySelector("#rv-author");
      if (el && el.value.trim()) setAuthor(el.value);
      if (!author()) { if (el) el.focus(); toast("Add your name first"); return false; }
      return true;
    }

    // ---- backend actions -------------------------------------------------
    function setTreatment(value) {
      if (!api) { toast("Review backend unavailable"); return; }
      var q = S.byId[S.selected];
      api.saveReviewSetItem({ market_slug: S.market_slug, week_start: S.week_start, ce_id: q.ce_id, ce_name: q.ce_name, treatment: value, reason: q.reason || "", source: q.source || "flag" })
        .then(function (res) { S.setRows[q.ce_id] = res.review_set_item || { treatment: value }; track("treatment_selected",{ce_id:q.ce_id,value_text:value}); render(); })
        .catch(function () { toast("Could not save treatment"); });
    }
    function runExtract() {
      var ta = root.querySelector("#rv-process-text"), text = ta ? ta.value.trim() : "";
      if(S.meetingBusy)return;
      if (!text) { if (ta) ta.focus(); toast("Paste the meeting notes first"); return; }
      if (!ensureAuthor()) return;
      S.meetingBusy=true;S.processSummary="Reading meeting notes…";render();
      var ceList = (S.headline.all_ces || []).map(function (c) { return { ce_id: String(c.ce_id), ce_name: c.ce_name || "" }; });
      var payload = { market_slug: S.market_slug, week: S.week_start, text: text, submitted_by: author(), ces: ceList };
      var call = (api && api.extractMeeting) ? api.extractMeeting(payload)
        : fetch("/api/review-extract", { method: "POST", credentials: "same-origin", headers: { "content-type": "application/json" }, body: JSON.stringify(payload) }).then(function (r) { return r.json(); });
      call.then(function (res) {
        if (!res || res.ok === false) throw new Error((res && res.error) || "extract failed");
        if(S.market_slug!==payload.market_slug||S.week_start!==payload.week)return;
        var ces = res.ces || [], total = 0, added = [];S.meetingResults=ces;S.meetingUnmatched=res.unmatched||[];
        ces.forEach(function (c) {
          var id = String(c.ce_id), arr = c.suggestions || [];
          total += arr.length;
          if (arr.length) S.suggestions[id] = arr.concat((S.suggestions[id] || []).filter(function(old){return !arr.some(function(n){return n.suggestion_id===old.suggestion_id;});}));
          if (!S.byId[id]) added.push({ ce_id: id, ce_name: c.ce_name, reason: "From meeting notes", source: "manual" });
        });
        if (added.length) { S.setRowsList = (S.setRowsList || []).concat(added); buildQueue(); }
        S.processSummary = (res.replayed ? "Previously imported: " : "Extracted ") + total + " suggestion" + (total === 1 ? "" : "s") + " across " + ces.length +
          " CE" + (ces.length === 1 ? "" : "s") + "." + (total ? " Review the suggestions below." : " No pending suggestions.") + (res.already_reviewed ? " " + res.already_reviewed + " already reviewed; decisions kept." : "") + (res.unmatched_count ? " " + res.unmatched_count + (res.unmatched_count === 1 ? " passage needs" : " passages need") + " a CE name or ID. Clarify those passages and paste them again." : "");
        render(); toast("Distributed to " + ces.length + " CE" + (ces.length === 1 ? "" : "s"));
      }).catch(function (e) {
        S.processSummary=(e&&e.message)||"Extraction failed. Your transcript is preserved.";
      }).finally(function(){S.meetingBusy=false;render();});
    }
    function addCe(ceId) {
      if (!api) return;
      var reasonInput=root.querySelector("#rv-nomination-reason"),reason=String(reasonInput?reasonInput.value:S.nominationReason||"").trim();
      if(!reason){if(reasonInput)reasonInput.focus();toast("Add a nomination reason first");return;}S.nominationReason=reason;
      var ce = (S.headline.all_ces || []).find(function (c) { return String(c.ce_id) === String(ceId); }) || { ce_id: ceId };
      api.saveReviewSetItem({ market_slug: S.market_slug, week_start: S.week_start, ce_id: String(ceId), ce_name: ce.ce_name || "", treatment: "not_scheduled", reason: reason, source: "nomination" })
        .then(function () { return api.saveTimelineEvent({market_slug:S.market_slug,ce_id:String(ceId),ce_name:ce.ce_name||"",review_week:S.week_start,event_type:"nomination",approved_body:reason,approved_by:author()||"authenticated reviewer",idempotency_key:"nomination:"+S.week_start+":"+String(ceId)}); })
        .then(function () { S.adding = false; S.pickerQuery = ""; S.nominationReason=""; return loadQueue().then(function () { select(ceId); }); })
        .then(function () { toast("CE added to this week’s review"); })
        .catch(function () { toast("Could not add CE"); });
    }
    function removeCe(ceId) {
      if (!api) return;
      var ce = S.byId[String(ceId)] || {};
      api.saveReviewSetItem({ market_slug: S.market_slug, week_start: S.week_start, ce_id: String(ceId), ce_name: ce.ce_name || "", included: "false", source: "manual" })
        .then(function () { if (String(S.selected) === String(ceId)) S.selected = null; return loadQueue(); })
        .then(function () { toast("Removed from review set"); })
        .catch(function () { toast("Could not remove CE"); });
    }
    function saveRoleNote(role,button){
      if(!ensureAuthor()||!api||S.asyncBusy["note:"+role])return;
      var el=root.querySelector('[data-role-input="'+role+'"]'),text=el?el.value.trim():"";
      if(!text){if(el)el.focus();toast("Write the "+role+" note first");return;}
      S.asyncBusy["note:"+role]=true;if(button){button.disabled=true;button.textContent="Saving…";}
      var payload=Object.assign({},ident(S.selected),{note_type:role,note:text,author:author()});
      payload[role+"_note"]=text;payload[role+"_author"]=author();
      api.saveWeeklyNote(payload).then(function(res){S.weekly[S.selected]=res.weekly;delete S.roleDrafts[roleDraftKey(role)];S.editingRole="";toast(roleMeta(role).label+" saved");render();})
        .catch(function(){toast("Save failed · note kept locally");}).finally(function(){delete S.asyncBusy["note:"+role];});
    }
    function deleteRoleNote(role){
      if(!api||S.asyncBusy["note:"+role])return;S.asyncBusy["note:"+role]=true;
      api.deleteWeeklyNote(ident(S.selected),author(),role).then(function(res){S.weekly[S.selected]=res.weekly||null;toast(roleMeta(role).label+" deleted · audit retained");render();})
        .catch(function(){toast("Delete failed");}).finally(function(){delete S.asyncBusy["note:"+role];});
    }
    function saveNote() {
      if (!ensureAuthor() || !api) return;
      var ta = root.querySelector("#rv-note"); if (!ta.value.trim()) { ta.focus(); toast("Write an observation first"); return; }
      var btn=root.querySelector("#rv-save-note");if(btn){btn.disabled=true;btn.textContent="Saving…";}
      api.saveWeeklyNote(Object.assign({}, ident(S.selected), { bgm_note: ta.value.trim(), bgm_author: author() }))
        .then(function (res) { S.weekly[S.selected] = res.weekly; S.editingNote = false; delete S.drafts[S.selected]; S.noteDraft = null; S.mentionPreview = null; toast("Note saved"); render(); })
        .catch(function () { if(btn){btn.disabled=false;btn.textContent="Save note";} toast("Save failed · note kept locally"); });
    }
    function deleteNote() {
      if (!api) return;
      api.deleteWeeklyNote(ident(S.selected), author()).then(function (res) {
        S.weekly[S.selected] = res.weekly || null; S.confirmDelete = false; S.editingNote = false; toast("Note deleted · audit retained"); render();
      }).catch(function () { toast("Delete failed"); });
    }
    function startSlack() {
      var weekly = S.weekly[S.selected];
      if (weekly && weekly.slack_post_ts && !S.threadOperation) { window.open(weekly.slack_post_permalink || "#", "_blank"); return; }
      if (!ensureAuthor() || !api) return;
      if (!S.channel) { toast("No Slack channel configured for this market"); return; }
      var ta = root.querySelector("#rv-slack-message"); var text = ta ? ta.value.trim() : (S.slackDrafts[String(S.selected)] || "");
      if (!text) { if (ta) ta.focus(); toast("Write the discussion starter first"); return; }
      if(S.threadOperation==="new_parent"){
        var reason=root.querySelector("#rv-new-thread-reason");S.newThreadReason=String(reason?reason.value:S.newThreadReason||"").trim();
        if(!S.newThreadReason){if(reason)reason.focus();toast("Add a reason before starting a new discussion");return;}
      }
      S.slackDrafts[String(S.selected)]=text; S.mentionBusy = true; S.mentionPreview = null; render();
      api.resolveMentions(ident(S.selected), text).then(function (res) {
        S.mentionBusy = false;
        S.mentionPreview = { original_text: text, resolved_text: res.resolved_text || text, matches: res.matches || [], ambiguous: res.ambiguous || [] };
        render();
      }).catch(function () { S.mentionBusy = false; render(); toast("Could not resolve Slack names · message not posted"); });
    }
    function postSlack() {
      var p = S.mentionPreview, weekly = S.weekly[S.selected];
      if (!p || (p.ambiguous || []).length) { toast("Clarify ambiguous names before posting"); return; }
      if (!ensureAuthor() || !api) return;
      if (!S.channel) { toast("No Slack channel configured for this market"); return; }
      var text = String(p.original_text || "").trim();
      var id = ident(S.selected), reqId = "wbr_" + S.week_start + "_" + id.ce_id + "_" + hash(id.ce_id + text);
      var btn=root.querySelector("#rv-confirm-slack");if(btn){btn.disabled=true;btn.textContent="Posting…";}
      api.startSlackDiscussion(Object.assign({}, id, { channel: S.channel.id, discussion_text: text, discussion_author: author(), request_id: reqId, report_url: location.href, thread_operation:S.threadOperation||"", replacement_reason:S.newThreadReason||"" }))
        .then(function (res) { S.weekly[S.selected] = res.weekly; if(res.thread)S.threadRegistry[S.selected]={active:res.thread,threads:[res.thread].concat((S.threadRegistry[S.selected]||{}).threads||[])}; delete S.slackDrafts[String(S.selected)];delete S.threadOperationByCe[String(S.selected)];delete S.newThreadReasonDrafts[String(S.selected)]; S.mentionPreview = null; S.threadOperation=""; S.newThreadReason=""; track("slack_discussion_started",{value_text:res.operation||"start"}); toast(res.operation==="continue"?"CE discussion continued":"CE discussion started"); render(); })
        .catch(function (e) { if(btn){btn.disabled=false;btn.textContent="Post to Slack";} toast((e && e.message) || "Post failed · discussion kept locally"); });
    }
    function syncThread() {
      if(!api)return;
      var id=ident(S.selected),key="summary:"+id.ce_id,binding=summaryThreadFor(S.weekly[id.ce_id],S.threadRegistry[id.ce_id]);
      if(S.asyncBusy[key])return;
      S.asyncBusy[key]=true;S.auditStatus[id.ce_id]="Reading Slack replies and summarizing…";render();
      api.syncWeeklyDiscussion(Object.assign({},id,{thread_binding_id:binding&&binding.binding_id||""})).then(function(res){
        if(!sameReport(id))return;
        if(res.weekly)S.weekly[id.ce_id]=res.weekly;
        if(res.ai_status&&["ok","no_new_source","current"].indexOf(res.ai_status)<0)throw new Error("Summary unavailable. Slack replies and the previous summary are preserved. Try again.");
        var save=res.weekly&&res.weekly.summary_status==="pending"?api.decideSummary(Object.assign({},id,{decision:"approved",decided_by:author(),thread_binding_id:res.weekly.thread_binding_id,slack_discussion_number:res.weekly.slack_discussion_number})):Promise.resolve(res);
        return save.then(function(saved){if(!sameReport(id))return;if(saved.weekly)S.weekly[id.ce_id]=saved.weekly;S.auditStatus[id.ce_id]=res.ai_status==="no_new_source"?"No replies to summarize yet.":"Discussion updated.";S.ceLoadedAt[id.ce_id]=0;loadCe(id.ce_id,true);});
      }).catch(function(error){if(!sameReport(id))return;S.auditStatus[id.ce_id]=error.message||"Could not summarize. Your previous summary is preserved. Try again.";}).finally(function(){delete S.asyncBusy[key];if(sameReport(id)&&S.selected===id.ce_id)render();});
    }

    function decideSummary(decision){
      if(!api)return;var id=ident(S.selected),key="summary:"+id.ce_id;if(S.asyncBusy[key])return;
      var weekly=S.weekly[id.ce_id]||{},draft=root.querySelector("#rv-summary-draft"),payload=Object.assign({},id,{decision:decision,decided_by:author()||"authenticated BGM",thread_binding_id:weekly.thread_binding_id||"",slack_discussion_number:weekly.slack_discussion_number||""});
      if(draft)payload.summary_json=draft.value;
      S.asyncBusy[key]=true;S.auditStatus[id.ce_id]="Saving summary…";render();
      api.decideSummary(payload).then(function(res){S.weekly[id.ce_id]=res.weekly;S.auditStatus[id.ce_id]=decision==="approved"?"Discussion updated.":"Summary updated.";loadMemoryInline(id.ce_id,true);}).catch(function(e){S.auditStatus[id.ce_id]=e.message||"Could not save summary.";}).finally(function(){delete S.asyncBusy[key];if(sameReport(id)&&S.selected===id.ce_id){render();if(decision==="regenerate")syncThread();}});
    }
    function acceptSuggestion(card) {
      var kind = card.dataset.kind, sid = card.dataset.suggestion;
      var body = ((card.querySelector("[data-sugg-body]") || {}).value || card.dataset.body || "").trim();
      if (!body) { var bodyEl = card.querySelector("[data-sugg-body]"); if (bodyEl) bodyEl.focus(); toast("Keep or edit the suggestion text first"); return; }
      if (kind === "comment") { decideSuggestionGroup(card, "approved", { destination: "comment", body: body }); return; }
      if (!ensureAuthor()) return;
      var owner = (card.querySelector("[data-w-owner]") || {}).value || card.dataset.owner || "";
      var due = (card.querySelector("[data-w-due]") || {}).value || card.dataset.due || "";
      var status = (card.querySelector("[data-w-status]") || {}).value || (kind === "check" ? "scheduled" : "needs_action");
      if ((kind === "action" && status === "needs_action" && !owner.trim()) || (kind === "check" && !due)) {
        S.expandedSuggestion=sid; render();
        var missing=root.querySelector(kind === "check"?'[data-suggestion="'+String(sid).replace(/"/g,'')+'"] [data-w-due]':'[data-suggestion="'+String(sid).replace(/"/g,'')+'"] [data-w-owner]');
        if(missing)missing.focus({preventScroll:true});
        toast(kind === "check"?"Choose the next review date":"Confirm an owner for work that needs action"); return;
      }
      decideSuggestionGroup(card, "approved", { destination: kind, body: body, owner: owner.trim(), due_date: due, work_status: status });
    }
    function decideSuggestionGroup(card, decision, fields) {
      var primary = card.dataset.suggestion, duplicates = String(card.dataset.duplicateIds || "").split(",").filter(Boolean);
      if (!api) return;
      var id=ident(S.selected),key="suggestion:"+primary,destination=fields&&fields.destination;
      if(S.asyncBusy[key])return;
      S.asyncBusy[key]=true;card.querySelectorAll("button").forEach(function(b){b.disabled=true;});
      S.auditStatus[id.ce_id]=decision==="approved"?"Saving approval…":"Dismissing suggestion…";
      api.decideSuggestion(Object.assign({ suggestion_id:primary, decision:decision, decided_by:author() }, fields || {})).then(function(result){
        if(!sameReport(id))return;
        // Apply only confirmed server records; a slow history refresh must not
        // leave an already-approved card inviting another click.
        S.suggestions[id.ce_id]=(S.suggestions[id.ce_id]||[]).filter(function(s){return s.suggestion_id!==primary;});
        if(result.comment)S.comments[id.ce_id]=[result.comment].concat((S.comments[id.ce_id]||[]).filter(function(c){return c.comment_id!==result.comment.comment_id;}));
        if(result.work_item)S.work[id.ce_id]=[result.work_item].concat((S.work[id.ce_id]||[]).filter(function(w){return w.work_id!==result.work_item.work_id;}));
        (S.meetingResults||[]).forEach(function(c){c.suggestions=(c.suggestions||[]).filter(function(s){return s.suggestion_id!==primary;});});
        if(decision==="approved"&&destination!=="comment")S.workTab="open";
        S.auditStatus[id.ce_id]=decision==="approved"?(destination==="comment"?"Observation saved to CE memory.":"Approved · moved to Open"):"Suggestion dismissed. Source retained.";
        track("suggestion_triaged",{ce_id:id.ce_id,value_number:1,value_text:decision,idempotency_key:"suggestion:"+primary+":"+decision});
        if(S.selected===id.ce_id)render();
        return Promise.all(duplicates.map(function(sid){return api.decideSuggestion({suggestion_id:sid,decision:"rejected",decided_by:author(),duplicate_of:primary});})).then(function(){return Promise.all([loadCe(id.ce_id,true),reloadWork()]);});
      }).catch(function(error){if(sameReport(id))S.auditStatus[id.ce_id]=error.message||"Could not update suggestion. Refresh to check its saved state before retrying.";})
        .finally(function(){delete S.asyncBusy[key];if(sameReport(id)&&S.selected===id.ce_id)render();});
    }
    function decideSuggestion(sid, decision, fields) {
      if (!api) return;
      api.decideSuggestion(Object.assign({ suggestion_id: sid, decision: decision, decided_by: author() }, fields || {}))
        .then(function () { toast(decision === "approved" ? "Added" : "Ignored · source retained"); return Promise.all([loadCe(S.selected,true), reloadWork()]); })
        .catch(function () { toast("Could not update suggestion"); });
    }
    function findImportedComment(commentId) {
      return (S.comments[S.selected] || []).filter(function (c) { return String(c.comment_id) === String(commentId); })[0] || null;
    }
    function saveImportedComment(commentId) {
      var c = findImportedComment(commentId); if (!c || !api || !ensureAuthor()) return;
      var row = root.querySelector('[data-comment="' + String(commentId).replace(/"/g, "") + '"]');
      var body = row && row.querySelector("[data-comment-body]") ? row.querySelector("[data-comment-body]").value.trim() : "";
      if (!body) { if (row) row.querySelector("[data-comment-body]").focus(); toast("Commentary cannot be empty"); return; }
      api.saveComment({ comment_id: c.comment_id, market_slug: c.market_slug, ce_id: c.ce_id, ce_name: c.ce_name,
        week_start: c.week_start, body: body, author_name: c.author_name || c.source_author || "Meeting",
        author_role: c.author_role || "", source_type: c.source_type || "granola", source_author: c.source_author || "",
        source_ref: c.source_ref || "", source_url: c.source_url || "", accepted_by: author() })
        .then(function () { S.editingComment = null; toast("Meeting note updated"); loadCe(S.selected); })
        .catch(function () { toast("Could not update commentary"); });
    }
    function deleteImportedComment(commentId) {
      if (!api || !ensureAuthor()) return;
      api.deleteComment(commentId, author()).then(function () { S.confirmDeleteComment = null; toast("Meeting note deleted · audit retained"); loadCe(S.selected); })
        .catch(function () { toast("Could not delete commentary"); });
    }
    function saveCompose() {
      if (!ensureAuthor() || !api) return;
      if(S.asyncBusy.createWork)return;
      var kind = S.compose,composeKey=composeDraftKey(S.selected,kind), text = root.querySelector("#rv-c-text").value.trim();
      if (!text) { root.querySelector("#rv-c-text").focus(); toast("Describe it first"); return; }
      var owner = root.querySelector("#rv-c-owner").value.trim(), due = root.querySelector("#rv-c-due").value, status = root.querySelector("#rv-c-status").value;
      if (kind === "action" && status === "needs_action" && !owner) { root.querySelector("#rv-c-owner").focus(); toast("Confirm an owner for work that needs action"); return; }
      if (kind === "check" && !due) { root.querySelector("#rv-c-due").focus(); toast("Choose the next review date"); return; }
      S.asyncBusy.createWork=true;
      var createRequestKey=composeKey+":"+[text,owner,due,status].join(":");
      var createRequest=S.sendRequests[createRequestKey]||(S.sendRequests[createRequestKey]="work_"+Date.now()+"_"+hash(createRequestKey));
      var started=performance.now(),tempId="pending_"+Date.now()+"_"+hash(text+owner+due),item={ work_id:tempId,market_slug:S.market_slug,ce_id:S.selected,ce_name:(S.byId[S.selected]||{}).ce_name,origin_week:S.week_start,kind:kind,text:text,owner:owner,due_date:due,status:status,source_type:"bgm_manual",idempotency_key:createRequest,_pending:true };
      S.composeDrafts[composeKey]={text:text,owner:owner,due:due,status:status};(S.work[String(S.selected)]=S.work[String(S.selected)]||[]).push(item);S.compose="";delete S.composeByCe[String(S.selected)];render();toast(kind==="check"?"Scheduling check…":"Creating action…");
      api.saveWork(Object.assign({},item,{work_id:""})).then(function(res){var list=S.work[String(item.ce_id)]||[],idx=list.indexOf(item);if(idx>=0)list[idx]=res.work_item||Object.assign({},item,{work_id:(res.work_item||{}).work_id||tempId,_pending:false});delete S.sendRequests[createRequestKey];delete S.composeDrafts[composeKey];console.info("review_work_persist_ms",Math.round(performance.now()-started));toast(kind==="check"?"Check scheduled":"Action created");render();return reloadWork();})
        .catch(function(){var list=S.work[String(item.ce_id)]||[],idx=list.indexOf(item);if(idx>=0)list.splice(idx,1);if(S.selected===String(item.ce_id))S.compose=kind;S.composeByCe[String(item.ce_id)]=kind;toast("Could not save work item · rolled back");render();})
        .finally(function(){S.asyncBusy.createWork=false;});
    }
    function toggleWork(workId) {
      var w = findWork(workId); if (!w || !api) return;
      var next = CLOSED.indexOf(w.status) >= 0 ? (w.kind === "check" ? "scheduled" : "needs_action") : "complete";
      saveWorkItem({ work_id: w.work_id, market_slug: w.market_slug, ce_id: w.ce_id, ce_name: w.ce_name, origin_week: w.origin_week, kind: w.kind, text: w.text, owner: w.owner || "", due_date: w.due_date || "", status: next, source_type: w.source_type || "bgm_manual" }, next === "complete" ? "Marked complete" : "Reopened");
    }
    function setWorkStatus(workId, status) {
      var w = findWork(workId); if (!w || !api) return;
      saveWorkItem({ work_id: w.work_id, market_slug: w.market_slug, ce_id: w.ce_id, ce_name: w.ce_name, origin_week: w.origin_week, kind: w.kind, text: w.text, owner: w.owner || "", due_date: w.due_date || "", status: status, source_type: w.source_type || "bgm_manual", source_ref:w.source_ref||"", source_url:w.source_url||"" }, "Status updated");
    }
    function saveWorkEdit(workId) {
      var w = findWork(workId); if (!w || !api || !ensureAuthor()) return;
      var row = root.querySelector('[data-work="' + String(workId).replace(/"/g, "") + '"]');
      if (!row) return;
      var text = (row.querySelector("[data-edit-text]") || {}).value || "";
      var owner = (row.querySelector("[data-edit-owner]") || {}).value || "";
      var due = (row.querySelector("[data-edit-due]") || {}).value || "";
      var status = (row.querySelector("[data-edit-status]") || {}).value || w.status;
      var carry=w.carry_forward;
      if (!text.trim()) { row.querySelector("[data-edit-text]").focus(); toast("Describe the work item first"); return; }
      if (w.kind === "action" && status === "needs_action" && !owner.trim()) { row.querySelector("[data-edit-owner]").focus(); toast("Confirm an owner for work that needs action"); return; }
      if (w.kind === "check" && !due) { row.querySelector("[data-edit-due]").focus(); toast("Choose the next review date"); return; }
      S.editingWork = null;
      saveWorkItem({ work_id: w.work_id, market_slug: w.market_slug, ce_id: w.ce_id, ce_name: w.ce_name, origin_week: w.origin_week,
        kind: w.kind, text: text.trim(), owner: owner.trim(), due_date: due, status: status,
        carry_forward:carry,source_type: w.source_type || "bgm_manual", source_ref: w.source_ref || "", source_url: w.source_url || "" }, "Work item updated");
    }
    function deleteWork(workId) {
      if (!ensureAuthor() || !api) return;
      if (typeof api.deleteWork !== "function") { toast("Delete is not available on this Review backend"); return; }
      api.deleteWork(workId, author()).then(function () {
        S.confirmDeleteWork = null; toast("Work item deleted · audit retained"); return reloadWork();
      }).catch(function () { toast("Could not delete work item"); });
    }
    function saveWorkItem(item, okMsg) { var key="work:"+String(item.work_id||"")+":"+String(item.status||"");if(S.asyncBusy[key])return;S.asyncBusy[key]=true;api.saveWork(item).then(function () { if(CLOSED.indexOf(item.status)>=0)track("action_closed",{ce_id:item.ce_id,value_text:item.status,idempotency_key:"action_closed:"+item.work_id+":"+item.status});S.auditStatus[item.ce_id]=okMsg;toast(okMsg); return reloadWork(); }).catch(function () { toast("Could not save work item"); }).finally(function(){delete S.asyncBusy[key];}); }
    function reloadWork() {
      if(!api)return Promise.resolve();var market=S.market_slug;S.workLoading=true;render();
      return api.work({market_slug:market},{refresh:true}).then(function(res){if(S.market_slug!==market)return;S.work={};(res.work_items||[]).forEach(function(w){var k=String(w.ce_id);(S.work[k]=S.work[k]||[]).push(w);});S.workLoaded=true;S.workError="";}).catch(function(e){if(S.market_slug===market)S.workError=e.message||"Actions unavailable";}).finally(function(){if(S.market_slug===market){S.workLoading=false;render();}});
    }

    function findWork(id) { var f = null; Object.keys(S.work).forEach(function (k) { S.work[k].forEach(function (w) { if (String(w.work_id) === String(id)) f = w; }); }); return f; }
    function focusRequirement(key){
      if(key==="suggestions"&&S.workTab!=="needs"){S.workTab="needs";render();}
      if(key==="work"){
        var unmanaged=openWorkFor(S.selected).filter(function(w){return !(String(w.carry_forward)==="true"||(w.owner&&(w.due_date||w.next_review_date))||(w.kind==="check"&&(w.due_date||w.next_review_date)));})[0];
        var neededTab=unmanaged&&(unmanaged.kind==="check"||String(unmanaged.carry_forward)==="true")?"later":"open";
        if(S.workTab!==neededTab){S.workTab=neededTab;render();}
      }
      var selector=key==="treatment"?"#rv-treatment":key==="discussion"?"#rv-discussion-section":key==="suggestions"?'#rv-actions-section [data-work-tab="needs"]':"#rv-actions-section .rv-work-requirement";
      if(key==="discussion"&&!(S.weekly[S.selected]||{}).slack_post_ts){var slackAction=root.querySelector("#rv-continue-slack,#rv-start-slack,#rv-retry-threads,#rv-discussion-section");if(slackAction){if(slackAction.focus)slackAction.focus({preventScroll:true});slackAction.scrollIntoView({block:"center",behavior:"smooth"});}return;}
      var target=root.querySelector(selector);if(target){if(target.focus)target.focus({preventScroll:true});target.scrollIntoView({block:"center",behavior:"smooth"});}
    }
    function finishReview() {
      var q = S.byId[S.selected], t = treatmentFor(q.ce_id);
      if (t === "not_scheduled") { root.querySelector("#rv-treatment").focus(); toast("Choose how you’ll review this CE"); return; }
      if (!ensureAuthor() || !api) return;
      var blockers=completionBlockers(q);if(blockers.length){focusRequirement(blockers[0].key);toast(blockers[0].label);return;}
      var weekly=S.weekly[q.ce_id]||{},summary="";try{if(String(weekly.summary_status)==="approved"){var parsed=JSON.parse(weekly.summary_approved_json||weekly.summary_json||"{}");summary=[].concat(parsed.findings||[],parsed.decisions||[]).map(function(x){return typeof x==="string"?x:(x.text||x.body||"");}).filter(Boolean).join(" · ");}}catch(e){}
      api.finishReview({ market_slug: S.market_slug, ce_id: q.ce_id, ce_name: q.ce_name, week_start: S.week_start, treatment: t, reviewer: author(), open_work_count: String(openWorkFor(q.ce_id).length), summary: summary, no_discussion_reason:String(S.noDiscussionDrafts[q.ce_id]||"").trim() })
        .then(function (res) { S.receipts[q.ce_id] = res.receipt || { reviewer: author() }; track("review_completed",{ce_id:q.ce_id,idempotency_key:"review_completed:"+S.market_slug+":"+S.week_start+":"+q.ce_id});toast("CE review finished"); render(); })
        .catch(function () { toast("Could not save review receipt"); });
    }
    function nextCe() {
      var open = S.queue.filter(function (x) { return !reviewedFor(x.ce_id) && String(x.ce_id) !== String(S.selected); });
      open.sort(function(a,b){var rank=function(q){var state=shortlistState(q);return state==="selected"?0:state==="candidate"?1:2;};return rank(a)-rank(b);});
      if (!open.length) { toast("Review queue complete for this week 🎉"); return; }
      select(open[0].ce_id);
    }
    function hash(raw) { var h = 2166136261; for (var i = 0; i < raw.length; i++) { h ^= raw.charCodeAt(i); h = Math.imul(h, 16777619); } return (h >>> 0).toString(16); }

    var visibleOnce = false;
    return {
      onShow: function () {
        var requested="";try{requested=new URL(location.href).searchParams.get("ce_id")||"";}catch(e){}
        if (refreshHeadline() || !S.loaded){loadQueue();if(requested&&ensureLocalCe(requested))select(requested);}
        else if(requested&&ensureLocalCe(requested))select(requested);else render();
        visibleOnce = true;
        track("review_return_usage",{idempotency_key:"return:"+S.market_slug+":"+S.week_start+":"+sessionId()});
      },
      focusCe: function (ceId) { refreshHeadline(); if(ensureLocalCe(ceId)){S.queueRevealUntil=Date.now()+2500;select(ceId);revealQueueSelection(ceId);return true;}return false; },
      prefetch: function(){refreshHeadline();if(!S.loaded)loadQueue();},
      onHide: function(){captureVisibleDrafts();if(ctx.releaseAnalytics)ctx.releaseAnalytics();},
      onWeekChange: function () { captureVisibleDrafts();refreshHeadline();if(visibleOnce)loadQueue(); }
    };
  };
})(typeof window !== "undefined" ? window : this);
