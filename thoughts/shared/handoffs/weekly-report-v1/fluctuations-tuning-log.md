# Fluctuations tuning log (NA 2026-07-06)

_Checkpoints to compare each threshold/logic change._

## Step 1 — paid Google-Search decomposition (CVR×AOV×TR)
NA 2026-07-06 · fluctuations: cvr=10 rpc=6 cm1=8 · down=15
| CE | signal | alert | mag% | dominant |
|---|---|---|---|---|
| Disneyland Resort California | cm1_per_conv | sustained_3d | -41.2 | CVR |
| Steamboat Natchez Tours | cm1_per_conv | sustained_3d | -31.9 | CVR |
| World of Coca-Cola | cm1_per_conv | sustained_3d | 41.9 |  |
| Hawaii Luaus | cm1_per_conv | sdlw | 73.6 |  |
| High Roller Observation Whee | cm1_per_conv | sustained_3d | 74.9 |  |
| Kennedy Space Center | cm1_per_conv | sustained_3d | 93.4 |  |
| Cruises - San Francisco | cm1_per_conv | sustained_3d | 105.5 |  |
| Canada's Wonderland Tickets | cm1_per_conv | sustained_3d | 122.6 |  |
| Six Flags Fiesta Texas Ticke | cvr | wow | -50.4 | CVR |
| Statue of Liberty | cvr | wow | -47.2 | CVR |
| Star of Honolulu | cvr | wow | -42.2 | CVR |
| New England Aquarium | cvr | wow | -41.9 | CVR |
| Kings Island Tickets | cvr | wow | -39.4 | CVR |
| Discovery Cove Orlando | cvr | wow | -39.3 | CVR |
| Seattle Whale Watching Tours | cvr | wow | -36.7 | CVR |
| LEGOLAND Florida | cvr | wow | -36.1 | CVR |
| Six Flags: Magic Mountain | cvr | wow | -33.8 | CVR |
| Museum of Modern Art (MoMA) | cvr | wow | -31.6 | CVR |
| Niagara Falls (Canada) Tours | rpc | sustained_3d | -41.0 | AOV |
| Boston Whale Watching Cruise | rpc | sustained_3d | -38.3 | CVR |
| Las Vegas Shows | rpc | sustained_3d | -23.1 | AOV |
| Cruises - Chicago | rpc | sustained_3d | 38.8 |  |
| Alcatraz Tours | rpc | sustained_3d | 64.9 |  |
| LEGOLAND New York | rpc | sustained_3d | 78.4 |  |

## Step 2 — 3-day persistence 20% → 25%
NA 2026-07-06 · fluctuations: cvr=10 rpc=6 cm1=6 · down=15
| CE | signal | alert | mag% |
|---|---|---|---|
| Disneyland Resort California | cm1_per_conv | sustained_3d | -41.2 |
| World of Coca-Cola | cm1_per_conv | sustained_3d | 41.9 |
| High Roller Observation Whee | cm1_per_conv | sustained_3d | 74.9 |
| Kennedy Space Center | cm1_per_conv | sustained_3d | 93.4 |
| Cruises - San Francisco | cm1_per_conv | sustained_3d | 105.5 |
| Canada's Wonderland Tickets | cm1_per_conv | sustained_3d | 122.6 |
| Six Flags Fiesta Texas Ticke | cvr | wow | -50.4 |
| Statue of Liberty | cvr | wow | -47.2 |
| Star of Honolulu | cvr | wow | -42.2 |
| New England Aquarium | cvr | wow | -41.9 |
| Kings Island Tickets | cvr | wow | -39.4 |
| Discovery Cove Orlando | cvr | wow | -39.3 |
| Seattle Whale Watching Tours | cvr | wow | -36.7 |
| LEGOLAND Florida | cvr | wow | -36.1 |
| Six Flags: Magic Mountain | cvr | wow | -33.8 |
| Museum of Modern Art (MoMA) | cvr | wow | -31.6 |
| Steamboat Natchez Tours | rpc | sustained_3d | -49.8 |
| Niagara Falls (Canada) Tours | rpc | sustained_3d | -41.0 |
| Boston Whale Watching Cruise | rpc | sustained_3d | -38.3 |
| Las Vegas Shows | rpc | sustained_3d | -23.1 |
| Alcatraz Tours | rpc | sustained_3d | 64.9 |
| LEGOLAND New York | rpc | sustained_3d | 78.4 |

## Step 3 — fct_orders 4-driver + multi-metric gate
NA 2026-07-06 · down-swings after gate = 7 (was 15). Decomposition = CVR×AOV×Completion×Take-rate, all Google-Search paid, orders from fct_orders. Gate: 1 red→≥25% (CVR≥30) · ≥2 red→collective RPC≤−20% · red-floor 15% · CM1/conv exempt.
| CE | alert | dominant | CVRΔ | AOVΔ | CRΔ | TRΔ |
|---|---|---|---|---|---|---|
| Discovery Cove Orlando | WoW | AOV | -23 | -33 | -3 | 4 |
| Disneyland Resort Californ | 3D | CVR | -23 | 8 | 1 | -2 |
| Kings Island Tickets | WoW | Take rate | -27 | -21 | 0 | -30 |
| LEGOLAND Florida | WoW | CVR | -40 | 15 | 0 | -2 |
| Six Flags Fiesta Texas Tic | WoW | CVR | -50 | 6 | 0 | -9 |
| Star of Honolulu | WoW | CVR | -41 | -26 | 26 | 6 |
| Statue of Liberty | WoW | CVR | -40 | 5 | -4 | 15 |

