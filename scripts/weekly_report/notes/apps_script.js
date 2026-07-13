/**
 * Google Apps Script — Weekly Report Notes backend.
 *
 * Deploy as: Web app → Execute as Me → Anyone.
 * Sheet tab "notes", row 1 headers:
 *   market_slug | ce_id | ce_name | week_start | author | text | section | status | updated
 *
 * ALL operations use GET (avoids POST redirect issues with Apps Script):
 *   ?action=list[&market=X][&week=Y][&status=Z]  → all notes (filtered)
 *   ?action=get&market=X&ce_id=Y                 → single note
 *   ?action=upsert&market_slug=X&ce_id=Y&text=Z[&ce_name=N&week_start=W&author=A&section=S&status=T]
 *   ?action=resolve&market_slug=X&ce_id=Y         → sets status=resolved
 */

var SHEET_NAME = "notes";
var HEADERS = [
  "market_slug","ce_id","ce_name","week_start","author","text","section","status","updated"
];

function getSheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) {
    sh = ss.insertSheet(SHEET_NAME);
    sh.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]);
    sh.getRange(1, 1, 1, HEADERS.length).setFontWeight("bold");
    sh.setFrozenRows(1);
  }
  return sh;
}

function allRows() {
  var sh = getSheet();
  var last = sh.getLastRow();
  if (last < 2) return [];
  var data = sh.getRange(2, 1, last - 1, HEADERS.length).getValues();
  var results = [];
  for (var i = 0; i < data.length; i++) {
    var obj = {};
    for (var j = 0; j < HEADERS.length; j++) obj[HEADERS[j]] = data[i][j];
    obj._row = i + 2;
    results.push(obj);
  }
  return results;
}

function findRow(market, ceId) {
  var rows = allRows();
  for (var i = 0; i < rows.length; i++) {
    if (rows[i].market_slug === market && String(rows[i].ce_id) === String(ceId)) return rows[i];
  }
  return null;
}

function doGet(e) {
  var p = e.parameter;
  var action = p.action || "list";

  if (action === "list") {
    var rows = allRows();
    if (p.market) rows = rows.filter(function(r){ return r.market_slug === p.market; });
    if (p.week)   rows = rows.filter(function(r){ return r.week_start === p.week; });
    if (p.status) rows = rows.filter(function(r){ return r.status === p.status; });
    return jsonResp({ ok: true, notes: rows });
  }

  if (action === "get") {
    var row = findRow(p.market, p.ce_id);
    return jsonResp({ ok: true, note: row || null });
  }

  if (action === "upsert") {
    var sh = getSheet();
    var existing = findRow(p.market_slug, p.ce_id);
    var now = new Date().toISOString();
    var text = p.text || "";
    var rowData = [
      p.market_slug || "",
      String(p.ce_id || ""),
      p.ce_name || "",
      p.week_start || "",
      p.author || "",
      text,
      p.section || "drawer",
      (text && text.trim()) ? (p.status || "open") : "resolved",
      now
    ];

    if (existing) {
      sh.getRange(existing._row, 1, 1, HEADERS.length).setValues([rowData]);
    } else {
      sh.appendRow(rowData);
    }
    return jsonResp({ ok: true, action: existing ? "updated" : "created", updated: now });
  }

  if (action === "resolve") {
    var found = findRow(p.market_slug, p.ce_id);
    if (found) {
      var sh2 = getSheet();
      sh2.getRange(found._row, HEADERS.indexOf("status") + 1).setValue("resolved");
      sh2.getRange(found._row, HEADERS.indexOf("updated") + 1).setValue(new Date().toISOString());
      return jsonResp({ ok: true, action: "resolved" });
    }
    return jsonResp({ ok: false, error: "not found" });
  }

  return jsonResp({ ok: false, error: "unknown action: " + action });
}

function jsonResp(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
