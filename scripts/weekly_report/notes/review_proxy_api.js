import { createHmac } from "node:crypto";
import { jwtVerify } from "jose";

const APPS_SCRIPT_URL = process.env.REVIEW_APPS_SCRIPT_URL ||
  "https://script.google.com/macros/s/AKfycbyvXB69WxTM1p9qO4tQXxPfV28mkXOOiTKqW8J4SH2P_vtblTYd6bUQGJSb8HyLLGhOjA/exec";

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
  if (req.method !== "GET") return res.status(405).json({ ok: false, error: "GET required" });

  let actor;
  try { actor = await authenticatedActor(req); } catch (_) { actor = null; }
  if (!actor) return res.status(401).json({ ok: false, error: "authenticated BGM identity required" });

  const base = `https://${req.headers.host || "market-notebook.vercel.app"}`;
  const incoming = new URL(req.url, base);
  if (incoming.searchParams.get("action") === "whoami")
    return res.status(200).json({ ok: true, actor_email: actor.email, actor_name: actor.name });

  const signingSecret = process.env.REVIEW_PROXY_SECRET ||
    process.env.REVIEW_AI_WEBHOOK_SECRET_V2 || process.env.REVIEW_AI_WEBHOOK_SECRET;
  if (!signingSecret) return res.status(503).json({ ok: false, error: "review proxy signing unavailable" });

  const target = new URL(APPS_SCRIPT_URL);
  incoming.searchParams.forEach((value, key) => target.searchParams.set(key, value));
  target.searchParams.set("actor_email", actor.email);
  target.searchParams.set("actor_ts", String(Math.floor(Date.now() / 1000)));
  const signature = createHmac("sha256", signingSecret)
    .update(canonicalParams(target.searchParams))
    .digest("hex");
  target.searchParams.set("actor_sig", signature);

  try {
    const upstream = await fetch(target, { method: "GET", redirect: "follow" });
    const text = await upstream.text();
    res.status(upstream.status);
    res.setHeader("content-type", upstream.headers.get("content-type") || "application/json; charset=utf-8");
    res.setHeader("cache-control", "no-store");
    return res.send(text);
  } catch (_) {
    return res.status(502).json({ ok: false, error: "review backend unavailable" });
  }
}