## Step 4 — unify RPC + CVR qualifiers onto fct_orders
NA 2026-07-06 · down-swings = 6 (was 7 with ads-qualifier + fct-gate). Qualifier + gate + decomposition all on one Google-Search funnel (fct orders + ads clicks).
Change in coverage: +Hawaii Luaus (fct-CVR drop the ads qualifier missed — false-negative closed); −Discovery Cove, −Kings Island (see handoff note: daily RPC engine gatekeeps WoW-collective drops).
  - Disneyland Resort California (3D, CVR)
  - Hawaii Luaus (WoW, CVR)
  - LEGOLAND Florida (WoW, CVR)
  - Six Flags Fiesta Texas Tickets (WoW, CVR)
  - Star of Honolulu (WoW, CVR)
  - Statue of Liberty (WoW, CVR)

## Step 5 — weekly collective-impact qualifier + weekly floors + Google-only CM1
NA 2026-07-06 · down-swings = 6 · up-swings = 8. Four changes, each checkpoint-validated (qualifier sets diffed vs live BQ after every edit):
1. **wow_driver_alerts** (new 4th qualifier): the Step-3 single/multi red gate evaluated on WoW funnel drivers for EVERY active CE — closes the Kings-Island gap (weekly collective drops no longer gatekept by 3-day daily persistence). Emitted as rpc/wow, deduped after CM1 → RPC-daily → CVR-WoW. Down-only, and only when net WoW-RPC is actually negative (a lone red offset by positive drivers = mix shift; caught Cruises-SF at RPC +332% pre-fix).
2. **MIN_ORDERS_WK = 10** on all weekly paths (cvr_drops, cvr_gray_zone, wow_driver_alerts), BOTH weeks — weekly analog of the daily min_conv_per_day=10. Kills Six Flags Fiesta Texas (5 orders W0) + LEGOLAND Florida (9 orders W0).
3. **CM1/conv → Google-Search only** (dropped Bing from ce_daily_ads — last Google+Bing signal). ⚠ Shifts the 2026-06-29 reference: CM1 gate now reproduces 4/5 CEs (Arte Museum NY's swing was partly Bing) — re-baseline validate_na.
4. **Daily engine: short-term trigger direction must match baseline dev** (SDLW/7d-WoW same sign as the 28d deviation). Zero behavioral change on 07-06 AND 06-29 — theoretical-hole closure only.

### Design decision (Jul-20) — CM1/conv stays exempt from the Step-3 driver gate. **Permanent, not provisional.**

**Why it's structurally correct (category mismatch, not convenience).** The Step-3 gate asks "is this
RPC move real + material across its four drivers?" — and those drivers are `RPC = CVR × AOV × CR × TR`,
a decomposition of **revenue-per-click**. CM1/conv is **margin-per-conversion** — a different quantity
the four RPC drivers do not multiply out to. Running CM1 through the driver gate isn't stricter QA; it
asks a question the math can't answer (a genuine margin collapse can have all four RPC drivers flat, and
vice-versa). CM1/conv is deliberately a *separate* signal because it catches a failure mode RPC
structurally misses: **margin erosion at stable revenue** (discounting / cost-creep — volume and
revenue-per-click hold, but each order earns less).

**It is not ungated.** CM1/conv has its own appropriate gate — the daily POF engine (≥20% baseline dev,
≥25% short-term, CV≤0.5, ≥10 conv/day, ≥500 clicks/35d, 3-day persistence ≥25%). Different signal,
different gate — coherent, not asymmetric-by-accident.

**The one real (latent) gap — materiality, NOT the driver gate.** CM1's POF gate checks *statistical*
abnormality + *volume*, but has **no $-materiality floor** — so the theoretical risk is a
statistically-real-but-financially-trivial CM1 alert. Not biting today: the single CM1 down-row is
**Disneyland — CM1/conv $50→$31/conv, 6-day persistent, $5.9K/wk spend** — large, sustained, expensive
(textbook margin erosion, correctly surfaced).

**Correct future dial if CM1 rows ever bloat:** add a **margin-materiality floor to CM1's OWN engine**
(min CM1-$ swing or min spend/wk) — the margin-world analog of what the collective-impact check does for
RPC. Do **not** force CM1 through the RPC driver gate. Documented-only for now (no code) — no evidence
it's needed, and an unused threshold is complexity the report hasn't earned.

| CE | signal | alert | dominant | mag% |
|---|---|---|---|---|
| Kings Island Tickets | rpc (collective) | WoW | Take rate | -59 |
| Discovery Cove Orlando | rpc (collective) | WoW | AOV | -48 |
| Star of Honolulu | cvr | WoW | CVR | -41 |
| Statue of Liberty | cvr | WoW | CVR | -40 |
| Disneyland Resort California | cm1_per_conv | 3D | CVR | -39 |
| Hawaii Luaus | cvr | WoW | CVR | -34 |

Qualifier counts: cm1=5 · rpc-daily=8 · cvr-wow=3 · wow-collective=5 (3 overlap upstream) · cv-excluded=0 · gray-zone=2.
