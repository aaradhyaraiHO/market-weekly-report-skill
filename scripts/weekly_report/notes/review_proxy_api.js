import { createHmac } from "node:crypto";
import { jwtVerify } from "jose";

const APPS_SCRIPT_URL = process.env.REVIEW_MODE_APPS_SCRIPT_URL;

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
  return { email, name: String(payload.name || email) };
}

export default async function handler(req, res) {
  if (!["GET", "POST"].includes(req.method)) return res.status(405).json({ ok: false, error: "GET or POST required" });

  let actor;
  try { actor = await authenticatedActor(req); } catch (_) { actor = null; }
  if (!actor) return res.status(401).json({ ok: false, error: "authenticated BGM identity required" });

  if (!APPS_SCRIPT_URL)
    return res.status(503).json({ ok: false, error: "isolated review backend unavailable" });

  const base = `https://${req.headers.host || "market-notebook.vercel.app"}`;
  const incoming = new URL(req.url, base);
  const body = req.method === "POST" ? (typeof req.body === "string" ? JSON.parse(req.body) : (req.body || {})) : null;
  const params = req.method === "POST" ? new URLSearchParams(Object.entries(body).map(([key, value]) => [key, String(value ?? "")])) : incoming.searchParams;
  if (params.get("action") === "whoami")
    return res.status(200).json({ ok: true, actor_email: actor.email, actor_name: actor.name });

  const signingSecret = process.env.REVIEW_MODE_PROXY_SECRET;
  if (!signingSecret) return res.status(503).json({ ok: false, error: "review proxy signing unavailable" });

  let target;
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

  try {
    const upstream = await fetch(target, req.method === "POST" ? {
      method: "POST", redirect: "follow", headers: {"content-type": "application/json"},
      body: JSON.stringify(Object.fromEntries(params.entries()))
    } : { method: "GET", redirect: "follow" });
    const text = await upstream.text();
    res.status(upstream.status);
    res.setHeader("content-type", upstream.headers.get("content-type") || "application/json; charset=utf-8");
    res.setHeader("cache-control", "no-store");
    return res.send(text);
  } catch (_) {
    return res.status(502).json({ ok: false, error: "review backend unavailable" });
  }
}
