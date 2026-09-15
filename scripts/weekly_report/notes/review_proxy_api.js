import { createHmac, randomUUID } from "node:crypto";
import { request as httpsRequest } from "node:https";
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
// The one-time ContentService response is a GET, including after a mutation.
// Keep this hop off fetch's shared connection pool: live timing isolated stalls
// before its response headers while the original Apps Script hop was fast.
// A fresh TLS connection retains normal certificate verification and the same
// abort budget. It never re-executes the original action or forwards its body.
function fetchReviewContentOnce(url, signal, trace) {
  return new Promise((resolve, reject) => {
    const started = Date.now();
    const req = httpsRequest(url, { method: "GET", agent: false, signal }, response => {
      const chunks = [];
      const body = new Promise((done, fail) => {
        response.on("data", chunk => chunks.push(chunk));
        response.on("end", () => done(Buffer.concat(chunks).toString("utf8")));
        response.on("error", fail);
        response.on("aborted", () => fail(new Error("review content interrupted")));
      });
      // Redirect bodies can be canceled without a text() consumer.
      body.catch(() => {});
      resolve({ status: response.statusCode,
        headers: { get: name => response.headers[name.toLowerCase()] || null },
        body: { cancel: async () => response.destroy() }, text: () => body });
    });
    req.on("socket", socket => {
      for (const phase of ["lookup", "connect", "secureConnect"])
        socket.once(phase, () => console.info("review_content_connection", { ...trace, phase, elapsed_ms: Date.now() - started }));
    });
    req.on("error", reject);
    req.end();
  });
}
async function fetchReviewContent(url, signal, trace) {
  // A one-time mutation result can be consumed even if its acknowledgement is
  // lost. Preserve its original deadline and durable-ID reconciliation; do not
  // cut it short or assume the response URL can safely be reused.
  if (trace.original_method === "POST") return fetchReviewContentOnce(url, signal, trace);
  // Healthy content headers arrived in 85–137ms; stalled connections stayed
  // silent after TLS until the entire 20s backend attempt expired. Recover
  // that response GET, not the backend operation. Three 3s header budgets stay
  // inside the existing overall read deadline; body reads retain that deadline.
  for (let contentAttempt = 1; contentAttempt <= 3; contentAttempt++) {
    if (signal?.aborted) throw new Error("review content aborted");
    const controller = new AbortController();
    const abort = () => controller.abort();
    if (signal) signal.addEventListener("abort", abort, { once: true });
    const timer = setTimeout(abort, 3000);
    let handedOff = false;
    const cleanup = () => { clearTimeout(timer); if (signal) signal.removeEventListener("abort", abort); };
    try {
      const response = await fetchReviewContentOnce(url, controller.signal, { ...trace, content_attempt: contentAttempt });
      clearTimeout(timer);
      handedOff = true;
      const readText = response.text, cancel = response.body.cancel;
      response.text = () => readText().finally(cleanup);
      response.body.cancel = async () => { try { await cancel(); } finally { cleanup(); } };
      return response;
    } catch (error) {
      console.warn("review_content_retry", { ...trace, content_attempt: contentAttempt, timeout: controller.signal.aborted, exhausted: contentAttempt === 3 });
      if (signal?.aborted || contentAttempt === 3) throw error;
    } finally {
      if (!handedOff) cleanup();
    }
  }
}
// ContentService returns the result through a separate one-time URL. Follow
// only its HTTPS content host, with no caching on *every* hop. Never replay the
// original POST to recover an uncertain response.
async function fetchReviewUpstream(target, init, trace = {}) {
  let url = new URL(target), options = { ...init, redirect: "manual", cache: "no-store" };
  for (let hop = 0; hop < 4; hop++) {
    const started = Date.now();
    const fields = { ...trace, hop, host: url.hostname, method: options.method };
    let response;
    try {
      response = url.hostname === "script.googleusercontent.com"
        ? await fetchReviewContent(url, init.signal, { ...trace, original_method: init.method })
        : await fetch(url, options);
      console.info("review_hop_headers", { ...fields, status: response.status, elapsed_ms: Date.now() - started });
    } catch (error) {
      console.warn("review_hop_failed", { ...fields, phase: "headers", elapsed_ms: Date.now() - started, timeout: !!init.signal?.aborted });
      throw error;
    }
    if (![301, 302, 303, 307, 308].includes(response.status)) return response;
    const location = response.headers.get("location");
    // Release the redirect response before issuing another fetch. Leaving its
    // body unread can strand pooled connections during concurrent CE reads.
    if (response.body) await response.body.cancel();
    if (!location) throw new Error("review redirect missing");
    const next = new URL(location, url);
    console.info("review_content_redirect", { ...trace, hop: hop + 1, status: response.status, method: options.method, host: next.hostname });
    if (next.protocol !== "https:" || next.hostname !== "script.googleusercontent.com")
      throw new Error("unexpected review redirect");
    // Never forward a mutation body or its signed credentials to a redirect.
    if (options.method === "POST" && ![301, 302, 303].includes(response.status))
      throw new Error("unsafe review POST redirect");
    options = { method: "GET", redirect: "manual", cache: "no-store", signal: init.signal };
    url = next;
  }
  throw new Error("review redirect limit");
}
async function readBackend(makeTarget, action, request_id) {
  for (let attempt = 0; attempt < 2; attempt++) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), READ_ATTEMPT_TIMEOUT_MS);
    try {
      const trace = { action, request_id, attempt: attempt + 1 };
      const upstream = await fetchReviewUpstream(makeTarget(), { method: "GET", signal: controller.signal }, trace);
      const bodyStarted = Date.now();
      let text;
      try {
        text = await upstream.text();
        console.info("review_body_complete", { ...trace, elapsed_ms: Date.now() - bodyStarted, status: upstream.status });
      } catch (error) {
        console.warn("review_body_failed", { ...trace, elapsed_ms: Date.now() - bodyStarted, timeout: controller.signal.aborted });
        throw error;
      }
      let body; try { body = JSON.parse(text); } catch (_) {}
      // ContentService serves JSON via a one-time redirect. A transient HTML
      // error (including a redirect 404) is not a Review result. Retry reads
      // only; preserve genuine JSON validation/access errors without retrying.
      const transportFailure = upstream.status === 429 || upstream.status >= 500 ||
        (![401, 403].includes(upstream.status) && (!body || typeof body.ok !== "boolean"));
      if (transportFailure) {
        console.warn("review_read_transport_failure", { action, request_id, attempt: attempt + 1, status: upstream.status });
        throw new Error("review upstream unavailable");
      }
      return { upstream, text };
    } catch (error) {
      console.warn("review_read_attempt_failed", { action, request_id, attempt: attempt + 1, timeout: controller.signal.aborted });
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
  const requestId = randomUUID();
  res.setHeader("x-review-request-id", requestId);
  let noteTimer;
  try {
    target = new URL(APPS_SCRIPT_URL);
    if (target.protocol !== "https:") throw new Error("HTTPS required");
  } catch (_) {
    return res.status(503).json({ ok: false, error: "isolated review backend misconfigured" });
  }
  function signParams() {
    params.set("actor_email", actor.email);
    params.set("actor_ts", String(Math.floor(Date.now() / 1000)));
    // Distinct signed requests must not reuse a cached ContentService redirect.
    // The nonce is covered by the existing signature; it adds no permission.
    params.set("actor_nonce", randomUUID());
    const signature = createHmac("sha256", signingSecret).update(canonicalParams(params)).digest("hex");
    params.set("actor_sig", signature);
  }

  res.setHeader("cache-control", "no-store");
  try {
    let upstream, text;
    if (req.method === "GET") {
      ({ upstream, text } = await readBackend(() => {
        signParams();
        const attemptTarget = new URL(target);
        params.forEach((value, key) => attemptTarget.searchParams.set(key, value));
        return attemptTarget;
      }, action, requestId));
    } else {
      signParams();
      // Only an opaque nonce enters the POST URL; identity, text and secrets
      // remain exclusively in the signed JSON body.
      target.searchParams.set("transport_nonce", params.get("actor_nonce"));
      const controller = action === "review_comment_upsert" ? new AbortController() : null;
      if (controller) noteTimer = setTimeout(() => controller.abort(), 18000);
      upstream = await fetchReviewUpstream(target, {
        method: "POST", headers: {"content-type": "application/json"},
        ...(controller ? { signal: controller.signal } : {}),
        body: JSON.stringify(Object.fromEntries(params.entries()))
      }, { action, request_id: requestId, attempt: 1 });
      text = await upstream.text();
    }
    res.setHeader("server-timing", `review;dur=${Date.now() - started}`);
    // A signed-request failure is a service problem, not an expired browser
    // session. Do not send the user through a pointless sign-in loop.
    let result; try { result = JSON.parse(text); } catch (_) {}
    if (result && result.ok === false && /^authenticated BGM identity required(?: \[(missing_field|expired|signature_mismatch)\])?$/.test(result.error || "")) {
      // Never log request bodies, identities, signatures, or service credentials.
      const reason = String(result.error).match(/\[(missing_field|expired|signature_mismatch)\]$/);
      console.warn("review_backend_auth_failed", { action, elapsed_ms: Date.now() - started, reason: reason ? reason[1] : "unclassified" });
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
    console.info("review_request_complete", { action, request_id: requestId, elapsed_ms: Date.now() - started });
    clearTimeout(noteTimer);
  }
}
