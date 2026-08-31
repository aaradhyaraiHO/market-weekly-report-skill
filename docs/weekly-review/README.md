# Weekly Growth Review Documentation

Complete guide to Headout's weekly revenue growth analysis system (V4).

---

## 📚 Quick Links

- **[Metric Audit](METRIC_AUDIT_DOUBTS.md)** - Comprehensive audit of all metrics with formulas and data sources
- **[Timestamp Fix](SLACK_TIMESTAMP_FIX.md)** - Critical fix for Slack timestamp bug (prevents year mismatch)
- **[Market Channel Mapping](MARKET_CHANNEL_MAPPING.md)** - Complete reference of all markets → Slack channels with IDs
- **[Canvas + File Guide](CANVAS_WITH_FILE_GUIDE.md)** - Alternative delivery method (condensed Canvas + MD file)

---

## 🎯 Overview

The weekly review analyzes revenue performance with:
- **Headline metrics**: Revenue, YoY%, ROI1
- **Executive narrative**: What happened and why (WoW drivers)
- **Revenue bridge**: Market-level structural deltas (seasonality-adjusted)
- **Supporting context**: 6-week trend, categories, channels
- **Top CE movers**: Largest revenue changes by Combined Entity
- **Profitability & efficiency**: CM%, paid ROI, market efficiency
- **Market deep dives**: Top 6 markets with CE-level RCA + live Slack context
- **Cross-cutting patterns**: Systemic issues across CEs
- **Prioritized actions**: What to do next

---

## 🚀 Quick Start

### Run Analysis

```bash
cd ~/analytics

# Option 1: Use the skill (recommended)
/weekly-review 2026-03-09

# Option 2: Run script directly
python3 scripts/weekly_growth_review_v4.py --week 2026-03-09
```

### Post to Slack

The `/weekly-review` skill handles everything:
1. Generates report from BigQuery
2. **Validates Slack timestamps** (prevents year mismatch bug)
3. Reads Slack channels for GM context
4. Creates Slack Canvas with full report
5. Posts to #team-central-biz

---

## 📋 Complete Workflow

### Stage 1: Determine Target Week

Target week must be a Monday (YYYY-MM-DD format). If not specified, uses most recent complete week.

### Stage 2: Generate Base Report

```bash
cd ~/analytics
python3 scripts/weekly_growth_review_v4.py --week 2026-03-09
```

This queries BigQuery (`headout-analytics.analytics_reporting`) and creates:
`~/analytics/thoughts/shared/weekly-reviews/weekly-review-2026-03-09.md`

### Stage 3: Read Slack Context

**⚠️ CRITICAL: Validate timestamps first to prevent year mismatch bug**

#### 3a. Get Correct Timestamps

```bash
cd ~/analytics
python3 scripts/get_slack_timestamps.py --week 2026-03-09
```

Expected output:
```
✅ Timestamp validation PASSED

Week: 2026-03-09
  Start: 2026-03-09 00:00:00
  End:   2026-03-15 23:59:59

Timestamps:
  oldest=1772994600
  latest=1773599399
```

**⚠️ STOP if validation fails** - indicates year mismatch or calculation error.

See [SLACK_TIMESTAMP_FIX.md](SLACK_TIMESTAMP_FIX.md) for details on the timestamp bug fix.

#### 3b. Load Slack Tools

```
ToolSearch(query="+slack read channel")
```

#### 3c. Read Market Channels

For each notable market in deep dives (top 3 decliners + top 3 growers):

```python
slack_read_channel(
  channel_id="CHANNEL_ID",
  oldest="1772994600",    # Use exact values from validation script
  latest="1773599399"
)
```

**Market → Channel Mapping:** use the single maintained reference in
[`MARKET_CHANNEL_MAPPING.md`](MARKET_CHANNEL_MAPPING.md). It distinguishes the
primary Review posting channel from alternate context channels and the separate
weekly-alert route. Do not copy the table into this guide: Mexico, GCC and the
North America Review override have changed independently in the past.

