# Notes Backend — One-Time Setup

## 1. Create the Google Sheet

1. Go to [sheets.google.com](https://sheets.google.com) → new blank spreadsheet
2. Name it `Weekly Report Notes`
3. Copy the Sheet ID from the URL: `https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit`

## 2. Deploy the Apps Script

1. In the sheet → Extensions → Apps Script
2. Replace the contents of `Code.gs` with `apps_script.js` from this directory
3. Deploy → New deployment:
   - Type: **Web app**
   - Execute as: **Me**
   - Who has access: **Anyone** (within Headout org)
4. Copy the deployment URL (looks like `https://script.google.com/macros/s/.../exec`)

## 3. Configure the pipeline

Add to `config.py`:

```python
NOTES_SHEET_ID = "<your-sheet-id>"
NOTES_SCRIPT_URL = "<your-deployment-url>"
```

Or set env vars:
```bash
export WR_NOTES_SHEET_ID="<your-sheet-id>"
export WR_NOTES_SCRIPT_URL="<your-deployment-url>"
```

## 4. Test

```bash
# List all notes (should return empty)
curl "<deployment-url>?action=list"

# Create a note
curl -X POST "<deployment-url>" \
  -H "Content-Type: application/json" \
  -d '{"action":"upsert","market_slug":"north_america","ce_id":"123","ce_name":"Test CE","week_start":"2026-07-06","author":"test","text":"hello","section":"drawer","status":"open"}'
```

The HTML reports will sync automatically once `NOTES_SCRIPT_URL` is configured.
Without it, comments fall back to localStorage only (existing behavior).
