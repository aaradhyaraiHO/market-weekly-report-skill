#!/usr/bin/env python3
"""One-off recovery — un-scramble the `Final action` (AT) column of the perf sheet's
`w/c 2026-07-26` tab.

Context (2026-08-10): the position-based export re-sorted data rows while perf's Final-action
cells stayed pinned by absolute row, scattering the 17 real finals onto the wrong CEs (e.g.
Kennedy [3111] inherited a bogus "Pause & review"). The current AT values are a pure PERMUTATION
of the Aug-7 5 PM aligned snapshot (identical value multiset) — so the fix is: clear every current
AT cell and re-write each of the 17 finals onto ITS CID's row, from /tmp/final_CLEAN_5pm.csv.

SAFETY: re-reads the live tab, asserts (a) all 17 recovered CIDs are locatable and (b) the current
AT multiset == the recovered multiset (proving a scramble, not new data), duplicates the tab as a
backup, then writes. Dry-run by default; pass --apply to write.
"""
from __future__ import annotations
import argparse, csv, json, subprocess, sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import export_perf_sheet as E  # reuse _gws / _colname / PERF_SHEET_ID

SPREADSHEET = E.PERF_SHEET_ID
TAB = "w/c 2026-07-26"
RECOVERED = Path("/tmp/final_CLEAN_5pm.csv")


def read_tab():
    ok, txt = E._gws(["spreadsheets", "values", "get"],
                     {"spreadsheetId": SPREADSHEET, "range": f"'{TAB}'!A1:BA400"})
    if not ok:
        sys.exit(f"read failed: {txt}")
    return json.loads(txt[txt.index("{"):]).get("values", [])


def first_ix(hdr, name, default=None):
    for i, h in enumerate(hdr):
        if str(h).strip().lower() == name.lower():
            return i
    return default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="perform the backup + write (else dry-run)")
    args = ap.parse_args()

    vals = read_tab()
    hdr = vals[0]
    i_cid = first_ix(hdr, "CID", 0)
    i_name = first_ix(hdr, "CID Name", 1)
    i_at = first_ix(hdr, "Final action")           # FIRST match = the real AT col
    if i_at is None:
        sys.exit("no 'Final action' column found")
    at_col = E._colname(i_at)
    print(f"tab={TAB!r}  Final-action col = {at_col} (idx {i_at})")

    def cell(r, i): return (str(r[i]).strip() if i < len(r) else "")

    # CID -> first row number (sheet rows are 1-based; data starts at row 2)
    cid_row = {}
    at_filled = {}   # row -> value
    for ri, r in enumerate(vals[1:], start=2):
        cid = cell(r, i_cid)
        if cid and cid not in cid_row:
            cid_row[cid] = (ri, cell(r, i_name))
        v = cell(r, i_at)
        if v:
            at_filled[ri] = (cid, cell(r, i_name), v)

    # recovered truth
    rec = []  # (raw_cid, ce, final)
    with open(RECOVERED) as fh:
        for row in csv.DictReader(fh):
            rec.append((row["CID"].strip(), row["CE"].strip(), row["Final action"].strip()))

    # (a) all recovered CIDs locatable
    missing = [c for c, _, _ in rec if c not in cid_row]
    if missing:
        sys.exit(f"ABORT — {len(missing)} recovered CIDs not in the tab: {missing}")

    # (b) scramble check: current AT multiset == recovered multiset
    cur_multi = Counter(v for _, _, v in at_filled.values())
    rec_multi = Counter(f for _, _, f in rec)
    # tolerate one stray non-final junk token (e.g. a leaked "Perf action" header word)
    junk = {"Perf action", "Perf comment", "Final action"}
    cur_clean = Counter({k: v for k, v in cur_multi.items() if k not in junk})
    if cur_clean != rec_multi:
        print("!! multiset mismatch — current(clean) vs recovered:")
        print("   current:", dict(cur_clean))
        print("   recovered:", dict(rec_multi))
        sys.exit("ABORT — current AT is not a clean permutation of the recovered set; needs human review.")
    print(f"OK  scramble confirmed: {sum(rec_multi.values())} finals, identical multiset "
          f"({'+1 junk token' if cur_multi != cur_clean else 'no junk'}).")

    # build write plan
    target_rows = {cid_row[c][0] for c, _, _ in rec}
    clears = sorted(r for r in at_filled if r not in target_rows)
    sets = [(cid_row[c][0], c, ce, f) for c, ce, f in rec]

    print(f"\nPLAN: clear {len(clears)} scrambled AT cells, set {len(sets)} correct finals.")
    print("--- CLEAR ---")
    for r in clears:
        cid, nm, v = at_filled[r]
        print(f"  {at_col}{r}  ({cid} {nm[:24]})  {v!r} -> ''")
    print("--- SET ---")
    for row, cid, ce, f in sorted(sets):
        print(f"  {at_col}{row}  ({cid} {ce[:24]})  -> {f!r}")

    if not args.apply:
        print("\n(dry-run — pass --apply to back up + write)")
        return

    # 1. backup: duplicate the tab
    print("\nbacking up (duplicateSheet)...")
    ok, txt = E._gws(["spreadsheets", "get"],
                     {"spreadsheetId": SPREADSHEET, "fields": "sheets(properties(sheetId,title))"})
    sid = None
    for sh in json.loads(txt[txt.index("{"):]).get("sheets", []):
        if sh["properties"]["title"] == TAB:
            sid = sh["properties"]["sheetId"]
    if sid is None:
        sys.exit("ABORT — could not find sheetId for backup")
    bkup = "BACKUP w-c 2026-07-26 (pre-ATfix 2026-08-10)"
    ok, txt = E._gws(["spreadsheets", "batchUpdate"], {"spreadsheetId": SPREADSHEET},
                     {"requests": [{"duplicateSheet": {"sourceSheetId": sid, "newSheetName": bkup}}]})
    print(("  ✓ " if ok else "  ✗ ") + f"backup tab: {bkup}" + ("" if ok else f"  {txt}"))
    if not ok and "already exists" not in txt:
        sys.exit("ABORT — backup failed")

    # 2. write clears + sets in one batch (RAW)
    data = ([{"range": f"'{TAB}'!{at_col}{r}", "values": [[""]]} for r in clears]
            + [{"range": f"'{TAB}'!{at_col}{row}", "values": [[f]]} for row, cid, ce, f in sets])
    ok, txt = E._gws(["spreadsheets", "values", "batchUpdate"], {"spreadsheetId": SPREADSHEET},
                     {"valueInputOption": "RAW", "data": data})
    print(("  ✓ " if ok else "  ✗ ") + f"wrote {len(data)} cells" + ("" if ok else f"  {txt}"))
    if not ok:
        sys.exit("ABORT — write failed (backup is intact)")

    # 3. verify read-back
    print("\nverifying...")
    v2 = read_tab()
    at2 = {ri: cell(r, i_at) for ri, r in enumerate(v2[1:], start=2) if cell(r, i_at)}
    ok_set = all(at2.get(row) == f for row, cid, ce, f in sets)
    stray = [r for r in clears if r in at2]
    print(f"  17 finals correct: {ok_set}")
    print(f"  scrambled cells cleared: {len(clears)-len(stray)}/{len(clears)}" + (f"  STILL SET: {stray}" if stray else ""))
    # Kennedy sanity
    ken = cid_row.get("3111")
    if ken:
        print(f"  Kennedy [3111] row{ken[0]} AT now: {at2.get(ken[0], '')!r} (expect empty)")
    print(f"  total AT-filled now: {len(at2)} (expect {len(sets)})")


if __name__ == "__main__":
    main()
