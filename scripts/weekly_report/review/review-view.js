/* Weekly Review tab — production logic (Eevee design language).
 *
 * Wires the review workspace to the live /api/review backend. Loaded as an external classic script;
 * the V2 shell calls window.initReviewView(ctx) from inside its IIFE, passing closure refs.
 *
 * UX model (per design references, Aug 2026):
 *  - BGM note: read card (avatar + name·role + meta + Edit/Delete links); textbox only when writing/editing.
 *  - Actions: checkbox-led task rows (task text as headline, owner·due·source meta, per-item status select,
 *    owner avatar). Scheduled checks use a date badge. Split "+ Add action" / "+ Schedule check".
 *  - Queue: "+ Add CE" searchable picker over all CEs; manual adds removable.
 *
 * No build step. Edit here, then re-run scripts/weekly_report/inject_review_view.py to redeploy.
 */
(function (global) {
  "use strict";

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
    rest_of_mea:{id:"C0889D22PM5",name:"mkt-mena-expansion-internal"},benelux:{id:"CKTFHT4AF",name:"mkt-uk"},
    nordics:{id:"CSQ10TALA",name:"mkt-csee"},south_america:{id:"CH2LRMJF2",name:"mkt-iberia"},
    mexico_central_america:{id:"C012949PQ81",name:"mkt-mexico"},headout:{id:"C0975BGAX0B",name:"team-central-biz"}
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
      receipts: {}, outcomes: {}, weekly: {}, weeklyHist: {}, threadRegistry: {}, work: {}, suggestions: {}, comments: {}, setRows: {}, setRowsList: [],
      loadingCe: {}, editingNote: false, editingRole: "", confirmDelete: false, adding: false, compose: "", addingGranola: false,
      processing: false, processSummary: "", noteDraft: null, roleDrafts: {}, slackDrafts: {}, queueQuery: "", queueFilter: "all", queueReason: "", queueCategory: "", queueOwner: "", queueTaskForce: "", queueBrowse: false, expandedSuggestion: "", workTab: "needs", mentionPreview: null, mentionBusy: false,
      editingWork: null, confirmDeleteWork: null, editingComment: null, confirmDeleteComment: null,
      threadOperation: "", newThreadReason: "", backlogView: "open", reconciliation: null, finishReasonOpen:false, showAllSuggestions:false,
      drafts: {}, outcomeDrafts: {}, noDiscussionDrafts:{}, ceLoadedAt: {}, ceRequestSeq: {}, ceControllers: {}, memoryCache: {}, memoryInflight: {}, memoryOpen: false, asyncBusy: {}
    };

    // Review mutations are BGM-only.  The server already has the authenticated
    // Google identity, so hydrate the local display name once instead of
    // blocking Granola/actions behind an unrelated manual name field.
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
      root.querySelectorAll("[data-role-input]").forEach(function (el) {
        S.roleDrafts[roleDraftKey(el.dataset.roleInput)] = el.value;
      });
      var note = root.querySelector("#rv-note");
      if (note) { S.noteDraft = note.value; S.drafts[String(S.selected)] = note.value; }
      var slack = root.querySelector("#rv-slack-message");
      if (slack) S.slackDrafts[String(S.selected)] = slack.value;
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
      return source === "slack" ? "Slack" : source === "granola" ? "Granola" : "Imported";
    }
    function suggestionSource(item) {
      var source = sourceName(item);
      if (source === "Slack") return '<span class="rv-origin slack">✦ AI · Slack</span>';
      if (source === "Granola") return '<span class="rv-origin granola">✦ AI · Granola</span>';
      return '<span class="rv-origin imported">✦ AI · Imported</span>';
    }

    // ---- queue construction ---------------------------------------------
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
    function ceMeta(ceId) {
      return ((S.headline && S.headline.all_ces) || []).filter(function (ce) { return String(ce.ce_id) === String(ceId); })[0] || {};
    }
    function shortlistState(q) {
      if (reviewedFor(q.ce_id)) return "reviewed";
      var treatment = treatmentFor(q.ce_id);
      if (["live", "async", "follow_up"].indexOf(treatment) >= 0) return "selected";
      if (treatment === "skip") return "skipped";
      return "candidate";
    }
    function queueState(q) {
      var shortlist = shortlistState(q);
      if (shortlist === "reviewed") return "reviewed";
      if (shortlist === "selected") return "in_progress";
      return "needs_review";
    }
    function visibleQueueRows() {
      var needle = String(S.queueQuery || "").trim().toLowerCase();
      return S.queue.filter(function (q) {
        var meta = ceMeta(q.ce_id), state = queueState(q);
        var haystack = [q.ce_name, q.ce_id, q.reason, meta.category, meta.city].join(" ").toLowerCase();
        return (!needle || haystack.indexOf(needle) >= 0) &&
          (S.queueFilter === "all" || state === S.queueFilter) &&
          (!S.queueReason || String(q.reason || "") === S.queueReason) &&
          (!S.queueCategory || String(meta.category || "") === S.queueCategory) &&
          (!S.queueOwner || String(meta.owner || meta.bgm_owner || "") === S.queueOwner) &&
          (!S.queueTaskForce || String(meta.task_force || "") === S.queueTaskForce);
      });
    }

    // ---- data loading (unchanged backend surface) -----------------------
    function refreshHeadline() {
      var h = ctx.getHeadline ? ctx.getHeadline() : null;
      if (!h) return false;
      var changed = h.market_slug !== S.market_slug || h.week_start !== S.week_start;
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
      var id = { market_slug: S.market_slug, week: S.week_start };
      return Promise.all([
        api.reviewSet(id).catch(function () { return { review_set: [] }; }),
        api.receipts({ market_slug: S.market_slug, week: S.week_start }).catch(function () { return { receipts: [] }; }),
        api.work({ market_slug: S.market_slug, week: S.week_start }).catch(function () { return { work_items: [] }; }),
        api.reconciliation({ market_slug:S.market_slug,week_start:S.week_start }).catch(function(){return null;})
      ]).then(function (res) {
        S.setRowsList = (res[0].review_set || []);
        S.setRows = {}; S.setRowsList.forEach(function (r) { S.setRows[String(r.ce_id)] = r; });
        S.receipts = {}; (res[1].receipts || []).forEach(function (r) { S.receipts[String(r.ce_id)] = r; });
        S.work = {}; (res[2].work_items || []).forEach(function (w) { var k = String(w.ce_id); (S.work[k] = S.work[k] || []).push(w); });
        S.reconciliation=res[3]||null;
        buildQueue();
        var selectedCount=S.queue.filter(function(q){return shortlistState(q)==="selected";}).length;track("shortlist_size",{value_number:selectedCount,value_text:String(S.queue.length),idempotency_key:"shortlist:"+S.market_slug+":"+S.week_start+":"+selectedCount});
        if (!S.selected || !S.byId[S.selected]) {
          var firstOpen = S.queue.filter(function (q) { return !reviewedFor(q.ce_id); })[0];
          S.selected = (firstOpen || S.queue[0] || {}).ce_id || null;
        }
        S.loaded = true; render();
        if (S.selected) loadCe(S.selected);
      });
    }
    function loadCe(ceId) {
      ceId=String(ceId);
      if (!api || S.loadingCe[ceId]) return S.loadingCe[ceId] || Promise.resolve();
      if (S.ceLoadedAt[ceId] && Date.now()-S.ceLoadedAt[ceId] < 60000) return Promise.resolve();
      S.loadingCe[ceId] = true;
      var seq=(S.ceRequestSeq[ceId]||0)+1; S.ceRequestSeq[ceId]=seq;
      var controller=typeof AbortController!=="undefined"?new AbortController():null; S.ceControllers[ceId]=controller;
      var requestOptions=controller?{signal:controller.signal}:{};
      var call=Promise.all([
        api.weeklyCommentary({ market_slug: S.market_slug, ce_id: ceId }, "", 8, requestOptions).catch(function () { return { weekly: [] }; }),
        api.suggestions({ market_slug: S.market_slug, ce_id: ceId, week: S.week_start }, false, requestOptions).catch(function () { return { suggestions: [] }; }),
        api.comments({ market_slug: S.market_slug, ce_id: ceId, week: S.week_start }, false, requestOptions).catch(function () { return { comments: [] }; }),
        api.threads({ market_slug:S.market_slug,ce_id:ceId },requestOptions).catch(function(){return {active_thread:null,threads:[]};})
      ]).then(function (res) {
        if(S.ceRequestSeq[ceId]!==seq)return;
        var rows = res[0].weekly || [];
        S.weekly[ceId] = rows.filter(function (r) { return String(r.week_start) === String(S.week_start); })[0] || null;
        S.weeklyHist[ceId] = rows;
        S.suggestions[ceId] = res[1].suggestions || [];
        S.comments[ceId] = res[2].comments || [];
        S.threadRegistry[ceId] = {active:res[3].active_thread||null,threads:res[3].threads||[]};
        S.loadingCe[ceId] = false; delete S.ceControllers[ceId]; S.ceLoadedAt[ceId]=Date.now();
        if (String(S.selected) === String(ceId)) render();
      }).catch(function () { if(S.ceRequestSeq[ceId]===seq)S.loadingCe[ceId] = false; });
      S.loadingCe[ceId]=call; return call;
    }

    function select(ceId) {
      if (S.selected && S.noteDraft != null) S.drafts[String(S.selected)] = S.noteDraft;
      if(S.selected&&String(S.selected)!==String(ceId)&&S.ceControllers[S.selected]){S.ceRequestSeq[S.selected]=(S.ceRequestSeq[S.selected]||0)+1;S.ceControllers[S.selected].abort();delete S.ceControllers[S.selected];S.loadingCe[S.selected]=false;}
      S.selected = String(ceId); S.confirmDelete = false; S.compose = ""; S.editingRole = ""; S.memoryOpen = false; S.queueBrowse = false; S.expandedSuggestion = ""; S.finishReasonOpen=false; S.showAllSuggestions=false;
      S.noteDraft = Object.prototype.hasOwnProperty.call(S.drafts, S.selected) ? S.drafts[S.selected] : null;
      S.editingNote = S.noteDraft != null;
      S.mentionPreview = null; S.threadOperation = ""; S.newThreadReason = ""; S.editingWork = null; S.confirmDeleteWork = null; S.editingComment = null; S.confirmDeleteComment = null;
      syncUrl(S.selected);
      render();
      if (!S.weekly[S.selected] && !S.loadingCe[S.selected]) loadCe(S.selected);
    }

    // ---- render: shell ---------------------------------------------------
    function render() {
      if (!S.headline) { root.innerHTML = ""; return; }
      root.innerHTML = '<div class="rv-layout">' + renderSide() + renderMain() + "</div>" +
        '<div class="rv-toast" id="rv-toast" hidden></div>' + renderMemoryDrawer();
      wire();
      if (S.queueRevealUntil > Date.now() && S.selected) setTimeout(function () { revealQueueSelection(S.selected); }, 0);
      if (S.memoryOpen) setTimeout(openMemory, 0);
    }

    function renderSide() {
      var open = S.queue.filter(function (q) { return !reviewedFor(q.ce_id); }).length;
      var total = S.queue.length, reviewed = total - open;
      var shortlistCounts={candidate:0,selected:0,skipped:0,reviewed:0};S.queue.forEach(function(q){shortlistCounts[shortlistState(q)]++;});
      var needle=String(S.queueQuery||"").trim().toLowerCase();
      var visibleQueue=visibleQueueRows();
      var counts={all:total,needs_review:0,in_progress:0,reviewed:0};S.queue.forEach(function(q){counts[queueState(q)]++;});
      var reasons=Array.from(new Set(S.queue.map(function(q){return String(q.reason||"");}).filter(Boolean))).sort();
      var categories=Array.from(new Set(S.queue.map(function(q){return String(ceMeta(q.ce_id).category||"");}).filter(Boolean))).sort();
      var owners=Array.from(new Set(S.queue.map(function(q){var m=ceMeta(q.ce_id);return String(m.owner||m.bgm_owner||"");}).filter(Boolean))).sort();
      var taskForces=Array.from(new Set(S.queue.map(function(q){return String(ceMeta(q.ce_id).task_force||"");}).filter(Boolean))).sort();
      var rows = visibleQueue.length ? renderQueueGroups(visibleQueue) :
        (needle?'<div class="rv-empty-queue"><strong>No CE matches</strong><span>Try a partial CE name or stable CE ID.</span></div>':
        '<div class="rv-empty-queue"><strong>No CEs flagged this week</strong><span>System flags and CEs you add appear here. ✅</span></div>');
      var picker = S.adding ? renderPicker() : "";
      return '<aside class="rv-side' + (S.queueBrowse ? ' open' : '') + '" aria-label="Review queue">' +
        '<div class="rv-mobile-side-head"><strong>Browse/search CEs</strong><button class="rv-close" type="button" id="rv-close-queue" aria-label="Close CE browser">×</button></div>' +
        '<div class="rv-eyebrow">Weekly review · w/c ' + esc(S.week_start) + "</div>" +
        '<div class="rv-side-head"><h2>' + (open ? open + " CE" + (open === 1 ? "" : "s") + " to review" : "All caught up") + "</h2>" +
        '<button class="rv-addce" type="button" id="rv-add-ce">＋ Add CE</button></div>' +
        '<div class="rv-shortlist-guide" id="rv-shortlist-guide"><strong>' + shortlistCounts.selected + ' selected this week</strong><span>Recommended: 3–5 CEs. The BGM decides.</span></div>' +
        '<div class="rv-subtle" id="rv-progress">' + reviewed + " of " + total + " reviewed · " + shortlistCounts.candidate + " candidates · " + shortlistCounts.skipped + " deferred</div>" +
        '<label class="rv-search"><span class="sr-only">Search CE</span><input id="rv-search-ce" type="search" placeholder="Search CE name or ID" value="'+esc(S.queueQuery||"")+'"><button type="button" id="rv-clear-search" aria-label="Clear CE search"'+(needle?'':' hidden')+'>×</button></label>'+
        '<div class="rv-queue-filters" role="group" aria-label="Filter review status">'+
        [['all','All'],['needs_review','Needs review'],['in_progress','In progress'],['reviewed','Reviewed']].map(function(f){return '<button type="button" class="rv-filter-chip'+(S.queueFilter===f[0]?' active':'')+'" data-queue-filter="'+f[0]+'">'+f[1]+' <span>'+counts[f[0]]+'</span></button>';}).join('')+'</div>'+
        '<div class="rv-queue-selects"><select id="rv-reason-filter" aria-label="Filter by review reason"><option value="">All reasons</option>'+reasons.map(function(v){return '<option'+(S.queueReason===v?' selected':'')+'>'+esc(v)+'</option>';}).join('')+'</select>'+
        '<select id="rv-category-filter" aria-label="Filter by category"><option value="">All categories</option>'+categories.map(function(v){return '<option'+(S.queueCategory===v?' selected':'')+'>'+esc(v)+'</option>';}).join('')+'</select>'+
        (owners.length?'<select id="rv-owner-filter" aria-label="Filter by owner"><option value="">All owners</option>'+owners.map(function(v){return '<option'+(S.queueOwner===v?' selected':'')+'>'+esc(v)+'</option>';}).join('')+'</select>':'')+
        (taskForces.length?'<select id="rv-task-force-filter" aria-label="Filter by task force"><option value="">All task forces</option>'+taskForces.map(function(v){return '<option'+(S.queueTaskForce===v?' selected':'')+'>'+esc(v)+'</option>';}).join('')+'</select>':'')+'</div>'+
        '<div class="rv-queue-label">Review queue</div>' + picker +
        '<div class="rv-queue-panel" id="rv-queue-review">' + rows + "</div></aside>";
    }
    function renderQueueGroups(rows){
      var labels={selected:"Selected this week",candidate:"Candidates",skipped:"Skipped / deferred",reviewed:"Reviewed"};
      var groups={selected:[],candidate:[],skipped:[],reviewed:[]};
      rows.forEach(function(q){groups[shortlistState(q)].push(q);});
      return ["selected","candidate","skipped","reviewed"].map(function(key){
        if(!groups[key].length)return "";
        return '<section class="rv-queue-group rv-queue-'+key+'"><div class="rv-queue-group-head"><span>'+labels[key]+'</span><span>'+groups[key].length+'</span></div>'+groups[key].map(queueRow).join("")+'</section>';
      }).join("");
    }
    function queueRow(q) {
      var reviewed = reviewedFor(q.ce_id), active = String(q.ce_id) === String(S.selected), t = treatmentFor(q.ce_id);
      var openN = openWorkFor(q.ce_id).length;
      var shortlist=shortlistState(q),shortlistLabel=shortlist==="selected"?"Selected":shortlist==="skipped"?"Deferred":shortlist==="reviewed"?"Reviewed":"Candidate";
      var tags = '<span class="rv-chip' + (reviewed ? " done" : "") + '">' + esc(shortlistLabel) + "</span>" +
        (openN ? '<span class="rv-chip">' + openN + " open</span>" : "") +
        (q.source === "manual" ? '<span class="rv-chip">manual</span>' : "");
      var details = '<button class="rv-ce-details" type="button" data-open-drawer-ce="' + esc(q.ce_id) + '" aria-label="Open ' + esc(q.ce_name) + ' details">↗</button>';
      var remove = q.source === "manual" ? '<button class="rv-ce-remove" type="button" data-remove-ce="' + esc(q.ce_id) + '" aria-label="Remove ' + esc(q.ce_name) + ' from review set">×</button>' : "";
      return '<div class="rv-ce-row-wrap">' +
        '<button class="rv-ce-row' + (active ? " active" : "") + (reviewed ? " reviewed" : "") + '" type="button" data-select-ce="' + esc(q.ce_id) + '">' +
        '<span class="rv-dot"></span><span class="rv-ce-copy"><strong>' + esc(q.ce_name) + "</strong>" +
        "<small>" + esc(q.reason) + ' · CE ' + esc(q.ce_id) + '</small><span class="rv-ce-tags">' + tags + "</span></span></button>" + details + remove + "</div>";
    }
    function renderProcessPanel() {
      return '<div class="rv-process" id="rv-process-panel">' +
        '<div class="rv-process-head">Paste a meeting’s notes or transcript. Claude extracts commentary and action items per CE — you approve each on the CE.</div>' +
        '<textarea id="rv-process-text" placeholder="Paste the Granola meeting notes / transcript for this market…"></textarea>' +
        (S.processSummary ? '<div class="rv-process-summary">' + S.processSummary + "</div>" : "") +
        '<div class="rv-process-foot"><button class="rv-btn small" type="button" id="rv-process-cancel">Close</button>' +
        '<button class="rv-btn small primary" type="button" id="rv-process-run">Extract &amp; distribute</button></div></div>';
    }
    function renderPicker() {
      return '<div class="rv-picker" id="rv-picker"><input id="rv-picker-input" type="search" placeholder="Add a CE to this week’s review…" value="' + esc(S.pickerQuery || "") + '">' +
        '<input id="rv-nomination-reason" type="text" placeholder="Nomination reason (required)" value="'+esc(S.nominationReason||"")+'">'+
        '<div class="rv-picker-results" id="rv-picker-results">' + renderPickerResults() + "</div></div>";
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
      var q = S.byId[S.selected];
      if (!q) return '<main class="rv-main"><div class="rv-workspace"><div class="rv-empty-state"><strong>Nothing to review</strong>' +
        "<span>No CE is flagged this week. Use ＋ Add CE to pull one in.</span></div></div></main>";
      var t = treatmentFor(q.ce_id), reviewed = reviewedFor(q.ce_id), blockers=completionBlockers(q),treatmentHelp={live:"Discuss together now; finish after the live review.",async:"Collect input asynchronously and finish when follow-through is clear.",follow_up:"Use this CE only to close or advance existing work.",skip:"Defer this CE for the week; record remains in the queue.",not_scheduled:"Choose the review path before finishing."}[t];
      var receipt = reviewed
        ? '<span class="rv-receipt done">✓ Reviewed by ' + esc((S.receipts[q.ce_id] || {}).reviewer || author() || "BGM") + "</span>"
        : !blockers.length ? '<span class="rv-receipt">Ready to finish</span>'
          : '<span class="rv-receipt">'+blockers.length+' item'+(blockers.length===1?'':'s')+' to resolve</span>';
      return '<main class="rv-main">' +
        '<div class="rv-mobile-current"><span><strong>'+esc(q.ce_name)+'</strong><small>CE '+esc(q.ce_id)+' · '+esc(TREATMENT_LABELS[t]||t)+'</small></span><button class="rv-btn" type="button" id="rv-browse-ces">Browse/search CEs</button></div>'+
        '<header class="rv-detail-head"><div class="rv-breadcrumb"><button class="rv-link" type="button" data-open-drawer-ce="' + esc(q.ce_id) + '">CE ' + esc(q.ce_id) + "</button> · " + esc(S.market) + "</div>" +
        '<div class="rv-title-line"><div><h1><button class="rv-title-link" type="button" data-open-drawer-ce="' + esc(q.ce_id) + '">' + esc(q.ce_name) + "</button></h1>" +
        "<p>Record what you know, decide the follow-through, and mark it reviewed.</p></div>" +
        '<div class="rv-button-row"><button class="rv-btn" type="button" id="rv-open-drawer">Open CE drawer</button></div></div>' +
        '<div class="rv-treatment-block"><div class="rv-step-line"><span class="rv-step">1</span><div><strong>Decide how to review</strong><span>'+esc(treatmentHelp)+'</span></div></div><div class="rv-status-line"><label for="rv-treatment">Review path</label>' +
        '<select class="rv-select" id="rv-treatment" aria-label="Review treatment">' +
        TREATMENT_ORDER.map(function (v) { return '<option value="' + v + '"' + (v === t ? " selected" : "") + ">" + esc(TREATMENT_LABELS[v]) + "</option>"; }).join("") +
        "</select>" + receipt + "</div></div></header>" +
        '<div class="rv-workspace">' + renderCommentaryCard(q) + renderActionsCard(q) + renderReconciliationCard(q) + renderMemoryRail(q) +
        (S.processing ? renderProcessPanel() : "") +
        '<div class="rv-resource-state">Saved to Review history · CE ' + esc(q.ce_id) + "</div></div>" +
        renderFinishBar(q,blockers,reviewed) + renderGranolaDock() +
        '<div class="rv-foot-actions"><button class="rv-btn" type="button" id="rv-next-ce">Next unreviewed →</button>' +
        '<button class="rv-btn primary" type="button" id="rv-finish"' + (blockers.length || reviewed ? " disabled" : "") + ">" +
        (reviewed ? "Reviewed ✓" : "Finish CE review") + "</button></div></footer></main>";
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
    function renderFinishBar(q,blockers,reviewed){
      var weekly=S.weekly[q.ce_id]||{},reason=S.noDiscussionDrafts[q.ce_id]||"";
      var list=reviewed?'<span class="rv-finish-state done">✓ Reviewed</span>':(!blockers.length?'<span class="rv-finish-state ready">Ready to finish</span>':'<div class="rv-finish-checks" aria-label="Items required to finish">'+blockers.map(function(b){return '<button type="button" class="rv-finish-check" data-resolve="'+b.key+'"><span aria-hidden="true">○</span>'+esc(b.label)+'</button>';}).join("")+'</div>');
      var reasonBox=!weekly.slack_post_ts&&S.finishReasonOpen?'<label class="rv-finish-reason" for="rv-no-discussion-reason"><span>Why is Slack not needed?</span><input id="rv-no-discussion-reason" value="'+esc(reason)+'" placeholder="Concise reason required"><button class="rv-btn small" id="rv-save-finish-reason" type="button">Use reason</button></label>':'';
      return '<footer class="rv-footer"><div class="rv-finish-copy"><strong>Finish review</strong>'+list+reasonBox+'</div>';
    }

    function roleMeta(role) {
      return role === "performance" ? {label:"Performance note",key:"performance_note",author:"performance_author",updated:"performance_updated_at",deleted:"performance_note_deleted_at"} :
        role === "bdm" ? {label:"BDM note",key:"bdm_note",author:"bdm_author",updated:"bdm_updated_at",deleted:"bdm_note_deleted_at"} :
        {label:"BGM note",key:"bgm_note",author:"bgm_author",updated:"bgm_updated_at",deleted:"note_deleted_at"};
    }
    function roleDraftKey(role){return String(S.selected)+":"+role;}
    function renderRoleNote(weekly,role){
      var m=roleMeta(role),saved=!!(weekly&&weekly[m.key]&&!weekly[m.deleted]),editing=S.editingRole===role;
      var draftKey=roleDraftKey(role),hasDraft=Object.prototype.hasOwnProperty.call(S.roleDrafts,draftKey),val=hasDraft?S.roleDrafts[draftKey]:(saved?weekly[m.key]:"");
      if(role!=="bgm"&&!saved)return "";
      if(role!=="bgm"&&saved)return '<details class="rv-role-note rv-role-readonly"><summary><span><strong>'+esc(m.label)+'</strong><small>Historical · read-only · '+esc(weekly[m.author]||"Unknown author")+'</small></span><span aria-hidden="true">⌄</span></summary><div class="rv-note-text">'+esc(weekly[m.key])+'</div></details>';
      if(role==="bgm"&&!saved&&!editing&&!hasDraft)return '<button class="rv-role-collapsed" type="button" data-role-open="bgm" aria-expanded="false"><span><strong>Add optional BGM observation</strong><small>Use only for useful context not already captured in Slack.</small></span><span aria-hidden="true">＋</span></button>';
      if(!editing&&saved)return '<div class="rv-role-note" data-role-note="'+role+'"><div class="rv-note-top"><span class="rv-note-name">'+esc(m.label)+'</span><span class="rv-note-metatxt">'+esc(weekly[m.author]||"Unknown author")+' · '+esc(weekly[m.updated]?fmtWhen(weekly[m.updated]):"saved")+'</span><span class="rv-note-links"><button class="rv-link" type="button" data-role-edit="'+role+'">Edit</button><button class="rv-link danger" type="button" data-role-delete="'+role+'">Delete</button></span></div><div class="rv-note-text">'+esc(weekly[m.key])+'</div></div>';
      return '<div class="rv-role-note rv-note-edit" data-role-note="'+role+'"><label class="rv-field-label" for="rv-note-'+role+'">'+esc(m.label)+'</label><textarea id="rv-note-'+role+'" data-role-input="'+role+'" placeholder="Add '+esc(m.label.toLowerCase())+' for this CE and week">'+esc(val)+'</textarea><div class="rv-note-foot"><span class="hint">Saved independently with author and timestamp.</span><div class="rv-note-actions">'+((editing||hasDraft)?'<button class="rv-btn small" type="button" data-role-cancel="'+role+'">Cancel</button>':'')+'<button class="rv-btn small primary" type="button" data-role-save="'+role+'">Save '+esc(m.label)+'</button></div></div></div>';
    }
    function renderWeeklySummary(weekly){
      if(!weekly||!weekly.slack_post_ts)return "";
      var approved=String(weekly.summary_status||"")==="approved",raw=approved?(weekly.summary_approved_json||weekly.summary_json):(weekly.summary_draft_json||""),summary=null;try{summary=raw?JSON.parse(raw):null;}catch(e){}
      function group(label,rows){return rows&&rows.length?'<div class="rv-sum-group"><span class="rv-sum-label">'+label+'</span><ul>'+rows.map(function(row){return '<li>'+esc(typeof row==="string"?row:(row.text||row.body||""))+'</li>';}).join("")+'</ul></div>':"";}
      var delayed=weekly.sync_status==="summary_delayed",pending=String(weekly.summary_status)==="pending",rejected=String(weekly.summary_status)==="rejected",status=delayed?"Summary delayed · Slack replies remain available":
        (approved?"Approved by "+(weekly.summary_approved_by||"BGM")+" · "+fmtWhen(weekly.summary_approved_at||weekly.summary_updated_at):(pending?"Draft summary awaiting BGM approval":(rejected?"Draft summary rejected":"Waiting for replies")));
      var content=summary?(group("Findings",summary.findings)+group("Decisions",summary.decisions)+group("Open points",summary.open_points)):"";
      return '<div class="rv-summary-surface'+(approved?' approved':'')+'"><div class="rv-summary-title"><div><span class="rv-origin slack">Slack</span><strong>'+(approved?'Approved discussion summary':'Draft discussion summary')+'</strong></div><span class="rv-attention-chip '+(approved?'approved':'')+'">'+(approved?'Approved':'Needs BGM approval')+'</span></div>'+
        '<div class="rv-sync-status'+(delayed?' delayed':'')+'"><span class="rv-live-dot"></span>'+esc(status)+'</div>'+
        (content?'<div class="rv-summary">'+content+'</div>':'<div class="rv-summary rv-summary-empty">No summary is available yet. Slack replies remain available at source.</div>')+
        (pending?'<div class="rv-summary-actions"><button class="rv-btn small primary" id="rv-summary-approve" type="button">Approve summary</button><details class="rv-summary-approval"><summary class="rv-btn small">Edit</summary><textarea id="rv-summary-draft">'+esc(raw)+'</textarea></details><button class="rv-btn small" id="rv-summary-reject" type="button">Dismiss</button><button class="rv-link" id="rv-summary-regenerate" type="button">Regenerate</button></div>':'')+'</div>';
    }
    function renderCommentaryCard(q){
      var weekly=S.weekly[q.ce_id]||{},hasWeekActivity=!!weekly.slack_post_ts,registry=S.threadRegistry[q.ce_id]||{},binding=registry.active||null,hasBinding=!!binding,slackKey=String(q.ce_id),slackText=S.slackDrafts[slackKey]||"";
      var thread=hasWeekActivity?'<div class="rv-thread-compact rv-thread-visible"><div class="rv-thread-status"><span><strong>Current Slack discussion</strong><small>'+(weekly.summary_updated_at?'Summary updated '+esc(fmtWhen(weekly.summary_updated_at)):'Waiting for replies')+'</small></span><span class="rv-status-chip">Active</span></div><div class="rv-thread"><a class="rv-btn small primary" href="'+esc(weekly.slack_post_permalink||binding&&binding.slack_permalink||"#")+'" target="_blank" rel="noopener">Open / continue thread ↗</a><button class="rv-btn small" type="button" id="rv-new-slack">Start new</button><button class="rv-btn small ghost" type="button" id="rv-sync-thread">Refresh summary</button></div>'+renderWeeklySummary(weekly)+'</div>':'';
      var priorChoice=!hasWeekActivity&&hasBinding?'<div class="rv-thread-choice"><div><strong>Existing CE discussion found</strong><span>Use the durable CE thread'+(binding.slack_permalink?' · <a href="'+esc(binding.slack_permalink)+'" target="_blank" rel="noopener">Open thread ↗</a>':'')+'</span></div><div class="rv-note-actions"><button class="rv-btn small primary" type="button" id="rv-continue-slack">Continue in Slack</button><button class="rv-btn small" type="button" id="rv-new-slack">Start new discussion</button></div></div>':'';
      var newThread=S.threadOperation==="new_parent"?'<div class="rv-new-thread-choice"><label class="rv-field-label" for="rv-new-thread-reason">Why start a new discussion?</label><input id="rv-new-thread-reason" value="'+esc(S.newThreadReason||"")+'" placeholder="Issue, owner, scope, or channel changed (required)"><div class="rv-note-actions"><button class="rv-link" type="button" id="rv-new-thread-cancel">Cancel</button><button class="rv-btn small primary" type="button" id="rv-start-slack">Preview new Slack post</button></div></div>':'';
      var normalStart=!hasWeekActivity&&!hasBinding?'<button class="rv-btn small primary" type="button" id="rv-start-slack"'+(S.mentionBusy?' disabled':'')+'>'+(S.mentionBusy?'Resolving names…':'Start Slack discussion')+'</button>':'';
      var canCompose=!hasWeekActivity||S.threadOperation==="new_parent"||S.threadOperation==="continue";
      var composer='<div class="rv-slack-composer"><label class="rv-field-label" for="rv-slack-message">Slack discussion</label><div class="rv-channel-preview">Will post to #'+esc((S.channel&&S.channel.name)||"unconfigured")+'</div>'+priorChoice+newThread+(canCompose?'<textarea id="rv-slack-message" placeholder="Write a discussion starter. This will not change the BGM observation.">'+esc(slackText)+'</textarea>'+renderMentionPreview():'')+'<div class="rv-note-actions">'+normalStart+'</div>'+thread+'</div>';
      return '<section class="rv-flow-section rv-discussion-module" id="rv-discussion-section"><div class="rv-module-head"><span class="rv-module-icon" aria-hidden="true">↗</span><div><div class="rv-card-title">Discussion highlights</div><div class="rv-card-sub">What the team discussed, what needs BGM approval, and the source thread.</div></div></div><div class="rv-module-surface"><div class="rv-card-body rv-role-notes">'+composer+'</div></div><div class="rv-optional-notes"><span class="rv-section-label">Optional context &amp; history</span>'+renderRoleNote(weekly,"bgm")+renderRoleNote(weekly,"performance")+renderRoleNote(weekly,"bdm")+'</div></section>';
    }

    function normalizedSuggestionBody(s) {
      return String((s && s.body) || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim().replace(/\s+/g, " ");
    }
    function renderReconciliationCard(q){
      var r=S.reconciliation;if(!r)return "";
      function count(key){return (r[key]||[]).filter(function(row){return !row.ce_id||String(row.ce_id)===String(q.ce_id);}).length;}
      var rows=[["Completed since prior cycle",count("completed_since_prior")],["Open",count("open")],["Blocked / overdue",count("blocked_overdue")],["Carried forward",count("carried_forward")],["Evidence suggests completion",count("evidence_suggesting_completion")],["Revisit required",count("revisit_required")]];
      return '<details class="rv-card rv-reconciliation"><summary><span><strong>Monday reconciliation</strong><small>Read-only work projection · no metric attribution</small></span><span aria-hidden="true">⌄</span></summary><div class="rv-card-body"><div class="rv-recon-grid">'+rows.map(function(x){return '<span><strong>'+x[1]+'</strong>'+esc(x[0])+'</span>';}).join("")+'</div><p class="hint">'+esc((r.later_economic_outcome||{}).reason||"Later economic outcome is unavailable.")+'</p></div></details>';
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

    function renderLegacyCommentaryCard(q) {
      var weekly = S.weekly[q.ce_id];
      var sugg = (S.suggestions[q.ce_id] || []).filter(function (s) {
        return (s.kind === "comment" || !s.kind) && String(s.source_type || "granola") === "granola";
      });
      var pending = dedupeSuggestions(sugg.filter(function (s) { return !s.decided_at && (s.status || "pending") === "pending"; }));
      var accepted = (S.comments[q.ce_id] || []).filter(function (c) { return !c.deleted_at && String(c.source_type || "") === "granola"; });
      var pendingHtml = pending.map(function (s) {
        return '<div class="rv-sugg" data-suggestion="' + esc(s.suggestion_id) + '" data-kind="comment">' +
          '<div class="rv-sugg-meta">' + suggestionSource(s) + '<span>·</span><span>' + esc(s.source_ref || s.source_author || "meeting") + "</span></div>" +
          '<textarea class="rv-sugg-edit" data-sugg-body aria-label="Edit suggested commentary">' + esc(s.body || "") + "</textarea>" +
          '<div class="rv-sugg-actions"><button class="rv-btn small primary" type="button" data-sugg-accept>Add to commentary</button>' +
          '<button class="rv-btn small" type="button" data-sugg-ignore>Ignore</button></div></div>';
      }).join("");
      var acceptedHtml = accepted.map(renderImportedComment).join("");

      var hasNote = !!(weekly && weekly.bgm_note && !weekly.note_deleted_at);
      var hasThread = !!(weekly && weekly.slack_post_ts);
      var noteAuthor = (weekly && weekly.bgm_author) || author() || "BGM";
      var summary = (function () { try { return weekly && weekly.summary_json ? JSON.parse(weekly.summary_json) : null; } catch (e) { return null; } })();
      function sumList(label, arr) {
        if (!arr || !arr.length) return "";
        return '<div class="rv-sum-group"><span class="rv-sum-label">' + label + "</span><ul>" +
          arr.map(function (x) { return "<li>" + esc(typeof x === "string" ? x : (x.text || x.body || "")) + "</li>"; }).join("") + "</ul></div>";
      }
      var summaryInner = summary ? (sumList("Findings", summary.findings) + sumList("Decisions", summary.decisions) + sumList("Open points", summary.open_points)) : "";
      var syncLabel = weekly && weekly.summary_updated_at ? "Updated " + fmtWhen(weekly.summary_updated_at) : "Waiting for replies";
      var delayed = weekly && weekly.sync_status === "summary_delayed";
      if (delayed) syncLabel = "Summary delayed · source replies remain in Slack";
      var threadStrip = hasThread ? '<div class="rv-thread-wrap"><div class="rv-thread">' + avatar("Slack", "sm") +
        '<div class="rv-thread-copy"><strong>CE Slack thread</strong><span>Discussion happens in Slack; replies are summarized back here, source-linked.</span></div>' +
        '<a class="rv-btn small ghost" href="' + esc(weekly.slack_post_permalink || "#") + '" target="_blank" rel="noopener">Open thread ↗</a>' +
        '<button class="rv-btn small" type="button" id="rv-sync-thread">Summarize now</button></div>' +
        '<div class="rv-sync-status' + (delayed ? " delayed" : "") + '"><span class="rv-live-dot"></span>Summarize now · Automatic sync every 5 minutes once Slack is connected · ' + esc(syncLabel) + "</div>" +
        (summaryInner ? '<div class="rv-summary"><div class="rv-summary-head">' + suggestionSource({ source_type: "slack" }) + '<span>Thread summary · source-linked</span></div>' + summaryInner + "</div>"
          : '<div class="rv-summary rv-summary-empty">Replies will be summarized here automatically once the team responds in Slack.</div>') +
        "</div>" : "";

      var noteBlock;
      if (hasNote && !S.editingNote) {
        var links = S.confirmDelete
          ? '<button class="rv-link danger" type="button" id="rv-del-yes">Confirm delete</button><button class="rv-link" type="button" id="rv-del-no">Cancel</button>'
          : '<button class="rv-link" type="button" id="rv-edit-note">Edit</button><button class="rv-link danger" type="button" id="rv-delete-note">Delete</button>';
        noteBlock = '<div class="rv-note"><div class="rv-note-read">' + avatar(noteAuthor) +
          '<div class="rv-note-body"><div class="rv-note-top"><span class="rv-note-name">' + esc(noteAuthor) + " · BGM</span>" +
          '<span class="rv-note-metatxt">' + esc(weekly.bgm_updated_at ? fmtWhen(weekly.bgm_updated_at) : "saved") + " · original</span>" +
          '<span class="rv-note-links">' + links + "</span></div>" +
          '<div class="rv-note-text">' + esc(weekly.bgm_note) + "</div>" +
          (hasThread ? "" : '<div class="rv-note-foot"><span class="hint"></span><div class="rv-note-actions"><button class="rv-btn small ghost" type="button" id="rv-start-slack">Start Slack discussion</button></div></div>') +
          "</div></div>" + threadStrip + "</div>";
      } else {
        var val = S.noteDraft != null ? S.noteDraft : (hasNote ? weekly.bgm_note : "");
        noteBlock = '<div class="rv-note rv-note-edit">' +
          (author() ? "" : '<input class="rv-note-author" id="rv-author" placeholder="Your name">') +
          '<textarea id="rv-note" placeholder="What is happening with this CE that the data can’t see?">' + esc(val) + "</textarea>" +
          renderMentionPreview() +
          '<div class="rv-note-foot"><span class="hint">Mention names naturally. You’ll preview resolved Slack tags before posting.</span>' +
          '<div class="rv-note-actions">' + (hasNote ? '<button class="rv-btn small" type="button" id="rv-cancel-note">Cancel</button>' : "") +
          '<button class="rv-btn small" type="button" id="rv-save-note">Save note</button>' +
          '<button class="rv-btn small primary" type="button" id="rv-start-slack"' + (S.mentionBusy ? " disabled" : "") + ">" + (S.mentionBusy ? "Resolving names…" : (hasThread ? "Open thread ↗" : "Preview Slack post")) + "</button></div></div>" +
          threadStrip + "</div>";
      }
      return '<section class="rv-card"><div class="rv-card-head"><span class="rv-step">1</span>' +
        '<div class="rv-card-headings"><div class="rv-card-title">Commentary &amp; observations</div>' +
        '<div class="rv-card-sub">One BGM note; discussion happens in Slack and is summarized back here — each stays source-attributed</div></div>' +
        '<span class="rv-card-count">' + (hasNote ? "BGM note saved" : "No note yet") + "</span></div>" +
        '<div class="rv-card-body">' + pendingHtml + acceptedHtml + noteBlock + "</div></section>";
    }

    function renderGranolaDock() {
      // Keep this visible, but do not offer a broken control across markets:
      // the Granola workspace key still needs verified note access. The
      // underlying extractor stays isolated in Preview until then.
      return '<div class="rv-granola-wip" role="note"><strong>Granola meeting</strong><span>WIP · meeting access is being connected</span></div>';
    }

    function renderImportedComment(c) {
      if (String(S.editingComment || "") === String(c.comment_id)) {
        return '<div class="rv-note rv-imported-comment" data-comment="' + esc(c.comment_id) + '"><div class="rv-sugg-meta">' + suggestionSource(c) + '<span>Accepted commentary</span></div>' +
          '<textarea class="rv-sugg-edit" data-comment-body>' + esc(c.body || "") + '</textarea><div class="rv-sugg-actions">' +
          '<button class="rv-btn small" type="button" data-comment-edit-cancel>Cancel</button><button class="rv-btn small primary" type="button" data-comment-save="' + esc(c.comment_id) + '">Save changes</button></div></div>';
      }
      return '<div class="rv-note rv-imported-comment"><div class="rv-note-read">' + avatar("Granola") +
        '<div class="rv-note-body"><div class="rv-note-top"><span class="rv-note-name">Meeting pointer</span><span class="rv-note-metatxt">' + suggestionSource(c) + " · " + esc(fmtWhen(c.updated_at || c.created_at)) + '</span>' +
        '<span class="rv-note-links">' + (String(S.confirmDeleteComment || "") === String(c.comment_id)
          ? '<span class="rv-delete-confirm">Delete?<button class="rv-link danger" type="button" data-comment-delete-confirm="' + esc(c.comment_id) + '">Confirm</button><button class="rv-link" type="button" data-comment-delete-cancel>Cancel</button></span>'
          : '<button class="rv-link" type="button" data-comment-edit="' + esc(c.comment_id) + '">Edit</button><button class="rv-link danger" type="button" data-comment-delete="' + esc(c.comment_id) + '">Delete</button>') + '</span></div>' +
        '<div class="rv-note-text">' + esc(c.body || "") + "</div>" + (c.source_url ? '<a class="rv-source-link" href="' + esc(c.source_url) + '" target="_blank" rel="noopener">Open Granola source ↗</a>' : "") + "</div></div></div>";
    }

    function renderMentionPreview() {
      var p = S.mentionPreview;
      if (!p) return "";
      var matches = p.matches || [], ambiguous = p.ambiguous || [];
      var resolved = matches.length ? '<div class="rv-mention-ok"><strong>Will tag</strong>' + matches.map(function (m) {
        return '<span class="rv-person-chip">@' + esc(m.name || m.slack_user_id) + "</span>";
      }).join("") + "</div>" : '<div class="rv-mention-neutral">No names were matched. You can still post without tags.</div>';
      var blocked = ambiguous.length ? '<div class="rv-mention-ambiguous"><strong>Clarify before posting</strong>' + ambiguous.map(function (a) {
        var names = (a.candidates || []).map(function (c) { return c.name; }).filter(Boolean).join(" or ");
        return '<span>“' + esc(a.name) + '” matches ' + esc(names || "more than one person") + ". Use their full Slack name.</span>";
      }).join("") + "</div>" : "";
      var operation=S.threadOperation==="new_parent"?"New parent discussion":S.threadOperation==="continue"?"Continue existing discussion":"Start Slack discussion";
      return '<div class="rv-mention-preview" aria-live="polite"><div class="rv-mention-title"><span>Slack post preview</span><button class="rv-link" type="button" id="rv-mention-cancel">Edit message</button></div>' +
        '<div class="rv-mention-neutral"><strong>'+esc(operation)+'</strong><span>#'+esc((S.channel&&S.channel.name)||"unconfigured")+(S.threadOperation==="new_parent"?' · prior thread remains in CE Memory':'')+'</span></div>'+resolved + blocked + '<div class="rv-mention-message">' + esc(p.original_text || "") + "</div>" +
        '<div class="rv-mention-actions"><button class="rv-btn small primary" type="button" id="rv-confirm-slack"' + (ambiguous.length ? " disabled" : "") + '>Post to Slack</button></div></div>';
    }

    function renderActionsCard(q) {
      var sugg = (S.suggestions[q.ce_id] || []).filter(function (s) { return s.kind === "action" || s.kind === "check" || s.kind === "comment" || !s.kind; });
      var pending = dedupeSuggestions(sugg.filter(function (s) { return !s.decided_at && (s.status || "pending") === "pending"; }));
      var allWork = workFor(q.ce_id),openAll=allWork.filter(function(w){return CLOSED.indexOf(w.status)<0&&!w.archived_at;}),doneAll=allWork.filter(function(w){return CLOSED.indexOf(w.status)>=0&&!w.archived_at;});
      var laterItems=openAll.filter(function(w){return w.kind==="check"||String(w.carry_forward)==="true";}),openItems=openAll.filter(function(w){return laterItems.indexOf(w)<0;}),visibleSuggestions=S.showAllSuggestions?pending:pending.slice(0,3);
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
      var doneHtml = doneAll.length ? '<details class="rv-done"><summary>Completed · ' + doneAll.length + " recent</summary>" +
        '<div class="rv-done-list">' + doneAll.slice(0,8).map(workRow).join("") + "</div></details>" : "";
      var emptyState = (openItems.length || laterItems.length || suggHtml || S.compose) ? "" :
        '<div class="rv-empty-state" style="margin-top:12px"><strong>No follow-through yet</strong><span>Add an action or schedule a check when the discussion creates work.</span></div>';
      var composer = S.compose ? renderCompose(S.compose) : "";
      var count = openAll.length ? openAll.length + " active" : (allWork.length ? "All done" : "No work yet");
      var tabs=[['needs','Needs review',pending.length],['open','Open',openItems.length],['later','Later',laterItems.length],['completed','Completed',doneAll.length]];
      var active=S.workTab||'needs',panel=active==='needs'?(suggHtml+(pending.length>3?'<button class="rv-link rv-see-more" type="button" id="rv-more-suggestions">'+(S.showAllSuggestions?'Show fewer':'See '+(pending.length-3)+' more')+'</button>':'')):active==='open'?(openHtml||'<div class="rv-empty-state"><strong>No open work</strong><span>Approved actions will appear here.</span></div>'):active==='later'?(laterHtml||'<div class="rv-empty-state"><strong>Nothing scheduled</strong><span>Checks and explicit carry-forward items will appear here.</span></div>'):(doneHtml||'<div class="rv-empty-state"><strong>No completed work</strong><span>Recent completed items will appear here.</span></div>');
      return '<section class="rv-flow-section rv-actions-module" id="rv-actions-section"><div class="rv-module-head"><span class="rv-module-icon attention" aria-hidden="true">✓</span><div class="rv-card-headings"><div class="rv-card-title">Actions &amp; follow-ups</div><div class="rv-card-sub">Review suggestions separately from work the team has already committed to.</div></div><span class="rv-card-count">'+count+'</span></div>' +
        '<div class="rv-source-bridge"><span aria-hidden="true">↓</span><strong>'+pending.length+' follow-up'+(pending.length===1?'':'s')+' suggested from this Slack discussion</strong></div><div class="rv-action-surface"><p class="rv-focus-summary">'+esc(focus)+'</p><div class="rv-action-tabs" role="tablist">'+tabs.map(function(t){return '<button type="button" role="tab" class="rv-action-tab'+(active===t[0]?' active':'')+'" aria-selected="'+(active===t[0]?'true':'false')+'" data-work-tab="'+t[0]+'">'+t[1]+' <span>'+t[2]+'</span></button>';}).join('')+'</div><div class="rv-action-panel">'+panel+emptyState+'</div>' +
        composer +
        '<div class="rv-add-row"><button class="rv-btn ghost small" type="button" id="rv-add-action">＋ Add action</button><button class="rv-btn ghost small" type="button" id="rv-add-check">＋ Schedule check</button></div></div></section>';
    }
    function workRow(w) {
      var done = CLOSED.indexOf(w.status) >= 0, isCheck = w.kind === "check";
      var src = w.source_type === "granola" ? "Granola" : w.source_type === "slack" ? "Slack" : w.source_type === "bgm_manual" ? "Manual" : (w.source_type || "");
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
        '<div class="rv-work-meta">' + meta + "</div>" +(unmanaged?'<button class="rv-work-requirement" type="button" data-work-edit="'+esc(w.work_id)+'">Add owner/date or carry forward to finish</button>':'')+
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
        '<label class="rv-checkline"><input type="checkbox" data-edit-carry'+(String(w.carry_forward)==="true"?' checked':'')+'> Explicitly carry this unresolved item into the next review</label>'+
        '<div class="rv-work-edit-actions"><button class="rv-btn small" type="button" data-work-edit-cancel>Cancel</button>' +
        '<button class="rv-btn small primary" type="button" data-work-edit-save="' + esc(w.work_id) + '">Save changes</button></div></div></div>';
    }
    function renderCompose(kind) {
      var isCheck = kind === "check";
      return '<div class="rv-compose" style="display:block"><div class="row1"><input type="text" id="rv-c-text" placeholder="' + (isCheck ? "What should we revisit next week?" : "What needs to happen?") + '"></div>' +
        '<div class="row2"><input type="text" id="rv-c-owner" placeholder="' + (isCheck ? "Owner (optional)" : "Owner") + '">' +
        '<input type="date" id="rv-c-due">' +
        '<select class="rv-select" id="rv-c-status">' + optionList(isCheck ? CHECK_STATUS : WORK_STATUS, isCheck ? "scheduled" : "needs_action") + "</select></div>" +
        '<div class="foot"><button class="rv-btn small" type="button" id="rv-c-cancel">Cancel</button>' +
        '<button class="rv-btn small primary" type="button" id="rv-c-save">' + (isCheck ? "Schedule check" : "Create action") + "</button></div></div>";
    }
    function renderMemoryRail() {
      return '<button class="rv-memory-rail" type="button" id="rv-open-memory"><span class="rv-memory-icon">↺</span>' +
        '<span class="rv-memory-copy"><strong>CE Memory</strong><span>Past weekly notes, work and source history for this CE</span></span><span class="rv-arrow">→</span></button>';
    }
    function renderMemoryDrawer() {
      return '<div class="rv-drawer-wrap" id="rv-memory-drawer" hidden><div class="rv-drawer" role="dialog" aria-modal="true">' +
        '<header class="rv-drawer-head"><div><div class="rv-eyebrow" id="rv-memory-eyebrow"></div><h2 id="rv-memory-title">CE Memory</h2>' +
        "<p>Original weekly records and work history.</p></div><button class=\"rv-close\" id=\"rv-close-memory\" type=\"button\" aria-label=\"Close\">×</button></header>" +
        '<div class="rv-drawer-body" id="rv-memory-body">'+renderMemoryLoading()+'</div></div></div>';
    }
    function renderMemoryLoading() {
      return '<div class="rv-memory-tabs" aria-hidden="true"><button class="rv-memory-tab active" disabled>Story</button><button class="rv-memory-tab" disabled>Work</button><button class="rv-memory-tab" disabled>Historical comments</button><button class="rv-memory-tab" disabled>Perf history</button></div><div class="rv-memory-loading" role="status" aria-live="polite"><div class="rv-skeleton wide"></div><div class="rv-skeleton"></div><div class="rv-skeleton short"></div><strong>Loading CE memory…</strong><span>Current Review stays usable. Slow or missing history will not block this report.</span></div>';
    }

    // ---- events ----------------------------------------------------------
    function bind(sel, fn) { var el = root.querySelector(sel); if (el) el.onclick = fn; }
    function wirePickerResults() {
      root.querySelectorAll("[data-pick-ce]").forEach(function (b) { b.onclick = function () { addCe(b.dataset.pickCe); }; });
    }
    function wire() {
      root.querySelectorAll("[data-select-ce]").forEach(function (b) { b.onclick = function () { select(b.dataset.selectCe); }; });
      root.querySelectorAll("[data-open-drawer-ce]").forEach(function (b) {
        b.onclick=function(e){e.preventDefault();e.stopPropagation();openAnalyticsDrawer(b.dataset.openDrawerCe);};
        b.onkeydown=function(e){if(e.key==="Enter"||e.key===" "){e.preventDefault();e.stopPropagation();openAnalyticsDrawer(b.dataset.openDrawerCe);}};
      });
      root.querySelectorAll("[data-open-ce]").forEach(function (b) { b.onclick = function () { select(b.dataset.openCe); }; });
      root.querySelectorAll("[data-remove-ce]").forEach(function (b) { b.onclick = function (e) { e.stopPropagation(); removeCe(b.dataset.removeCe); }; });
      bind("#rv-add-ce", function () { S.adding = !S.adding; S.pickerQuery = ""; render(); var i = root.querySelector("#rv-picker-input"); if (i) i.focus(); });
      bind("#rv-browse-ces", function () { captureVisibleDrafts(); S.queueBrowse = true; render(); var i=root.querySelector("#rv-search-ce");if(i)i.focus({preventScroll:true}); });
      bind("#rv-close-queue", function () { S.queueBrowse = false; render(); var b=root.querySelector("#rv-browse-ces");if(b)b.focus({preventScroll:true}); });
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
      if(search)search.oninput=function(){S.queueQuery=search.value;var clear=root.querySelector("#rv-clear-search");if(clear)clear.hidden=!String(S.queueQuery||"").trim();var panel=root.querySelector("#rv-queue-review");if(panel){var matches=visibleQueueRows();panel.innerHTML=matches.length?renderQueueGroups(matches):'<div class="rv-empty-queue"><strong>No CE matches</strong><span>Clear search or adjust the local filters.</span></div>';wire();}};
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
      root.querySelectorAll("[data-resolve]").forEach(function(b){b.onclick=function(){focusRequirement(b.dataset.resolve);};});
      bind("#rv-save-finish-reason",function(){var input=root.querySelector("#rv-no-discussion-reason"),value=String(input?input.value:"").trim();if(!value){if(input)input.focus();toast("Add a concise reason");return;}S.noDiscussionDrafts[S.selected]=value;S.finishReasonOpen=false;render();toast("No-discussion reason ready for the review receipt");});
      var finishReason=root.querySelector("#rv-no-discussion-reason");if(finishReason)finishReason.oninput=function(){S.noDiscussionDrafts[S.selected]=finishReason.value;};
      bind("#rv-continue-slack", function(){S.threadOperation="continue";startSlack();});
      bind("#rv-new-slack", function(){S.threadOperation="new_parent";S.mentionPreview=null;render();var reason=root.querySelector("#rv-new-thread-reason");if(reason)reason.focus();});
      bind("#rv-new-thread-cancel", function(){S.threadOperation="";S.newThreadReason="";S.mentionPreview=null;render();});
      bind("#rv-confirm-slack", postSlack);
      bind("#rv-mention-cancel", function () { S.mentionPreview = null; render(); var n = root.querySelector("#rv-slack-message"); if (n) n.focus(); });
      var noteInput = root.querySelector("#rv-note");
      if (noteInput) noteInput.oninput = function () { S.noteDraft = noteInput.value; S.drafts[S.selected]=S.noteDraft; S.mentionPreview = null; };
      var slackInput=root.querySelector("#rv-slack-message");if(slackInput)slackInput.oninput=function(){S.slackDrafts[String(S.selected)]=slackInput.value;S.mentionPreview=null;};
      var threadReason=root.querySelector("#rv-new-thread-reason");if(threadReason)threadReason.oninput=function(){S.newThreadReason=threadReason.value;S.mentionPreview=null;};
      bind("#rv-sync-thread", syncThread);
      bind("#rv-summary-approve", function(){decideSummary("approved");});
      bind("#rv-summary-reject", function(){decideSummary("rejected");});
      bind("#rv-summary-regenerate", function(){decideSummary("regenerate");});
      bind("#rv-granola-toggle", function () { S.addingGranola = !S.addingGranola; render(); var i = root.querySelector("#rv-granola-link"); if (i) i.focus(); });
      bind("#rv-granola-cancel", function () { S.addingGranola = false; S.processing = false; render(); });
      bind("#rv-granola-add", addGranola);
      bind("#rv-granola-transcript", function () {
        S.processing = true; S.addingGranola = false; render();
        var transcript = root.querySelector("#rv-process-text"); if (transcript) transcript.focus();
      });
      bind("#rv-process-cancel", function () { S.processing = false; render(); });
      bind("#rv-process-run", runExtract);
      var glink = root.querySelector("#rv-granola-link"); if (glink) glink.onkeydown = function (e) { if (e.key === "Enter") { e.preventDefault(); addGranola(); } };
      root.querySelectorAll(".rv-sugg").forEach(function (card) {
        var acc = card.querySelector("[data-sugg-accept]"), ig = card.querySelector("[data-sugg-ignore]");
        if (acc) acc.onclick = function () { acceptSuggestion(card); };
        if (ig) ig.onclick = function () { decideSuggestionGroup(card, "rejected", {}); };
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
      bind("#rv-add-action", function () { S.compose = S.compose === "action" ? "" : "action"; render(); var i = root.querySelector("#rv-c-text"); if (i) i.focus(); });
      bind("#rv-add-check", function () { S.compose = S.compose === "check" ? "" : "check"; render(); var i = root.querySelector("#rv-c-text"); if (i) i.focus(); });
      bind("#rv-c-cancel", function () { S.compose = ""; render(); });
      bind("#rv-c-save", saveCompose);
      bind("#rv-next-ce", nextCe);
      bind("#rv-finish", finishReview);
      bind("#rv-open-memory", openMemory);
      bind("#rv-close-memory", function () { S.memoryOpen = false; root.querySelector("#rv-memory-drawer").hidden = true; });
      var wrap = root.querySelector("#rv-memory-drawer");
      if (wrap) wrap.onclick = function (e) { if (e.target === wrap) { S.memoryOpen = false; wrap.hidden = true; } };
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
      if (!text) { if (ta) ta.focus(); toast("Paste the meeting notes first"); return; }
      if (!ensureAuthor()) return;
      var btn = root.querySelector("#rv-process-run"); if (btn) { btn.textContent = "Extracting…"; btn.disabled = true; }
      var ceList = (S.headline.all_ces || []).map(function (c) { return { ce_id: String(c.ce_id), ce_name: c.ce_name || "" }; });
      var payload = { market_slug: S.market_slug, week: S.week_start, text: text, submitted_by: author(), ces: ceList };
      var call = (api && api.extractMeeting) ? api.extractMeeting(payload)
        : fetch("/api/review-extract", { method: "POST", credentials: "same-origin", headers: { "content-type": "application/json" }, body: JSON.stringify(payload) }).then(function (r) { return r.json(); });
      call.then(function (res) {
        if (!res || res.ok === false) throw new Error((res && res.error) || "extract failed");
        var ces = res.ces || [], total = 0, added = [];
        ces.forEach(function (c) {
          var id = String(c.ce_id), arr = c.suggestions || [];
          total += arr.length;
          if (arr.length) S.suggestions[id] = (S.suggestions[id] || []).concat(arr);
          if (!S.byId[id]) added.push({ ce_id: id, ce_name: c.ce_name, reason: "From meeting notes", source: "manual" });
        });
        if (added.length) { S.setRowsList = (S.setRowsList || []).concat(added); buildQueue(); }
        S.processSummary = "Extracted " + total + " suggestion" + (total === 1 ? "" : "s") + " across " + ces.length +
          " CE" + (ces.length === 1 ? "" : "s") + ". Open each CE to approve — accepted items land on the CE and its Review history.";
        render(); toast("Distributed to " + ces.length + " CE" + (ces.length === 1 ? "" : "s"));
      }).catch(function (e) {
        toast((e && e.message) || "Extraction failed");
        var b = root.querySelector("#rv-process-run"); if (b) { b.textContent = "Extract & distribute"; b.disabled = false; }
      });
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
      if (weekly && weekly.slack_post_ts && S.threadOperation!=="new_parent") { window.open(weekly.slack_post_permalink || "#", "_blank"); return; }
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
        .then(function (res) { S.weekly[S.selected] = res.weekly; if(res.thread)S.threadRegistry[S.selected]={active:res.thread,threads:[res.thread].concat((S.threadRegistry[S.selected]||{}).threads||[])}; delete S.slackDrafts[String(S.selected)]; S.mentionPreview = null; S.threadOperation=""; S.newThreadReason=""; track("slack_discussion_started",{value_text:res.operation||"start"}); toast(res.operation==="continue"?"CE discussion continued":"CE discussion started"); render(); })
        .catch(function (e) { if(btn){btn.disabled=false;btn.textContent="Post to Slack";} toast((e && e.message) || "Post failed · discussion kept locally"); });
    }
    function syncThread() {
      if (!api) return;
      var button = root.querySelector("#rv-sync-thread"); if (button) { button.disabled = true; button.textContent = "Summarizing…"; }
      api.syncWeeklyDiscussion(ident(S.selected)).then(function (res) {
        if (res.weekly) S.weekly[S.selected] = res.weekly;
        toast(res.new_replies && res.new_replies.length ? "Summary updated from new replies" : "Summary is current");
        render();
        Promise.all([loadCe(S.selected), reloadWork()]).catch(function(){});
      }).catch(function () { toast("Could not summarize now · automatic sync will retry"); render(); });
    }
    function decideSummary(decision){
      if(!api||S.asyncBusy.summary)return;
      var draft=root.querySelector("#rv-summary-draft"),payload=Object.assign({},ident(S.selected),{decision:decision,decided_by:author()||"authenticated BGM"});
      if(draft)payload.summary_json=draft.value;
      S.asyncBusy.summary=true;var btn=root.querySelector("#rv-summary-"+decision);if(btn){btn.disabled=true;btn.textContent=decision==="approved"?"Approving…":"Saving…";}
      api.decideSummary(payload).then(function(res){S.weekly[S.selected]=res.weekly;toast(decision==="approved"?"Summary approved for CE Memory":(decision==="rejected"?"Summary rejected":"Regeneration requested"));render();if(decision==="regenerate")syncThread();})
        .catch(function(e){toast((e&&e.message)||"Could not update summary");render();}).finally(function(){delete S.asyncBusy.summary;});
    }
    function addGranola() {
      if (!ensureAuthor() || !api) return;
      var inp = root.querySelector("#rv-granola-link"), url = inp ? inp.value.trim() : "";
      if (!/^https:\/\/([a-z0-9-]+\.)*granola\.ai\//i.test(url)) { if (inp) inp.focus(); toast("Paste a valid Granola meeting link"); return; }
      // Include the complete report catalogue, not just today's review queue:
      // one meeting may contain several CEs. The server emits only exact,
      // source-linked pending suggestions; it never writes commentary/work
      // directly and it never touches the legacy actions service.
      var catalogue = (S.headline && S.headline.all_ces) || [];
      var ces = catalogue.map(function (ce) { return { ce_id: String(ce.ce_id || ""), ce_name: String(ce.ce_name || "") }; })
        .filter(function (ce) { return ce.ce_id && ce.ce_name; });
      if (!ces.length) { toast("CE catalogue is unavailable · meeting was not sent"); return; }
      api.ingestGranolaLink({ market_slug: S.market_slug, week_start: S.week_start, source_url: url, ces: ces })
        .then(function (result) {
          S.addingGranola = false;
          toast(result.suggestions ? result.suggestions + " pending Granola suggestion" + (result.suggestions === 1 ? "" : "s") + " added" : "Meeting queued for reconciliation");
          return Promise.all([loadCe(S.selected), reloadWork()]);
        })
        .catch(function (e) { toast((e && e.message) || "Could not attach meeting"); });
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
      var calls = [api.decideSuggestion(Object.assign({ suggestion_id:primary, decision:decision, decided_by:author() }, fields || {}))];
      duplicates.forEach(function (sid) { calls.push(api.decideSuggestion({ suggestion_id:sid, decision:"rejected", decided_by:author(), duplicate_of:primary })); });
      Promise.all(calls).then(function(){track("suggestion_triaged",{value_number:duplicates.length+1,value_text:decision,idempotency_key:"suggestion:"+primary+":"+decision});toast(decision==="approved"?(duplicates.length?"Added · duplicate suggestions archived":"Added"):"Ignored · source retained");return Promise.all([loadCe(S.selected),reloadWork()]);}).catch(function(){toast("Could not update suggestion");});
    }
    function decideSuggestion(sid, decision, fields) {
      if (!api) return;
      api.decideSuggestion(Object.assign({ suggestion_id: sid, decision: decision, decided_by: author() }, fields || {}))
        .then(function () { toast(decision === "approved" ? "Added" : "Ignored · source retained"); return Promise.all([loadCe(S.selected), reloadWork()]); })
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
        week_start: c.week_start, body: body, author_name: c.author_name || c.source_author || "Granola",
        author_role: c.author_role || "", source_type: c.source_type || "granola", source_author: c.source_author || "",
        source_ref: c.source_ref || "", source_url: c.source_url || "", accepted_by: author() })
        .then(function () { S.editingComment = null; toast("Granola commentary updated"); loadCe(S.selected); })
        .catch(function () { toast("Could not update commentary"); });
    }
    function deleteImportedComment(commentId) {
      if (!api || !ensureAuthor()) return;
      api.deleteComment(commentId, author()).then(function () { S.confirmDeleteComment = null; toast("Granola commentary deleted · audit retained"); loadCe(S.selected); })
        .catch(function () { toast("Could not delete commentary"); });
    }
    function saveCompose() {
      if (!ensureAuthor() || !api) return;
      if(S.asyncBusy.createWork)return;
      var kind = S.compose, text = root.querySelector("#rv-c-text").value.trim();
      if (!text) { root.querySelector("#rv-c-text").focus(); toast("Describe it first"); return; }
      var owner = root.querySelector("#rv-c-owner").value.trim(), due = root.querySelector("#rv-c-due").value, status = root.querySelector("#rv-c-status").value;
      if (kind === "action" && status === "needs_action" && !owner) { root.querySelector("#rv-c-owner").focus(); toast("Confirm an owner for work that needs action"); return; }
      if (kind === "check" && !due) { root.querySelector("#rv-c-due").focus(); toast("Choose the next review date"); return; }
      S.asyncBusy.createWork=true;
      var started=performance.now(),tempId="pending_"+Date.now()+"_"+hash(text+owner+due),item={ work_id:tempId,market_slug:S.market_slug,ce_id:S.selected,ce_name:(S.byId[S.selected]||{}).ce_name,origin_week:S.week_start,kind:kind,text:text,owner:owner,due_date:due,status:status,source_type:"bgm_manual",_pending:true };
      (S.work[String(S.selected)]=S.work[String(S.selected)]||[]).push(item);S.compose="";render();toast(kind==="check"?"Scheduling check…":"Creating action…");
      api.saveWork(Object.assign({},item,{work_id:""})).then(function(res){var list=S.work[String(item.ce_id)]||[],idx=list.indexOf(item);if(idx>=0)list[idx]=res.work_item||Object.assign({},item,{work_id:(res.work_item||{}).work_id||tempId,_pending:false});console.info("review_work_persist_ms",Math.round(performance.now()-started));toast(kind==="check"?"Check scheduled":"Action created");render();return reloadWork();})
        .catch(function(){var list=S.work[String(item.ce_id)]||[],idx=list.indexOf(item);if(idx>=0)list.splice(idx,1);S.compose=kind;toast("Could not save work item · rolled back");render();})
        .finally(function(){S.asyncBusy.createWork=false;});
    }
    function toggleWork(workId) {
      var w = findWork(workId); if (!w || !api) return;
      var next = CLOSED.indexOf(w.status) >= 0 ? (w.kind === "check" ? "scheduled" : "needs_action") : "complete";
      saveWorkItem({ work_id: w.work_id, market_slug: w.market_slug, ce_id: w.ce_id, ce_name: w.ce_name, origin_week: w.origin_week, kind: w.kind, text: w.text, owner: w.owner || "", due_date: w.due_date || "", status: next, source_type: w.source_type || "bgm_manual" }, next === "complete" ? "Marked complete" : "Reopened");
    }
    function setWorkStatus(workId, status) {
      var w = findWork(workId); if (!w || !api) return;
      saveWorkItem({ work_id: w.work_id, market_slug: w.market_slug, ce_id: w.ce_id, ce_name: w.ce_name, origin_week: w.origin_week, kind: w.kind, text: w.text, owner: w.owner || "", due_date: w.due_date || "", status: status, source_type: w.source_type || "bgm_manual" }, "Status updated");
    }
    function saveWorkEdit(workId) {
      var w = findWork(workId); if (!w || !api || !ensureAuthor()) return;
      var row = root.querySelector('[data-work="' + String(workId).replace(/"/g, "") + '"]');
      if (!row) return;
      var text = (row.querySelector("[data-edit-text]") || {}).value || "";
      var owner = (row.querySelector("[data-edit-owner]") || {}).value || "";
      var due = (row.querySelector("[data-edit-due]") || {}).value || "";
      var status = (row.querySelector("[data-edit-status]") || {}).value || w.status;
      var carry=!!((row.querySelector("[data-edit-carry]")||{}).checked);
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
    function saveWorkItem(item, okMsg) { var key="work:"+String(item.work_id||"")+":"+String(item.status||"");if(S.asyncBusy[key])return;S.asyncBusy[key]=true;api.saveWork(item).then(function () { if(CLOSED.indexOf(item.status)>=0)track("action_closed",{ce_id:item.ce_id,value_text:item.status,idempotency_key:"action_closed:"+item.work_id+":"+item.status});toast(okMsg); return reloadWork(); }).catch(function () { toast("Could not save work item"); }).finally(function(){delete S.asyncBusy[key];}); }
    function reloadWork() {
      if (!api) return Promise.resolve();
      return api.work({ market_slug: S.market_slug, week: S.week_start }).then(function (res) {
        S.work = {}; (res.work_items || []).forEach(function (w) { var k = String(w.ce_id); (S.work[k] = S.work[k] || []).push(w); }); render();
      }).catch(function () {});
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
      if(key==="discussion"&&!(S.weekly[S.selected]||{}).slack_post_ts){S.finishReasonOpen=true;render();var reason=root.querySelector("#rv-no-discussion-reason");if(reason){reason.focus({preventScroll:true});reason.scrollIntoView({block:"center",behavior:"smooth"});}return;}
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
    function openMemory() {
      var wrap = root.querySelector("#rv-memory-drawer"), body = root.querySelector("#rv-memory-body"), q = S.byId[S.selected];
      S.memoryOpen = true;
      root.querySelector("#rv-memory-title").textContent = q.ce_name + " memory";
      root.querySelector("#rv-memory-eyebrow").textContent = "CE " + q.ce_id + " · " + S.market;
      wrap.hidden = false;
      if (!api) { body.innerHTML = '<div class="rv-empty-state"><strong>Backend unavailable</strong></div>'; return; }
      var key=S.market_slug+"|"+S.week_start+"|"+q.ce_id,cached=S.memoryCache[key];
      if(cached){body.innerHTML=renderMemory(cached);wireMemory(body);return;}
      if(S.memoryInflight[key])return;
      body.innerHTML=renderMemoryLoading();
      S.memoryInflight[key]=api.memory({ market_slug: S.market_slug, ce_id: q.ce_id }).then(function (res) { S.memoryCache[key]=res; var current=root.querySelector("#rv-memory-body");if(current&&S.memoryOpen&&String(S.selected)===String(q.ce_id)){current.innerHTML=renderMemory(res);wireMemory(current);}return res; })
        .catch(function () { var current=root.querySelector("#rv-memory-body");if(current&&S.memoryOpen)current.innerHTML = '<div class="rv-memory-tabs" aria-hidden="true"><button class="rv-memory-tab active" disabled>Story</button><button class="rv-memory-tab" disabled>Work</button><button class="rv-memory-tab" disabled>Historical comments</button><button class="rv-memory-tab" disabled>Perf history</button></div><div class="rv-empty-state"><strong>CE memory is temporarily unavailable</strong><span>Current Review data remains available. Try again later; missing history never blocks this report.</span></div>'; });
      S.memoryInflight[key].finally(function(){delete S.memoryInflight[key];});
    }
    function renderMemory(res) {
      // The isolated Review API returns explicit table-shaped keys. Keep the
      // older aliases as a compatibility fallback, but prefer the canonical
      // names so CE Memory always contains the BGM note and Slack summary that
      // were just written in Review mode.
      var weekly = res.weekly_commentary || res.weekly || [], work = res.work_items || res.work || [], receipts = res.receipts || [], threads=res.slack_threads||[],timeline=res.timeline||[];
      var legacy = res.historical_comments || res.legacy_notes || res.legacyNotes || [], sourceStatus=res.historical_source_status||{};
      var perf = res.perf_history || res.perf_actions || [];
      var story = weekly.map(function (w) {
        var summary = null;
        try { summary = String(w.summary_status||"")==="approved" ? JSON.parse(w.summary_approved_json||w.summary_json||"") : null; } catch (e) {}
        var points = summary ? [].concat(summary.findings || [], summary.decisions || [], summary.open_points || []) : [];
        var slackStory = points.length ? '<div class="rv-memory-source"><div class="rv-source-label">✦ AI · Slack · thread summary</div><ul>' +
          points.map(function (p) { return "<li>" + esc(typeof p === "string" ? p : (p.text || p.body || "")) + "</li>"; }).join("") + "</ul>" +
          (w.slack_post_permalink ? '<a class="rv-source-link" href="' + esc(w.slack_post_permalink) + '" target="_blank" rel="noopener">Open source thread ↗</a>' : "") + "</div>" : "";
        return '<article class="rv-week-card"><div class="rv-week-head">w/c ' + esc(w.week_start) + "<span>" + esc(w.bgm_author || "BGM") + "</span></div>" +
          '<div class="rv-week-body"><div class="rv-source-label">BGM note · original</div><p>' + esc(w.note_deleted_at ? "(deleted · audit retained)" : (w.bgm_note || "—")) + "</p>" + slackStory + "</div></article>";
      }).join("");
      var threadHistory=threads.map(function(t){return '<article class="rv-week-card"><div class="rv-week-head">Slack discussion<span>'+esc(t.binding_status||"active")+'</span></div><div class="rv-week-body"><div class="rv-source-label">'+esc(t.created_reason||"CE discussion")+'</div><p>'+(t.slack_permalink?'<a class="rv-source-link" href="'+esc(t.slack_permalink)+'" target="_blank" rel="noopener">Open source thread ↗</a>':'Permalink unavailable')+'</p><div class="rv-source-meta">'+[t.created_by?t.created_by:"",t.replacement_week?"w/c "+t.replacement_week:"",t.replaced_reason?"Replaced: "+t.replaced_reason:""].filter(Boolean).map(esc).join(" · ")+'</div></div></article>';}).join("");
      var timelinePanel=timeline.map(function(e){return '<article class="rv-week-card rv-timeline-event"><div class="rv-week-head">'+esc(String(e.event_type||"event").replace(/_/g," "))+'<span>'+esc(e.review_week||fmtWhen(e.occurred_at)||"")+'</span></div><div class="rv-week-body"><div class="rv-source-label">'+esc(e.source_type||"Review")+(e.approval_state?' · '+esc(e.approval_state):'')+'</div><p>'+esc(e.approved_body||e.original_body||"—")+'</p><div class="rv-source-meta">'+[e.actor_name||"",e.related_work_id?"Work "+e.related_work_id:""].filter(Boolean).map(esc).join(" · ")+(e.source_url?' · <a class="rv-source-link" href="'+esc(e.source_url)+'" target="_blank" rel="noopener">Source ↗</a>':'')+'</div></div></article>';}).join("");
      var storyPanel = timelinePanel || (story+threadHistory) || '<div class="rv-empty-state"><strong>No current Review commentary history yet</strong></div>';
      var legacyPanel = legacy.map(function (n) {
        return '<article class="rv-week-card"><div class="rv-week-head">w/c ' + esc(n.week_start || "date unavailable") + "<span>" + esc(n.author_name || "author unavailable") + "</span></div>" +
          '<div class="rv-week-body"><div class="rv-source-label">Historical CE comment · read-only</div><p>' + esc(n.body || "—") + "</p>" +
          '<div class="rv-source-meta">' + esc(n.created_at || "timestamp unavailable") + (n.duplicate_count>1?" · "+esc(n.duplicate_count)+" duplicate rows":"") + "</div></div></article>";
      }).join("") || '<div class="rv-empty-state"><strong>' + ((sourceStatus.comments||{}).unavailable?"Historical comments source unavailable":"No historical CE comments") + '</strong><span>Missing history never blocks this report.</span></div>';
      var workPanel = work.map(function (w) {
        return '<article class="rv-week-card"><div class="rv-week-head">' + (w.kind === "check" ? "Scheduled check" : "Action") + "<span>w/c " + esc(w.origin_week) + "</span></div>" +
          '<div class="rv-week-body"><div class="rv-source-label">' + esc((w.status || "").replace(/_/g, " ")) + "</div><p>" + esc(w.text) + "</p>" +
          '<div class="rv-source-meta">' + (w.owner ? esc(w.owner) : "no owner") + (w.due_date ? " · " + esc(fmtDue(w.due_date)) : "") + "</div></div></article>";
      }).join("");
      var receiptPanel = receipts.map(function (r) {
        return '<article class="rv-week-card"><div class="rv-week-head">Review receipt<span>w/c ' + esc(r.week_start) + "</span></div>" +
          '<div class="rv-week-body"><div class="rv-source-label">' + esc(TREATMENT_LABELS[r.treatment] || r.treatment) + " · " + esc(r.reviewer || "") + "</div><p>" + esc(r.summary || "—") + "</p></div></article>";
      }).join("");
      var workTab = (workPanel + receiptPanel) || '<div class="rv-empty-state"><strong>No work or receipts yet</strong></div>';
      var perfPanel = perf.length ? perf.map(function (p) {
        return '<article class="rv-week-card"><div class="rv-week-head">Perf action<span>w/c ' + esc(p.week_start || p.week || "") + "</span></div>" +
          '<div class="rv-week-body"><div class="rv-source-label">Historical Performance action · read-only</div><p>' + esc(p.action_text || p.text || p.action || p.comment || "—") + "</p>" +
          '<div class="rv-source-meta">' + [p.owner?"owner "+esc(p.owner):"",p.status?"status "+esc(String(p.status).replace(/_/g," ")):"",p.outcome?"outcome "+esc(p.outcome):"",p.updated_at?esc(p.updated_at):"",p.duplicate_count>1?esc(p.duplicate_count)+" duplicate rows":""].filter(Boolean).join(" · ") + "</div></div></article>";
      }).join("") : '<div class="rv-empty-state rv-perf-unavailable"><strong>' + ((sourceStatus.actions||{}).unavailable?"Performance history source unavailable":"No historical Performance actions") + '</strong><span>No value is inferred when history is missing.</span></div>';
      return '<div class="rv-memory-tabs"><button class="rv-memory-tab active" type="button" data-mem="story">Story</button>' +
        '<button class="rv-memory-tab" type="button" data-mem="work">Work</button>' +
        '<button class="rv-memory-tab" type="button" data-mem="comments">Historical comments</button>' +
        '<button class="rv-memory-tab" type="button" data-mem="perf">Perf history</button></div>' +
        '<div class="rv-memory-panel" id="rv-mem-story">' + storyPanel + "</div>" +
        '<div class="rv-memory-panel" id="rv-mem-work" hidden>' + workTab + "</div>" +
        '<div class="rv-memory-panel" id="rv-mem-comments" hidden>' + legacyPanel + "</div>" +
        '<div class="rv-memory-panel" id="rv-mem-perf" hidden>' + perfPanel + "</div>";
    }
    function wireMemory(body) {
      body.querySelectorAll(".rv-memory-tab").forEach(function (b) {
        b.onclick = function () {
          body.querySelectorAll(".rv-memory-tab").forEach(function (t) { t.classList.toggle("active", t === b); });
          body.querySelector("#rv-mem-story").hidden = b.dataset.mem !== "story";
          body.querySelector("#rv-mem-work").hidden = b.dataset.mem !== "work";
          body.querySelector("#rv-mem-comments").hidden = b.dataset.mem !== "comments";
          body.querySelector("#rv-mem-perf").hidden = b.dataset.mem !== "perf";
        };
      });
    }
    function hash(raw) { var h = 2166136261; for (var i = 0; i < raw.length; i++) { h ^= raw.charCodeAt(i); h = Math.imul(h, 16777619); } return (h >>> 0).toString(16); }

    var visibleOnce = false;
    return {
      onShow: function () {
        var requested="";try{requested=new URL(location.href).searchParams.get("ce_id")||"";}catch(e){}
        if (refreshHeadline() || !S.loaded) loadQueue().then(function(){if(requested&&ensureLocalCe(requested))select(requested);});
        else if(requested&&ensureLocalCe(requested))select(requested);else render();
        visibleOnce = true;
        track("review_return_usage",{idempotency_key:"return:"+S.market_slug+":"+S.week_start+":"+sessionId()});
      },
      focusCe: function (ceId) { refreshHeadline(); if(ensureLocalCe(ceId)){S.queueRevealUntil=Date.now()+2500;select(ceId);revealQueueSelection(ceId);return true;}return false; },
      prefetch: function(){refreshHeadline();if(!S.loaded)loadQueue();},
      onWeekChange: function () { if(S.selected&&S.noteDraft!=null)S.drafts[String(S.selected)]=S.noteDraft; Object.keys(S.ceRequestSeq).forEach(function(k){S.ceRequestSeq[k]++;}); S.selected = null; S.weekly = {}; S.suggestions = {}; S.ceLoadedAt={}; S.memoryCache={}; S.loaded = false; if (visibleOnce) loadQueue(); }
    };
  };
})(typeof window !== "undefined" ? window : this);
