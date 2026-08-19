/**
 * /api/actions — legacy diagnostic action proxy.
 *
 * This path is intentionally separate from /api/review. It targets only the
 * established version-13 Weekly Report Notes deployment, and permits only the
 * three diagnostic action routes. It must never read any REVIEW_MODE_* value.
 */
import { createHmac } from "node:crypto";
import { jwtVerify } from "jose";

const LEGACY_ACTIONS_URL = "https://script.google.com/macros/s/AKfycbyvXB69WxTM1p9qO4tQXxPfV28mkXOOiTKqW8J4SH2P_vtblTYd6bUQGJSb8HyLLGhOjA/exec";
const ALLOWED_ACTIONS = new Set(["action_list", "action_upsert", "action_delete"]);

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
    .sort(([a], [b]) => a.localeCompare(b))
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
  return { email };
}

export default async function handler(req, res) {
  if (!["GET", "POST"].includes(req.method)) return res.status(405).json({ ok: false, error: "GET or POST required" });
  let actor;
  try { actor = await authenticatedActor(req); } catch (_) { actor = null; }
  if (!actor) return res.status(401).json({ ok: false, error: "authenticated Headout identity required" });

  const base = `https://${req.headers.host || "market-notebook.vercel.app"}`;
  const incoming = new URL(req.url, base);
  const body = req.method === "POST" ? (typeof req.body === "string" ? JSON.parse(req.body) : (req.body || {})) : null;
  const params = req.method === "POST"
    ? new URLSearchParams(Object.entries(body).map(([key, value]) => [key, String(value ?? "")]))
    : incoming.searchParams;
  const action = params.get("action") || "";
  if (!ALLOWED_ACTIONS.has(action)) return res.status(400).json({ ok: false, error: "diagnostic action required" });

  const signingSecret = process.env.ACTIONS_PROXY_SECRET;
  if (!signingSecret) return res.status(503).json({ ok: false, error: "diagnostic action proxy unavailable" });
  const target = new URL(LEGACY_ACTIONS_URL);
  params.set("actor_email", actor.email);
  params.set("actor_ts", String(Math.floor(Date.now() / 1000)));
  params.set("actor_sig", createHmac("sha256", signingSecret).update(canonicalParams(params)).digest("hex"));
  if (req.method === "GET") params.forEach((value, key) => target.searchParams.set(key, value));

  try {
    const upstream = await fetch(target, req.method === "POST" ? {
      method: "POST", redirect: "follow", headers: { "content-type": "application/json" },
      body: JSON.stringify(Object.fromEntries(params.entries())),
    } : { method: "GET", redirect: "follow" });
    const text = await upstream.text();
    res.status(upstream.status);
    res.setHeader("content-type", upstream.headers.get("content-type") || "application/json; charset=utf-8");
    res.setHeader("cache-control", "no-store");
    return res.send(text);
  } catch (_) {
    return res.status(502).json({ ok: false, error: "diagnostic action backend unavailable" });
  }
}
