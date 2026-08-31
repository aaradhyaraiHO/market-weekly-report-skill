# Review market → Slack channel mapping

This is the Review workflow routing reference. It mirrors the runtime maps in
`scripts/weekly_report/review/review-view.js` and
`scripts/weekly_report/notes/review_apps_script.js`.

Review is enabled for the 17 market reports. The Headout/global report is not a
Review destination and must not render a Review tab. Weekly alert delivery is a
separate contract in `alert/market_channels.json`; notably, North America alerts
still use `#mkt-usa`, while Review discussions use `#adhoc-north-america`.

## Primary Review posting routes

One Review discussion has one stable primary channel. Names are display labels;
channel IDs are the routing authority.

| Market slug | Report market | Primary Review channel | Channel ID | Scope note |
|---|---|---|---|---|
| `north_america` | North America | `#adhoc-north-america` | `C0BQHT29WMB` | Review-only override; alerts remain in `#mkt-usa` |
| `italy` | Italy | `#mkt-italy-switzerland-malta` | `C045L2WQ79P` | Italy, Malta, Switzerland |
| `france` | France | `#mkt-france` | `CH64TEB71` | France and Monaco |
| `iberia` | Iberia | `#mkt-iberia` | `CH2LRMJF2` | Andorra, Portugal, Spain |
| `united_kingdom` | United Kingdom | `#mkt-uk` | `CKTFHT4AF` | UK and Ireland |
| `benelux` | Benelux | `#mkt-uk` | `CKTFHT4AF` | Shared UK route |
| `csee` | CSEE | `#mkt-csee` | `CSQ10TALA` | CSEE portfolio |
| `nordics` | Nordics | `#mkt-csee` | `CSQ10TALA` | Shared CSEE route |
| `east_asia` | East Asia | `#mkt-japan` | `CQD6220VB` | Primary posting home; alternate read channels below |
| `oceania` | Oceania | `#mkt-anz` / `#mkt-australia` | `CHKRLFDPU` | Same channel ID; report payload may display `mkt-anz` |
| `sea` | South East Asia | `#mkt-singapore` | `C5WFYN82H` | Primary posting home; alternate read channels below |
| `uae` | United Arab Emirates | `#mkt-mena` | `C046622L80Z` | UAE only |
| `gcc` | GCC | `#mkt-mena-expansion-internal` | `C0889D22PM5` | Separate from UAE, per 27 Jul 2026 routing decision |
| `north_africa` | North Africa | `#mkt-mena-expansion-internal` | `C0889D22PM5` | Shared expansion route |
| `rest_of_mea` | Rest of MEA | `#mkt-mena-expansion-internal` | `C0889D22PM5` | Shared expansion route |
| `south_america` | South America | `#mkt-iberia` | `CH2LRMJF2` | Shared Iberia route |
| `mexico_central_america` | Mexico & Central America | `#mkt-mexico` | `C012949PQ81` | Dedicated corrected route; not Iberia |

## Alternate context/read channels

Alternates may be scanned for context and mention-directory membership. They do
not change the primary channel used to start a Review discussion.

| Market | Alternate channel IDs |
|---|---|
| East Asia | `C01C4NPLYN6` (Hong Kong), `C01CARUM1CL` (Korea), `C0809DN93DH` (China/Taiwan) |
| Oceania | `C039TMH0GEP` (New Zealand), `C097DVBLHGS` (Fiji) |
| South East Asia | `C03R4UJ4DHC` (Thailand), `C01CHADFPAM` (Malaysia), `C03US4WRHB6` (Indonesia), `C05D50N5BQW` (Vietnam) |

## Excluded global route

| Route | Slack alert channel | Review behavior |
|---|---|---|
| Headout/global | `#team-central-biz` (`C0975BGAX0B`) | Weekly alert only; no Review tab and no Review discussion composer |

## Authorization and routing rules

- The authenticated user must independently pass the BGM/GM/admin allowlist.
  Slack membership alone never grants Review access.
- The server validates the submitted channel ID against the market mapping.
- Missing or failed CE-thread discovery never falls back to “no thread.”
- Shared channels do not merge market data: every request remains scoped by
  `market_slug + review_week + stable CE ID`.
- New channels require a runtime-map update, bot invitation, contract-test
  update, and this document change in the same reviewed release.

## Source-of-truth checks

The contract suite compares every market primary channel in the frontend and
isolated backend. `alert/market_channels.json` remains authoritative for weekly
alert delivery, not for the North America Review override. This document was
reconciled to runtime on 31 Aug 2026.
