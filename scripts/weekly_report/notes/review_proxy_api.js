import { createHmac } from "node:crypto";
import { jwtVerify } from "jose";

// The legacy proxy secret name is deliberately unsupported; Review owns separate credentials.
const APPS_SCRIPT_URL = process.env.REVIEW_MODE_APPS_SCRIPT_URL;
const REVIEW_ACTION = /^review_/;
// Keep this boundary intentionally narrow.  The Review proxy is not a generic
// tunnel to either Apps Script deployment; diagnostic/V1 routes must use the
// legacy actions proxy instead.
const REVIEW_ACTIONS = new Set([
  "review_comment_list", "review_comment_upsert", "review_comment_delete",
  "review_work_list", "review_work_upsert", "review_work_delete",
  "review_receipt_list", "review_receipt_upsert", "review_outcome_list", "review_outcome_upsert",
  "review_timeline", "review_timeline_event_upsert", "review_backlog", "review_reconciliation",
  "review_telemetry_record",
  "review_set_list", "review_set_upsert", "review_memory",
  "review_weekly_list", "review_weekly_note_upsert", "review_weekly_note_delete",
  "review_weekly_slack_post", "review_weekly_sync", "review_summary_decide", "review_mention_resolve", "review_thread_list",
  "review_suggestion_list", "review_suggestion_decide", "review_source_inbox",
  "review_source_reconcile",
  "review_slack_post", "review_slack_scan",
]);

function parseCookies(header) {
  const output = {};
  String(header || "").split(/;\s*/).forEach((pair) => {
    const index = pair.indexOf("=");
    if (index > 0) output[pair.slice(0, index)] = pair.slice(index + 1);
  });
  return output;
}

function canonicalParams(params) {
  return [...params.entries()]
    .filter(([key]) => key !== "actor_sig")
    .sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0)
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
    .join("\n");
}

async function authenticatedActor(req) {
  const token = parseCookies(req.headers.cookie).mmr_session;
  const authSecret = process.env.AUTH_SECRET;
  if (!token || !authSecret) return null;
  const { payload } = await jwtVerify(token, new TextEncoder().encode(authSecret));
  const email = String(payload.email || "").trim().toLowerCase();
  const domain = String(process.env.ALLOWED_DOMAIN || "headout.com").toLowerCase();
  if (!email.endsWith(`@${domain}`)) return null;
  return { email, name: String(payload.name || email) };
}

// Two read attempts, including response-body reads, fit inside the browser's
// 45-second budget. Mutations never enter this retry path.
const READ_ATTEMPT_TIMEOUT_MS = 20000;
async function readBackend(target) {
  for (let attempt = 0; attempt < 2; attempt++) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), READ_ATTEMPT_TIMEOUT_MS);
    try {
      const upstream = await fetch(target, { method: "GET", redirect: "follow", signal: controller.signal });
      const text = await upstream.text();
      if (upstream.status >= 500 && upstream.status <= 599) throw new Error("review upstream unavailable");
      return { upstream, text };
    } catch (error) {
      if (attempt === 1) throw error;
    } finally {
      clearTimeout(timeout);
    }
  }
}

