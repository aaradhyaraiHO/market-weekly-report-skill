/*
 * Granola REST pull → isolated Weekly Review ingestion.
 *
 * Deploy as /api/granola-pull. This endpoint deliberately has no browser
 * credential and never writes to the legacy Weekly Report Notes/actions store.
 * A caller supplies the current Review CE catalogue for one market/week. Full
 * CE-name matches become pending suggestions; every other note is preserved in
 * the Review reconciliation inbox. BGM approval remains required downstream.
 */
import { createHash, timingSafeEqual } from "node:crypto";

const GRANOLA_API = "https://public-api.granola.ai/v1/notes";
const MAX_NOTES = 60;

function sameSecret(actual, expected) {
  const a = Buffer.from(String(actual || ""));
  const b = Buffer.from(String(expected || ""));
  return a.length === b.length && a.length > 0 && timingSafeEqual(a, b);
}

function clean(value, limit = 24000) { return String(value || "").trim().slice(0, limit); }
function norm(value) { return clean(value, 4000).toLowerCase().replace(/[^a-z0-9]+/g, " ").replace(/\s+/g, " ").trim(); }

function noteIdFromUrl(sourceUrl) {
  try {
    const parsed = new URL(String(sourceUrl || ""));
    if (!/(^|\.)granola\.ai$/i.test(parsed.hostname)) return "";
    // Shared URLs are commonly /t/<uuid>-<share-suffix>; Granola's API uses
    // the stable UUID, which also appears after the browser redirects to /d/.
    return (parsed.pathname.match(/\/(?:t|d)\/([0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12})/i) || [])[1] || "";
  } catch (_) { return ""; }
}
function sourceItemRef(sourceRef, match, item) {
  const material = [sourceRef, match.market_slug, match.week_start, match.ce_id,
    clean(item.kind, 32), clean(item.body, 4000), clean(item.proposed_due_date, 20)].join("\n");
  return `${sourceRef}:${createHash("sha256").update(material).digest("hex").slice(0, 20)}`;
}

function bodyFor(note) {
  const candidates = [note.summary, note.notes, note.content, note.transcript, note.ai_summary];
  for (const candidate of candidates) {
    if (typeof candidate === "string" && candidate.trim()) return clean(candidate);
    if (candidate && typeof candidate === "object") {
      const text = candidate.text || candidate.content || candidate.summary;
      if (typeof text === "string" && text.trim()) return clean(text);
    }
  }
  return "";
}

async function granola(url) {
  const token = process.env.GRANOLA_API_KEY;
  if (!token) throw new Error("GRANOLA_API_KEY is not configured");
  const response = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) throw new Error(`Granola returned ${response.status}`);
  return response.json();
}

async function listNotes(updatedAfter) {
  const params = new URLSearchParams({ page_size: "30" });
  if (updatedAfter) params.set("updated_after", updatedAfter);
  const listed = await granola(`${GRANOLA_API}?${params}`);
  return (Array.isArray(listed.notes) ? listed.notes : []).slice(0, MAX_NOTES);
}

async function fullNote(note) {
  const id = clean(note.id, 120);
  if (!id) return null;
  return granola(`${GRANOLA_API}/${encodeURIComponent(id)}`);
}

function matchesFor(note, ces) {
  const haystack = norm(`${note.title || ""} ${bodyFor(note)}`);
  return (Array.isArray(ces) ? ces : []).map((ce) => ({
    ce_id: clean(ce.ce_id, 80), ce_name: clean(ce.ce_name, 240),
  })).filter((ce) => ce.ce_id && norm(ce.ce_name).length >= 6 && haystack.includes(norm(ce.ce_name)))
    .map((ce) => ({ ...ce, match_status: "exact", confidence: "high" }));
}

async function jsonPost(url, body, headers) {
  const response = await fetch(url, { method: "POST", headers: { "content-type": "application/json", ...headers }, body: JSON.stringify(body) });
  const result = await response.json().catch(() => ({}));
  if (!response.ok || result.ok === false) throw new Error(result.error || `upstream returned ${response.status}`);
  return result;
}

