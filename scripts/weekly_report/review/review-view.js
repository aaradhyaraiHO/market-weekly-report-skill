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
    ["no_action_needed", "No action needed"], ["complete", "Complete"]
  ];
  var CHECK_STATUS = [
    ["scheduled", "Scheduled"], ["monitoring", "Monitoring"],
    ["self_recovering", "Self-recovering"], ["complete", "Complete"]
  ];
  var CLOSED = ["complete", "cancelled", "no_action_needed"];
  var MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];
  // Primary posting routes mirror alert/market_channels.json. Alternate market
  // channels remain read/mention sources; one discussion must have one stable home.
  var MARKET_CHANNELS = {
    north_america:{id:"CNSHDD2H1",name:"mkt-usa"},italy:{id:"C045L2WQ79P",name:"mkt-italy-switzerland-malta"},
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
      receipts: {}, weekly: {}, weeklyHist: {}, work: {}, suggestions: {}, comments: {}, setRows: {}, setRowsList: [],
      loadingCe: {}, editingNote: false, confirmDelete: false, adding: false, compose: "", addingGranola: false,
      processing: false, processSummary: "", noteDraft: null, mentionPreview: null, mentionBusy: false,
      editingWork: null, confirmDeleteWork: null, editingComment: null, confirmDeleteComment: null,
      drafts: {}, ceLoadedAt: {}, ceRequestSeq: {}, ceControllers: {}, memoryCache: {}, memoryInflight: {}, asyncBusy: {}
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
    function openAnalyticsDrawer(ceId) {
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

    // ---- data loading (unchanged backend surface) -----------------------
    function refreshHeadline() {
      var h = ctx.getHeadline ? ctx.getHeadline() : null;
      if (!h) return false;
      var changed = h.market_slug !== S.market_slug || h.week_start !== S.week_start;
      S.headline = h; S.market = h.market || h.market_slug || ""; S.market_slug = h.market_slug || h.market || "";
      S.week_start = h.week_start || ""; S.week_end = h.week_end || "";
      var ch = (h.notes_channels || (ctx.getBaseHeadline && ctx.getBaseHeadline().notes_channels) || {})[S.market_slug];
      S.channel = ch || MARKET_CHANNELS[S.market_slug] || null;
      return changed;
    }
    function loadQueue() {
      refreshHeadline();
      if (!api) { S.setRowsList = []; buildQueue(); render(); return Promise.resolve(); }
      // Paint the snapshot-backed queue immediately. Remote review state then
      // enriches it without delaying tab navigation.
      if (!S.loaded) { buildQueue(); S.loaded = true; render(); }
      var id = { market_slug: S.market_slug, week: S.week_start };
      return Promise.all([
        api.reviewSet(id).catch(function () { return { review_set: [] }; }),
        api.receipts({ market_slug: S.market_slug, week: S.week_start }).catch(function () { return { receipts: [] }; }),
        api.work({ market_slug: S.market_slug, week: S.week_start }).catch(function () { return { work_items: [] }; })
      ]).then(function (res) {
        S.setRowsList = (res[0].review_set || []);
        S.setRows = {}; S.setRowsList.forEach(function (r) { S.setRows[String(r.ce_id)] = r; });
        S.receipts = {}; (res[1].receipts || []).forEach(function (r) { S.receipts[String(r.ce_id)] = r; });
        S.work = {}; (res[2].work_items || []).forEach(function (w) { var k = String(w.ce_id); (S.work[k] = S.work[k] || []).push(w); });
        buildQueue();
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
        api.comments({ market_slug: S.market_slug, ce_id: ceId, week: S.week_start }, false, requestOptions).catch(function () { return { comments: [] }; })
      ]).then(function (res) {
        if(S.ceRequestSeq[ceId]!==seq)return;
        var rows = res[0].weekly || [];
        S.weekly[ceId] = rows.filter(function (r) { return String(r.week_start) === String(S.week_start); })[0] || null;
        S.weeklyHist[ceId] = rows;
        S.suggestions[ceId] = res[1].suggestions || [];
        S.comments[ceId] = res[2].comments || [];
        S.loadingCe[ceId] = false; delete S.ceControllers[ceId]; S.ceLoadedAt[ceId]=Date.now();
        if (String(S.selected) === String(ceId)) render();
      }).catch(function () { if(S.ceRequestSeq[ceId]===seq)S.loadingCe[ceId] = false; });
      S.loadingCe[ceId]=call; return call;
    }

    function select(ceId) {
      if (S.selected && S.noteDraft != null) S.drafts[String(S.selected)] = S.noteDraft;
      if(S.selected&&String(S.selected)!==String(ceId)&&S.ceControllers[S.selected]){S.ceRequestSeq[S.selected]=(S.ceRequestSeq[S.selected]||0)+1;S.ceControllers[S.selected].abort();delete S.ceControllers[S.selected];S.loadingCe[S.selected]=false;}
      S.selected = String(ceId); S.confirmDelete = false; S.compose = "";
      S.noteDraft = Object.prototype.hasOwnProperty.call(S.drafts, S.selected) ? S.drafts[S.selected] : null;
      S.editingNote = S.noteDraft != null;
      S.mentionPreview = null; S.editingWork = null; S.confirmDeleteWork = null; S.editingComment = null; S.confirmDeleteComment = null;
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
    }

    function renderSide() {
      var open = S.queue.filter(function (q) { return !reviewedFor(q.ce_id); }).length;
      var total = S.queue.length, reviewed = total - open;
      var rows = S.queue.length ? S.queue.map(queueRow).join("") :
        '<div class="rv-empty-queue"><strong>No CEs flagged this week</strong><span>System flags and CEs you add appear here. ✅</span></div>';
      var picker = S.adding ? renderPicker() : "";
      return '<aside class="rv-side">' +
        '<div class="rv-eyebrow">Weekly review · w/c ' + esc(S.week_start) + "</div>" +
        '<div class="rv-side-head"><h2>' + (open ? open + " CE" + (open === 1 ? "" : "s") + " to review" : "All caught up") + "</h2>" +
        '<button class="rv-addce" type="button" id="rv-add-ce">＋ Add CE</button></div>' +
        '<div class="rv-subtle" id="rv-progress">' + reviewed + " of " + total + " reviewed</div>" +
        '<div class="rv-queue-label">Review queue</div>' + picker +
        '<div class="rv-queue-panel" id="rv-queue-review">' + rows + "</div></aside>";
    }
    function queueRow(q) {
      var reviewed = reviewedFor(q.ce_id), active = String(q.ce_id) === String(S.selected), t = treatmentFor(q.ce_id);
      var openN = openWorkFor(q.ce_id).length;
      var tags = '<span class="rv-chip' + (reviewed ? " done" : "") + '">' + (reviewed ? "Reviewed" : esc(TREATMENT_LABELS[t] || t)) + "</span>" +
        (openN ? '<span class="rv-chip">' + openN + " open</span>" : "") +
        (q.source === "manual" ? '<span class="rv-chip">manual</span>' : "");
      var remove = q.source === "manual" ? '<button class="rv-ce-remove" type="button" data-remove-ce="' + esc(q.ce_id) + '" title="Remove from review set">×</button>' : "";
      return '<div style="position:relative">' + remove +
        '<button class="rv-ce-row' + (active ? " active" : "") + (reviewed ? " reviewed" : "") + '" type="button" data-select-ce="' + esc(q.ce_id) + '">' +
        '<span class="rv-dot"></span><span class="rv-ce-copy"><strong class="rv-ce-identity" role="link" tabindex="0" data-open-drawer-ce="' + esc(q.ce_id) + '">' + esc(q.ce_name) + "</strong>" +
        "<small>" + esc(q.reason) + ' · <span class="rv-ce-identity" role="link" tabindex="0" data-open-drawer-ce="' + esc(q.ce_id) + '">CE ' + esc(q.ce_id) + '</span></small><span class="rv-ce-tags">' + tags + "</span></span></button></div>";
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
      var t = treatmentFor(q.ce_id), reviewed = reviewedFor(q.ce_id);
      var receipt = reviewed
        ? '<span class="rv-receipt done">✓ Reviewed by ' + esc((S.receipts[q.ce_id] || {}).reviewer || author() || "BGM") + "</span>"
        : t !== "not_scheduled" ? '<span class="rv-receipt">Ready to finish</span>'
          : '<span class="rv-receipt">Choose how you’ll review this CE</span>';
      var footHint = reviewed ? "Review saved — open work carries into next week"
        : t === "not_scheduled" ? "Set a treatment above to finish this CE" : "Finish when you’re done with this CE";
      return '<main class="rv-main">' +
        '<header class="rv-detail-head"><div class="rv-breadcrumb"><button class="rv-link" type="button" data-open-drawer-ce="' + esc(q.ce_id) + '">CE ' + esc(q.ce_id) + "</button> · " + esc(S.market) + "</div>" +
        '<div class="rv-title-line"><div><h1><button class="rv-title-link" type="button" data-open-drawer-ce="' + esc(q.ce_id) + '">' + esc(q.ce_name) + "</button></h1>" +
        "<p>Record what you know, decide the follow-through, and mark it reviewed.</p></div>" +
        '<div class="rv-button-row"><button class="rv-btn" type="button" id="rv-open-drawer">Open CE drawer</button></div></div>' +
        '<div class="rv-status-line"><label for="rv-treatment">Review as</label>' +
        '<select class="rv-select" id="rv-treatment" aria-label="Review treatment">' +
        TREATMENT_ORDER.map(function (v) { return '<option value="' + v + '"' + (v === t ? " selected" : "") + ">" + esc(TREATMENT_LABELS[v]) + "</option>"; }).join("") +
        "</select>" + receipt + "</div></header>" +
        '<div class="rv-workspace">' + renderCommentaryCard(q) + renderActionsCard(q) + renderMemoryRail(q) +
        (S.processing ? renderProcessPanel() : "") +
        '<div class="rv-resource-state">Saved to Review history · CE ' + esc(q.ce_id) + "</div></div>" +
        '<footer class="rv-footer"><span class="rv-foot-hint">' + esc(footHint) + "</span>" + renderGranolaDock() +
        '<div class="rv-foot-actions"><button class="rv-btn" type="button" id="rv-next-ce">Next CE →</button>' +
        '<button class="rv-btn primary" type="button" id="rv-finish"' + (t === "not_scheduled" || reviewed ? " disabled" : "") + ">" +
        (reviewed ? "Reviewed ✓" : "Finish CE review") + "</button></div></footer></main>";
    }

    function renderCommentaryCard(q) {
      var weekly = S.weekly[q.ce_id];
      var sugg = (S.suggestions[q.ce_id] || []).filter(function (s) {
        return (s.kind === "comment" || !s.kind) && String(s.source_type || "granola") === "granola";
      });
      var pending = sugg.filter(function (s) { return !s.decided_at && (s.status || "pending") === "pending"; });
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
      return '<div class="rv-mention-preview" aria-live="polite"><div class="rv-mention-title"><span>Slack post preview</span><button class="rv-link" type="button" id="rv-mention-cancel">Edit message</button></div>' +
        resolved + blocked + '<div class="rv-mention-message">' + esc(p.original_text || "") + "</div>" +
        '<div class="rv-mention-actions"><button class="rv-btn small primary" type="button" id="rv-confirm-slack"' + (ambiguous.length ? " disabled" : "") + '>Post to Slack</button></div></div>';
    }

    function renderActionsCard(q) {
      var sugg = (S.suggestions[q.ce_id] || []).filter(function (s) { return s.kind === "action" || s.kind === "check"; });
      var pending = sugg.filter(function (s) { return !s.decided_at && (s.status || "pending") === "pending"; });
      var allWork = workFor(q.ce_id);
      var openItems = allWork.filter(function (w) { return CLOSED.indexOf(w.status) < 0; });
      var doneItems = allWork.filter(function (w) { return CLOSED.indexOf(w.status) >= 0; });
      var openN = openItems.length;
      var suggHtml = pending.map(function (s) {
        var isCheck = s.kind === "check";
        return '<div class="rv-sugg" data-suggestion="' + esc(s.suggestion_id) + '" data-kind="' + esc(s.kind) + '">' +
          '<div class="rv-sugg-meta">' + suggestionSource(s) + '<span>·</span><span>' + esc(s.source_ref || s.source_author || "source") + "</span>" +
          "<span>·</span><span>" + (isCheck ? "suggested check" : "suggested action") + "</span></div>" +
          '<textarea class="rv-sugg-edit" data-sugg-body aria-label="Edit suggested ' + (isCheck ? "check" : "action") + '">' + esc(s.body || "") + "</textarea>" +
          '<div class="rv-work-controls" style="display:grid;grid-template-columns:1fr 1fr auto;gap:8px;margin-bottom:10px">' +
          '<input type="text" data-w-owner placeholder="' + (isCheck ? "Owner (optional)" : "Owner") + '" value="' + esc(s.proposed_owner || "") + '" style="min-height:38px;padding:8px 10px;border:1px solid var(--rv-g400);border-radius:10px">' +
          '<input type="date" data-w-due value="' + esc(s.proposed_due_date || "") + '" style="min-height:38px;padding:8px 10px;border:1px solid var(--rv-g400);border-radius:10px">' +
          '<select data-w-status class="rv-select">' + optionList(isCheck ? CHECK_STATUS : WORK_STATUS, isCheck ? "scheduled" : "needs_action") + "</select></div>" +
          '<div class="rv-sugg-actions"><button class="rv-btn small primary" type="button" data-sugg-accept>' + (isCheck ? "Schedule check" : "Create action") + "</button>" +
          '<button class="rv-btn small" type="button" data-sugg-ignore>Ignore</button></div></div>';
      }).join("");
      var openHtml = openItems.map(workRow).join("");
      var doneHtml = doneItems.length ? '<details class="rv-done"><summary>Archived · ' + doneItems.length + " done</summary>" +
        '<div class="rv-done-list">' + doneItems.map(workRow).join("") + "</div></details>" : "";
      var emptyState = (openItems.length || pending.length || S.compose) ? "" :
        '<div class="rv-empty-state" style="margin-top:12px"><strong>No open actions</strong><span>Add an action or schedule a check below. Slack and Granola suggestions appear here for confirmation.</span></div>';
      var composer = S.compose ? renderCompose(S.compose) : "";
      var count = openN ? openN + " open" : (allWork.length ? "All done" : "No work yet");
      return '<section class="rv-card"><div class="rv-card-head"><span class="rv-step">2</span>' +
        '<div class="rv-card-headings"><div class="rv-card-title">Actions &amp; follow-ups</div>' +
        '<div class="rv-card-sub">Every item carries its owner, source, status and next check</div></div>' +
        '<span class="rv-card-count">' + count + "</span></div>" +
        '<div class="rv-card-body">' + suggHtml + openHtml + emptyState + doneHtml +
        composer +
        '<div class="rv-add-row"><button class="rv-btn ghost small" type="button" id="rv-add-action">＋ Add action</button>' +
        '<button class="rv-btn ghost small" type="button" id="rv-add-check">＋ Schedule check</button></div></div></section>';
    }
    function workRow(w) {
      var done = CLOSED.indexOf(w.status) >= 0, isCheck = w.kind === "check";
      var src = w.source_type === "granola" ? "Granola" : w.source_type === "slack" ? "Slack" : w.source_type === "bgm_manual" ? "Manual" : (w.source_type || "");
      var srcLink = w.source_url ? '<a href="' + esc(w.source_url) + '" target="_blank" rel="noopener">' + esc(src || "source") + " ↗</a>" : esc(src);
      var meta = [w.owner ? esc(w.owner) : (isCheck ? "" : "no owner"), w.due_date ? (isCheck ? "returns " : "due ") + esc(fmtDue(w.due_date)) : "", srcLink].filter(Boolean).join(" · ");
      var left = isCheck && w.due_date
        ? '<span class="rv-datebadge"><span class="m">' + MONTHS[(parseDate(w.due_date) || new Date()).getUTCMonth()] + '</span><span class="d">' + (parseDate(w.due_date) || new Date()).getUTCDate() + "</span></span>"
        : '<button class="rv-check' + (done ? " on" : "") + '" type="button" data-work-toggle="' + esc(w.work_id) + '" title="' + (done ? "Reopen" : "Mark complete") + '">' + (done ? "✓" : "") + "</button>";
      var right = w.owner ? avatar(w.owner, "sm") : '<span class="rv-av sm none">–</span>';
      if (String(S.editingWork || "") === String(w.work_id)) return renderWorkEdit(w);
      return '<div class="rv-work' + (done ? " done" : "") + '" data-work="' + esc(w.work_id) + '">' + left +
        '<div class="rv-work-main">' + (isCheck ? '<div class="rv-work-kicker">Next review check</div>' : "") +
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
        '<div class="rv-drawer-body" id="rv-memory-body"><div class="rv-empty-state"><strong>Loading…</strong></div></div></div></div>';
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
      var pick = root.querySelector("#rv-picker-input");
      if (pick) pick.oninput = function () {
        S.pickerQuery = pick.value;
        var res = root.querySelector("#rv-picker-results");
        if (res) { res.innerHTML = renderPickerResults(); wirePickerResults(); }
      };
      wirePickerResults();

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
      bind("#rv-start-slack", startSlack);
      bind("#rv-confirm-slack", postSlack);
      bind("#rv-mention-cancel", function () { S.mentionPreview = null; render(); var n = root.querySelector("#rv-note"); if (n) n.focus(); });
      var noteInput = root.querySelector("#rv-note");
      if (noteInput) noteInput.oninput = function () { S.noteDraft = noteInput.value; S.drafts[S.selected]=S.noteDraft; S.mentionPreview = null; };
      bind("#rv-sync-thread", syncThread);
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
        if (ig) ig.onclick = function () { decideSuggestion(card.dataset.suggestion, "rejected", {}); };
      });
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
      bind("#rv-close-memory", function () { root.querySelector("#rv-memory-drawer").hidden = true; });
      var wrap = root.querySelector("#rv-memory-drawer");
      if (wrap) wrap.onclick = function (e) { if (e.target === wrap) wrap.hidden = true; };
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
        .then(function (res) { S.setRows[q.ce_id] = res.review_set_item || { treatment: value }; render(); })
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
      var ce = (S.headline.all_ces || []).find(function (c) { return String(c.ce_id) === String(ceId); }) || { ce_id: ceId };
      api.saveReviewSetItem({ market_slug: S.market_slug, week_start: S.week_start, ce_id: String(ceId), ce_name: ce.ce_name || "", treatment: "not_scheduled", reason: "Added to review", source: "manual" })
        .then(function () { S.adding = false; S.pickerQuery = ""; return loadQueue().then(function () { select(ceId); }); })
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
      if (weekly && weekly.slack_post_ts) { window.open(weekly.slack_post_permalink || "#", "_blank"); return; }
      if (!ensureAuthor() || !api) return;
      if (!S.channel) { toast("No Slack channel configured for this market"); return; }
      var ta = root.querySelector("#rv-note"); var text = ta ? ta.value.trim() : (weekly && weekly.bgm_note) || "";
      if (!text) { if (ta) ta.focus(); toast("Write the discussion starter first"); return; }
      S.noteDraft = text; S.drafts[S.selected]=text; S.editingNote = true; S.mentionBusy = true; S.mentionPreview = null; render();
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
      api.startSlackDiscussion(Object.assign({}, id, { channel: S.channel.id, bgm_note: text, bgm_author: author(), request_id: reqId, report_url: location.href }))
        .then(function (res) { S.weekly[S.selected] = res.weekly; S.editingNote = false; delete S.drafts[S.selected]; S.noteDraft = null; S.mentionPreview = null; toast("CE discussion started"); render(); })
        .catch(function (e) { if(btn){btn.disabled=false;btn.textContent="Post to Slack";} toast((e && e.message) || "Post failed · note remains saved"); });
    }
    function syncThread() {
      if (!api) return;
      var button = root.querySelector("#rv-sync-thread"); if (button) { button.disabled = true; button.textContent = "Summarizing…"; }
      api.syncWeeklyDiscussion(ident(S.selected)).then(function (res) {
        if (res.weekly) S.weekly[S.selected] = res.weekly;
        toast(res.new_replies && res.new_replies.length ? "Summary updated from new replies" : "Summary is current");
        return Promise.all([loadCe(S.selected), reloadWork()]);
      }).catch(function () { toast("Could not summarize now · automatic sync will retry"); render(); });
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
      var body = ((card.querySelector("[data-sugg-body]") || {}).value || "").trim();
      if (!body) { var bodyEl = card.querySelector("[data-sugg-body]"); if (bodyEl) bodyEl.focus(); toast("Keep or edit the suggestion text first"); return; }
      if (kind === "comment") { decideSuggestion(sid, "approved", { destination: "comment", body: body }); return; }
      if (!ensureAuthor()) return;
      var owner = (card.querySelector("[data-w-owner]") || {}).value || "";
      var due = (card.querySelector("[data-w-due]") || {}).value || "";
      var status = (card.querySelector("[data-w-status]") || {}).value || (kind === "check" ? "scheduled" : "needs_action");
      if (kind === "action" && status === "needs_action" && !owner.trim()) { card.querySelector("[data-w-owner]").focus(); toast("Confirm an owner for work that needs action"); return; }
      if (kind === "check" && !due) { card.querySelector("[data-w-due]").focus(); toast("Choose the next review date"); return; }
      decideSuggestion(sid, "approved", { destination: kind, body: body, owner: owner.trim(), due_date: due, work_status: status });
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
      var kind = S.compose, text = root.querySelector("#rv-c-text").value.trim();
      if (!text) { root.querySelector("#rv-c-text").focus(); toast("Describe it first"); return; }
      var owner = root.querySelector("#rv-c-owner").value.trim(), due = root.querySelector("#rv-c-due").value, status = root.querySelector("#rv-c-status").value;
      if (kind === "action" && status === "needs_action" && !owner) { root.querySelector("#rv-c-owner").focus(); toast("Confirm an owner for work that needs action"); return; }
      if (kind === "check" && !due) { root.querySelector("#rv-c-due").focus(); toast("Choose the next review date"); return; }
      saveWorkItem({ market_slug: S.market_slug, ce_id: S.selected, ce_name: (S.byId[S.selected] || {}).ce_name, origin_week: S.week_start, kind: kind, text: text, owner: owner, due_date: due, status: status, source_type: "bgm_manual" }, kind === "check" ? "Check scheduled" : "Action created");
      S.compose = "";
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
      if (!text.trim()) { row.querySelector("[data-edit-text]").focus(); toast("Describe the work item first"); return; }
      if (w.kind === "action" && status === "needs_action" && !owner.trim()) { row.querySelector("[data-edit-owner]").focus(); toast("Confirm an owner for work that needs action"); return; }
      if (w.kind === "check" && !due) { row.querySelector("[data-edit-due]").focus(); toast("Choose the next review date"); return; }
      S.editingWork = null;
      saveWorkItem({ work_id: w.work_id, market_slug: w.market_slug, ce_id: w.ce_id, ce_name: w.ce_name, origin_week: w.origin_week,
        kind: w.kind, text: text.trim(), owner: owner.trim(), due_date: due, status: status,
        source_type: w.source_type || "bgm_manual", source_ref: w.source_ref || "", source_url: w.source_url || "" }, "Work item updated");
    }
    function deleteWork(workId) {
      if (!ensureAuthor() || !api) return;
      if (typeof api.deleteWork !== "function") { toast("Delete is not available on this Review backend"); return; }
      api.deleteWork(workId, author()).then(function () {
        S.confirmDeleteWork = null; toast("Work item deleted · audit retained"); return reloadWork();
      }).catch(function () { toast("Could not delete work item"); });
    }
    function saveWorkItem(item, okMsg) { api.saveWork(item).then(function () { toast(okMsg); reloadWork(); }).catch(function () { toast("Could not save work item"); }); }
    function reloadWork() {
      if (!api) return Promise.resolve();
      return api.work({ market_slug: S.market_slug, week: S.week_start }).then(function (res) {
        S.work = {}; (res.work_items || []).forEach(function (w) { var k = String(w.ce_id); (S.work[k] = S.work[k] || []).push(w); }); render();
      }).catch(function () {});
    }
    function findWork(id) { var f = null; Object.keys(S.work).forEach(function (k) { S.work[k].forEach(function (w) { if (String(w.work_id) === String(id)) f = w; }); }); return f; }
    function finishReview() {
      var q = S.byId[S.selected], t = treatmentFor(q.ce_id);
      if (t === "not_scheduled") { root.querySelector("#rv-treatment").focus(); toast("Choose how you’ll review this CE"); return; }
      if (!ensureAuthor() || !api) return;
      api.finishReview({ market_slug: S.market_slug, ce_id: q.ce_id, ce_name: q.ce_name, week_start: S.week_start, treatment: t, reviewer: author(), open_work_count: String(openWorkFor(q.ce_id).length), summary: (S.weekly[q.ce_id] && S.weekly[q.ce_id].bgm_note) || "" })
        .then(function (res) { S.receipts[q.ce_id] = res.receipt || { reviewer: author() }; toast("CE review finished"); render(); })
        .catch(function () { toast("Could not save review receipt"); });
    }
    function nextCe() {
      var open = S.queue.filter(function (x) { return !reviewedFor(x.ce_id) && String(x.ce_id) !== String(S.selected); });
      if (!open.length) { toast("Review queue complete for this week 🎉"); return; }
      select(open[0].ce_id);
    }
    function openMemory() {
      var wrap = root.querySelector("#rv-memory-drawer"), body = root.querySelector("#rv-memory-body"), q = S.byId[S.selected];
      root.querySelector("#rv-memory-title").textContent = q.ce_name + " memory";
      root.querySelector("#rv-memory-eyebrow").textContent = "CE " + q.ce_id + " · " + S.market;
      wrap.hidden = false;
      if (!api) { body.innerHTML = '<div class="rv-empty-state"><strong>Backend unavailable</strong></div>'; return; }
      var key=S.market_slug+"|"+S.week_start+"|"+q.ce_id,cached=S.memoryCache[key];
      if(cached){body.innerHTML=renderMemory(cached);wireMemory(body);return;}
      if(S.memoryInflight[key])return;
      body.innerHTML='<div class="rv-empty-state"><strong>Loading CE memory…</strong></div>';
      S.memoryInflight[key]=api.memory({ market_slug: S.market_slug, ce_id: q.ce_id }).then(function (res) { S.memoryCache[key]=res; body.innerHTML = renderMemory(res); wireMemory(body); })
        .catch(function () { body.innerHTML = '<div class="rv-empty-state"><strong>Could not load CE memory</strong></div>'; });
      S.memoryInflight[key].finally(function(){delete S.memoryInflight[key];});
    }
    function renderMemory(res) {
      // The isolated Review API returns explicit table-shaped keys. Keep the
      // older aliases as a compatibility fallback, but prefer the canonical
      // names so CE Memory always contains the BGM note and Slack summary that
      // were just written in Review mode.
      var weekly = res.weekly_commentary || res.weekly || [], work = res.work_items || res.work || [], receipts = res.receipts || [];
      var legacy = res.historical_comments || res.legacy_notes || res.legacyNotes || [], sourceStatus=res.historical_source_status||{};
      var perf = res.perf_history || res.perf_actions || [];
      var story = weekly.map(function (w) {
        var summary = null;
        try { summary = w.summary_json ? JSON.parse(w.summary_json) : null; } catch (e) {}
        var points = summary ? [].concat(summary.findings || [], summary.decisions || [], summary.open_points || []) : [];
        var slackStory = points.length ? '<div class="rv-memory-source"><div class="rv-source-label">✦ AI · Slack · thread summary</div><ul>' +
          points.map(function (p) { return "<li>" + esc(typeof p === "string" ? p : (p.text || p.body || "")) + "</li>"; }).join("") + "</ul>" +
          (w.slack_post_permalink ? '<a class="rv-source-link" href="' + esc(w.slack_post_permalink) + '" target="_blank" rel="noopener">Open source thread ↗</a>' : "") + "</div>" : "";
        return '<article class="rv-week-card"><div class="rv-week-head">w/c ' + esc(w.week_start) + "<span>" + esc(w.bgm_author || "BGM") + "</span></div>" +
          '<div class="rv-week-body"><div class="rv-source-label">BGM note · original</div><p>' + esc(w.note_deleted_at ? "(deleted · audit retained)" : (w.bgm_note || "—")) + "</p>" + slackStory + "</div></article>";
      }).join("");
      var storyPanel = story || '<div class="rv-empty-state"><strong>No current Review commentary history yet</strong></div>';
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
      },
      focusCe: function (ceId) { refreshHeadline(); if(ensureLocalCe(ceId)){select(ceId);var active=root.querySelector('[data-select-ce="'+String(ceId).replace(/"/g,'\\"')+'"]');if(active)active.scrollIntoView({block:"nearest"});return true;}return false; },
      prefetch: function(){refreshHeadline();if(!S.loaded)loadQueue();},
      onWeekChange: function () { if(S.selected&&S.noteDraft!=null)S.drafts[String(S.selected)]=S.noteDraft; Object.keys(S.ceRequestSeq).forEach(function(k){S.ceRequestSeq[k]++;}); S.selected = null; S.weekly = {}; S.suggestions = {}; S.ceLoadedAt={}; S.memoryCache={}; S.loaded = false; if (visibleOnce) loadQueue(); }
    };
  };
})(typeof window !== "undefined" ? window : this);
