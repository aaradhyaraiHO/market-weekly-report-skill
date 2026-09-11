# Weekly Market Review (skill)

Source of truth for the Headout weekly market report — pipeline, template, spec, and final builds.
Imported 2026-07-12 from `~/analytics` safepoint branch `weekly-report-v1` (1c0b55d0).

- `scripts/weekly_report/` — pipeline: `python3 weekly_market_report.py <north_america|italy|oceania|all> --week YYYY-MM-DD`
- `thoughts/shared/market-report-weekly-v1-spec.md` — locked spec (buckets B1–B5, validation, gap classification)
- `thoughts/shared/weekly-report-v1/` — final rendered builds + gap audit
- `dbt/` — reference copies of the ce_weekly_* models; canonical home = analytics repo, PR from safepoint branch `weekly-report-v1`
- Sibling pattern: ~/market-monthly-review-skill (sync-skill.sh mirrors into analytics)

## Current bucket dependencies

Current report tables use `buckets_final`, produced by `buckets.build_buckets`.
Losing Money and RPC/CM1 thresholds live in `buckets.py`, `alerts.py`, and
`config.py`. The retired B1/B2/B3/B4 display cascade, ten-row narrative cap,
and legacy bucket sparklines are no longer generated. New snapshots omit
`bucket_b3`, `bucket_b4`, and `bucket_cascade`; existing snapshots remain readable.

B1 is still computed because its movement rows supply Scale-Up tROAS context.
The global builder also retains B1/B3/B4 candidate IDs to preserve its existing
CE drawer selection; market builds no longer run B3/B4. Removing these remaining
classifiers requires migrating those dependencies and checking CE-selection and
Scale-Up parity. Cached-snapshot metric fallbacks remain supported.

## V2 baseline verification

Phase 1 freezes the observable V1 producer/consumer boundary with synthetic edge cases,
minimized and pseudonymized sparse/dense/global snapshot shapes, snapshot contracts, downstream
coverage, manual browser-smoke evidence, a coverage matrix, and golden outputs under
`tests/weekly_report/`.
The verification path is local and no-write with respect to the checkout and every production
integration:

```sh
python3 scripts/weekly_report/verify_baseline.py
```

## V2 Market Headlines preview

The V2 headline is an isolated, no-publish renderer over the existing schema-v1
snapshot. It does not change the V1 report, bucket engines, Slack payloads,
Sheets, publishing, or sidecar loading.

```sh
python3 scripts/weekly_report/render_v2.py \
  tests/weekly_report/fixtures/snapshot_north_america_2026-08-02.json \
  --out /tmp/weekly-v2-headline.html
```

An optional approved goals sidecar may be supplied with `--goals`. Its top-level
shape is `{"markets":{"market_slug":{...}}}`. A usable market record requires
`month`, `monthly_goal`, `mtd_revenue`, `forecast_revenue`, and `as_of`; otherwise
the report explicitly shows that the target comparison is unavailable.

Build that frozen sidecar with the same canonical revenue field used by V1:

```sh
python3 scripts/weekly_report/build_v2_goals.py \
  /path/to/snapshot_north_america_2026-08-02.json \
  --out /tmp/weekly-v2-goals.json
```

The command is read-only against BigQuery and performs no publishing. It uses
an approved market target when present, falls back to a CE-target roll-up only
when the market row is absent, and never adds the two grains together. Because
`revenue_goals` is Drive-backed, the local gcloud login must include Drive
access (`gcloud auth login --enable-gdrive-access`).

The V2 All-CE view reads the complete Overall/Paid weekly metric set,
TY/LY trajectories, metadata, customer-country composition and current
`buckets_final` membership directly from the same snapshot. It supports
snapshot-backed search and multi-select filters, sorting, top-mover order,
grouping, ratio-safe subtotals, contribution context and expandable
W0/W-1/change/WoW/YoY evidence. BDM and Growth regions are never inferred from
management type or lifecycle stage. They can be attached with
`--ce-dimensions` using this optional shape:

```json
{
  "markets": {
    "market_slug": {
      "ce_id": {
        "bdm_region": "BDM region name",
        "growth_region": "Growth region name"
      }
    }
  }
}
```

When this approved mapping is absent, the two organizational filters remain
disabled while all snapshot-backed portfolio controls, evidence and CE detail
continue to work. The V2 CE drawer consumes the live schema-v1 Overall/Paid
series, Shapley result, channels, funnel, TGIDs, booking-grain variants,
five-band lead-time mix, and customer-country mix. Missing blocks omit cleanly;
resource trendlines are not synthesized when a historical sidecar is absent.
Saved views, watchlists, custom groups and general review notes remain separate
migration slices. Diagnostic Action status/comments preserve the V1 Sheet
contract and sync through the authenticated notebook review proxy.

## V2 parallel weekly run and release gate

V1 remains the default weekly renderer. To build V1 and V2 from the same fresh
snapshots, fetch approved monthly targets, and run the V2 parity gate without
publishing either artifact:

```sh
python3 scripts/weekly_report/weekly_market_report.py all \
  --week YYYY-MM-DD --renderer both --no-open
```