Look for:
- Supply issues (inventory, availability, closures)
- Campaign changes (paused ads, new experiments, budget shifts)
- Competitor activity (price changes, new entrants)
- External events (weather, holidays, local events)

#### 3d. Read Global Context Channels

Always read these cross-cutting channels:
- **#tf-bugalert** (C038T64PD) - Bugs impacting revenue or metrics
- **#pod-live-entertainment** (C042A57T52Q) - Live entertainment pod updates

#### 3e. Replace Placeholders

After reading Slack, replace placeholder lines in report with actual context:

```markdown
**GM Context (from #mkt-france):**
- Disneyland Paris inventory expanded ([link](https://headout.slack.com/archives/CH64TEB71/p1772994600123456)) (Mar 9)
- Vivaticket competition update ([link](https://headout.slack.com/archives/CH64TEB71/p1773012345678901)) (Mar 10)
```

**Always verify message timestamps:**
- Message `ts` should be between `oldest` and `latest` from validation
- If `ts` is outside range (e.g., 1741xxxxxx), it's from wrong year - SKIP IT

### Stage 4: Post to Slack Canvas

```
# Load tools
ToolSearch("select:mcp__claude_ai_Slack__slack_create_canvas")
ToolSearch("select:mcp__claude_ai_Slack__slack_send_message")

# Create Canvas with full report content
# Post to #team-central-biz (C0975BGAX0B)
```

---

## 📊 Key Metrics & Formulas

See [METRIC_AUDIT_DOUBTS.md](METRIC_AUDIT_DOUBTS.md) for complete formulas and data sources.

### ROI1 (Total Acquisition ROI)

```
ROI1 = (revenue + co_marketing + insider - direct_costs) /
       (coupons + wallet + ad_spend[13 channels] + affiliate + creator_collab)
```

**13 Ad Spend Channels:**
1. google_ads
2. pmax
3. travel_ads
4. google_ads_remarketing
5. pmax_remarketing
6. google_ads_split
7. pmax_split
8. travel_ads_split
9. meta_ads
10. tiktok_ads
11. apple_search_ads
12. bing_ads
13. x_ads

### Contribution Margin %

```
CM% = (revenue - direct_costs - ad_spend) / revenue
```

### Rev/Click

```
Rev/Click = revenue / count_ad_clicks
```

---

## 🐛 Known Issues & Fixes

### Slack Timestamp Bug (FIXED)

**Issue:** Slack context was pulled from March 2025 instead of March 2026.

**Root cause:** Unix timestamp calculation error - used 1741xxxxxx (2025) instead of 1773xxxxxx (2026).

**Impact:** All GM Context bullets across 6 markets were from conversations 1 year ago.

**Fix:** Created validation script that checks timestamps are in correct year range before Slack API calls.

**Prevention:** Always run `scripts/get_slack_timestamps.py --week {date}` before reading Slack.

See [SLACK_TIMESTAMP_FIX.md](SLACK_TIMESTAMP_FIX.md) for complete details.

### Stale Report Data

**Issue:** Report file shows different values than BigQuery/dashboard.

**Root cause:** Manual edits to report file kept stale data from previous generation.

**Fix:** Always regenerate report fresh with `python3 scripts/weekly_growth_review_v4.py --week {date}`.

**Never edit report files manually** - all edits should be in script logic only.

---

## 📁 File Structure

```
~/analytics/
├── scripts/
│   ├── weekly_growth_review_v4.py          # Main report generator
│   ├── get_slack_timestamps.py             # Timestamp validation (CRITICAL)
│   ├── create_condensed_canvas.py          # Condensed canvas creator (optional)
│   └── post_weekly_canvas_with_file.sh     # Workflow script (optional)
│
├── plugins/weekly-growth-review/commands/
│   └── weekly-review.md                    # /weekly-review skill definition
│
├── thoughts/shared/weekly-reviews/
│   └── weekly-review-2026-03-09.md         # Generated reports (one per week)
│
└── docs/weekly-review/                     # This documentation folder
    ├── README.md                            # This file
    ├── METRIC_AUDIT_DOUBTS.md              # Metrics audit
    ├── SLACK_TIMESTAMP_FIX.md              # Timestamp bug fix
    └── CANVAS_WITH_FILE_GUIDE.md           # Alternative delivery method
```

