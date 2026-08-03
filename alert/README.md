# Weekly Market Alert System (merge-into-report-skill bundle)

Turns a **weekly market report** (HTML) into a Slack alert posted to that
market's channel. Built to be **merged into the report-generation skill**: after
the skill produces the weekly report, Claude runs the three scripts here to build
and post the alert per market.

**Split by source (kept internally consistent):**
- The **summary + 3 bucket tables** are read straight from the report JSON.
- The **per-CE revenue diagnosis** (the thread replies) is computed from
  **BigQuery**, user-based, so it matches Omni — exactly like the monthly alert.
  The report's own funnel/channel fields are NOT user-based enough for a correct
  paid-vs-organic-in-users demand RCA, so that half must come from BigQuery.

---

## What it produces (per market)

Two top-level Slack messages:

```
MSG 1 — Weekly Summary  (headline + 6 main metrics + top-3 up/down movers)
   └─ thread: 🔴 Losing Money            (bucket_b1)
   └─ thread: 🔻 RPC Fluctuations Down   (bucket1_fluctuations, direction=down)
   └─ thread: 🔺 RPC Fluctuations Up     (bucket1_fluctuations, direction=up)

MSG 2 — Weekly Movers  (top CEs grouped: Losing Money / RPC Down / RPC Up)
   └─ thread: per-CE revenue diagnosis (one reply per CE, BigQuery-computed)
```