The V2 run writes one report per market under
`thoughts/shared/weekly-report-v2/` and a machine-readable release manifest to
`.cache/weekly_report/v2_release_<week>.json`. The gate fails closed if V2
changes shared V1 revenue, All-CE membership, current `buckets_final`
membership, mover order, or Shapley evidence. Optional goals and resource
enrichments report per-market warnings instead of taking down the V1 build.

Existing snapshots can be rendered and checked without rerunning BigQuery:

```sh
python3 scripts/weekly_report/release_v2.py \
  --glob '.cache/weekly_report/snapshot_*_YYYY-MM-DD.json' \
  --out-dir /tmp/weekly-v2-release \
  --manifest /tmp/weekly-v2-release/manifest.json
```

Approved live target enrichment is included by default. Use `--no-fetch-goals`
only for an explicitly offline render; missing supplied goals are then recorded
as per-market warnings. A partial market run preserves unrequested records in
the shared goals artifact, while every requested market is refreshed or removed
after a failed lookup so stale data cannot masquerade as current. These commands
do not publish, deploy, post to Slack, or write Sheets. The staged publish path
continues to reject V2 until the route is explicitly activated after a reviewed
parallel run; V1 therefore remains the rollback path.

### Autonomous V2 release package

The canonical full-run command packages all 17 configured markets plus Headout,
runs the V1 baseline and V2 parity gates, stages a self-contained notebook, and
dry-runs every market alert:

```sh
python3 scripts/weekly_report/run_v2_release.py \
  --week YYYY-MM-DD \
  --base-notebook /absolute/path/to/verified-complete-notebook
```

The safe default performs no deployment, Slack post, or Sheet write. It records a
machine-readable receipt at `.cache/weekly_report/v2_run_<week>.json` and stages
the notebook under `.cache/weekly_report/v2_package_<week>/notebook/`. Inspect the
exact plan without running anything with `--plan`.

Production writes remain explicit and ordered after all gates:

```sh
python3 scripts/weekly_report/run_v2_release.py \
  --week YYYY-MM-DD \
  --base-notebook /absolute/path/to/verified-complete-notebook \
  --deploy --post-alerts
```

Use that authorized release command once, not first as a build and then again
against the same populated staging directory. Browser mode pauses after deploy;
resume the receipt's `planned_steps` verification and frozen-delivery commands,
not generation/deployment. Read `docs/v2/release-workflow.md` before executing.

The canonical V2 release now includes Headout in alert preparation and delivery.
Supply `--base-notebook /absolute/path/to/verified-complete-notebook` (or
`WEEKLY_BASE_NOTEBOOK`) so staging preserves the whole notebook and its archives.
Never deploy an empty report-only directory. The staging destination must be empty.
All RCA is prepared before delivery; the frozen bundle is reused for retries.
Live posting requires authenticated exact-artifact link checks and Slack read-back
access for every destination, including private Headout (`groups:history`).
The standalone V2 `run_weekly.py --post` path is disabled; V1 is unchanged.
See `docs/v2/unattended-release-readiness-2026-09-11.md` for activation gates,
credentials, and safe retry commands. V1 remains the rollback renderer.

The V2 publish stage also installs `api/review.js` from
`scripts/weekly_report/notes/review_proxy_api.js`. The notebook runtime must
provide `AUTH_SECRET`, `ALLOWED_DOMAIN`, `REVIEW_PROXY_SECRET`, and
`REVIEW_APPS_SCRIPT_URL`, and its package must include `jose`. The Apps Script
deployment must have the same `REVIEW_PROXY_SECRET` script property. V2 keeps a
local draft while editing, but only displays an action/comment as synced after
this authenticated proxy confirms the existing Weekly Actions Sheet write.

## Weekly Market Alert V2

The locked two-parent V2 alert is isolated under `alert/v2/` and consumes the
live schema-v2 report. V1 remains the default alert and rollback path.

Check static send readiness without network calls or Slack writes:

```sh
python3 alert/v2/check_readiness.py
```

Once a V2 report is live, generate a safe dry run through the staged runner:

```sh
python3 scripts/weekly_report/run_weekly.py <market|all> \
  --week <YYYY-MM-DD> --stage alert --alert-version v2
```

Do not add `--post`; the standalone V2 live path is disabled. Use the canonical
release and frozen delivery flow above. It requires approved BGM IDs/channel
routes, exact-week reports, all selected CE RCA, live report proof and Slack
read-back access before any new parent is sent. Missing required RCA fails closed.
Preserve the existing duplicate ledger and per-message journals during retries.

Deployment/runtime prerequisites that intentionally stay outside the repository:

- authenticated read access to BigQuery for OKR and RCA enrichment;
- `REVENUE_ALERT_SLACK_TOKEN` supplied by the deployment secret store (never a file);
- the alert bot invited to every channel in `alert/market_channels.json`;
- one reviewed all-market plus Headout package before authorized frozen delivery.

## Maintained skill instructions

The GitHub-tracked V2 skill is `.claude/skills/weekly-market-report-v2/SKILL.md`.
Its release procedure is `docs/v2/release-workflow.md`; the legacy report and V2
alert skills route there too. Keep any installed local copy of the V2 skill in
sync with this version. Code tests/pushes, live deployment and scheduling
activation are separate states.
