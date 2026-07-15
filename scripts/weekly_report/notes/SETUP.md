# GM Notes Backend — Setup

The weekly report's GM-note drawer talks to a Google Sheet (via an Apps Script
web app) and can post notes to Slack. Everything degrades gracefully: with no
backend configured, notes fall back to browser localStorage only.

## Architecture

```
report.html (browser)
   │  GET ?action=upsert|list|post
   ▼
Apps Script web app  ──►  Google Sheet  (source of truth: one note per CE per week)
   │  chat.postMessage
   ▼
Slack #mkt-* channel  (thread per CE/week; permalink stored back in the sheet)
```

- **Save** → writes the note to the sheet (keyed on market + ce_id + week).
- **Post to #channel** → posts the note to the market's Slack channel, stores the
  thread `ts` + permalink. Re-posting threads an update under the same message.
- **View thread** → the Post button becomes a deep-link once a thread exists.
- **History** → prior weeks' notes for the same CE, read-only.

## 1. Sheet + Apps Script (already deployed)

- Sheet: `Weekly Report Notes` (ID `1hC_IAsJrlPcpFv5K49eRtcwgK6i_DkAt4ZvETxlK-s8`)
- Web app URL is set in `config.py` → `NOTES_SCRIPT_URL`

If redeploying: paste `apps_script.js` into the sheet's Apps Script editor
(Extensions → Apps Script), then Deploy → Manage deployments → New version.
The `notes` tab auto-creates with headers on first call.

## 2. Slack posting (one-time)

The Post button reuses the existing **`REVENUE_ALERT_SLACK_TOKEN`** bot
(the "Monthly Market Review" bot). To enable posting:

1. In the Apps Script editor: **Project Settings (gear) → Script properties → Add**
   - Property: `SLACK_BOT_TOKEN`
   - Value: the `xoxb-…` token (same one exported as `REVENUE_ALERT_SLACK_TOKEN`)
2. **Invite the bot to each market channel** it will post to:
   - `/invite @Monthly Market Review` in `#mkt-usa`, `#mkt-italy-switzerland-malta`, `#mkt-anz`
3. Redeploy a new version so the property is picked up.

Without `SLACK_BOT_TOKEN`, Save still works; Post returns an error and the
button shows "Post failed".

## 3. Channel map

Market → channel is in `config.py` → `NOTES_SLACK_CHANNELS`:

| Market | Channel | ID |
|--------|---------|-----|
| north_america | #mkt-usa | CNSHDD2H1 |
| italy | #mkt-italy-switzerland-malta | C045L2WQ79P |
| oceania | #mkt-anz | CHKRLFDPU |

Add a market by adding a row here (and inviting the bot to that channel).

## 4. Test

```bash
# list (empty ok)
curl -sL "$WR_NOTES_SCRIPT_URL?action=list&market=north_america"

# save a note
curl -sL "$WR_NOTES_SCRIPT_URL?action=upsert&market_slug=north_america&ce_id=220&ce_name=Test&week_start=2026-07-06&note=hello&author=me"

# post to slack (needs SLACK_BOT_TOKEN + bot in channel)
curl -sL "$WR_NOTES_SCRIPT_URL?action=post&market_slug=north_america&ce_id=220&ce_name=Test&week_start=2026-07-06&channel=CNSHDD2H1&text=hello&author=me"
```
