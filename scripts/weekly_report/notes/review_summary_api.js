import { timingSafeEqual } from "node:crypto";

const OPENAI_URL = "https://api.openai.com/v1/chat/completions";
const MODEL = process.env.REVIEW_AI_MODEL || "gpt-5.6-luna";

function sameSecret(actual, expected) {
  const a = Buffer.from(String(actual || ""));
  const b = Buffer.from(String(expected || ""));
  return a.length === b.length && a.length > 0 && timingSafeEqual(a, b);
}

function strings(value, limit = 8) {
  return (Array.isArray(value) ? value : [])
    .filter((item) => typeof item === "string" && item.trim())
    .slice(0, limit)
    .map((item) => item.trim());
}

function suggestions(value, limit = 8) {
  return (Array.isArray(value) ? value : [])
    .filter((item) => item && typeof item.text === "string" && item.text.trim())
    .slice(0, limit)
    .map((item) => ({
      text: item.text.trim(),
      due_date: /^\d{4}-\d{2}-\d{2}$/.test(item.due_date || "") ? item.due_date : "",
      confidence: item.confidence || "summary_derived",
    }));
}

function cleanRecords(records) {
  return (Array.isArray(records) ? records : []).slice(0, 200).map((record) => ({
    source_ref: String(record.source_ref || "").slice(0, 240),
    source_url: String(record.source_url || "").slice(0, 1000),
    author: String(record.author || record.source_author || "Unknown").slice(0, 160),
    body: String(record.body || "").slice(0, 4000),
    created_at: String(record.created_at || "").slice(0, 80),
  })).filter((record) => record.source_ref && record.body);
}

async function askModel(instruction, payload) {
  const token = process.env.OPENAI_API_KEY;
  if (!token) throw new Error("OpenAI API authentication unavailable");
  const response = await fetch(OPENAI_URL, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      model: MODEL,
      response_format: { type: "json_object" },
      messages: [
        { role: "system", content: instruction },
        { role: "user", content: JSON.stringify(payload) },
      ],
    }),
  });
  if (!response.ok) {
    const failure = await response.json().catch(() => ({}));
    const code = failure?.error?.code || failure?.error?.type || "unknown_error";
    throw new Error(`OpenAI API returned ${response.status} (${code})`);
  }
  const result = await response.json();
  const content = result?.choices?.[0]?.message?.content;
  if (!content) throw new Error("OpenAI API returned no content");
  return JSON.parse(content);
}

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "POST required" });
  const expectedSecret = process.env.REVIEW_AI_WEBHOOK_SECRET_V2 || process.env.REVIEW_AI_WEBHOOK_SECRET;
  if (!sameSecret(req.headers["x-review-secret"], expectedSecret))
    return res.status(401).json({ error: "unauthorized" });

  const body = typeof req.body === "string" ? JSON.parse(req.body) : (req.body || {});
  const records = cleanRecords(body.records);
  if (!records.length) return res.status(400).json({ error: "source records required" });
  try {
    if (body.mode === "weekly_thread_summary") {
      const allowed = new Set(records.map((record) => record.source_ref));
      const result = await askModel(
        "Summarize an internal weekly CE Slack discussion. Use only supplied records. " +
        "Return JSON with arrays: findings, decisions, open_points (concise strings), " +
        "action_suggestions and check_suggestions (objects with text and optional YYYY-MM-DD due_date), " +
        "and source_refs. Preserve uncertainty, do not infer owners, and cite only supplied source_refs.",
        { identity: body.identity || {}, previous_summary: body.previous_summary || {}, records },
      );
      const sourceRefs = strings(result.source_refs, 200).filter((ref) => allowed.has(ref));
      if (!sourceRefs.length) throw new Error("summary omitted valid source references");
      return res.status(200).json({ summary: {
        findings: strings(result.findings),
        decisions: strings(result.decisions),
        open_points: strings(result.open_points),
        action_suggestions: suggestions(result.action_suggestions),
        check_suggestions: suggestions(result.check_suggestions),
        source_refs: sourceRefs,
      }});
    }

    const result = await askModel(
      "Extract concise commentary, action, or dated-check suggestions from internal source records. " +
      "Return JSON {suggestions:[{source_ref,kind,body,proposed_due_date,confidence}]}. " +
      "kind must be comment, action, or check. Use only supplied text and source_refs; never infer an owner.",
      { source_type: body.source_type || "unknown", identity: body.identity || {}, records },
    );
    const allowed = new Set(records.map((record) => record.source_ref));
    const output = (Array.isArray(result.suggestions) ? result.suggestions : []).filter((item) =>
      item && allowed.has(item.source_ref) && ["comment", "action", "check"].includes(item.kind) &&
      typeof item.body === "string" && item.body.trim()
    ).slice(0, 20).map((item) => ({
      source_ref: item.source_ref,
      kind: item.kind,
      body: item.body.trim(),
      proposed_owner: "",
      proposed_due_date: /^\d{4}-\d{2}-\d{2}$/.test(item.proposed_due_date || "") ? item.proposed_due_date : "",
      confidence: item.confidence || "source_derived",
    }));
    return res.status(200).json({ suggestions: output });
  } catch (error) {
    console.error("review-summary failed:", error instanceof Error ? error.message : "unknown error");
    return res.status(502).json({ error: "summary unavailable" });
  }
}
