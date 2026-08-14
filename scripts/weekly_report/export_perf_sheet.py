#!/usr/bin/env python3
"""Task 2 — Weekly Flagged export → perf's spreadsheet (1sXd0m…), NEW TAB per week.

Emits one row per flagged Losing-Money CE (existing + new). Approved clean layout (2026-08-03):

  CID · CID Name · Category · Market                                        (identity)
  W0 block (Cost·Clicks·CPC·Conv·CVR·CM1·ROI·CM2) · W-1 · W-2 · W-3         (4 weekly blocks)
  New/Exist · Tier · CM2 -ve 2wk · ROI Change(W0/W-1−1) · Clicks Change     (flags)
  GM action · GM comment                          (export owns — from the report store)
  Perf action · Perf comment · Final action       (PERF fills in the sheet — export never writes)

Metric representation matches the live sheet: CVR & ROI as FRACTIONS (0–1), Cost/CPC/CM1/CM2
in $, Clicks/Conversion as counts. Weekly metrics come from the snapshot losing_money rows'
`weeks` blocks (Conversion derived = CVR × Clicks; the store doesn't carry a raw count).

Dry-run prints the rows. The live-sheet WRITE is a separate, main-only step (not wired here) —
GUARD: never write the shared sheet from a worktree build.

Usage:
    python3 export_perf_sheet.py --snapshot <snapshot.json> --dry-run     # single (fixture) file
    python3 export_perf_sheet.py --week YYYY-MM-DD --dry-run               # all markets in .cache
"""
from __future__ import annotations
import argparse, datetime as dt, glob, json, os, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import config  # noqa: E402
import bucket_views  # noqa: E402
CACHE = Path(config.__file__).resolve().parents[2] / ".cache" / "weekly_report"
PERF_SHEET_ID = "1sXd0m2d2Qc5rg99ctpp_hnN5Jg8mtsRAwds_i2ZuwLo"   # perf's Weekly Flagged spreadsheet


def _colname(i):
    s = ""; i += 1
    while i > 0:
        i, r = divmod(i - 1, 26); s = chr(65 + r) + s
    return s

# Column order = the live `Final Loosing money` header (A → AU).
WEEK_METRICS = ["Cost", "Clicks", "CPC", "Conversion", "CVR", "CM1", "ROI", "CM2"]
HEADER = (["CID", "CID Name", "Category", "Market"]
          + [f"W{w} {m}" for w in range(4) for m in WEEK_METRICS]      # 4 weekly blocks W0..W3
          + ["New/Exist", "Tier", "CM2 -ve 2wk", "ROI Change", "Clicks Change",
             "GM action", "GM comment",                                # export owns (from store)
             "Perf action", "Perf comment", "Final action"])           # PERF fills — export never writes

GM_ACT_LBL = {"negative_seasonality": "Negative seasonality", "roas_change": "ROAS target change",
              "scale_down": "Scale down", "pause": "Pause", "pause_review": "Pause & review",
              "no_change": "No change", "skip": "Skip"}


def _week_cells(w: dict | None) -> list:
    """The 8 sheet metrics for one week block, matching the live sheet's units."""
    if not w:
        return [""] * 8
    spend = w.get("spend"); clicks = w.get("clicks"); cpc = w.get("cpc")
    cvr_pct = w.get("cvr"); cm1 = w.get("cm1"); roi_pct = w.get("roi"); cm2 = w.get("cm2")
    conv = round(cvr_pct / 100.0 * clicks) if (cvr_pct is not None and clicks) else ""   # CVR = 100·conv/clk
    return [spend if spend is not None else "",
            clicks if clicks is not None else "",
            cpc if cpc is not None else "",
            conv,
            round(cvr_pct / 100.0, 4) if cvr_pct is not None else "",      # fraction (0–1)
            cm1 if cm1 is not None else "",
            round(roi_pct / 100.0, 4) if roi_pct is not None else "",      # fraction
            cm2 if cm2 is not None else ""]


