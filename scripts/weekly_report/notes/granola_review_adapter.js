import { timingSafeEqual } from "node:crypto";

const APPS_SCRIPT_URL = process.env.REVIEW_APPS_SCRIPT_URL ||
  "https://script.google.com/macros/s/AKfycbyvXB69WxTM1p9qO4tQXxPfV28mkXOOiTKqW8J4SH2P_vtblTYd6bUQGJSb8HyLLGhOjA/exec";

function sameSecret(actual, expected) {
  const a = Buffer.from(String(actual || ""));
  const b = Buffer.from(String(expected || ""));
  return a.length === b.length && a.length > 0 && timingSafeEqual(a, b);
}

function cleanMeeting(value) {
  const meeting = value && typeof value === "object" ? value : {};
  const id = String(meeting.id || meeting.meeting_id || "").trim();
  const body = String(meeting.summary || meeting.notes || "").trim();
  if (!id || !body) throw new Error("meeting id and source notes are required");
  return {
    id,
    title: String(meeting.title || "Granola meeting").slice(0, 240),
    source_url: String(meeting.url || `https://notes.granola.ai/t/${id}`).slice(0, 1000),
    source_author: String(meeting.author || meeting.note_taker || "Granola").slice(0, 160),
    occurred_at: String(meeting.occurred_at || meeting.date || "").slice(0, 80),
    body: body.slice(0, 24000),
  };
}

function cleanMatches(value) {
  return (Array.isArray(value) ? value : []).slice(0, 20).map((match) => ({
    market_slug: String(match.market_slug || "").trim(),
    week_start: String(match.week_start || "").trim(),
    ce_id: String(match.ce_id || "").trim(),
    ce_name: String(match.ce_name || "").trim(),
    confidence: String(match.confidence || "").trim(),
    match_status: String(match.match_status || (match.ce_id ? "exact" : "ambiguous")),
  })).filter((match) => match.market_slug && match.week_start);
}

async function jsonPost(url, body, headers = {}) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json", ...headers },
    body: JSON.stringify(body),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok || result.ok === false) throw new Error(result.error || `upstream returned ${response.status}`);
  return result;
}

async function extractSuggestions(meeting, match, aiUrl) {
  if (!aiUrl) throw new Error("review AI URL is not configured");
  const secret = process.env.REVIEW_AI_WEBHOOK_SECRET_V2 || process.env.REVIEW_AI_WEBHOOK_SECRET;
  if (!secret) throw new Error("review AI secret is not configured");
  const sourceRef = `granola:${meeting.id}`;
  const result = await jsonPost(aiUrl, {
    mode: "source_suggestions",
    source_type: "granola",
    identity: match,
    records: [{
      source_ref: sourceRef,
      source_url: meeting.source_url,
      author: meeting.source_author,
      body: meeting.body,
      created_at: meeting.occurred_at,
    }],
  }, { "x-review-secret": secret });
  return (Array.isArray(result.suggestions) ? result.suggestions : []).map((suggestion, index) => ({
    market_slug: match.market_slug,
    week_start: match.week_start,
    ce_id: match.ce_id,
    ce_name: match.ce_name,
    source_type: "granola",
    source_author: meeting.source_author,
    source_ref: `${sourceRef}:${suggestion.kind}:${index + 1}`,
    source_url: meeting.source_url,
    occurred_at: meeting.occurred_at,
    kind: suggestion.kind,
    body: suggestion.body,
    proposed_owner: "",
    proposed_due_date: suggestion.proposed_due_date || "",
    confidence: suggestion.confidence || match.confidence || "source_derived",
    match_status: "exact",
  }));
}

async function ingest(items) {
  if (!APPS_SCRIPT_URL) throw new Error("REVIEW_APPS_SCRIPT_URL is not configured");
  const secret = process.env.REVIEW_INGEST_SECRET;
  if (!secret) throw new Error("REVIEW_INGEST_SECRET is not configured");
  return jsonPost(APPS_SCRIPT_URL, {
    action: "review_source_ingest",
    ingest_secret: secret,
    source_type: "granola",
    items,
  });
}

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ ok: false, error: "POST required" });
  if (!sameSecret(req.headers["x-granola-secret"], process.env.GRANOLA_WEBHOOK_SECRET))
    return res.status(401).json({ ok: false, error: "unauthorized" });

  try {
    const body = typeof req.body === "string" ? JSON.parse(req.body) : (req.body || {});
    const meeting = cleanMeeting(body.meeting);
    const matches = cleanMatches(body.matches);
    const exact = matches.filter((match) => match.ce_id && match.match_status === "exact");
    const aiUrl = process.env.REVIEW_AI_WEBHOOK_URL ||
      `https://${req.headers.host || "market-notebook.vercel.app"}/api/review-summary`;
    let items = [];
    for (const match of exact) items.push(...await extractSuggestions(meeting, match, aiUrl));

    // No confident CE match: preserve the source in reconciliation and do not
    // let it enter CE Memory, commentary, or work automatically.
    if (!items.length) {
      const candidate = matches[0] || {};
      items = [{
        market_slug: candidate.market_slug || String(body.market_slug || "").trim(),
        week_start: candidate.week_start || String(body.week_start || "").trim(),
        source_type: "granola",
        source_author: meeting.source_author,
        source_ref: `granola:${meeting.id}`,
        source_url: meeting.source_url,
        occurred_at: meeting.occurred_at,
        candidate_ce_id: candidate.ce_id || "",
        candidate_ce_name: candidate.ce_name || "",
        match_confidence: candidate.confidence || "",
        match_status: candidate.match_status || "unmatched",
        kind: "comment",
        body: meeting.body,
      }];
    }
    if (!items[0].market_slug || !items[0].week_start)
      return res.status(400).json({ ok: false, error: "market_slug and week_start are required" });

    const result = await ingest(items);
    return res.status(200).json({ ok: true, meeting_id: meeting.id, exact_matches: exact.length, result });
  } catch (error) {
    console.error("granola review ingestion failed:", error instanceof Error ? error.message : "unknown error");
    return res.status(502).json({ ok: false, error: "Granola review ingestion unavailable" });
  }
}
