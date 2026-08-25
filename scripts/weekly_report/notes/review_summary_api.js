import { timingSafeEqual } from "node:crypto";

const ANTHROPIC_URL = "https://api.anthropic.com/v1/messages";
const MODEL = process.env.REVIEW_AI_MODEL || "claude-haiku-4-5-20251001";
// REVIEW_MODE_* is the canonical isolated-service name.  The two older names
// make this route deployable against the existing Review-only Vercel setup
// during the rename; neither belongs to the legacy diagnostic action service.
const REVIEW_AI_SECRET = process.env.REVIEW_MODE_AI_WEBHOOK_SECRET ||
  process.env.REVIEW_AI_WEBHOOK_SECRET_V2 || process.env.REVIEW_AI_WEBHOOK_SECRET;

const WEEKLY_SCHEMA = {
  type: "object",
  properties: {
    findings: { type: "array", items: { type: "string" } },
    decisions: { type: "array", items: { type: "string" } },
    open_points: { type: "array", items: { type: "string" } },
    action_suggestions: { type: "array", items: { type: "object", properties: {
      text: { type: "string" }, due_date: { type: "string" }, confidence: { type: "string" },
    }, required: ["text", "due_date", "confidence"], additionalProperties: false } },
    check_suggestions: { type: "array", items: { type: "object", properties: {
      text: { type: "string" }, due_date: { type: "string" }, confidence: { type: "string" },
    }, required: ["text", "due_date", "confidence"], additionalProperties: false } },
    source_refs: { type: "array", items: { type: "string" } },
  },
  required: ["findings", "decisions", "open_points", "action_suggestions", "check_suggestions", "source_refs"],
  additionalProperties: false,
};

const SUGGESTIONS_SCHEMA = {
  type: "object",
  properties: { suggestions: { type: "array", items: { type: "object", properties: {
    source_ref: { type: "string" }, kind: { type: "string", enum: ["comment", "action", "check"] },
    body: { type: "string" }, proposed_due_date: { type: "string" }, confidence: { type: "string" },
  }, required: ["source_ref", "kind", "body", "proposed_due_date", "confidence"], additionalProperties: false } } },
  required: ["suggestions"],
  additionalProperties: false,
};

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

function addDays(ymd, days) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(ymd || ""))) return "";
  const value = new Date(`${ymd}T00:00:00.000Z`);
  value.setUTCDate(value.getUTCDate() + days);
  return value.toISOString().slice(0, 10);
}

function normalizeWeeklyCheckDates(value, identity) {
  return suggestions(value).map((item) => {
    // We only resolve the unambiguous relative phrase "next week". It is
    // anchored to the Review week's start, never to the server's current date,
    // so a retry or delayed five-minute sync cannot silently change the check.
    if (!item.due_date && /\b(?:review|revisit|check|follow up|follow-up).*\bnext week\b|\bnext week\b/i.test(item.text)) {
      const dueDate = addDays(identity?.week_start, 7);
      if (dueDate) return { ...item, due_date: dueDate, confidence: "summary_derived_relative_date" };
    }
    return item;
  });
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

async function askModel(instruction, payload, schema) {
  const token = process.env.ANTHROPIC_API_KEY;
  if (!token) throw new Error("Anthropic API authentication unavailable");
  const response = await fetch(ANTHROPIC_URL, {
    method: "POST",
    headers: { "x-api-key": token, "anthropic-version": "2023-06-01", "Content-Type": "application/json" },
    body: JSON.stringify({
      model: MODEL,
      max_tokens: 2500,
      system: instruction,
      messages: [{ role: "user", content: JSON.stringify(payload) }],
      tools: [{ name: "emit_result", description: "Return the validated review result.", input_schema: schema, strict: true }],
      tool_choice: { type: "tool", name: "emit_result", disable_parallel_tool_use: true },
    }),
  });
  if (!response.ok) {
    const failure = await response.json().catch(() => ({}));
    const code = failure?.error?.code || failure?.error?.type || "unknown_error";
    throw new Error(`Anthropic API returned ${response.status} (${code})`);
  }
  const result = await response.json();
  const output = result?.content?.find((item) => item?.type === "tool_use" && item?.name === "emit_result")?.input;
  if (!output || typeof output !== "object") throw new Error("Anthropic API returned no structured result");
  return output;
}

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "POST required" });
  const expectedSecret = REVIEW_AI_SECRET;
  // A missing secret must never turn this endpoint into an accidentally open
  // summarizer.  Callers can surface the explicit unavailable state and retain
  // the original Slack records until the service is configured.
  if (!expectedSecret)
    return res.status(503).json({ error: "review summary unavailable" });
  if (!sameSecret(req.headers["x-review-secret"], expectedSecret))
    return res.status(401).json({ error: "unauthorized" });

  if (!process.env.ANTHROPIC_API_KEY)
    return res.status(503).json({ error: "review summary unavailable" });

  const body = typeof req.body === "string" ? JSON.parse(req.body) : (req.body || {});
  const records = cleanRecords(body.records);
  if (!records.length) return res.status(400).json({ error: "source records required" });
  try {
    if (body.mode === "weekly_thread_summary") {
      const allowed = new Set(records.map((record) => record.source_ref));
      const result = await askModel(
        "Summarize an internal weekly CE Slack discussion. Use only supplied records. " +
        "Return JSON with arrays: findings, decisions, open_points (concise strings), " +
        "action_suggestions and check_suggestions (objects with text and optional YYYY-MM-DD due_date). " +
        "For an explicit 'next week' check, emit it as a check_suggestion with blank due_date; the workflow will anchor it to the Review week, " +
        "and source_refs. Preserve uncertainty, do not infer owners, and cite only supplied source_refs.",
        { identity: body.identity || {}, previous_summary: body.previous_summary || {}, records },
        WEEKLY_SCHEMA,
      );
      const sourceRefs = strings(result.source_refs, 200).filter((ref) => allowed.has(ref));
      if (!sourceRefs.length) throw new Error("summary omitted valid source references");
      return res.status(200).json({ summary: {
        findings: strings(result.findings),
        decisions: strings(result.decisions),
        open_points: strings(result.open_points),
        action_suggestions: suggestions(result.action_suggestions),
        check_suggestions: normalizeWeeklyCheckDates(result.check_suggestions, body.identity || {}),
        source_refs: sourceRefs,
      }});
    }

    const result = await askModel(
      "Extract concise commentary, action, or dated-check suggestions from internal source records. " +
      "Return JSON {suggestions:[{source_ref,kind,body,proposed_due_date,confidence}]}. " +
      "kind must be comment, action, or check. Use only supplied text and source_refs; never infer an owner.",
      { source_type: body.source_type || "unknown", identity: body.identity || {}, records },
      SUGGESTIONS_SCHEMA,
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
