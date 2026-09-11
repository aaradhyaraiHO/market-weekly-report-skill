---
name: weekly-market-report-v2
description: Build, inspect, verify, and safely release Headout Weekly Market Report V2. Use for weekly snapshots, targets, movers, CE drawers, Mini Audit, V1/V2 parity, full-notebook staging, and duplicate-safe market plus Headout alert delivery.
---

# Weekly Market Report V2

Use the canonical weekly repository and its existing shared data engine. V1 remains available as the fallback; a code push is not production deployment or scheduling activation.

## Start safely

- Read `README.md`, inspect the branch and `git status --short`, and preserve unrelated changes. Do not create another checkout unless requested.
- For data-contract work, read `references/architecture.md`.
- For orchestration, deployment, alerting or unattended readiness, read `docs/v2/release-workflow.md` in the repository completely. That is the maintained operator procedure; dated readiness notes are evidence, not activation permission.
- Report generation is read-only against sources. Deploying, posting, editing Sheets or enabling scheduling requires user authorization for that action.

## Data and report invariants

- Use complete Sunday–Saturday weeks, passed explicitly as their Sunday start. Do not fall back to a prior week or release an incomplete preview as completed.
- Reuse shared snapshot metrics, `buckets_final`, mover order, Shapley output and sidecar conventions. Confirm grain, dates, IDs, units and null handling before editing a metric; do not recreate calculations in the browser.
- Google/Bing evidence is additive: retain raw operands and comparison history for all configured markets and the true-global Headout build. Follow `docs/v2/future-platform-history-2026-09-11.md` when changing this path. Do not change SQL/formulas/buckets, backfill live reports or invent missing values as a side effect.
- Optional report enrichments fail independently with explicit unavailable states. Required alert RCA is different: every selected Top/Bottom CE must be enriched before any new parent is sent. Missing/failed RCA blocks the release, not silently skips a CE.
- Preserve notes, current comments, Mini Audit, CE memory, historical pages and runtime ledgers. A UI patch does not authorize data regeneration or alert replay.
- CSEE + Nordics retain their current shared-page/two-dataset behavior; true aggregation is paused unless the user reopens it.
- Follow the repository's existing UI tokens and components. Keep transformations in pure Python view models where practical, JavaScript focused on interaction/display.

## Build and verify

Inspect the complete no-write plan first:

```sh
python3 scripts/weekly_report/run_v2_release.py --week YYYY-MM-DD \
  --base-notebook /absolute/path/to/verified-complete-notebook --plan
```

Without `--plan`, the default builds local artifacts and performs read-only queries; it does not deploy, post Slack or write Sheets. A complete verified base notebook and a separate empty staging destination are required. The plan includes all configured markets plus Headout, frozen RCA preparation, parity and preservation gates.

For a targeted offline renderer loop:

```sh
python3 scripts/weekly_report/verify_baseline.py
python3 scripts/weekly_report/render_v2.py <snapshot.json> --out /tmp/weekly-v2.html
```

Supply approved frozen goals when needed; use BigQuery read-only to build them. Never label missing source data as zero or infer targets from growth.

Before committing: run targeted tests, `python3 -m unittest discover -s tests/weekly_report`, baseline verification and `git diff --check`. Inspect representative sparse/dense/global UI when changing rendering. Tests with fake integrations do not establish live delivery, summary persistence or source completeness.

## Release boundaries

- Use `run_v2_release.py` and the immutable `prepare_delivery.py` → `safe_delivery.py` workflow described in the operator procedure. Do not use the legacy poster for V2 live sends or retries; `run_weekly.py --alert-version v2 --post` is disabled.
- An authorized deployment pauses in browser mode. Use the user's signed-in browser to capture fresh exact-artifact evidence for every manifest route; never extract credentials. `awaiting_browser_verification` is not completion.
- Only deliver the frozen bundle after live proof validates. Require Slack read access in every destination, including private Headout. Missing scope/admin access is a blocker, not a reason to repost or skip verification.
- Preserve the ledger and delivery journal across failures. Reconcile ambiguous sends using read-back; never clear state or regenerate payloads to retry.
- Enable a recurring schedule only after an approved supervised run verifies the exact release and all Slack parents/RCA replies. Use the product's scheduling mechanism selected by the user, not an invented substitute.

## Handoff

State separately what is tested, committed, pushed, deployed and activated. For a live run, return `Market | Parent alert | Top/Bottom RCA | Missing/Failed RCA`, grounded in Slack thread reads. Report remaining access/data gaps and the retained rollback path. Never describe a passing local suite or a “no new replies” smoke as a new-delivery end-to-end pass.
