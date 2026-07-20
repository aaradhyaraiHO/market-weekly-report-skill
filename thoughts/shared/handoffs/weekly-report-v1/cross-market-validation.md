# Cross-market validation — fluctuations logic (Step 5)

Validates the Step-5 fluctuation engine (WoW collective qualifier · MIN_ORDERS_WK=10 ·
Google-only CM1 · short-term direction check) on **IT + OC**, the two stale markets.
NA is the calibrated reference (6 down / 8 up). Week: **2026-07-06** unless noted.

Harness: `/tmp/ckpt_market.py <slug> <week>` — recomputes the 4 qualifier sets live from BQ,
runs the Step-3 gate, and asserts: weekly floors honored · collective is net-negative RPC ·
drivers reconcile to RPC · overlaps deduped downstream.

## Assertions checked per market
1. **Floors** — every CVR-WoW / WoW-collective qualifier clears ≥300 clicks + ≥10 orders BOTH weeks.
2. **Direction** — every WoW-collective row has net WoW-RPC < 0 (no mix-shift false positives).
3. **Dedup** — no CE double-listed across cm1 → rpc-daily → cvr-wow → wow-collective.
4. **Reconciliation** — CVR×AOV×CR×TR ≈ RPC move (±3pp) for collective rows.
5. **Count** — down-swings land near the meeting's ~5-6 target (sanity, not a hard gate off-NA).

---

## North America (reference) — 2026-07-06
`down=6 · up=8` · cm1=5 rpc-daily=8 cvr-wow=3 wow-collective=5 · cv-excluded=0. All assertions pass.
Collective catches: Kings Island −59%, Discovery Cove −48% (surface nowhere else).

## Italy — 2026-07-06
`down=6 · up=7` · cm1=4 rpc-daily=7 cvr-wow=2 wow-collective=6 · cv-excluded=3. **All assertions pass.**
Down-swings: Teatro La Fenice −61% (CVR) · Train Passes-Zurich −50% (AOV) · Airport Transfers-Venice
−45% (AOV) · Mirabilandia −34% (CVR) · Veiled Christ −30% (TR) · Blue Grotto −30% (AOV).
Net-new via collective qualifier (4): Train Passes-Zurich (AOV −44), Airport Transfers-Venice
(AOV −29/CVR −28), **Veiled Christ (TR −27, CVR +3)**, **Blue Grotto (AOV −42, CVR +13)**.

## Oceania — 2026-07-06
`down=7 · up=9` · cm1=6 rpc-daily=6 cvr-wow=4 wow-collective=7 · cv-excluded=0. **All assertions pass.**
Down-swings: Kaikoura Whale Watching −44% (CVR) · Hobbiton −40% (CVR) · Dreamworld −37% (AOV) ·
Kuranda Scenic Railway −34% (CVR) · Sydney Tower Eye −34% (AOV) · Currumbin Wildlife −33% (Completion) ·
Cruises-Perth −27% (AOV). Net-new via collective (3): Sydney Tower Eye (AOV −29), **Currumbin
(CR −24 — completion-driven)**, **Cruises-Perth (AOV −32, CVR +19)**.

---

## Findings / anomalies

**1. Logic is robust cross-market — zero anomalies.** Floors honored, direction clean (no mix-shift
false positives), drivers reconcile to RPC (±3pp), dedup correct on all three markets. No code change
needed; the Step-5 engine generalizes off the NA calibration.

**2. HEADLINE: the collective qualifier directly fixes the meeting's "AOV/TR underrepresented"
complaint — verified on all 3 markets.** The Jul-19 note: *"Most current flags are CVR-only; take rate
and AOV fluctuations are underrepresented."* Of the 7 net-new collective catches across IT+OC, **5 are
AOV/TR/CR-dominant**, and three have **positive CVR** (Blue Grotto CVR +13/AOV −42 · Cruises-Perth
CVR +19/AOV −32 · Veiled Christ CVR +3/TR −27). The pre-Step-5 weekly path (CVR-WoW-only) would have
missed every one. This is the qualifier earning its place, not padding it — it's surfacing the exact
class the meeting said was invisible.

**3. Counts: NA 6 · IT 6 · OC 7 down-swings** — all on/near the ~5-6 target. OC is +1 over; every OC row
is a legit ≥27% reconciling drop, so I did **not** tune. If strictly ≤6 everywhere is wanted, the only
lever is a *global* dial (`FX_COLLECTIVE_MIN` 20→25 or `FX_SINGLE_MIN` 25→30) — but that would also drop
real NA/IT catches. Recommend leaving as-is; 7 on the smallest market is noise, not drift.

**4. Eyeball item (not a bug): Currumbin Wildlife (OC) is Completion-dominant (CR −24%)** — rare, since
CR is usually stable ~92%. Assertions confirm it reconciles, so it's a real completed-vs-booked drop
(likely a supply/fulfilment issue worth an Ops look), not a data artifact. Flagging because CR-dominant
rows are unusual enough to sanity-check in the live report.

**5. CV-excluded working:** IT dropped 3 CEs on the noisy-baseline CV gate (cm1=4, cv-excluded=3);
NA/OC had 0. Expected behavior — the gate removes statistically unreliable CM1 baselines.

**Verdict: Step-5 logic validated across all 3 pilot markets. Ship-ready pending Slack sign-off.**

---

## Round 2 — ads source + matured-window (2026-07-20, commit 175f397)

Default run (report week = just-ended **2026-07-13→07-19**; §4 matured window **07-13→07-17, 5d** vs
07-06→07-10, pro-rated floors). All-ads source. Assertions pass on all 3 (reconciliation, direction,
floors, no immature-day leakage).

| Market | §4 window | down | up |
|---|---|---|---|
| North America | 07-13→07-17 (5d) | 7 | 3 |
| Italy | 07-13→07-17 (5d) | **14** ⚠ | 2 |
| Oceania | 07-13→07-17 (5d) | 6 | 3 |

**⚠ Italy = 14 down-swings** — >2× the ~5-6 target. Not a correctness issue (all reconcile), but worth
a tuning look. Likely drivers: (a) the 5-day matured window is thinner/noisier on driver ratios,
especially with pro-rated floors (~214 clicks / 7 orders) letting smaller CEs through; (b) ads
attribution on a smaller market; (c) genuinely a rough IT week (many −40%+ CVR drops: Palazzo Vecchio,
Matterhorn, Jungfraujoch…). **Recommend:** eyeball the IT §4 list before sign-off; if it's window-noise
rather than real, the dial is either the pro-rated floor multiplier or a min-absolute floor on the
partial window. NA/OC are on-target, so this is IT-specific, not a systemic over-fire.

**Attribution caveat (all markets):** flags are Google-attributed movement; cross-check surprising
ones against actual orders before acting (see New England Aquarium in the sign-off spec).