def rows_for_snapshot(snap: dict, gm_actions: dict[str, dict], camp_cat: dict | None = None) -> list[list]:
    meta = snap.get("meta", {})
    market = meta.get("market", "")
    camp_cat = camp_cat or {}
    flagged = bucket_views.final_losing_money_rows(snap)
    # CE-level category from the CE list — used only as a FALLBACK now. The Category column is the
    # CAMPAIGN-level category (ads_campaign_stats.campaign_category, via camp_cat) per Aditya
    # 2026-08-04: the campaign-stats dashboard's category filter, not the combined-entity category.
    cat = {}
    for c in snap.get("ces", []) or []:
        cat[str(c.get("ce_id"))] = ((c.get("metadata") or {}).get("category") or "")
    out = []
    for r in flagged:
        cid = str(r.get("ce_id"))
        wk = r.get("weeks") or []
        w = {i: (wk[i] if i < len(wk) else None) for i in range(4)}
        blocks = []
        for i in range(4):
            blocks += _week_cells(w[i])
        cm2_0 = (w[0] or {}).get("cm2"); cm2_1 = (w[1] or {}).get("cm2")
        roi0 = (w[0] or {}).get("roi"); roi1 = (w[1] or {}).get("roi")
        clk0 = (w[0] or {}).get("clicks"); clk1 = (w[1] or {}).get("clicks")
        neg2 = "True" if (cm2_0 is not None and cm2_1 is not None and cm2_0 < 0 and cm2_1 < 0) else "False"
        roi_chg = round(roi0 / roi1 - 1, 4) if (roi0 and roi1) else ""
        clk_chg = round(clk0 / clk1 - 1, 4) if (clk0 and clk1) else ""
        gm = gm_actions.get(cid, {})
        gm_act = GM_ACT_LBL.get(gm.get("status", ""), gm.get("status", ""))
        out.append([cid, r.get("ce_name", ""), camp_cat.get(cid) or cat.get(cid, ""), market]
                   + blocks
                   + [r.get("new_existing", ""), r.get("tier", ""), neg2, roi_chg, clk_chg,
                      gm_act, gm.get("note", ""),
                      "", "", ""])             # Perf action / comment / final — perf fills in the sheet
    return out


def _fetch_gm_actions(market_slug: str, week: str, attempts: int = 4) -> dict[str, dict]:
    """GM action layer (bucket=losing_money) for the market-week, from the store.

    RETRIES on transient failure: the Apps Script endpoint throttles under the rapid
    13-market batch, and the old silent `except: return {}` turned a throttle timeout
    into blank GM columns — i.e. it CLOBBERED real GM comments in the sheet (seen
    2026-08-03: Italy's Colosseum/Ferrari comments dropped on a publish-all). On total
    failure we RAISE, never return {} — callers must skip the write rather than blank
    the columns. A genuinely comment-less market returns {} normally (no exception)."""
    import time, urllib.parse, urllib.request
    base = os.environ.get("WR_NOTES_SCRIPT_URL") or config.NOTES_SCRIPT_URL
    if not base:
        return {}
    q = urllib.parse.urlencode({"action": "action_list", "market": market_slug, "week": week})
    last = None
    for i in range(attempts):
        try:
            with urllib.request.urlopen(base + "?" + q, timeout=25) as r:
                data = json.loads(r.read().decode())
            return {str(a["ce_id"]): a for a in data.get("actions", [])
                    if a.get("bucket") == "losing_money" and a.get("ce_id")}
        except Exception as e:
            last = e
            if i < attempts - 1:
                time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"GM action fetch failed for {market_slug} {week} after {attempts} tries: {last}")


def _fetch_campaign_categories(week: str) -> dict[str, str]:
    """Dominant CAMPAIGN-level category per CE for the report week, from ads_campaign_stats
    (`campaign_category` — the 'campaign stats' dashboard's category filter, per Aditya
    2026-08-04). One query, all markets; category weighted by clicks (the campaign a CID spends
    the most on). Best-effort: on failure returns {}, and the caller falls back to the CE-level
    category so the export never breaks. Keyed by str(ce_id)."""
    try:
        import bq  # google.cloud.bigquery via ADC — same client the snapshot build uses
        w0 = dt.date.fromisoformat(week)
        w_end = w0 + dt.timedelta(days=6)          # Sun-start report week → Sat end
        sql = f"""
        WITH c AS (
          SELECT campaign_target_combined_entity_id AS ce_id,
                 campaign_category,
                 SUM(count_clicks) AS clicks
          FROM {config.ADS_STATS}
          WHERE report_date BETWEEN @start AND @end
            AND ad_platform IN ('Google Ads','Microsoft Ads')
            AND campaign_advertising_channel_type = 'SEARCH'
            AND campaign_category IS NOT NULL
          GROUP BY 1, 2
        )
        SELECT ce_id, campaign_category
        FROM c
        QUALIFY ROW_NUMBER() OVER (PARTITION BY ce_id ORDER BY clicks DESC) = 1
        """
        df = bq.query_df(sql, "campaign_category",
                         {"start": config.iso(w0), "end": config.iso(w_end)})
        return {str(r["ce_id"]): r["campaign_category"] for _, r in df.iterrows()
                if r.get("campaign_category")}
    except Exception as e:
        print(f"  ! campaign_category fetch failed ({e}) — falling back to CE-level category")
        return {}


