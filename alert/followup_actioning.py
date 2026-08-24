#!/usr/bin/env python3
"""
Build "close-the-loop" follow-up drafts for the Monday weekly-alert pings.

Reads Perf's weekly Losing-Money tab (CID · Name · Category grain), maps each row
to its market channel, groups per market, and threads the follow-up under that
market's Monday alert (anchor from alert/posted_ledger.json).

The sheet layout changed after the pilot week, so tab + columns are configured
per-week in WEEK_CFG.

  v2 (w/c 2026-07-26 onward): action = AT "Final action", comment = AQ (the
  `perf:` portion only — the `growth:` half is dropped), market = col D.

DRAFT-FIRST: writes drafts to alert/followup_drafts_<week>.json and prints them.
It does NOT post. Posting is a separate confirmed step (post_followups.py).

Usage: python3 followup_actioning.py --week 2026-07-26
"""
from __future__ import annotations
import argparse, json, subprocess
from collections import OrderedDict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHEET_ID = "1sXd0m2d2Qc5rg99ctpp_hnN5Jg8mtsRAwds_i2ZuwLo"

# Per-week sheet config (layout changed after the pilot).
#   cols are 0-based indices; comment_mode 'perf_only' keeps just the perf: line of AQ.
WEEK_CFG = {
    "2026-07-20": dict(tab="Final Loosing money", gid=1066981225, layout="v1",
                       cid=0, name=1, cat=2, market=3, action=42, comment=43, comment2=44),
    "2026-07-26": dict(tab="w/c 2026-07-26", gid=1579918324, layout="v2",
                       cid=0, name=1, cat=2, market=3, action=45, comment=42,
                       comment_mode="perf_only"),
}

# Market label (sheet col D / Account) -> alert slug (must match posted_ledger + channel map)
MARKET_MAP = {
    "Iberia": "iberia", "North America": "north_america", "Oceania": "oceania", "Anz": "oceania",
    "France": "france", "Italy": "italy", "CSEE": "csee", "Cee": "csee", "See": "csee",
    "East Asia": "east_asia", "SEA": "sea", "Sea": "sea", "South East Asia": "sea",
    "United Kingdom": "united_kingdom", "United Arab Emirates": "uae", "UAE": "uae",
    "Nordics": "nordics", "Benelux": "benelux", "GCC": "gcc",
    "North Africa": "north_africa", "Africa": "rest_of_mea", "Rest of MEA": "rest_of_mea",
    "South America": "south_america", "Latam": "south_america",
    "Mexico & Central America": "mexico_central_america",
    "Central Categories": "_summary",
}
# Middle East (v1 only) → per-CID: Six Flags Qiddiya (Saudi) → gcc; the rest → uae
def middle_east_slug(cid: str) -> str:
    return "gcc" if cid.strip().startswith("6761") else "uae"

MARKET_NAME = {
    "iberia": "Iberia", "north_america": "North America", "oceania": "Oceania",
    "france": "France", "italy": "Italy", "csee": "CSEE", "east_asia": "East Asia",
    "sea": "SEA", "united_kingdom": "United Kingdom", "uae": "UAE", "gcc": "GCC",
    "rest_of_mea": "Rest of MEA", "nordics": "Nordics", "benelux": "Benelux",
    "north_africa": "North Africa", "south_america": "South America",
    "mexico_central_america": "Mexico & Central America",
}
CC_TAGS = ["UM1FKLCLC", "U02DB3R3EDC"]   # Pranathi Varri · Aditya Vikram Singh


def gws_get(rng: str):
    out = subprocess.run(
        ["/opt/homebrew/bin/gws", "sheets", "spreadsheets", "values", "get",
         "--params", json.dumps({"spreadsheetId": SHEET_ID, "range": rng}),
         "--format", "json"],
        capture_output=True, text=True).stdout
    out = "\n".join(l for l in out.splitlines() if "keyring" not in l)
    return json.loads(out).get("values", [])


def clean(s: str) -> str:
    fixes = {"‚Äì": "–", "‚Äî": "—", "‚Äô": "’", "‚Äò": "‘", "‚Äú": "“", "‚Äù": "”",
             "√©": "é", "√®": "è", "√™": "ê", "√´": "ë", "√°": "á", "√†": "à", "√¢": "â",
             "√≠": "í", "√≥": "ó", "√∫": "ú", "√±": "ñ", "√ß": "ç",
             "√â": "É", "√Å": "Á", "√ì": "Ó", "√ö": "Ú"}
    for bad, good in fixes.items():
        s = s.replace(bad, good)
    return s.strip()