Each per-CE diagnosis reply (all figures **user-based**, matching Omni):
- **Revenue (WoW)** headline (predicted revenue, the report's basis) + Omni
  week-over-week deep-link
- **Drivers of Revenue Change** — a `Driver | W-1 | W0 | Δ%` table:
  - **Traffic** = distinct users (`COUNT(DISTINCT user_id)`)
  - **CVR** = converting users / traffic  *(the CVR shown everywhere)*
  - **AOV** = gross bookings / orders
  - **Completion** = completed / gross bookings
  - **Take rate** = revenue / completed bookings
  - **⭐ Primary driver(s)** — from an internal 5-factor Shapley decomposition
    (which uses an orders/user CVR *internally only*, never displayed). Every
    factor contributing ≥30% of the move is named, e.g. `Primary drivers: CVR,
    Traffic`. No contribution % is shown.
- **Long-term Context — verdict** — `W0 | L4W avg | LY Pre | LY Post(Δ%)` for
  Revenue + all 5 drivers (seasonality view). Verdict = 🟢 Seasonal / 🔴 Anomalous
  / ⚪ Limited Data.
- **🚦 Demand RCA** — Paid vs Organic in **unique users**; if paid is the driver,
  a channel-mix breakdown in users (Google / Microsoft / Other paid).
- **📉 CVR RCA** — user CVR + funnel steps (LP2S / S2C / C2O) in users.

Every table + the summary ends with **"🔎 Find further information and actions →
weekly report"** (the market's Vercel page).

---

## Files

| File | Role |
|---|---|
| `weekly_alert.py` | Parses the report JSON for one market → writes the summary + 3 tables + MSG2 with `{"$rca": id}` thread refs. Prints `RCA_CE_IDS`/`WEEK`. Stdlib only. |
| `weekly_rca_helper.py` | Runs the WoW BigQuery query for the selected CEs + week → user-based per-CE diagnosis blocks (`rca_blocks.json`). Needs BigQuery. |
| `revenue_drop_alert.py` | Shared RCA engine (factor math, Shapley primary driver, Long-term Context, Demand/CVR RCA, Block Kit builders). Imported by the helper. |
| `sql/ce_revenue_cvr_drop_ids.sql` | The CE-filtered WoW query the helper runs (traffic = distinct users; revenue = `sum_revenue_predicted`; paid/organic/channel users; funnel steps; L4W + LY). |
| `sql/ce_revenue_cvr_drop.sql` | Full-scan WoW query (reference; the `_ids` variant is what the helper uses). |
| `post_message.py` | Posts a payload to Slack (threads, block-splitting, permalinks); resolves `{"$rca": id}` refs from the helper's output. Needs `requests`. |
| `market_channels.json` | market_slug → Slack channel ID (all point at the test channel now). |
| `requirements.txt` | `requests` + BigQuery client stack. |

---

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# BigQuery auth (project headout-analytics):
gcloud auth application-default login          # local testing (ADC)
# (production: GOOGLE_APPLICATION_CREDENTIALS=<service-account.json>)

# Slack bot token — provided out-of-band, NOT in this bundle.
export REVENUE_ALERT_SLACK_TOKEN="xoxb-…"
```
> 🔑 **Claude: ask for the token.** It's shared separately by the alert owner and
> intentionally not in this bundle. Before any real post, prompt:
> *"Please provide the Slack bot token (xoxb-…) so I can set REVENUE_ALERT_SLACK_TOKEN."*
> Never hardcode/commit it; the bot must be invited to every channel it posts to.

BigQuery **is** required now (for the per-CE diagnosis). The query is filtered to
the selected CEs and capped at 20 GB billed (~10 GB actual for ~10 CEs, a few s).

---

## The report input

The weekly report HTML embeds a `<script type="application/json" id="report-data">`
blob with `markets: [ … ]` (often several markets in one file, e.g. NA/IT/OC).
`weekly_alert.py` selects one market via `--market-slug` (e.g. `north_america`).
The report's `weekly[]` array is 12 weeks **ascending** — the report week is the
LAST element; the alert reads W0/W-1 as the two most-recent weeks.

---

## End-to-end flow (what the merged skill runs, per market)

```bash
# 1) Build the summary + tables payload; capture the CE ids + week it prints
python weekly_alert.py \
    --file "<weekly-report.html>" \
    --market-slug north_america \
    --out payload.json
#   → prints:  RCA_CE_IDS=<comma-separated ids>
#              WEEK=<week_start>..<week_end>
#   (also stored in payload.json under "_rca")

# 2) Compute the BigQuery-backed, user-based per-CE diagnosis blocks
python weekly_rca_helper.py \
    --ce-ids "<RCA_CE_IDS>" \
    --week-start <week_start> --week-end <week_end> \
    --out rca_blocks.json

# 3) Post to that market's channel (stitches the $rca refs to the blocks)
python post_message.py --payload payload.json --rca-blocks rca_blocks.json \
    --channel <market channel id>
```

- Resolve the channel from `market_channels.json[markets][<slug>]`.
- `--report-url` on step 1 is optional; derived from the slug if omitted.

**Looping all markets** (the scale step): iterate the market slugs present in the
report, run the three commands for each, posting to its channel. Keep everything
on the test channel until real channel IDs are filled in.

---

## Data-basis notes (important — kept internally consistent)

- **Revenue = `sum_revenue_predicted`** everywhere (the report's default basis),
  so the BigQuery RCA headline matches the report's summary/tables.
- **Traffic = distinct users** (`COUNT(DISTINCT user_id)`), never clicks.
- **Displayed CVR = converting users / traffic**, identical in the drivers table,
  Long-term Context, and the CVR RCA — so no two "CVR" numbers ever disagree.
- **An orders/user CVR is used only inside the Shapley** primary-driver calc (it
  makes the 5-factor decomposition close exactly). It is never displayed.
- **Demand RCA is in unique users** — paid vs organic users, then channel mix in
  users when paid is the driver. Matches Omni.
- Funnel filters mirror Omni's CE dashboard (PERFORMANCE_MAX excluded, 30-day
  completion window, no page-type filter).
- **Omni deep-links** point at the **W0 week** only (`week_start … week_end`).
  Omni's built-in *previous-period* comparison automatically pulls the prior
  7 days (= W-1), so the link lands on the exact WoW window the RCA diagnoses —
  no need to encode both weeks in the URL.

---

## Test it (safe — posts to #revenue-alert-testing)

```bash
export REVENUE_ALERT_SLACK_TOKEN="xoxb-…"     # ask the alert owner
gcloud auth application-default login          # BigQuery ADC

python weekly_alert.py --file "<weekly-report.html>" --market-slug north_america --out payload.json
#   → note the RCA_CE_IDS and WEEK it prints
python weekly_rca_helper.py --ce-ids "<RCA_CE_IDS>" --week-start <s> --week-end <e> --out rca_blocks.json
python post_message.py --payload payload.json --rca-blocks rca_blocks.json --dry-run            # inspect
python post_message.py --payload payload.json --rca-blocks rca_blocks.json --channel C0B6U94PGJ0 # post to test
```

---

## Merging into the report generation engine

After your engine writes the weekly report HTML, add one alert step that loops
the market slugs present in the report and runs the 3-command flow per market.
The scripts are plain CLIs, so the hook can be a tiny shell/Python wrapper — no
need to import anything from your engine:

```python
import json, re, subprocess, os
from pathlib import Path

REPORT = "weekly-report.html"          # the file your engine just produced
BUNDLE = Path("weekly-alert-system")   # this folder
os.environ["REVENUE_ALERT_SLACK_TOKEN"] = "<xoxb-… ask the alert owner>"
PY = "python"                          # a venv with requirements.txt installed

# market slugs actually present in the report
data = json.loads(re.search(r'id="report-data"[^>]*>(.*?)</script>',
                            Path(REPORT).read_text(), re.S).group(1))
slugs = [m["meta"]["market_slug"] for m in data["markets"]]
channels = json.loads((BUNDLE / "market_channels.json").read_text())["markets"]

for slug in slugs:
    subprocess.run([PY, "weekly_alert.py", "--file", REPORT,
                    "--market-slug", slug, "--out", "payload.json"],
                   cwd=BUNDLE, check=True)
    hand = json.loads((BUNDLE / "payload.json").read_text())["_rca"]
    ids = ",".join(hand["ce_ids"])
    subprocess.run([PY, "weekly_rca_helper.py", "--ce-ids", ids,
                    "--week-start", hand["week_start"], "--week-end", hand["week_end"],
                    "--out", "rca_blocks.json"], cwd=BUNDLE, check=True)
    subprocess.run([PY, "post_message.py", "--payload", "payload.json",
                    "--rca-blocks", "rca_blocks.json",
                    "--channel", channels[slug]], cwd=BUNDLE, check=True)

# headout = the PORTFOLIO rollup (all 42 markets) — its OWN report file, posts to
# #team-central-biz (channels["headout"]). It's part of the weekly sweep: run it
# alongside the per-market loop above. (Excluded from the Thursday ping — see
# thursday_actions_ping: it would re-ping every market's CEs.)
subprocess.run([PY, "weekly_alert.py", "--file", "weekly-report-headout.html",
                "--market-slug", "headout", "--out", "payload.json"], cwd=BUNDLE, check=True)
hand = json.loads((BUNDLE / "payload.json").read_text())["_rca"]
subprocess.run([PY, "weekly_rca_helper.py", "--ce-ids", ",".join(hand["ce_ids"]),
                "--week-start", hand["week_start"], "--week-end", hand["week_end"],
                "--out", "rca_blocks.json"], cwd=BUNDLE, check=True)
subprocess.run([PY, "post_message.py", "--payload", "payload.json", "--rca-blocks", "rca_blocks.json",
                "--slug", "headout", "--week", hand["week_start"],
                "--channel", channels["headout"]], cwd=BUNDLE, check=True)
```

Keep every `market_channels.json` entry on the test channel (`C0B6U94PGJ0`)
until the real per-market channel IDs are filled in and the bot is invited.
`weekly_alert.py` prints `RCA_CE_IDS=…` / `WEEK=…` and also writes them into
`payload.json` under `_rca`, so the middle step can read them either way.

## TODO before go-live
- Fill real per-market channel IDs in `market_channels.json` (+ invite the bot).
- Slack token + BigQuery service account via secret/env (never committed).
- Confirm the 3 buckets & column choices with GMs; tweak in `weekly_alert.py`
  (`table_losing` / `table_fluct` column lists).
