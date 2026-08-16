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

    function request(action, params) {
      var query = new URLSearchParams({action: action});
      Object.keys(params || {}).forEach(function(key) {
        var value = params[key];
        if (value !== undefined && value !== null) query.set(key, String(value));
      });
      return fetch(baseUrl + "?" + query.toString(), {redirect: "follow"})
        .then(function(response) { return response.json(); })
        .then(function(body) {
          if (!body || !body.ok) throw new Error((body && body.error) || "Weekly Review request failed");
          return body;
        });
    }

    return {
      comments: function(identity, includeDeleted) {
        return request("review_comment_list", Object.assign({}, identity, {include_deleted: !!includeDeleted}));
      },
      saveComment: function(comment) {
        required(comment.author_name, "author_name");
        return request("review_comment_upsert", comment);
      },
      deleteComment: function(commentId, deletedBy) {
        return request("review_comment_delete", {comment_id: commentId, deleted_by: deletedBy});
      },
      work: function(filter) { return request("review_work_list", filter || {}); },
      saveWork: function(item) { return request("review_work_upsert", item); },
      finishReview: function(receipt) { return request("review_receipt_upsert", receipt); },
      receipts: function(identity) { return request("review_receipt_list", identity); },
      reviewSet: function(identity) { return request("review_set_list", identity); },
      saveReviewSetItem: function(item) { return request("review_set_upsert", item); },
      memory: function(identity) { return request("review_memory", identity); },
      weeklyCommentary: function(identity, before, limit) {
        return request("review_weekly_list", Object.assign({}, identity, {before: before || "", limit: limit || 26}));
      },
      saveWeeklyNote: function(note) {
        required(note.bgm_author, "bgm_author");
        required(note.bgm_note, "bgm_note");
        return request("review_weekly_note_upsert", note);
      },
      deleteWeeklyNote: function(identity, deletedBy) {
        return request("review_weekly_note_delete", Object.assign({}, identity, {deleted_by: deletedBy}));
      },
      resolveMentions: function(identity, text) {
        return request("review_mention_resolve", Object.assign({}, identity, {text: text}));
      },
      startSlackDiscussion: function(message) {
        required(message.request_id, "request_id");
        return request("review_weekly_slack_post", message);
      },
      syncWeeklyDiscussion: function(identity) { return request("review_weekly_sync", identity); },
      askInSlack: function(message) { return request("review_slack_post", message); },
      scanSlack: function(identity) { return request("review_slack_scan", identity); },
      suggestions: function(identity, includeDecided) {
        return request("review_suggestion_list", Object.assign({}, identity, {include_decided: !!includeDecided}));
      },
      granolaSuggestions: function(identity, includeDecided) {
        return request("review_suggestion_list", Object.assign({}, identity, {
          source_type: "granola", include_decided: !!includeDecided
        }));
      },
      decideSuggestion: function(decision) { return request("review_suggestion_decide", decision); },
      sourceInbox: function(identity, includeReconciled) {
        return request("review_source_inbox", Object.assign({}, identity, {include_reconciled: !!includeReconciled}));
      },
      reconcileSource: function(match) { return request("review_source_reconcile", match); }
    };
  }

  global.createWeeklyReviewApi = createWeeklyReviewApi;
})(typeof window !== "undefined" ? window : this);