---

## 🔧 Core Scripts

### weekly_growth_review_v4.py

Queries BigQuery and generates markdown report.

**Usage:**
```bash
python3 scripts/weekly_growth_review_v4.py --week 2026-03-09
```

**Data source:** `headout-analytics.analytics_reporting.combined_entity_stats`

**Output:** `thoughts/shared/weekly-reviews/weekly-review-2026-03-09.md`

### get_slack_timestamps.py

Validates Slack API timestamps are in correct year range. **CRITICAL** to prevent year mismatch bug.

**Usage:**
```bash
python3 scripts/get_slack_timestamps.py --week 2026-03-09
```

**Output:**
```
✅ Timestamp validation PASSED
oldest=1772994600
latest=1773599399
```

**Always use these exact values** in all Slack API calls.

---

## 🎨 Alternative Delivery Methods

### Option 1: Full Slack Canvas (Current)

**Status:** ✅ Current approach

- Posts complete report to Slack Canvas
- Native markdown support
- All content in one place
- Canvas may condense if > 50KB

### Option 2: Condensed Canvas + MD File

**Status:** 📝 Available but not currently used

See [CANVAS_WITH_FILE_GUIDE.md](CANVAS_WITH_FILE_GUIDE.md) for details.

**Approach:**
- 10-15KB condensed canvas (headline + top markets + top CEs + top insights)
- Full MD file linked from canvas (all details)
- Best of both worlds: scannable overview + complete data

**Scripts:**
- `scripts/create_condensed_canvas.py`
- `scripts/post_weekly_canvas_with_file.sh`

---

## ✅ Pre-Run Checklist

Before running analysis:
- [ ] Have target week date (Monday, YYYY-MM-DD format)
- [ ] BigQuery data is fresh (daily run at 04:05 UTC)
- [ ] Slack MCP tools are available
- [ ] `~/analytics` is current working directory

---

## 🧪 Testing

### Test Timestamp Validation

```bash
cd ~/analytics

# Test 2026 week (should pass)
python3 scripts/get_slack_timestamps.py --week 2026-03-09

# Test 2025 week (should pass with different timestamps)
python3 scripts/get_slack_timestamps.py --week 2025-03-10

# Test invalid week (should fail)
python3 scripts/get_slack_timestamps.py --week 2026-03-10
# Error: 2026-03-10 is not a Monday
```

### Verify Report Generation

```bash
cd ~/analytics
python3 scripts/weekly_growth_review_v4.py --week 2026-03-09

# Check output exists
ls -lh thoughts/shared/weekly-reviews/weekly-review-2026-03-09.md

# Verify metrics match BigQuery
# Compare ROI1, revenue, spend values with dashboard
```

---

## 📞 Support

**Issues with:**
- **Metrics/formulas**: See [METRIC_AUDIT_DOUBTS.md](METRIC_AUDIT_DOUBTS.md)
- **Slack timestamps**: See [SLACK_TIMESTAMP_FIX.md](SLACK_TIMESTAMP_FIX.md)
- **Delivery format**: See [CANVAS_WITH_FILE_GUIDE.md](CANVAS_WITH_FILE_GUIDE.md)

**Common fixes:**
- Stale data → Regenerate report fresh
- Wrong year Slack context → Run timestamp validation script
- Canvas too large → Use condensed canvas approach
- Metrics mismatch → Check BigQuery source directly

---

## 📈 Recent Updates

**2026-03-16:**
- ✅ Fixed Slack timestamp bug (year mismatch 2025→2026)
- ✅ Created timestamp validation script
- ✅ Added mandatory validation to skill workflow
- ✅ Consolidated all documentation

**2026-03-15:**
- ✅ Comprehensive metrics audit completed
- ✅ Verified all formulas match BigQuery sources
- ✅ Documented ROI1 discrepancy (stale report file)

---

**Ready to run!** 🚀

Start with: `/weekly-review 2026-03-09` or `python3 scripts/weekly_growth_review_v4.py --week 2026-03-09`
