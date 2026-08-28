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
    var cache = {}, inflight = {}, CACHE_MS = 60000;

    function request(action, params, options) {
      var query = new URLSearchParams({action: action});
      Object.keys(params || {}).forEach(function(key) {
        var value = params[key];
        if (value !== undefined && value !== null) query.set(key, String(value));
      });
      var url = baseUrl + "?" + query.toString(), now = Date.now(), opts = options || {};
      if (!opts.refresh && cache[url] && now - cache[url].at < (opts.ttl || CACHE_MS)) return Promise.resolve(cache[url].body);
      if (!opts.refresh && inflight[url]) return inflight[url];
      inflight[url] = fetch(url, {redirect: "follow", credentials: "same-origin", signal: opts.signal})
        .then(function(response) { return response.json(); })
        .then(function(body) {
          if (!body || !body.ok) throw new Error((body && body.error) || "Weekly Review request failed");
          cache[url] = {at: Date.now(), body: body};
          return body;
        }).finally(function() { delete inflight[url]; });
      return inflight[url];
    }

    function post(action, params) {
      return fetch(baseUrl, {
        method: "POST",
        headers: {"content-type": "application/json"},
        credentials: "same-origin",
        body: JSON.stringify(Object.assign({action: action}, params || {}))
      }).then(function(response) { return response.json(); })
        .then(function(body) {
          if (!body || !body.ok) throw new Error((body && body.error) || "Weekly Review request failed");
          // Any successful mutation may change queue, CE history, work, or
          // memory. Drop read caches only after confirmation from the server.
          cache = {};
          return body;
        });
    }

    return {
      // The Review proxy derives this from the authenticated Google session.
      // UI writes must use it rather than asking a signed-in BGM to re-enter
      // their name in every browser/device.
      whoami: function() { return request("whoami", {}); },
      comments: function(identity, includeDeleted, options) {
        return request("review_comment_list", Object.assign({}, identity, {include_deleted: !!includeDeleted}), options);
      },
      saveComment: function(comment) {
        required(comment.author_name, "author_name");
        return post("review_comment_upsert", comment);
      },
      deleteComment: function(commentId, deletedBy) {
        return post("review_comment_delete", {comment_id: commentId, deleted_by: deletedBy});
      },
      work: function(filter) { return request("review_work_list", filter || {}); },
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
      reviewSet: function(identity) { return request("review_set_list", identity); },
      saveReviewSetItem: function(item) { return post("review_set_upsert", item); },
      memory: function(identity, refresh) { return request("review_memory", identity, {refresh: !!refresh, ttl: 300000}); },
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
      syncWeeklyDiscussion: function(identity) { return post("review_weekly_sync", identity); },
      askInSlack: function(message) { return post("review_slack_post", message); },
      scanSlack: function(identity) { return post("review_slack_scan", identity); },
      suggestions: function(identity, includeDecided, options) {
        return request("review_suggestion_list", Object.assign({}, identity, {include_decided: !!includeDecided}), options);
      },
      granolaSuggestions: function(identity, includeDecided) {
        return request("review_suggestion_list", Object.assign({}, identity, {
          source_type: "granola", include_decided: !!includeDecided
        }));
      },
      attachGranolaMeeting: function(link) {
        required(link.source_url, "source_url");
        required(link.submitted_by, "submitted_by");
        return post("review_granola_link_submit", link);
      },
      // A BGM-pasted meeting must use the authenticated, link-specific
      // extractor.  The older attachGranolaMeeting call is retained only for
      // historical source-inbox records; it merely queues a URL and does not
      // produce CE suggestions.
      ingestGranolaLink: function(payload) {
        required(payload.source_url, "source_url");
        required(payload.market_slug, "market_slug");
        required(payload.week_start, "week_start");
        required(payload.ces, "ces");
        return fetch("/api/granola-link", {
          method: "POST",
          credentials: "same-origin",
          headers: {"content-type": "application/json"},
          body: JSON.stringify(payload)
        }).then(function(response) { return response.json(); })
          .then(function(body) {
            if (!body || !body.ok) throw new Error((body && body.error) || "Granola meeting extraction failed");
            return body;
          });
      },
      decideSuggestion: function(decision) { return post("review_suggestion_decide", decision); },
      sourceInbox: function(identity, includeReconciled) {
        return request("review_source_inbox", Object.assign({}, identity, {include_reconciled: !!includeReconciled}));
      },
      reconcileSource: function(match) { return post("review_source_reconcile", match); },
      prefetch: function(action, params, ttl) { return request(action, params || {}, {ttl: ttl || CACHE_MS}).catch(function() { return null; }); },
      clearCache: function() { cache = {}; inflight = {}; }
    };
  }

  global.createWeeklyReviewApi = createWeeklyReviewApi;
})(typeof window !== "undefined" ? window : this);
