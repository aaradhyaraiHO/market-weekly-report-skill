# Slack Timestamp Bug - Fixed

**Date:** 2026-03-16
**Issue:** Slack context was pulled from March 2025 instead of March 2026

---

## 🐛 **What Happened**

When reading Slack channels for the weekly review, timestamps were calculated incorrectly:
- **Expected:** March 2026 (~1772994600 to ~1773599399)
- **Actual:** March 2025 (~1741478400 to ~1742169600)
- **Result:** All GM Context bullets were from conversations 1 year ago

**Impact:**
- ❌ All Slack context across 6 market deep dives (wrong year)
- ❌ Global context from #tf-bugalert and #pod-live-entertainment (wrong year)
- ✅ BigQuery data (revenue, metrics, RCA) - CORRECT (not affected)

---

## ✅ **Fix Implemented**

### 1. Created Timestamp Helper Script

**File:** `scripts/get_slack_timestamps.py`

**Usage:**
```bash
python3 scripts/get_slack_timestamps.py --week 2026-03-09
```

**Output:**
```
✅ Timestamp validation PASSED

Week: 2026-03-09
  Start: 2026-03-09 00:00:00
  End:   2026-03-15 23:59:59

Timestamps:
  oldest=1772994600
  latest=1773599399
```

**Features:**
- ✅ Validates timestamps are in correct year range
- ✅ Detects year mismatches automatically
- ✅ Provides exact values for Slack API calls
- ✅ Works for any year (2024-2027+)

### 2. Updated Skill with Validation

**File:** `plugins/weekly-growth-review/commands/weekly-review.md`

**New Stage 3a: CRITICAL: Get Correct Timestamps**
```bash
# MUST run this before reading Slack
python3 scripts/get_slack_timestamps.py --week {target_week}
```

**Changes:**
- ✅ Added mandatory timestamp validation step
- ✅ Requires using script-generated timestamps
- ✅ Added timestamp verification for messages
- ✅ Clear instructions to STOP if validation fails

---

## 🛡️ **Prevention**

### Before Reading Slack (ALWAYS):

1. **Run validation script:**
   ```bash
   python3 scripts/get_slack_timestamps.py --week 2026-03-09
   ```

2. **Check output:**
   - ✅ Should see "Timestamp validation PASSED"
   - ✅ Verify year matches (2026 for March 2026)
   - ❌ If validation fails, STOP and investigate

3. **Use exact timestamps:**
   - Copy `oldest` and `latest` from script output
   - Use in ALL Slack API calls
   - DO NOT calculate timestamps manually

### While Reading Slack:

4. **Verify message timestamps:**
   - Check `ts` field of each message
   - Should be between `oldest` and `latest` from validation
   - If outside range, message is from wrong time period - SKIP IT

---

## 📋 **Checklist for Future Runs**

- [ ] Run `get_slack_timestamps.py --week {date}`
- [ ] Verify "Timestamp validation PASSED"
- [ ] Copy exact `oldest` and `latest` values
- [ ] Use these timestamps for ALL Slack reads
- [ ] Verify message `ts` is in expected range
- [ ] Check Slack message links point to correct dates

---

## 🧪 **Testing**

### Test the script:
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

### Verify timestamps are different:
- 2025-03-10: oldest=~1741564800
- 2026-03-09: oldest=~1772994600
- Difference: ~31536000 seconds (1 year)

---

## 📚 **Technical Details**

### Unix Timestamp Ranges by Year (March):

| Year | Approximate Range (March 1-31) |
|------|--------------------------------|
| 2024 | 1709251200 - 1711929599 |
| 2025 | 1741478400 - 1743465599 |
| 2026 | 1772553600 - 1775231999 |
| 2027 | 1804089600 - 1806767999 |

### Validation Logic:
- Script calculates expected range for the year
- Compares calculated timestamps against expected range
- Fails if difference is > 1 month (likely year error)

---

## ✅ **Status**

- [x] Bug identified and root cause found
- [x] Timestamp helper script created
- [x] Validation added to skill workflow
- [x] Testing completed
- [x] Documentation updated

**Ready for next run with correct timestamps!**
