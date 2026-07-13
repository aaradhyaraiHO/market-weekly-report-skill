/**
 * Google Apps Script — Weekly Report Notes backend.
 *
 * Deploy as: Web app → Execute as Me → Anyone with link.
 * Sheet layout (row 1 headers):
 *   market_slug | ce_id | ce_name | week_start | author | text | section | status | updated
 *
 * GET  ?action=list[&market=X][&week=Y]  → all notes (filtered)
 * GET  ?action=get&market=X&ce_id=Y      → single note
 * POST {action:"upsert", market_slug, ce_id, ce_name, week_start, author, text, section, status}
 * POST {action:"resolve", market_slug, ce_id}  → sets status=resolved
 */

const SHEET_NAME = "notes";
const HEADERS = [
  "market_slug","ce_id","ce_name","week_start","author","text","section","status","updated"
];

function getSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) {
    sh = ss.insertSheet(SHEET_NAME);
    sh.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]);
    sh.getRange(1, 1, 1, HEADERS.length).setFontWeight("bold");
    sh.setFrozenRows(1);
  }
  return sh;
}

function allRows() {
  const sh = getSheet();
  const last = sh.getLastRow();
  if (last < 2) return [];
  const data = sh.getRange(2, 1, last - 1, HEADERS.length).getValues();
  return data.map((r, i) => {
    const obj = {};
    HEADERS.forEach((h, j) => obj[h] = r[j]);
    obj._row = i + 2;
    return obj;
  });
}

function findRow(market, ceId) {
  return allRows().find(r => r.market_slug === market && r.ce_id === ceId);
}

function doGet(e) {
  const p = e.parameter;
  const action = p.action || "list";

  if (action === "get") {
    const row = findRow(p.market, p.ce_id);
    return jsonResp({ ok: true, note: row || null });
  }

  let rows = allRows();
  if (p.market) rows = rows.filter(r => r.market_slug === p.market);
  if (p.week)   rows = rows.filter(r => r.week_start === p.week);
  if (p.status) rows = rows.filter(r => r.status === p.status);
  return jsonResp({ ok: true, notes: rows });
}

function doPost(e) {
  const body = JSON.parse(e.postData.contents);
  const action = body.action || "upsert";

  if (action === "upsert") {
    const sh = getSheet();
    const existing = findRow(body.market_slug, body.ce_id);
    const now = new Date().toISOString();
    const row = [
      body.market_slug || "",
      body.ce_id || "",
      body.ce_name || "",
      body.week_start || "",
      body.author || "",
      body.text || "",
      body.section || "drawer",
      body.status || "open",
      now
    ];

    if (existing) {
      sh.getRange(existing._row, 1, 1, HEADERS.length).setValues([row]);
    } else {
      sh.appendRow(row);
    }
    return jsonResp({ ok: true, action: existing ? "updated" : "created", updated: now });
  }

  if (action === "resolve") {
    const existing = findRow(body.market_slug, body.ce_id);
    if (existing) {
      const sh = getSheet();
      sh.getRange(existing._row, HEADERS.indexOf("status") + 1).setValue("resolved");
      sh.getRange(existing._row, HEADERS.indexOf("updated") + 1).setValue(new Date().toISOString());
      return jsonResp({ ok: true, action: "resolved" });
    }
    return jsonResp({ ok: false, error: "not found" });
  }

  if (action === "bulk") {
    const sh = getSheet();
    const notes = body.notes || [];
    let created = 0, updated = 0;
    const now = new Date().toISOString();
    notes.forEach(n => {
      const existing = findRow(n.market_slug, n.ce_id);
      const row = [
        n.market_slug || "", n.ce_id || "", n.ce_name || "",
        n.week_start || "", n.author || "", n.text || "",
        n.section || "drawer", n.status || "open", now
      ];
      if (existing) { sh.getRange(existing._row, 1, 1, HEADERS.length).setValues([row]); updated++; }
      else { sh.appendRow(row); created++; }
    });
    return jsonResp({ ok: true, created, updated });
  }

  return jsonResp({ ok: false, error: "unknown action: " + action });
}

function jsonResp(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
