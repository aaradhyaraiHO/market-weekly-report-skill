# Market → Slack Channel Mapping Reference

Complete mapping of Headout markets to Slack channels for weekly review context gathering.

---

## Complete Market List (21 markets)

| Market | Region | Channel(s) | Channel ID(s) | Countries/Notes |
|--------|--------|-----------|---------------|-----------------|
| **North America** | North America | #mkt-usa | `CNSHDD2H1` | USA, Canada, Bahamas |
| **Central Live Entertainment** | Central Categories | #pod-live-entertainment | `C042A57T52Q` | Cross-market live entertainment category |
| **Italy** | Europe | #mkt-italy | `C045L2WQ79P` | Italy, Malta, Switzerland |
| **France** | Europe | #mkt-france | `CH64TEB71` | France, Monaco |
| **Iberia** | Europe | #mkt-iberia | `CH2LRMJF2` | Andorra, Portugal, Spain |
| **CSEE** | Europe | #mkt-csee | `CSQ10TALA` | Albania, Austria, Bosnia and Herzegovina, Bulgaria, Croatia, Czech Republic, Estonia, Germany, Greece, Hungary, Latvia, Moldova, Montenegro, North Macedonia, Poland, Romania, Serbia, Slovakia, Slovenia, Turkey (23 countries) |
| **United Kingdom** | Europe | #mkt-uk | `CKTFHT4AF` | UK + Ireland |
| **Benelux** | Europe | #mkt-uk | `CKTFHT4AF` | Belgium, Luxembourg, Netherlands (rolls up to UK channel) |
| **Nordics** | Europe | #mkt-csee | `CSQ10TALA` | Denmark, Finland, Iceland, Norway, Sweden (rolls up to CSEE channel) |
| **East Asia (JPN, SK, HK)** | Asia-Pacific | #mkt-japan<br>#mkt-hongkong<br>#mkt-korea | `CQD6220VB`<br>`C01C4NPLYN6`<br>`C01CARUM1CL` | Japan + South Korea + Hong Kong (read all 3 channels) |
| **Oceania** | Asia-Pacific | #mkt-australia<br>#mkt-new-zealand<br>mkt-fiji | `CHKRLFDPU`<br>`C039TMH0GEP`<br>`C097DVBLHGS` | Australia + New Zealand + Fiji (read all 3 channels) |
| **SEA (SIN + THA)** | Asia-Pacific | #mkt-singapore<br>#mkt-thailand | `C5WFYN82H`<br>`C03R4UJ4DHC` | Singapore + Thailand |
| **SEA (MLY + IND + VN)** | Asia-Pacific | #mkt-malaysia<br>#mkt-indonesia<br>#mkt-vietnam | `C01CHADFPAM`<br>`C03US4WRHB6`<br>`C05D50N5BQW` | Malaysia + Indonesia + Vietnam |
| **East Asia (CN, TW)** | Asia-Pacific | #mkt-china-taiwan | `C0809DN93DH` | China, Macao, Taiwan |
| **South America** | LATAM | #mkt-iberia | `CH2LRMJF2` | Argentina, Brazil, Chile, Colombia, Peru (rolls up to Iberia channel) |
| **Mexico & Central America** | LATAM | #mkt-iberia | `CH2LRMJF2` | Antigua and Barbuda, Barbados, Costa Rica, Dominican Republic, Jamaica, Mexico, Panama (rolls up to Iberia channel) |
| **United Arab Emirates** | Middle East and North Africa | #mkt-mena | `C046622L80Z` | UAE |
| **GCC** | Middle East and North Africa | #mkt-mena | `C046622L80Z` | Bahrain, Oman, Qatar, Saudi Arabia (rolls up to MENA channel) |
| **Egypt** | Middle East and North Africa | mkt-mena-expansion-internal | `C0889D22PM5` | Egypt (internal expansion channel) |
| **Morocco** | Middle East and North Africa | mkt-mena-expansion-internal | `C0889D22PM5` | Morocco (internal expansion channel) |

---

## Market Notes

### Asia-Pacific Region

The Asia-Pacific region has **two separate "East Asia" markets**:
- **East Asia (JPN, SK, HK)**: Japan + South Korea + Hong Kong
- **East Asia (CN, TW)**: China + Taiwan

These are distinct markets with different channel mappings.

---

## Regional Rollups

Some markets don't have dedicated channels and roll up to regional channels:

