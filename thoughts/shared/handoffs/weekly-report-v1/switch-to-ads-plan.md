# Switch plan — Fluctuations metrics + qualifiers → ads_campaign_stats

> **✅ SHIPPED (2026-07-20, commit 175f397).** Implemented as planned, plus the matured-window
> maturity handling. See tuning-log Step 6 + cross-market-validation. CR/TR resolved via the
> `attributed_value` pair (all-ads, reconciles). Decision: **accepted ads** (canonical Omni source);
> attribution caveat documented in the sign-off spec.

_Reverses the Step-4 fct_orders unification. Motivation: single-source, fresher data, and the
canonical Omni definitions live on ads. Corrects the earlier "ads can't do completion" finding —
CR is sane when paired as `attributed_value_completed ÷ attributed_value` (not ÷ gross_bookings)._

## Canonical decomposition (all from ads_campaign_stats, Google Ads · SEARCH)
```
CVR = count_attributed_orders / count_clicks
AOV = sum_conversion_value_offline_gross_bookings / count_attributed_orders
CR  = sum_attributed_value_completed / sum_attributed_value          ← the fix (attr_value base)
TR  = sum_conversion_value_offline_revenue / (gross_bookings * CR)
RPC = revenue / clicks   ≡  CVR × AOV × CR × TR   (reconciles exactly; CR base cancels in TR)
```
Filter on every pull: `ad_platform='Google Ads'` · `campaign_advertising_channel_type='SEARCH'` ·
`(account_name != 'Things To Do' OR account_name IS NULL)` · market · date window.
Funnel frame needs 6 fields: **clicks, orders, booked, attr_value, attr_completed, revenue**.

## Code changes

**1. `fetch.py`**
- Replace `ce_daily_orders_google` (fct_orders) with the funnel fields pulled from `ads_campaign_stats`
  — fold into `ce_daily_paid_google` (already Google:Search ads) so the funnel is single-source, no
  merge/join. Add: `count_attributed_orders`, `sum_conversion_value_offline_gross_bookings`,
  `sum_attributed_value`, `sum_attributed_value_completed`, `sum_conversion_value_offline_revenue`.
- Add the `account_name != 'Things To Do'` exclusion here **and** to `ce_daily_ads` (CM1/conv) for
  consistency.
- Retire `FCT_ORDERS` usage in the fluctuation path (keep the constant; other sections may use it).

**2. `build_snapshot.py`**
- Drop the `d_orders_g` (fct) fetch + the `d_orders_g.merge(d_paid_g…)` step. `d_funnel_g` becomes the
  ads daily frame directly (columns: clicks/orders/booked/attr_value/attr_completed/revenue). Keep the
  variable name so downstream signatures don't change.

**3. `alerts.py`**
- `_driver_windows`: change `cr = completed/booked` → `cr = attr_completed/attr_value`; `tr = rev/completed`
  → `tr = rev/(booked*cr)`. Carry `attr_value`/`attr_completed` through `_osum`. (AOV/CVR unchanged.)
- `wow_driver_alerts._drv`: same CR/TR redefinition.
- `cvr_drops`, RPC-daily qualifier, MIN_ORDERS_WK floor: unchanged logic — `orders` now =
  `count_attributed_orders`, `revenue` now = ads offline revenue. Volume gates still hold.
- **Step-5 logic (collective qualifier, orders floor, direction check) is untouched — only the source
  frame feeding it changes.**

**4. `buckets.py`** — no change; `seasonality` reads `r.drivers` which now carry ads-based CR/TR.

**5. Report (`report_template.html`)**
- Add a `*` source footnote on the Fluctuations tables, highlighted:
  *"\* All metrics from ads_campaign_stats (Google Ads · Search). Completion/Take-rate via internal
  attribution (attributed conversion value). Last 3 days excluded for data maturity."*

**6. `config.py`** — optional `--week` maturity guard: warn/reject a week whose Sunday is < MATURITY_DAYS
  (3) old, so an override can't pull immature days. (Default already safe via `latest_complete_week`.)

## Decision needed
- **Scope of "all metrics":** the Losing Money / per-CE weekly `rpc`, `tr_pct`, `cr_pct` currently come
  from `combined_entity_stats` (business), NOT fct. Switch those to ads too (full consistency), or leave
  them (they're a different, business-ROI context)? **Recommend: leave for now** — they feed the CM2/ROI
  state view, not the RPC decomposition; switching them is a separate, larger change.

## Repercussions (validate, don't assume)
- **AOV/TR levels move ~12–15%** vs fct (ads attributes more gross-booking value); CVR/CR/RPC/orders/
  revenue agree within ~1–2% (verified on CE 5714 + market). WoW *movements* likely similar but the
  gate may flag a slightly different set → **must re-run the checkpoint harness + cross-market**.
- Step-4 accuracy doc conclusion ("ads completion >100%, unusable") is **superseded** — it used the
  wrong denominator. Document the corrected pairing.
- fct exclusions (city-card, fraud/dummy/failed, user_type) drop out; the ads `account_name` exclusion
  replaces them as the one filter to carry.
- Freshness improves (ads matures faster than order-grounded fct).

## Validation gate (before merge)
1. `/tmp/ckpt_market.py` on NA/IT/OC — floors honored, direction clean, drivers reconcile to RPC.
2. Diff the flagged CE set vs current fct-based build (which CEs enter/leave, and why).
3. `validate_na` still PASS (CM1/conv path unaffected).
4. Update tuning-log + sign-off spec + accuracy doc.

## Rollback
Single-commit revert restores the fct funnel; Step-5 logic is source-agnostic so nothing else moves.
