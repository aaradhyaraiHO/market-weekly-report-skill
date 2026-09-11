# Weekly V2 architecture reference

## Boundary

The canonical repository contains one weekly data engine and temporarily two renderers:

- V1: production-safe renderer, delivery path, and rollback.
- V2: Oak/Eevee renderer consuming the same schema-v1 market snapshot plus optional enrichments.

Do not fork business logic between renderers. If a shared calculation is wrong, fix it deliberately at the shared producer with contract coverage. If a V2 view needs additional context, add a backward-compatible field or sidecar.

## Data ownership

| Surface | Authority |
|---|---|
| Weekly metrics and TY/LY series | V1 snapshot |
| Buckets and membership | `buckets_final` through the shared bucket accessor |
| Top-mover ordering and seasonal context | V1 headline/mover output |
| Shapley decomposition | V1 weekly flow engine |
| Monthly market and CE goals | Frozen V2 goals sidecar built from approved BigQuery sources |
| Business-country slicing | Approved CE dimension joined by stable CE/CID key |
| TGID and variant facts | Booking-grain source joined by TGID/variant IDs |
| Lead-time bands and resource histories | Read-only BigQuery enrichments with explicit snapshot fields |
| Human-entered metadata | CID-keyed sidecar; never name-keyed |

## Failure policy

- Core V1 snapshot failure: fail the build visibly.
- Optional V2 enrichment failure: preserve the core report, omit or mark only that feature unavailable, and log the cause.
- Required alert RCA failure: stop frozen-bundle preparation before any new parent delivery. This is distinct from optional report enrichment.
- Schema mismatch or grain ambiguity: stop that enrichment rather than guessing.
- Missing historical series: show unavailable; never synthesize history from a current value.
- Missing target: show unavailable; never infer an approved target from weekly growth.

## Parity gates

Compare V1 and V2 for every shared market and week:

- current and prior weekly revenue;
- same-week last-year revenue where available;
- All-CE totals and stable IDs;
- bucket membership;
- mover order and movement clocks;
- Shapley net movement;
- Overall/Paid metric values and units.

V2-only targets, country slices, variants, and histories require reconciliation to their source totals but do not need to appear in V1.

## Activation stages

1. Merge code with V1 still default.
2. Generate V1 and V2 in parallel from the same snapshot.
3. Review representative sparse, dense, multi-country, and Headout/global reports.
4. Make V2 the published renderer behind an explicit flag or route.
5. Retain V1 generation for several weekly cycles before retirement.

For the current full-notebook release, browser proof and frozen Slack delivery
procedure, read `docs/v2/release-workflow.md` in the repository. This architecture
reference does not establish that production cutover or unattended activation has
passed its live gates.