| Market | Rolls Up To | Channel | Channel ID | Notes |
|--------|-------------|---------|------------|-------|
| **Benelux** | UK | #mkt-uk | `CKTFHT4AF` | Belgium, Luxembourg, Netherlands |
| **Nordics** | CSEE | #mkt-csee | `CSQ10TALA` | Denmark, Finland, Iceland, Norway, Sweden |
| **GCC** | MENA | #mkt-mena | `C046622L80Z` | Bahrain, Oman, Qatar, Saudi Arabia |
| **South America** | Iberia | #mkt-iberia | `CH2LRMJF2` | 5 countries |
| **Mexico & Central America** | Iberia | #mkt-iberia | `CH2LRMJF2` | 7 countries |

---

## Multi-Channel Markets

These markets require reading **multiple** Slack channels:

### East Asia (JPN, SK, HK)
- #mkt-japan (`CQD6220VB`)
- #mkt-hongkong (`C01C4NPLYN6`)
- #mkt-korea (`C01CARUM1CL`)

### Oceania (Australia + New Zealand + Fiji)
- #mkt-australia (`CHKRLFDPU`)
- #mkt-new-zealand (`C039TMH0GEP`)
- mkt-fiji (`C097DVBLHGS`)

### SEA (SIN + THA)
- #mkt-singapore (`C5WFYN82H`)
- #mkt-thailand (`C03R4UJ4DHC`)

### SEA (MLY + IND + VN)
- #mkt-malaysia (`C01CHADFPAM`)
- #mkt-indonesia (`C03US4WRHB6`)
- #mkt-vietnam (`C05D50N5BQW`)

---

## CSEE Country Breakdown

**CSEE (Central and Southeast Europe)** includes **23 countries**:
- Albania
- Austria
- Bosnia and Herzegovina
- Bulgaria
- Croatia
- Czech Republic
- Estonia
- Germany
- Greece
- Hungary
- Latvia
- Moldova
- Montenegro
- North Macedonia
- Poland
- Romania
- Serbia
- Slovakia
- Slovenia
- Turkey

All CSEE countries share the same Slack channel: **#mkt-csee** (`CSQ10TALA`)

**Nordics also roll up to CSEE channel**: Denmark, Finland, Iceland, Norway, Sweden

---

## Global Context Channels (Always Read)

These channels should be read for **every** weekly review regardless of which markets are notable:

| Channel | Channel ID | Purpose |
|---------|------------|---------|
| #tf-bugalert | `C038T64PD` | Bugs impacting revenue or metrics |
| #pod-live-entertainment | `C042A57T52Q` | Live entertainment pod updates (also a market category) |

---

## Usage in Weekly Review

### Stage 3b: Read Market Channels

For each notable market in the weekly review (top 3 structural decliners + top 3 structural growers):

1. **Find the market** in the table above
2. **Note the channel(s)** - some markets have multiple channels
3. **Use validated timestamps** from `scripts/get_slack_timestamps.py`
4. **Call Slack API** for each channel:

```python
slack_read_channel(
  channel_id="CHANNEL_ID",
  oldest="1772994600",    # From validation script
  latest="1773599399"
)
```

5. **For multi-channel markets**, read all listed channels
6. **For rollup markets**, read the rollup channel (e.g., South America → #mkt-iberia)

### What to Look For

In each channel, look for:
- **Supply issues**: Inventory, availability, closures, maintenance
- **Campaign changes**: Paused ads, new experiments, budget shifts
- **Competitor activity**: Price changes, new entrants
- **External events**: Weather, holidays, local events, regulations

---

## Updating This Mapping

This mapping should be updated when:
- New markets are added to Headout's portfolio
- Markets are reorganized (e.g., MENA → UAE + Egypt + Morocco)
- New Slack channels are created for existing markets
- Channel IDs change (rare, but possible during Slack workspace migrations)

**Update locations:**
- This file: `docs/weekly-review/MARKET_CHANNEL_MAPPING.md`
- Main README: `docs/weekly-review/README.md` (abbreviated table)
- Skill file: `plugins/weekly-growth-review/commands/weekly-review.md` (abbreviated table)

---

---

## ✅ Complete Coverage

All 21 markets now have verified Slack channel IDs. The mapping is complete and ready for use in weekly reviews.

**Verified against:**
- ✅ BigQuery `dim_combined_entities` table (market-country-region mappings)
- ✅ Slack workspace (channel names and IDs)

---

**Last updated:** 2026-03-17 (verified against BQ and Slack)
