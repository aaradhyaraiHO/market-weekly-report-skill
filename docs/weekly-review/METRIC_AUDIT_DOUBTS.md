# Weekly Review V4 - Metric Audit & Doubts

**Week analyzed:** March 9-15, 2026
**Date:** 2026-03-16

---

## ✅ VERIFIED METRICS (Correct)

### 1. ROI1 Formula
**Formula:** `(revenue + co_marketing + insider - direct_costs) / (coupons + wallet + ad_spend[13] + affiliate + creator_collab)`

| Source | Value |
|--------|-------|
| BigQuery (V4 formula) | 1.503x (150.29%) |
| Dashboard | 1.503x (150.29%) |
| Report | 1.5x (150%) |

✅ **Status:** Dashboard and V4 script match perfectly. Report rounded correctly.

---

## ⚠️ DOUBT #1: Revenue - Which field to use?

**Available fields in `combined_entity_stats`:**
- `sum_revenue` (actual)
- `sum_revenue_predicted`

| Field | Value | Used By |
|-------|-------|---------|
| sum_revenue | $2,399,436 | ❓ Unknown |
| sum_revenue_predicted | $2,329,471 | ✅ V4 script, Dashboard |
| **Difference** | **$69,964 (2.92%)** | |

**Report shows:** $2.34M

### Questions:
1. Why does `sum_revenue` differ from `sum_revenue_predicted` by $70K?
2. Which field should we use for weekly reviews?
3. Does the dashboard use `sum_revenue_predicted`?

### Recommendation:
- Keep using `sum_revenue_predicted` (current V4 formula) ✅
- But understand what the $70K difference represents

---

## ⚠️ DOUBT #2: Ad Spend - HUGE mismatch ($233K difference!)

**V4 Script uses 13 channels:**
1. sum_google_ads_spend
2. sum_pmax_ads_spend
3. sum_travel_ads_spend
4. sum_google_remarketing_ads_spend
5. sum_google_brand_ads_spend
6. sum_google_split_ads_spend ← "Split" channels
7. sum_microsoft_ads_spend
8. sum_microsoft_split_ads_spend ← "Split" channels
9. sum_facebook_ads_spend
10. sum_facebook_remarketing_ads_spend
11. sum_facebook_split_ads_spend ← "Split" channels
12. sum_criteo_remarketing_ads_spend
13. sum_apple_ads_spend

| Source | Value |
|--------|-------|
| BigQuery (13 channels) | $1,312,132 |
| Report shows | $1,079,100 |
| **Difference** | **$233,032 (21.6%)** |

### Questions:
1. **Does the report exclude the 3 "split" channels?**
   - google_split: $?
   - microsoft_split: $?
   - facebook_split: $?
2. What are "split" channels? Are they double-counting?
3. Does the dashboard use all 13 channels or only 10?

### Action Required:
- Query the "split" channel values individually
- Verify if report should use 10 or 13 channels
- Check dashboard definition of `gross_marketing_cost`

---

## ⚠️ DOUBT #3: CM% (Contribution Margin %) - WRONG formula?

| Source | Value |
|--------|-------|
| BigQuery calculation | 90.8% |
| Report shows | 46.1% |
| **Difference** | **44.7 percentage points** |

**Current V4 formula:**
```
CM% = (revenue + co_marketing + insider - direct_costs) / revenue * 100
CM% = $2,114,772 / $2,329,471 * 100 = 90.8%
```

**This is WRONG.** CM% should likely be:
```
CM% = (revenue - ALL costs) / revenue * 100
```

### Questions:
1. What's the correct CM% formula for Headout?
2. Should it include ALL costs (coupons, wallet, ad spend, etc.)?
3. Does the dashboard have a CM% field we can reference?

### Suspected Correct Formula:
```
CM% = (revenue - direct_costs - ad_spend - coupons - wallet - affiliate - creator_collab) / revenue * 100
```

Let me calculate:
```
CM = $2,329,471 - $214,699 - $1,312,132 - $67,465 - $27,572 - $0 - $0
CM = $707,603
CM% = $707,603 / $2,329,471 * 100 = 30.4%
```

Still doesn't match 46.1%. **Need the correct formula.**

---

## ⚠️ DOUBT #4: Rev/Click - Missing "paid-only" clicks field?

| Field | Value | Calculated Rev/Click |
|-------|-------|---------------------|
| count_ad_clicks | 1,290,809 | $1.80 |
| Report shows | ❓ | $2.21 |
| **Difference** | | **$0.41 (22.8%)** |

**Problem:** `count_ad_clicks` might include:
- Paid clicks ✅
- Organic impressions/clicks ❌
- Direct traffic ❌

### Questions:
1. Is there a `count_paid_ad_clicks` or similar field?
2. Should Rev/Click use paid revenue only, not total revenue?
3. Does the dashboard have a "paid clicks" metric?

### Action Required:
- Check if paid-only click field exists
- Verify if Rev/Click should be: `paid_revenue / paid_clicks` not `total_revenue / all_clicks`

---

## 🔍 NEXT STEPS

### Immediate Actions:
1. **Check dashboard definitions:**
   - What is `gross_marketing_cost`? (10 or 13 channels?)
   - What is CM% formula?
   - What click field does it use?

2. **Query "split" channels individually:**
   ```sql
   SELECT
       SUM(sum_google_split_ads_spend),
       SUM(sum_microsoft_split_ads_spend),
       SUM(sum_facebook_split_ads_spend)
   FROM combined_entity_stats
   WHERE report_date BETWEEN '2026-03-09' AND '2026-03-15'
   ```

3. **Find paid-only clicks field:**
   - Check `campaign_device_stats` table
   - Check if clicks should be summed from channel-specific fields

### Questions for User:
1. Should we use `sum_revenue` or `sum_revenue_predicted`?
2. Does "split" channel spending double-count with main channels?
3. What's the correct CM% formula at Headout?
4. Where should paid-only clicks come from?

---

## Summary Table

| Metric | Report Value | BQ Calculated | Status | Issue |
|--------|--------------|---------------|--------|-------|
| Revenue | $2.34M | $2.33M | ⚠️ Close | $70K diff between actual vs predicted |
| ROI1 | 1.5x (150%) | 1.503x (150.29%) | ✅ Verified | Matches dashboard |
| Ad Spend | $1,079K | $1,312K | ❌ WRONG | $233K diff - split channels? |
| CM% | 46.1% | 90.8% | ❌ WRONG | Formula issue |
| Rev/Click | $2.21 | $1.80 | ❌ WRONG | Need paid-only clicks |