async function suggestionsFor(meeting, match) {
  const url = process.env.REVIEW_MODE_AI_WEBHOOK_URL;
  const secret = process.env.REVIEW_MODE_AI_WEBHOOK_SECRET || process.env.REVIEW_AI_WEBHOOK_SECRET_V2 || process.env.REVIEW_AI_WEBHOOK_SECRET;
  if (!url || !secret) throw new Error("Review AI summary endpoint is not configured");
  const sourceRef = `granola:${meeting.id}`;
  const result = await jsonPost(url, {
    mode: "source_suggestions", source_type: "granola", identity: match,
    records: [{ source_ref: sourceRef, source_url: meeting.url, author: meeting.author, body: meeting.body, created_at: meeting.occurred_at }],
  }, { "x-review-secret": secret });
  return (Array.isArray(result.suggestions) ? result.suggestions : []).slice(0, 20).map((item) => ({
    market_slug: match.market_slug, week_start: match.week_start, ce_id: match.ce_id, ce_name: match.ce_name,
    source_type: "granola", source_author: meeting.author, source_ref: sourceItemRef(sourceRef, match, item),
    source_url: meeting.url, occurred_at: meeting.occurred_at, kind: item.kind, body: clean(item.body, 4000),
    proposed_owner: "", proposed_due_date: clean(item.proposed_due_date, 20), confidence: item.confidence || "source_derived", match_status: "exact",
  })).filter((item) => item.body && ["comment", "action", "check"].includes(item.kind));
}

async function ingest(items) {
  const url = process.env.REVIEW_MODE_APPS_SCRIPT_URL;
  const secret = process.env.REVIEW_MODE_INGEST_SECRET;
  if (!url || !secret) throw new Error("Review ingestion endpoint is not configured");
  return jsonPost(url, { action: "review_source_ingest", ingest_secret: secret, source_type: "granola", items });
}

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ ok: false, error: "POST required" });
  if (!sameSecret(req.headers["x-review-secret"], process.env.REVIEW_MODE_AI_WEBHOOK_SECRET || process.env.REVIEW_AI_WEBHOOK_SECRET_V2 || process.env.REVIEW_AI_WEBHOOK_SECRET))
    return res.status(401).json({ ok: false, error: "unauthorized" });
  let body;
  try { body = typeof req.body === "string" ? JSON.parse(req.body) : (req.body || {}); }
  catch (_) { return res.status(400).json({ ok: false, error: "invalid JSON" }); }
  const market = clean(body.market_slug, 120), week = clean(body.week_start, 20);
  if (!market || !/^\d{4}-\d{2}-\d{2}$/.test(week)) return res.status(400).json({ ok: false, error: "market_slug and week_start are required" });
  try {
    const sourceUrl = clean(body.source_url, 1000);
    const linkedId = sourceUrl ? noteIdFromUrl(sourceUrl) : "";
    if (sourceUrl && !linkedId) return res.status(400).json({ ok: false, error: "valid Granola meeting link required" });
    // A pasted link is deliberately link-specific. We never substitute the
    // newest meeting, which could attach an unrelated call to a CE.
    const notes = linkedId ? [{ id: linkedId, web_url: sourceUrl }] : await listNotes(clean(body.updated_after, 20) || week);
    const items = [];
    for (const listed of notes) {
      const note = await fullNote(listed);
      if (!note) continue;
      const meeting = { id: clean(note.id, 120), title: clean(note.title, 240), body: bodyFor(note),
        url: clean(note.web_url || listed.web_url || `https://notes.granola.ai/t/${note.id}`, 1000),
        author: clean((note.owner || {}).name || (listed.owner || {}).name || "Granola", 160), occurred_at: clean(note.updated_at || note.created_at, 80) };
      if (!meeting.id || !meeting.body) continue;
      const matches = matchesFor(note, body.ces).map((match) => ({ ...match, market_slug: market, week_start: week }));
      if (matches.length) {
        for (const match of matches) items.push(...await suggestionsFor(meeting, match));
      } else {
        items.push({ market_slug: market, week_start: week, source_type: "granola", source_author: meeting.author,
          source_ref: `granola:${meeting.id}`, source_url: meeting.url, occurred_at: meeting.occurred_at,
          match_status: "unmatched", kind: "comment", body: meeting.body });
      }
    }
    if (items.length) await ingest(items);
    return res.status(200).json({ ok: true, notes_scanned: notes.length, items_queued: items.length });
  } catch (error) {
    console.error("granola-pull failed:", error instanceof Error ? error.message : "unknown error");
    return res.status(502).json({ ok: false, error: "Granola pull unavailable" });
  }
}
