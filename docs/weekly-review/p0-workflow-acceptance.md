# BGM Review P0 acceptance matrix

This is the single acceptance checklist for the core Slack-first BGM workflow. The deterministic design fixture is `review-workflow-design-mockup.html?scenario=<state>`. It makes no backend calls and preserves the selected market, week, stable CE ID, and optional BGM-observation draft while states are exercised.

| State | Deterministic fixture | Visible BGM choice | Intended backend operation | Gate status |
| --- | --- | --- | --- | --- |
| Thread discovery loading | `?scenario=loading` | No Start or Continue action is shown | Read `ce_threads` using `market_slug + stable_ce_id` | Visually demonstrated; backend read contract verified; live latency not exercised here |
| Discovery failure | `?scenario=failure` | Retry; never infer “no thread” | No mutation; retry authoritative discovery | Visually demonstrated; failure contract verified |
| No existing thread | `?scenario=none` | Start Slack discussion | Create initial parent and bind market + CE | Visually demonstrated; backend contract verified; no live mutation in design gate |
| Prior bound thread, no current-week activity | `?scenario=prior` | Continue existing (recommended), or Start new | Continue reuses the bound parent; Start new enters confirmation | Visually demonstrated with deterministic fixture; backend contract verified; controlled Preview mutation pending approval |
| Current-week thread | `?scenario=current` | Open/continue current thread, or Start new | Open current binding; Start new enters confirmation | Visually demonstrated; current binding read verified; no live mutation in design gate |
| Start-new confirmation | `?scenario=startnew` | Required reason, channel/mentions preview, Cancel, Confirm | Create replacement parent with actor, reason, predecessor/successor permalinks, market/week/CE and idempotency key | Visually demonstrated; backend contract verified; controlled Preview mutation pending approval |
| No Slack needed | `?scenario=noslack` | Explicit finish-time BGM exception with concise reason | Store exception only with final CE/week review receipt | Visually demonstrated as an on-demand finish exception; not default discussion chrome; no live mutation in design gate |

## Context and preservation checks

- **Market/channel:** North America routes to `#adhoc-north-america` in every fixture.
- **Identity:** every state displays stable CE `3111`, not a name-derived key.
- **Week:** every state displays `w/c 16 Aug 2026`.
- **Drafts:** the optional BGM observation sits outside the replaced Slack-state region, so switching lifecycle states does not recreate or clear it.
- **Start new:** the preview includes market channel, mentions, CE/week context, and predecessor-preservation copy before confirmation.
- **No false no-thread:** loading and failure states expose no Start action.

## Agreed product checklist

| Product item | Status |
| --- | --- |
| One treatment control | Visually demonstrated |
| Authoritative thread discovery with loading, failure, no-thread, prior, and current states | Visually demonstrated; backend contract verified |
| BGM discretion between Continue and Start new | Visually demonstrated; backend contract verified |
| Start-new reason, preview, confirmation, provenance and idempotency | Visually demonstrated; backend contract verified; live mutation deferred |
| No-Slack reason only as a finish-time exception | Visually demonstrated; backend contract verified |
| Approved Slack summary as authoritative discussion memory | Visually demonstrated; backend contract verified |
| Suggested / Open / Later / Completed separation | Visually demonstrated |
| Optional BGM observation and read-only historical role notes | Visually demonstrated; compatibility contract verified |
| Completion without a separate outcome form | Visually demonstrated; backend contract verified |
| Responsive queue, drawer round-trip, draft preservation and CE Memory fail-soft behavior | Existing product contracts preserved; complete Preview revalidation deferred until visual approval |
| Granola activation, prioritization/hero/cooldown, PostgreSQL migration, automatic causal attribution | Deferred by product decision |
| Stable Preview deployment, controlled writes, production deployment | Verified and deployed on 2026-08-31; Headout remains Review-free |
