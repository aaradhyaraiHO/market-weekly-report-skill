#!/usr/bin/env python3
"""
Build "close-the-loop" follow-up drafts for the Monday weekly-alert pings.

Reads Perf's "Final Loosing money" tab (CID · Name · Category grain), maps each
row to its market channel, groups per market, and threads the follow-up under
that market's Monday alert (anchor from alert/posted_ledger.json).

DRAFT-FIRST: this only writes drafts to alert/followup_drafts_<week>.json and
prints them. It does NOT post. Posting is a separate confirmed step.

Usage: python3 followup_actioning.py [--week 2026-07-20]
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from collections import OrderedDict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHEET_ID = "1sXd0m2d2Qc5rg99ctpp_hnN5Jg8mtsRAwds_i2ZuwLo"
TAB = "Final Loosing money"

# Account (sheet) -> market slug. Middle East is per-CE (see CE_OVERRIDE).
ACCOUNT_MAP = {
    "Iberia": "iberia", "North America": "north_america", "Anz": "oceania",
    "France": "france", "Italy": "italy", "Cee": "csee", "See": "csee",
    "East Asia": "east_asia", "Sea": "sea", "United Kingdom": "united_kingdom",
    "Africa": "rest_of_mea",
    "Latam": "_summary", "Central Categories": "_summary",
}
# Middle East → per-CID: Six Flags Qiddiya (Saudi) → gcc; the rest (Dubai/AbuDhabi) → uae
def middle_east_slug(cid: str) -> str:
    return "gcc" if cid.strip().startswith("6761") else "uae"

MARKET_NAME = {
    "iberia": "Iberia", "north_america": "North America", "oceania": "Oceania",
    "france": "France", "italy": "Italy", "csee": "CSEE", "east_asia": "East Asia",
    "sea": "SEA", "united_kingdom": "United Kingdom", "uae": "UAE", "gcc": "GCC",
    "rest_of_mea": "Rest of MEA",
}
# CC — tagged on every follow-up (Slack user IDs)
CC_TAGS = ["UM1FKLCLC", "U02DB3R3EDC"]   # Pranathi Varri · Aditya Vikram Singh
# Perf's working tracker (per-campaign metrics + full comments) — linked for detail
SHEET_URL = "https://docs.google.com/spreadsheets/d/1sXd0m2d2Qc5rg99ctpp_hnN5Jg8mtsRAwds_i2ZuwLo/edit#gid=1066981225"


def gws_get(rng: str):
    out = subprocess.run(
        ["/opt/homebrew/bin/gws", "sheets", "spreadsheets", "values", "get",
         "--params", json.dumps({"spreadsheetId": SHEET_ID, "range": rng}),
         "--format", "json"],
        capture_output=True, text=True).stdout
    out = "\n".join(l for l in out.splitlines() if "keyring" not in l)
    return json.loads(out).get("values", [])


def clean(s: str) -> str:
    # best-effort fix of common UTF-8-as-MacRoman mojibake seen in the sheet
    fixes = {
        "‚Äì": "–", "‚Äî": "—", "‚Äô": "’", "‚Äò": "‘", "‚Äú": "“", "‚Äù": "”",
        "√©": "é", "√®": "è", "√™": "ê", "√´": "ë",
        "√°": "á", "√†": "à", "√¢": "â",
        "√≠": "í", "√≥": "ó", "√∫": "ú", "√±": "ñ", "√ß": "ç",
        "√â": "É", "√Å": "Á", "√ì": "Ó", "√ö": "Ú",
    }
    for bad, good in fixes.items():
        s = s.replace(bad, good)
    return s.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", default="2026-07-20")
    args = ap.parse_args()
    week = args.week

    ledger = json.loads((HERE / "posted_ledger.json").read_text()).get(week, {})
    rows = gws_get(f"'{TAB}'!A3:AU105")

    def g(r, i): return clean(r[i]) if i < len(r) else ""

    # market slug -> list of {cid, name, category, action, final, why}
    by_market: "OrderedDict[str,list]" = OrderedDict()
    summary_bucket = []
    for r in rows:
        cid, name, cat, account = g(r, 0), g(r, 1), g(r, 2), g(r, 3)
        action = g(r, 42); perf = g(r, 43); pc2 = g(r, 44)
        final = g(r, 45); gm = g(r, 46)
        if not (cid or name):
            continue
        if account == "Middle East":
            slug = middle_east_slug(cid)      # per-CE: Qiddiya→gcc, else uae
        else:
            slug = ACCOUNT_MAP.get(account, "_summary")   # unknown account → surface, don't drop
        if slug == "_summary":
            summary_bucket.append((account, name, cat, action))
            continue
        why = perf or pc2
        decision = final or (gm if gm and gm != "#N/A" else "")
        by_market.setdefault(slug, []).append(
            {"cid": cid, "name": name, "category": cat,
             "action": action, "decision": decision, "why": why})

    cc_line = "cc: " + " ".join(f"<@{u}>" for u in CC_TAGS)

    drafts = OrderedDict()
    for slug, items in by_market.items():
        anchor = ledger.get(slug, {})
        # Show CID · Name · Category · Action Taken · Comments (per Perf's sheet;
        # NOT the GM/Final decision). Roll up campaign rows that share the SAME
        # (action, comments) into one line listing their categories; rows that
        # differ (different action or comment) stay as separate lines.
        groups = OrderedDict()
        for it in items:
            key = (it["cid"], it["name"], it["action"], it["why"])
            groups.setdefault(key, []).append(it["category"])
        lines = [f"📋 *Follow-up on Monday's Losing-Money flags — what Perf actioned (w/c {week})*",
                 f"_Closing the loop on the alert above. For each flagged CE: the action Perf took + their reasoning._",
                 f"_{len(groups)} CEs · {len(items)} campaigns._", ""]
        for (cid, name, action, why), cats in groups.items():
            cats = [c for c in cats if c]
            if len(cats) > 1:
                catstr = f" · _{len(cats)} campaigns:_ " + ", ".join(cats)
            elif cats:
                catstr = f" · {cats[0]}"
            else:
                catstr = ""
            lines.append(f"• *{name}* [{cid}]{catstr}")
            lines.append(f"     *Perf action:* {action or '—'}")
            if why:
                lines.append(f"     *Perf note:* {why}")
        lines.append("")
        lines.append(f"📊 More detail — per-campaign metrics + full comments: <{SHEET_URL}|Losing-Money tracker>")
        lines.append(cc_line)
        drafts[slug] = {
            "market": MARKET_NAME.get(slug, slug),
            "channel": anchor.get("channel"),
            "thread_ts": anchor.get("msg1_ts"),
            "have_anchor": bool(anchor.get("msg1_ts")),
            "n_ces": len(groups),
            "n_items": len(items),
            "text": "\n".join(lines),
        }

    outp = HERE / f"followup_drafts_{week}.json"
    outp.write_text(json.dumps({"week": week, "drafts": drafts,
                                "summary_no_channel": summary_bucket}, indent=2, ensure_ascii=False))

    # ---- console review ----
    print(f"week {week} · {len(drafts)} market drafts · {sum(d['n_items'] for d in drafts.values())} CE·campaign lines")
    print(f"drafts written -> {outp}\n")
    for slug, d in drafts.items():
        anchor = "✓ threads under Monday ping" if d["have_anchor"] else "⚠ NO Monday anchor — would post fresh"
        print(f"  {d['market']:16s} {d['n_items']:2d} items · ch={d['channel']} · {anchor}")
    if summary_bucket:
        print(f"\n  No-channel (summary only, NOT posted): {len(summary_bucket)}")
        for acc, name, cat, act in summary_bucket:
            print(f"    - [{acc}] {name} · {cat} · {act}")

    print("\n" + "=" * 70)
    print("SAMPLE DRAFT — first market")
    print("=" * 70)
    first = next(iter(drafts.values()))
    print(first["text"])


if __name__ == "__main__":
    main()
