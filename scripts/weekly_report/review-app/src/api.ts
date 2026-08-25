/* Review API client (TS port of review-client.js). In the report it authenticates via the
 * mmr_session cookie through the /api/review proxy. In the mockup a global stub is provided,
 * so we reuse window.createWeeklyReviewApi when present. */
export type Ident = { market_slug: string; ce_id: string; ce_name?: string; week_start?: string };

function make(baseUrl: string) {
  // The isolated Review Apps Script accepts reads over GET, but deliberately
  // rejects mutations over GET so note/action text cannot leak into URLs.
  const mutations = new Set([
    "review_set_upsert", "review_receipt_upsert", "review_work_upsert", "review_work_delete",
    "review_weekly_note_upsert", "review_weekly_note_delete", "review_weekly_slack_post",
    "review_weekly_sync", "review_suggestion_decide", "review_granola_link_submit",
  ]);
  const req = (action: string, params?: Record<string, unknown>) => {
    if (mutations.has(action)) return post(action, params);
    const q = new URLSearchParams({ action });
    Object.entries(params || {}).forEach(([k, v]) => { if (v !== undefined && v !== null) q.set(k, String(v)); });
    return fetch(`${baseUrl}?${q.toString()}`, { redirect: "follow", credentials: "same-origin" })
      .then((r) => r.json())
      .then((b) => { if (!b || !b.ok) throw new Error((b && b.error) || "request failed"); return b; });
  };
  const post = (action: string, params?: Record<string, unknown>) =>
    fetch(baseUrl, { method: "POST", credentials: "same-origin", headers: { "content-type": "application/json" }, body: JSON.stringify({ action, ...(params || {}) }) })
      .then((r) => r.json()).then((b) => { if (!b || !b.ok) throw new Error((b && b.error) || "request failed"); return b; });
  return {
    reviewSet: (id: any) => req("review_set_list", id),
    saveReviewSetItem: (item: any) => req("review_set_upsert", item),
    receipts: (id: any) => req("review_receipt_list", id),
    finishReview: (r: any) => req("review_receipt_upsert", r),
    work: (f: any) => req("review_work_list", f || {}),
    saveWork: (item: any) => req("review_work_upsert", item),
    deleteWork: (workId: string, deletedBy: string) => req("review_work_delete", { work_id: workId, deleted_by: deletedBy }),
    weeklyCommentary: (id: any, before?: string, limit?: number) => req("review_weekly_list", { ...id, before: before || "", limit: limit || 26 }),
    saveWeeklyNote: (n: any) => req("review_weekly_note_upsert", n),
    deleteWeeklyNote: (id: any, by: string) => req("review_weekly_note_delete", { ...id, deleted_by: by }),
    startSlackDiscussion: (m: any) => req("review_weekly_slack_post", m),
    syncWeeklyDiscussion: (id: any) => req("review_weekly_sync", id),
    // The active review surface needs pending suggestions from both Slack and
    // Granola. Source attribution is rendered in the UI; neither source is
    // silently converted into a work item.
    suggestions: (id: any, incl?: boolean) => req("review_suggestion_list", { ...id, include_decided: !!incl }),
    granolaSuggestions: (id: any, incl?: boolean) => req("review_suggestion_list", { ...id, source_type: "granola", include_decided: !!incl }),
    decideSuggestion: (d: any) => req("review_suggestion_decide", d),
    attachGranolaMeeting: (link: any) => post("review_granola_link_submit", link),
    // A pasted Granola URL is processed server-side. The browser never sees a
    // Granola credential, and an unmatched transcript is reconciliation-only.
    ingestGranolaLink: (p: any) => fetch("/api/granola-link", { method: "POST", credentials: "same-origin", headers: { "content-type": "application/json" }, body: JSON.stringify(p) })
      .then((r) => r.json()).then((b) => { if (!b || !b.ok) throw new Error((b && b.error) || "Granola extraction failed"); return b; }),
    memory: (id: any) => req("review_memory", id),
    extractMeeting: (p: any) => {
      const g = window as any;
      if (g.createWeeklyReviewApi && g.__RV_HEADLINE) {
        // mock path (native mockup): reuse the stub's extractMeeting if present
        const stub = g.createWeeklyReviewApi("/api/review");
        if (stub.extractMeeting) return stub.extractMeeting(p);
      }
      return fetch("/api/review-extract", { method: "POST", credentials: "same-origin", headers: { "content-type": "application/json" }, body: JSON.stringify(p) }).then((r) => r.json());
    },
  };
}

export function getApi() {
  const g = window as any;
  if (g.createWeeklyReviewApi) return g.createWeeklyReviewApi("/api/review");
  return make("/api/review");
}
export type Api = ReturnType<typeof make>;