def _gws(sub, params, body=None):
    """Run a gws sheets call. Returns (ok, text)."""
    cmd = ["gws", "sheets"] + sub + ["--params", json.dumps(params), "--format", "json"]
    if body is not None:
        cmd += ["--json", json.dumps(body)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode == 0, (r.stdout or r.stderr).strip()


def _tab_sheet_id(spreadsheet_id, tab):
    """Numeric sheetId for a tab title (needed for grid-range requests). None if not found."""
    ok, txt = _gws(["spreadsheets", "get"],
                   {"spreadsheetId": spreadsheet_id, "fields": "sheets(properties(sheetId,title))"})
    if not ok:
        return None
    try:
        txt = txt[txt.index("{"):]                 # strip the gws 'Using keyring backend' preamble
        for sh in json.loads(txt).get("sheets", []):
            if sh["properties"]["title"] == tab:
                return sh["properties"]["sheetId"]
    except Exception:
        return None
    return None


def _on_main():
    r = subprocess.run(["git", "-C", str(HERE), "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip() == "main"


# Perf's three columns (export never authors their VALUES — only re-homes them by CID).
PERF_COLS = {"Perf action": 43, "Perf comment": 44, "Final action": 45}


def _read_tab(spreadsheet_id, tab):
    """Current values of a tab (A1:BZ…), or [] if it doesn't exist / read fails."""
    ok, txt = _gws(["spreadsheets", "values", "get"],
                   {"spreadsheetId": spreadsheet_id, "range": f"'{tab}'!A1:BZ3000"})
    if not ok:
        return []
    try:
        return json.loads(txt[txt.index("{"):]).get("values", [])
    except Exception:
        return []


def _perf_by_cid(tab_rows):
    """From a tab's values → ({cid: (perf_action, perf_comment, final_action)}, [cid order top→bottom]).
    Perf columns are located BY HEADER NAME (first match, so the real cols win over any duplicate
    'Perf comment'/'Final action' columns), falling back to the export's fixed positions. This is the
    key that lets perf entries follow their CE regardless of row order."""
    if not tab_rows:
        return {}, []
    hdr = [str(c).strip() for c in tab_rows[0]]
    ci = hdr.index("CID") if "CID" in hdr else 0
    ix = {name: (hdr.index(name) if name in hdr else pos) for name, pos in PERF_COLS.items()}
    pa, pc, fa = ix["Perf action"], ix["Perf comment"], ix["Final action"]
    m, order = {}, []
    for r in tab_rows[1:]:
        cid = (str(r[ci]).strip() if ci < len(r) else "")
        if not cid:
            continue
        g = lambda i: (str(r[i]).strip() if i < len(r) else "")
        m[cid] = (g(pa), g(pc), g(fa)); order.append(cid)
    return m, order


def write_weekly_tab(rows, week, spreadsheet_id=PERF_SHEET_ID):
    """Populate the `w/c <week>` tab — CID-KEYED so perf's columns can never drift:
      1. READ the current tab → capture perf cells (Perf action/comment/Final) BY CID + the
         existing CID row order (BEFORE we overwrite anything).
      2. Reorder: existing CIDs keep their current-tab position (stable — no mid-week reshuffle);
         newly-flagged CIDs append at the bottom.
      3. Re-place each perf cell onto ITS CID's new row (perf follows its CE).
      4. Write header + all rows (A..AT, 46 cols) and CLEAR any columns to the RIGHT (AU+) so
         stray duplicate 'Perf comment'/'Final action' columns can't accumulate.
    Because perf cells are addressed by CID, any re-sort / market add / maturation is harmless.
    DEPLOY ONLY FROM AN ALIGNED SHEET — step 1 trusts the current CID↔perf pairing (a NEW week's
    fresh tab is aligned by construction; an existing drifted tab must be restored first)."""
    tab = f"w/c {week}"
    last = _colname(len(HEADER) - 1)              # AT — export owns A..AT (46 cols)
    # 1. current tab: perf cells by CID + row order  (BEFORE we overwrite anything)
    cur_perf, cur_order = _perf_by_cid(_read_tab(spreadsheet_id, tab))
    # 2. stable order: existing CIDs first (current order), new CIDs appended
    by_cid = {str(r[0]): r for r in rows}
    seen = set(cur_order)
    ordered = ([by_cid[c] for c in cur_order if c in by_cid]
               + [r for r in rows if str(r[0]) not in seen])
    # 3. build full rows — perf cols (43/44/45) re-placed BY CID
    full = []
    for r in ordered:
        row = list(r[:len(HEADER)]); row += [""] * (len(HEADER) - len(row))
        row[43], row[44], row[45] = cur_perf.get(str(r[0]), ("", "", ""))   # perf follows its CE
        full.append(row)
    # 4a. ensure tab + unmerge header row (best-effort; keeps flat per-column labels)
    _gws(["spreadsheets", "batchUpdate"], {"spreadsheetId": spreadsheet_id},
         {"requests": [{"addSheet": {"properties": {"title": tab}}}]})
    sid = _tab_sheet_id(spreadsheet_id, tab)
    if sid is not None:
        _gws(["spreadsheets", "batchUpdate"], {"spreadsheetId": spreadsheet_id},
             {"requests": [{"unmergeCells": {"range": {"sheetId": sid, "startRowIndex": 0,
               "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": len(HEADER)}}}]})
    # 4b. header (A1:AT1) + all rows (A2:AT{n+1}) — perf columns included, CID-correct
    _gws(["spreadsheets", "values", "update"],
         {"spreadsheetId": spreadsheet_id, "range": f"'{tab}'!A1:{last}1", "valueInputOption": "USER_ENTERED"},
         {"values": [HEADER]})
    ok, txt = _gws(["spreadsheets", "values", "update"],
                   {"spreadsheetId": spreadsheet_id,
                    "range": f"'{tab}'!A2:{last}{len(full) + 1}", "valueInputOption": "USER_ENTERED"},
                   {"values": full})
    # 4c. sweep any columns to the RIGHT of AT (duplicate 'Perf comment'/'Final action' junk)
    rcol = _colname(len(HEADER))                  # AU — first column past the contract
    _gws(["spreadsheets", "values", "clear"],
         {"spreadsheetId": spreadsheet_id, "range": f"'{tab}'!{rcol}1:BZ{len(full) + 1}"})
    return ok, tab, txt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", help="single snapshot json (fixture/dry-run)")
    ap.add_argument("--week", default=config.iso(config.latest_complete_week()))
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--write", dest="dry_run", action="store_false",
                    help="write the weekly tab to the perf sheet (MAIN checkout only)")
    args = ap.parse_args()

    paths = [args.snapshot] if args.snapshot else sorted(glob.glob(str(CACHE / f"snapshot_*_{args.week}.json")))
    if not paths:
        raise SystemExit("no snapshot(s) found")

    camp_cat = _fetch_campaign_categories(args.week)   # campaign-level Category (all markets, one query)
    all_rows = []
    for p in paths:
        snap = json.load(open(p))
        meta = snap.get("meta", {})
        if meta.get("market_slug") == "headout":
            continue
        gm = _fetch_gm_actions(meta.get("market_slug", ""), args.week)
        all_rows += rows_for_snapshot(snap, gm, camp_cat)

    if args.dry_run:
        print(f"{len(all_rows)} flagged rows · {len(HEADER)} columns (A..{_colname(len(HEADER)-1)})\n")
        print(" | ".join(f"{_colname(i)}:{h}" for i, h in enumerate(HEADER)))
        print("-" * 100)
        for row in all_rows:
            show = row[:12] + ["…"] + row[36:]     # identity + W0 block + tail (skip W1..W3 for width)
            print(" | ".join(str(x) for x in show))
        return
    # live write — publish-only-from-main (writing the shared perf sheet)
    if not _on_main() and os.environ.get("WR_ALLOW_WORKTREE_WRITE") != "1":
        sys.exit("REFUSING to write the perf sheet from a non-main checkout (publish-only-from-main). "
                 "Run from main, or set WR_ALLOW_WORKTREE_WRITE=1 for a test.")
    ok, tab, txt = write_weekly_tab(all_rows, args.week)
    print(f"{'✓' if ok else '✗'} wrote {len(all_rows)} rows → tab '{tab}'" + ("" if ok else f"\n{txt}"))


if __name__ == "__main__":
    main()
