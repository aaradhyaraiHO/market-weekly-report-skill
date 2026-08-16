// Keep the report UI behind the existing Headout session, but allow the
// server-to-server review webhook to enforce its own X-Review-Secret contract.
// Merge this matcher into the deployment project's existing middleware.
export const config = {
  matcher: ["/((?!api/auth|api/review-summary|api/granola-review).*)"],
};
