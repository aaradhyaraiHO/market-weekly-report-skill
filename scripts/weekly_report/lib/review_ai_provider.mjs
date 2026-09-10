// Server-only Review configuration. Changing provider never changes storage or
// silently retries the same source against another provider.
export function useReviewOpenAI() {
  const provider = String(process.env.REVIEW_AI_PROVIDER || "anthropic").trim().toLowerCase();
  if (!["anthropic", "openai"].includes(provider)) throw new Error("Review AI provider is not supported");
  return provider === "openai";
}

export function reviewAIConfigured() {
  try {
    return Boolean(useReviewOpenAI() ? process.env.REVIEW_OPENAI_API_KEY : process.env.ANTHROPIC_API_KEY);
  } catch { return false; }
}

// Validate the object/array/string schema subset used by the Review routes.
// A malformed provider result must not become an empty, apparently valid summary.
function matchesSchema(value, schema) {
  if (schema.enum && !schema.enum.includes(value)) return false;
  if (schema.type === "string") return typeof value === "string";
  if (schema.type === "array") return Array.isArray(value) && value.every(item => matchesSchema(item, schema.items));
  if (schema.type === "object") {
    if (!value || typeof value !== "object" || Array.isArray(value)) return false;
    const properties = schema.properties || {};
    return (schema.required || []).every(key => Object.hasOwn(value, key)) &&
      Object.keys(value).every(key => Object.hasOwn(properties, key) && matchesSchema(value[key], properties[key]));
  }
  return false;
}

export async function askReviewOpenAI(instruction, payload, schema, maxOutputTokens = 4000) {
  const token = process.env.REVIEW_OPENAI_API_KEY;
  if (!token) throw new Error("Review OpenAI authentication unavailable");
  const response = await fetch("https://api.openai.com/v1/responses", {
    method: "POST",
    signal: AbortSignal.timeout(45000),
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      model: process.env.REVIEW_OPENAI_MODEL || "gpt-4.1-mini-2025-04-14",
      store: false,
      instructions: instruction,
      input: [{ role: "user", content: JSON.stringify(payload) }],
      max_output_tokens: maxOutputTokens,
      text: { format: { type: "json_schema", name: "review_result", strict: true, schema } },
    }),
  });
  if (!response.ok) {
    const failure = await response.json().catch(() => ({}));
    const code = failure?.error?.code;
    const reason = code === "insufficient_quota" ? "credits_unavailable"
      : response.status === 401 ? "authentication_failed"
      : response.status === 429 ? "rate_limited" : "request_rejected";
    // Never include provider error messages, credentials, or source content in logs.
    throw new Error(`OpenAI ${response.status}: ${reason}`);
  }
  const result = await response.json().catch(() => null);
  if (result?.status !== "completed") throw new Error("OpenAI response incomplete");
  const content = (Array.isArray(result.output) ? result.output : [])
    .filter(item => item.type === "message")
    .flatMap(item => Array.isArray(item.content) ? item.content : []);
  if (content.some(item => item.type === "refusal")) throw new Error("OpenAI response refused");
  const text = content.filter(item => item.type === "output_text").map(item => item.text).join("");
  let output;
  try { output = JSON.parse(text); } catch { throw new Error("OpenAI returned invalid structured output"); }
  if (!matchesSchema(output, schema)) throw new Error("OpenAI returned invalid structured output");
  return output;
}
