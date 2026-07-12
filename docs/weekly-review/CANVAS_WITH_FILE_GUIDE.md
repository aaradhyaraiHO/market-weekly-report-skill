# Weekly Review: Canvas + MD File

✅ **Best of both worlds:** Scannable Canvas in Slack + Full details in MD file

---

## 🎯 **The Approach**

1. **Condensed Canvas** (10-15KB) → Posted to #team-central-biz
   - Headline metrics
   - Executive summary (500 chars)
   - Top 5 markets from revenue bridge
   - Top 8 CE movers
   - Top 3 market insights
   - Top 5 actions
   - Link to full report

2. **Full MD File** (72KB) → Linked from Canvas
   - Complete 6-week trend
   - All markets with structural deltas
   - All CEs with RCA
   - Slack context from all channels
   - Complete tables and metrics

---

## 🚀 **Quick Start**

### One-Command Workflow:

```bash
cd ~/analytics

# Generate report + create canvas + prep for posting
./scripts/post_weekly_canvas_with_file.sh 2026-03-09
```

**This script:**
1. ✅ Creates condensed canvas (~10-15KB)
2. ✅ Gets GitHub URL for full MD file
3. ✅ Shows canvas content (ready to post)
4. ✅ Provides posting instructions

---

## 📋 **Manual Workflow**

### Step 1: Generate Report

```bash
cd ~/analytics
python3 scripts/weekly_growth_review_v4.py --week 2026-03-09
```

### Step 2: Create Condensed Canvas

```bash
python3 scripts/create_condensed_canvas.py \
    --week 2026-03-09 \
    --report-file thoughts/shared/weekly-reviews/weekly-review-2026-03-09.md \
    --output /tmp/canvas-2026-03-09.md
```

**Output size:** ~10-15KB (Canvas won't condense this)

### Step 3: Upload Full MD File

**Option A: GitHub** (if repo accessible to team)
```bash
cd ~/analytics
git add thoughts/shared/weekly-reviews/weekly-review-2026-03-09.md
git commit -m "Weekly review 2026-03-09"
git push origin main

# Get URL
echo "https://github.com/[org]/[repo]/blob/main/thoughts/shared/weekly-reviews/weekly-review-2026-03-09.md"
```

**Option B: Google Drive**
1. Upload `weekly-review-2026-03-09.md` to Drive
2. Right-click → Get link → "Anyone with link can view"
3. Copy link

**Option C: Dropbox/Internal server**
- Upload file, get shareable link

### Step 4: Update Canvas with File Link

```bash
# Replace placeholder with actual URL
sed -i '' 's|REPLACE_WITH_FILE_LINK|YOUR_ACTUAL_URL|g' /tmp/canvas-2026-03-09.md
```

### Step 5: Post to Slack

**Via MCP tools (in Claude):**
```
ToolSearch("select:mcp__claude_ai_Slack__slack_create_canvas")

# Then create canvas with content from /tmp/canvas-2026-03-09.md
```

**Or manually:**
1. Copy canvas: `cat /tmp/canvas-2026-03-09.md | pbcopy`
2. Go to #team-central-biz in Slack
3. Click "+" → "Create a canvas"
4. Paste content
5. Title: "Weekly Growth Review — 2026-03-09"
6. Click "Share in channel"

---

## 📊 **What Team Sees**

### In Slack Canvas (~2 min read):
```markdown
# Weekly Growth Review — 2026-03-09

**$2.34M revenue | +25.0% YoY | ROI1: 1.5x (150%)**

---

## Executive Summary

Revenue grew $167.8K WoW to $2.34M (+25% YoY), with notable efficiency
improvement: spend dropped 15% WoW...

---

## Revenue Bridge (Top Markets)

| Market | TY Rev | WoW Δ | Structural Δ | ...
| France | $X.XXM | +$XXK | +$16K | ...
[Top 5 markets only]

---

## Top CE Movers

[Top 8 CEs by revenue change]

---

## Key Market Insights

• France: Disneyland Paris +787% YoY despite Vivaticket...
• CSEE: Acropolis CTR collapse -$33K structural...
• Iberia: Sagrada Familia offsetting declines...

---

## Prioritized Actions

1. **France: Scale Disneyland Paris**
2. **CSEE: Fix Acropolis campaign CTR**
...

---

## 📄 Full Report

For complete analysis including:
• 6-week revenue trend
• All 20+ markets with CE-level RCA
• Complete Slack context
• All tables and metrics

**→ [View Full Report (Markdown)](link)**
```

### Click Through to Full MD:
- All sections unabridged
- Complete tables
- All markets (not just top 5)
- All CEs (not just top 8)
- Full Slack context from all channels

---

## ✅ **Why This Works**

| Need | Canvas | MD File |
|------|--------|---------|
| Quick scan | ✅ 10-15KB, 2 min read | ❌ Too long |
| Markdown formatting | ✅ Native support | ✅ Yes |
| In Slack | ✅ Yes | ❌ External link |
| Full details | ❌ Condensed | ✅ Complete |
| Deep dive | ❌ Summaries only | ✅ All metrics |
| Team-friendly | ✅ Easy | ✅ Markdown viewable |
| Week-over-week | ✅ Thread/channel | ✅ Commit history |

**Best of both!**
- Canvas = Overview for everyone
- MD file = Details for analysts

---

## 🔧 **Customizing Condensed Canvas**

Edit `scripts/create_condensed_canvas.py` to adjust:
- Length of executive summary (default: 500 chars)
- Number of markets shown (default: top 5)
- Number of CEs shown (default: top 8)
- Market insight length (default: 150 chars each)

**Target:** Keep canvas < 15KB to avoid condensing

---

## 📁 **Files Created**

| File | Purpose |
|------|---------|
| `scripts/create_condensed_canvas.py` | Creates 10-15KB canvas from full report |
| `scripts/post_weekly_canvas_with_file.sh` | One-command workflow |
| `plugins/weekly-growth-review/commands/weekly-review.md` | Updated skill |
| `CANVAS_WITH_FILE_GUIDE.md` | This guide |

---

## 💡 **Pro Tips**

1. **Commit MD files to git** - automatic versioning, team has GitHub access
2. **Use Slack threads** - post each week in same thread for easy week-over-week
3. **Pin Canvas** - pin first week's canvas, update thread each week
4. **Search works** - full MD content is indexed if on GitHub
5. **Mobile-friendly** - Canvas renders well in Slack mobile app

---

## 🎯 **Next Steps**

1. **Test the workflow:**
   ```bash
   ./scripts/post_weekly_canvas_with_file.sh 2026-03-09
   ```

2. **Post to Slack:**
   - Copy canvas content
   - Create canvas in #team-central-biz
   - Share in channel

3. **Get feedback:**
   - Is condensed canvas scannable enough?
   - Do people click through to full MD?
   - Adjust condensing logic if needed

4. **Automate (optional):**
   - Add to Airflow DAG for Monday runs
   - Or keep manual for flexibility

---

**Questions?** The condensed canvas gives you:
- ✅ Markdown formatting (Canvas native support)
- ✅ Scannable overview (~10-15KB, 2 min read)
- ✅ Link to full details (MD file)
- ✅ No external tools (all in Slack)
- ✅ Team-friendly (no .md editor needed)

This is the **sweet spot** between Canvas (too small) and Google Docs (external tool).