def perf_only(aq: str) -> str:
    """From an AQ cell shaped 'growth: …\\nperf: …' return ONLY the perf: portion.
    If there's no growth:/perf: scaffolding, return the whole cell. If only growth
    is filled (perf empty), return ''."""
    if not aq:
        return ""
    for line in aq.split("\n"):
        s = line.strip()
        if s.lower().startswith("perf:"):
            return s[len("perf:"):].strip()
    low = aq.lower()
    if "growth:" not in low and "perf:" not in low:
        return aq.strip()
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", default="2026-07-26")
    args = ap.parse_args()
    week = args.week
    cfg = WEEK_CFG[week]

    ledger = json.loads((HERE / "posted_ledger.json").read_text()).get(week, {})
    sheet_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid={cfg['gid']}"
    rows = gws_get(f"'{cfg['tab']}'!A2:AV260")

    def g(r, i): return clean(r[i]) if (i is not None and i < len(r)) else ""

    by_market: "OrderedDict[str,list]" = OrderedDict()
    summary_bucket, no_comment = [], []
    for r in rows:
        cid, name, cat, market = g(r, cfg["cid"]), g(r, cfg["name"]), g(r, cfg["cat"]), g(r, cfg["market"])
        if not (cid or name):
            continue
        action = g(r, cfg["action"])
        if not action:                      # only rows Perf has given a Final action
            continue
        if cfg["layout"] == "v2":
            why = perf_only(g(r, cfg["comment"]))
        else:
            why = g(r, cfg["comment"]) or g(r, cfg.get("comment2"))

        if market == "Middle East":
            slug = middle_east_slug(cid)
        else:
            slug = MARKET_MAP.get(market, "_summary")
        if slug == "_summary":
            summary_bucket.append((market, name, cat, action, why))
            continue
        if not why:
            no_comment.append((slug, name, cid, action))
        by_market.setdefault(slug, []).append(
            {"cid": cid, "name": name, "category": cat, "action": action, "why": why})

    cc_line = "cc: " + " ".join(f"<@{u}>" for u in CC_TAGS)
    drafts = OrderedDict()
    for slug, items in by_market.items():
        anchor = ledger.get(slug, {})
        groups = OrderedDict()
        for it in items:
            groups.setdefault((it["cid"], it["name"], it["action"], it["why"]), []).append(it["category"])
        lines = [f"📋 *Follow-up on Monday's Losing-Money flags — what Perf actioned (w/c {week})*",
                 f"_Closing the loop on the alert above. For each flagged CE: the action Perf took + their reasoning._",
                 f"_{len(groups)} CEs actioned._", ""]
        for (cid, name, action, why), cats in groups.items():
            cats = [c for c in cats if c]
            if len(cats) > 1:
                catstr = f" · _{len(cats)} campaigns:_ " + ", ".join(cats)
            elif cats:
                catstr = f" · {cats[0]}"
            else:
                catstr = ""
            lines.append(f"• *{name}* [{cid}]{catstr}")
            lines.append(f"     *Perf action:* {action}")
            if why:
                lines.append(f"     *Perf note:* {why}")
        lines.append("")
        lines.append(f"📊 More detail — per-campaign metrics + full comments: <{sheet_url}|Losing-Money tracker>")
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
                                "summary_no_channel": summary_bucket,
                                "actioned_without_comment": no_comment},
                               indent=2, ensure_ascii=False))

    print(f"week {week} · tab '{cfg['tab']}' · {len(drafts)} market drafts · "
          f"{sum(d['n_ces'] for d in drafts.values())} CEs actioned")
    print(f"drafts written -> {outp.name}\n")
    for slug, d in drafts.items():
        a = "✓ threads under Monday ping" if d["have_anchor"] else "⚠ NO anchor — would post fresh"
        print(f"  {d['market']:16s} {d['n_ces']:2d} CEs · ch={d['channel']} · {a}")
    if no_comment:
        print(f"\n  actioned but NO perf comment ({len(no_comment)}) — action-only lines:")
        for slug, name, cid, act in no_comment:
            print(f"    - [{MARKET_NAME.get(slug, slug)}] {name} [{cid}] · {act}")
    if summary_bucket:
        print(f"\n  No channel (not posted): {len(summary_bucket)}")
        for market, name, cat, act, why in summary_bucket:
            print(f"    - [{market}] {name} · {act}")


if __name__ == "__main__":
    main()
