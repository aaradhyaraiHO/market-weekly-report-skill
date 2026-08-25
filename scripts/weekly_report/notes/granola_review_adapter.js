import { createHash, timingSafeEqual } from "node:crypto";

const APPS_SCRIPT_URL = process.env.REVIEW_MODE_APPS_SCRIPT_URL;
const REVIEW_AI_SECRET = process.env.REVIEW_MODE_AI_WEBHOOK_SECRET ||
  process.env.REVIEW_AI_WEBHOOK_SECRET_V2 || process.env.REVIEW_AI_WEBHOOK_SECRET;

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

// Do not use the model response position as an identifier. A retry can return
// the same suggestions in a different order; the Review store must recognise
// those as the same source record rather than create duplicate work.
function sourceItemRef(sourceRef, match, suggestion) {
  const material = [
    sourceRef,
    match.market_slug,
    match.week_start,
    match.ce_id,
    String(suggestion.kind || "comment"),
    String(suggestion.body || "").trim(),
    String(suggestion.proposed_due_date || "").trim(),
  ].join("\n");
  return `${sourceRef}:${createHash("sha256").update(material).digest("hex").slice(0, 20)}`;
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
  const secret = REVIEW_AI_SECRET;
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
  return (Array.isArray(result.suggestions) ? result.suggestions : []).map((suggestion) => ({
    market_slug: match.market_slug,
    week_start: match.week_start,
    ce_id: match.ce_id,
    ce_name: match.ce_name,
    source_type: "granola",
    source_author: meeting.source_author,
    source_ref: sourceItemRef(sourceRef, match, suggestion),
    source_url: meeting.source_url,
    occurred_at: meeting.occurred_at,
    kind: suggestion.kind,
    body: suggestion.body,
    proposed_owner: "",
    proposed_due_date: suggestion.proposed_due_date || "",
    confidence: suggestion.confidence || match.confidence || "source_derived",
    match_status: "exact",
  })).filter((suggestion) => suggestion.body && ["comment", "action", "check"].includes(suggestion.kind));
}

async function ingest(items) {
  if (!APPS_SCRIPT_URL) throw new Error("REVIEW_MODE_APPS_SCRIPT_URL is not configured");
  const secret = process.env.REVIEW_MODE_INGEST_SECRET;
  if (!secret) throw new Error("REVIEW_MODE_INGEST_SECRET is not configured");
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
    const aiUrl = process.env.REVIEW_MODE_AI_WEBHOOK_URL;
    let items = [];
    for (const match of exact) items.push(...await extractSuggestions(meeting, match, aiUrl));

    // No confident CE match: preserve the source in reconciliation and do not
    // let it enter CE Memory, commentary, or work automatically.
    if (!items.length) {
      // Preserve an exact match which yielded no conservative AI suggestions
      // as reconciliation evidence. It must *not* be silently converted into
      // a CE suggestion just because it has a candidate CE id.
      const candidate = exact[0] || matches[0] || {};
      items = [{
        market_slug: candidate.market_slug || String(body.market_slug || "").trim(),
        week_start: candidate.week_start || String(body.week_start || "").trim(),
        source_type: "granola",
        source_author: meeting.source_author,
        source_ref: `granola:${meeting.id}:unprocessed`,
        source_url: meeting.source_url,
        occurred_at: meeting.occurred_at,
        candidate_ce_id: candidate.ce_id || "",
        candidate_ce_name: candidate.ce_name || "",
        match_confidence: candidate.confidence || "",
        match_status: "unmatched",
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