export default async function handler(req, res) {
  if (!["GET", "POST"].includes(req.method)) return res.status(405).json({ ok: false, error: "GET or POST required" });

  let actor;
  try { actor = await authenticatedActor(req); } catch (_) { actor = null; }
  res.setHeader("cache-control", "no-store");
  if (!actor) return res.status(401).json({ ok: false, code: "AUTH_REQUIRED", error: "authenticated BGM identity required" });

  if (!APPS_SCRIPT_URL)
    return res.status(503).json({ ok: false, error: "isolated review backend unavailable" });

  const base = `https://${req.headers.host || "market-notebook.vercel.app"}`;
  const incoming = new URL(req.url, base);
  let body = null;
  if (req.method === "POST") {
    try { body = typeof req.body === "string" ? JSON.parse(req.body) : (req.body || {}); }
    catch (_) { return res.status(400).json({ ok: false, error: "invalid JSON" }); }
  }
  const params = req.method === "POST" ? new URLSearchParams(Object.entries(body).map(([key, value]) => [key, String(value ?? "")])) : incoming.searchParams;
  if (params.get("action") === "whoami")
    return res.status(200).json({ ok: true, actor_email: actor.email, actor_name: actor.name });
  const action = params.get("action") || "";
  if (!REVIEW_ACTION.test(action) || !REVIEW_ACTIONS.has(action))
    return res.status(400).json({ ok: false, error: "review action required" });

  // A browser cannot supply infrastructure credentials. The authenticated
  // server adds its existing project automation credential to the signed POST
  // used by the Apps Script summarizer. It never enters a URL or response.
  params.delete("review_ai_protection_bypass");
  if (req.method === "POST" && ["review_weekly_sync", "review_slack_scan"].includes(action) && process.env.VERCEL_AUTOMATION_BYPASS_SECRET)
    params.set("review_ai_protection_bypass", process.env.VERCEL_AUTOMATION_BYPASS_SECRET);

  const signingSecret = String(process.env.REVIEW_MODE_PROXY_SECRET || "").trim();
  if (!signingSecret) return res.status(503).json({ ok: false, error: "review proxy signing unavailable" });

  let target;
  const started = Date.now();
  let noteTimer;
  try {
    target = new URL(APPS_SCRIPT_URL);
    if (target.protocol !== "https:") throw new Error("HTTPS required");
  } catch (_) {
    return res.status(503).json({ ok: false, error: "isolated review backend misconfigured" });
  }
  params.set("actor_email", actor.email);
  params.set("actor_ts", String(Math.floor(Date.now() / 1000)));
  const signature = createHmac("sha256", signingSecret)
    .update(canonicalParams(params))
    .digest("hex");
  params.set("actor_sig", signature);
  if (req.method === "GET") params.forEach((value, key) => target.searchParams.set(key, value));

  res.setHeader("cache-control", "no-store");
  try {
    let upstream, text;
    if (req.method === "GET") {
      ({ upstream, text } = await readBackend(target));
    } else {
      const controller = action === "review_comment_upsert" ? new AbortController() : null;
      if (controller) noteTimer = setTimeout(() => controller.abort(), 18000);
      upstream = await fetch(target, {
        method: "POST", redirect: "follow", headers: {"content-type": "application/json"},
        ...(controller ? { signal: controller.signal } : {}),
        body: JSON.stringify(Object.fromEntries(params.entries()))
      });
      text = await upstream.text();
    }
    res.setHeader("server-timing", `review;dur=${Date.now() - started}`);
    // A signed-request failure is a service problem, not an expired browser
    // session. Do not send the user through a pointless sign-in loop.
    let result; try { result = JSON.parse(text); } catch (_) {}
    if (result && result.ok === false && result.error === "authenticated BGM identity required") {
      // Never log request bodies, identities, signatures, or service credentials.
      console.warn("review_backend_auth_failed", { action, elapsed_ms: Date.now() - started });
      return res.status(502).json({ ok: false, code: "REVIEW_BACKEND_AUTH_FAILED", error: "The note service could not verify this request. Your draft is kept; please retry. If it persists, report this error." });
    }
    res.status(upstream.status);
    res.setHeader("content-type", upstream.headers.get("content-type") || "application/json; charset=utf-8");
    return res.send(text);
  } catch (_) {
    if (req.method === "POST" && action === "review_comment_upsert")
      return res.status(504).json({ ok: false, code: "REVIEW_SAVE_UNCONFIRMED", error: "The save response did not arrive. Check the saved note before retrying." });
    return res.status(502).json({ ok: false, error: "review backend unavailable" });
  } finally {
    clearTimeout(noteTimer);
  }
}
