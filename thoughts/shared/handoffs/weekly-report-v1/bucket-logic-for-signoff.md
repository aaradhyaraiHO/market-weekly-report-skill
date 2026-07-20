# Weekly Market Report — Bucket Classification Logic

_For review & sign-off · covers how every action bucket is defined and built · v1 (2026-07-20)_

## What this is

Each week, every Combined Entity (CE) in a market is scored against a fixed set of rules and
sorted into **action buckets**. This doc states the exact logic so it can be approved and handed
to owners. Two principles run throughout:

- **Monthly = state, Weekly = change.** The weekly report is tuned to catch *movement* (a swing
  this week), while still flagging chronic *states* (a CE bleeding for a month).
- **All paid-marketing signals are scoped to paid Google Search only**, sourced from
  `ads_campaign_stats` — the same source as the Omni dashboards. Revenue-per-click and its drivers
  (CVR·AOV·Completion·Take-rate), the margin signal, and the ROI/spend columns all use paid
  Google-Search data. This is a campaign-action report, not a full-funnel analysis.
- **Data-maturity handling.** The report is generated for the just-completed week, but paid
  attribution (orders / revenue / completion) takes ~3 days to settle. So the **Fluctuations bucket
  compares the *matured portion* of the report week against the same days a week earlier** (volume
  floors pro-rated), while §1 headlines — on business predicted revenue, which settles instantly —
  stay on the full report week. The 28-day ROI/spend context uses the last fully-matured week.
- **Attribution caveat (read before acting).** Because paid signals use *Google Ads attribution*,
  they occasionally diverge from order-truth — Google can credit fewer/more conversions than
  actually occurred. A flagged down-swing is Google's attributed movement, not always a real
  order decline. Cross-check a surprising flag against actual orders before cutting spend.

A CE must be **active** to be considered: revenue or spend in at least 3 of the last 4 weeks.

---

## How buckets are built (the pipeline)

1. **Detect movement once.** Four detectors look for revenue-quality swings; a CE that trips more
   than one is assigned to a single "home" detector by priority (margin → revenue-per-click daily →
   conversion-rate weekly → weekly collective), so it is never double-counted.
2. **Filter to the real opportunities.** A multi-metric gate (below) removes minor/noisy swings,
   capping the list to roughly the top 5–6 per week.
3. **Sort into families.** Surviving swings split by direction — *down* → **Defend**, *up* →
   **Compound**. Separately, CEs are scanned for chronic loss (Defend), scale-up potential
   (Compound), and lifecycle stage.

**Overlap is intentional.** Chronic-loss ("Losing Money") and this-week-swing ("Fluctuations") are
different lenses on the same CE — a CE can appear in both because they answer different questions
(is it bleeding over a month? / did it break this week?). Exclusivity applies only *within* a bucket.

---

## The buckets

### DEFEND — protect revenue at risk

**1. Losing Money** (chronic state — 4-week loss). Funded CEs (>$1,000 paid spend over 4 weeks) that
aren't earning it back. Each gets one **Status** (the table's Status column), checked first-match-wins
— the Status tells you *why* it's flagged and *what to do*:

- **Full waste** — spent money but got *zero* paid conversions in 4 weeks. Total loss. → Pause first.
- **Paused** — was funded across the window, but spend is $0 *this week*. ROI reads blank (no spend to
  divide by). It's already stopped. → Confirm the pause was intentional.
- **Tracking gap** — *is* spending this week, but ROI wouldn't compute (current-week margin data didn't
  populate). A data-feed issue, *not* waste — the CE may be fine. → Verify tracking before acting.
- **Bleeder** — the core case: ROI < 100% and a material 4-week loss (≥ $200). Severity sub-tag:
  *New* (1st week) · *"3w/4w…"* (weeks bleeding) · *Chronic* (≥6 weeks) · *Escalating* (ROI just fell
  >30 points week-over-week — getting worse fast). → Pause or scale down (guideline below).
- **Recovering** — still bleeding, but the weekly loss has *at least halved* vs the prior 3 weeks.
  Climbing out. → Hold, don't cut. (Sorted to the bottom.)
- Small bleeders (<$1k spend) roll into a single summary line.

*Action guideline for a bleeder 3–4 weeks in with no recovery:* New CE → pause if ROI <30%; Existing CE
→ pause if ROI <70%; otherwise scale down within the week.

**2. Fluctuations ↓** (this-week revenue-quality drop). A CE qualifies via **any** detector, then
must clear the gate:
- **Conversion rate (CVR):** >30% week-over-week drop, ≥300 clicks and ≥10 orders in both weeks.
  *CVR is weekly-only by decision — a 3-day CVR dip isn't actionable and is caught by other alerts.*
- **Revenue-per-click (RPC), daily:** ≥20% deviation vs the 28-day baseline **and** ≥25% short-term
  move, holding for 3 days.
- **Weekly collective:** a CE whose drivers collectively collapsed week-over-week (see gate) even if
  no single daily pattern tripped — this catches multi-driver weekly drops the daily engine misses.
- **Margin-per-conversion (CM1):** a separate profitability signal (see note below).

### COMPOUND — double down on what's working

**3. Scale-Up.** ROI ≥ 155% in at least 3 of the last 4 weeks, and not cliffing (ROI didn't fall
>30 points this week). Ranked by estimated incremental revenue from scaling.

**4. Fluctuations ↑.** Same detectors as Fluctuations ↓, direction = up.

### LIFECYCLE — grow the next tier (CEs never yet at "Pro" scale)

**5. New CEs** — two lanes:
- **Graduated** — trailing run-rate now reaches Pro scale ($3,333/mo) and the CE was not Pro in any
  of the prior 4 quarters (genuinely new).
- **On-pace** — not Pro yet, but running at ≥70% of the Pro weekly rate and revenue is rising.

**6. Iteration / Untapped** — never-Pro CEs split by whether a team is actively working them:
- **Iteration** (has recent team input) — reason cascade: *Waiting for takeoff* (barely any traffic)
  → *Needs inputs* (converts below its category median) → *Manual check*.
- **Untapped** (no team input) — meaningful scale, nobody working it.

---

## The multi-metric gate (why we don't over-flag)

Revenue-per-click decomposes into four drivers: **Conversion rate × Average order value ×
Completion rate × Take rate.** For each down-swing:

- A driver is **"red"** if it moved adversely by ≥15%.
- **One red driver** → keep only if that driver moved ≥25% (conversion rate: ≥30%).
- **Two or more red** → keep only if the drivers *together* pulled revenue-per-click down ≥20%
  ("collective impact").

This is what caps the weekly list to the top ~5–6 opportunities and surfaces the driver that caused
each drop (not just "revenue fell").

---

## Two decisions to confirm

1. **Revenue-per-click qualifier is baseline AND short-term** (≥20% off the 28-day norm *and* a ≥25%
   recent move) — i.e. abnormal *and* new. This is stricter than "either/or"; it's what keeps the
   list to real breaks and matches the alert set reviewed in the meeting.
2. **Margin-per-conversion (CM1) is a separate signal, exempt from the four-driver gate.** It
   measures per-order profitability, which the revenue-per-click drivers don't decompose — so it's
   gated by its own volume/statistical checks, not the driver gate. It catches margin erosion at
   stable revenue (e.g. discounting) that the other signals would miss.

---

## Validation

Logic validated live on all three pilot markets (North America, Italy, Oceania) for week
2026-07-06: **6 / 6 / 7 down-swings** — on the ~5-6 target. Every flagged driver reconciles to the
revenue-per-click move; volume floors and direction checks pass on all markets.

_Sign-off: ______________________ · Date: ___________
