/* Weekly Review V2 browser client.
 *
 * Deliberately contains no UI state and no second localStorage task model. The
 * Review workspace, Open work view, and CE-drawer sidecar all call this client
 * and receive the same Sheet-backed records.
 */
(function(global) {
  "use strict";

  function required(value, name) {
    if (value == null || String(value).trim() === "") throw new Error(name + " is required");
  }

  function createWeeklyReviewApi(baseUrl) {
    required(baseUrl, "baseUrl");
    var cache = {}, inflight = {}, generation=0, CACHE_MS = 60000;

    function fetchJson(url,options,timeoutMs){
      var controller=new AbortController(),timer=setTimeout(function(){controller.abort();},timeoutMs||15000);
      var opts=Object.assign({},options||{},{signal:controller.signal});
      return fetch(url,opts).then(function(response){
        return response.json().catch(function(){throw new Error(response.status===401?"Please sign in again.":"The audit service did not return a valid response.");}).then(function(body){
          if(!response.ok||!body||!body.ok)throw new Error(body&&body.error||"Audit request failed ("+response.status+")");
          return body;
        });
      }).catch(function(error){if(error.name==="AbortError")throw new Error("The audit service took too long. Your draft is preserved. Retry when ready.");throw error;}).finally(function(){clearTimeout(timer);});
    }

    function request(action, params, options) {
      var query = new URLSearchParams({action: action});
      Object.keys(params || {}).forEach(function(key) {
        var value = params[key];
        if (value !== undefined && value !== null) query.set(key, String(value));
      });
      var url = baseUrl + "?" + query.toString(), now = Date.now(), opts = options || {};
      if (!opts.refresh && cache[url] && now - cache[url].at < (opts.ttl || CACHE_MS)) return Promise.resolve(cache[url].body);
      if (!opts.refresh && inflight[url]) return inflight[url];
      var requestGeneration=generation;
      var running = fetchJson(url, {redirect: "follow", credentials: "same-origin"}, opts.timeoutMs)
        .then(function(body) {
          if (!body || !body.ok) throw new Error((body && body.error) || "Weekly Review request failed");
          if(requestGeneration===generation)cache[url] = {at: Date.now(), body: body};
          return body;
        }).finally(function() { if(inflight[url]===running)delete inflight[url]; });
      inflight[url]=running;
      return running;
    }

    function post(action, params) {
      return fetchJson(baseUrl, {
        method: "POST",
        headers: {"content-type": "application/json"},
        credentials: "same-origin",
        body: JSON.stringify(Object.assign({action: action}, params || {}))
      }, 90000)
        .then(function(body) {
          if (!body || !body.ok) throw new Error((body && body.error) || "Weekly Review request failed");
          // Any successful mutation may change queue, CE history, work, or
          // memory. Drop read caches only after confirmation from the server.
          cache = {}; inflight = {}; generation++;
          return body;
        });
    }

    return {
      extractMeeting: function(payload){return fetchJson("/api/review-extract",{method:"POST",credentials:"same-origin",headers:{"content-type":"application/json"},body:JSON.stringify(payload)},90000).then(function(body){cache={};generation++;return body;});},
      // The Review proxy derives this from the authenticated Google session.
      // UI writes must use it rather than asking a signed-in BGM to re-enter
      // their name in every browser/device.
      whoami: function() { return request("whoami", {}); },
      comments: function(identity, includeDeleted, options) {
        var comments=[];
        function page(before){return request("review_comment_list", Object.assign({}, identity, {include_deleted: !!includeDeleted,before:before||""}), options).then(function(res){
          comments=comments.concat(res.comments||[]);
          return res.next_before?page(res.next_before):Object.assign({},res,{comments:comments});
        });}
        return page("");
      },
      saveComment: function(comment) {
        required(comment.author_name, "author_name");
        return post("review_comment_upsert", comment);
      },
      deleteComment: function(commentId, deletedBy) {
        return post("review_comment_delete", {comment_id: commentId, deleted_by: deletedBy});
      },
      work: function(filter) {
        var rows=[],seen={};
        function page(before){return request("review_work_list",Object.assign({},filter||{},before?{before:before}:{})).then(function(res){
          rows=rows.concat(res.work_items||[]);
          if(res.next_before){if(seen[res.next_before])throw new Error("Action history could not finish loading. Please retry.");seen[res.next_before]=true;return page(res.next_before);}
          return Object.assign({},res,{work_items:rows});
        });}
        return page();
      },
      saveWork: function(item) { return post("review_work_upsert", item); },
      deleteWork: function(workId, deletedBy) {
        required(workId, "work_id");
        required(deletedBy, "deleted_by");
        return post("review_work_delete", {work_id: workId, deleted_by: deletedBy});
      },
      finishReview: function(receipt) { return post("review_receipt_upsert", receipt); },
      receipts: function(identity) { return request("review_receipt_list", identity); },
      outcomes: function(identity) { return request("review_outcome_list", identity); },
      saveOutcome: function(outcome) { return post("review_outcome_upsert", outcome); },
      timeline: function(identity) { return request("review_timeline", identity, {ttl: 300000}); },
      saveTimelineEvent: function(event) { return post("review_timeline_event_upsert", event); },
      backlog: function(identity) { return request("review_backlog", identity, {ttl: 60000}); },
      reconciliation: function(identity) { return request("review_reconciliation", identity, {ttl: 60000}); },
      recordTelemetry: function(event) { return post("review_telemetry_record", event); },
      reviewSet: function(identity) { return request("review_set_list", identity); },
      saveReviewSetItem: function(item) { return post("review_set_upsert", item); },
      memory: function(identity, refresh) { return request("review_memory", identity, {refresh: !!refresh, ttl: 300000, timeoutMs:45000}); },
      weeklyCommentary: function(identity, before, limit, options) {
        return request("review_weekly_list", Object.assign({}, identity, {before: before || "", limit: limit || 26}), options);
      },
      saveWeeklyNote: function(note) {
        required(note.note_type || "bgm", "note_type");
        required(note.author || note.bgm_author || note.performance_author || note.bdm_author, "author");
        required(note.note || note.bgm_note || note.performance_note || note.bdm_note, "note");
        return post("review_weekly_note_upsert", note);
      },
      deleteWeeklyNote: function(identity, deletedBy, noteType) {
        return post("review_weekly_note_delete", Object.assign({}, identity, {deleted_by: deletedBy, note_type: noteType || "bgm"}));
      },
      resolveMentions: function(identity, text) {
        return request("review_mention_resolve", Object.assign({}, identity, {text: text}));
      },
      startSlackDiscussion: function(message) {
        required(message.request_id, "request_id");
        return post("review_weekly_slack_post", message);
      },
      threads: function(identity, options) { return request("review_thread_list", identity, options); },
      syncWeeklyDiscussion: function(identity) { return post("review_weekly_sync", identity); },
      decideSummary: function(decision) { return post("review_summary_decide", decision); },
      askInSlack: function(message) { return post("review_slack_post", message); },
      scanSlack: function(identity) { return post("review_slack_scan", identity); },
      suggestions: function(identity, includeDecided, options) {
        return request("review_suggestion_list", Object.assign({}, identity, {include_decided: !!includeDecided}), options);
      },
      decideSuggestion: function(decision) { return post("review_suggestion_decide", decision); },
      sourceInbox: function(identity, includeReconciled) {
        return request("review_source_inbox", Object.assign({}, identity, {include_reconciled: !!includeReconciled}));
      },
      reconcileSource: function(match) { return post("review_source_reconcile", match); },
      prefetch: function(action, params, ttl) { return request(action, params || {}, {ttl: ttl || CACHE_MS}).catch(function() { return null; }); },
      clearCache: function() { cache = {}; inflight = {}; generation++; }
    };
  }

  global.createWeeklyReviewApi = createWeeklyReviewApi;
})(typeof window !== "undefined" ? window : this);
