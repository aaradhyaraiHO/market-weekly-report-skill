"""Stress-test the FINAL bucket set (B1 ROI/CM2 · B2 Fluctuations · B4 Scale-Up=4wk-agg≥155)
across a market snapshot. Emits a scorecard + anomaly flags. Run per market; loop to harden."""
import sys, pickle
SNAP = pickle.load(open(sys.argv[1], "rb"))
MKT = sys.argv[1].split("/")[-1].replace("_snap.pkl", "")
CES = SNAP["ces"]
def _rows(o): return (o.get("rows") if isinstance(o, dict) else o) or []
B1 = _rows(SNAP.get("bucket_b1")); FL = _rows(SNAP.get("bucket1_fluctuations")); B4 = _rows(SNAP.get("bucket_b4"))
TRO = {r["ce_id"]: r.get("troas_target_pct") for r in B1}

SCALE_AGG = 155.0; SEAS_UP = 140.0; SEAS_DN = 120.0; MIN_ACTIVE = 3

def active_wks(wk): return sum(1 for w in wk[-4:] if (w.get("revenue") or 0) > 0 or (w.get("spend") or 0) > 0)
def is_existing(ce):
    wk = ce.get("weekly") or []
    md = ce.get("metadata") or {}
    return active_wks(wk) >= MIN_ACTIVE   # data-driven (metadata flag unreliable)
def roi_agg4(wk):
    r = [w.get("roi_pct") for w in wk[-4:] if w.get("roi_pct") is not None]
    return (sum(r)/4) if len(r) == 4 else None
def roi_3of4(wk, t=155.0):
    r = [w.get("roi_pct") for w in wk[-4:]]
    return len(r) == 4 and sum(1 for x in r if x is not None and x >= t) >= 3
def roi2(wk):
    r = [w.get("roi_pct") for w in wk[-2:] if w.get("roi_pct") is not None]
    return (sum(r)/len(r)) if r else None
CEID = {c["ce_id"]: c for c in CES}

# ---- B1 ROI/CM2 (movement) ----
b1_moves = {}
for r in B1:
    b1_moves.setdefault(r.get("movement") or "?", 0)
    b1_moves[r.get("movement") or "?"] += 1
B1_LOSER_IDS = {r['ce_id'] for r in B1 if (r.get('movement') or '') in ('CLIFF','NEW','ESCALATION')}
b1_losers = len(B1_LOSER_IDS)
b1_exits = b1_moves.get("EXIT", 0)

# ---- B2 Fluctuations: direction + ROI gate + existing-only ----
b2 = {"+ve": 0, "-ve": 0, "gate_hold": 0, "new_excluded": 0}
b2_new_leak = []
for r in FL:
    ce = CEID.get(r["ce_id"]);
    if not ce: continue
    wk = ce.get("weekly") or []; d = r.get("direction"); ro = (wk[-1].get("roi_pct") if wk else None) or 0
    if not is_existing(ce):
        b2["new_excluded"] += 1; b2_new_leak.append(r["ce_name"][:20]); continue
    if d == "up" and ro > SEAS_UP: b2["+ve"] += 1
    elif d == "down" and ro < SEAS_DN: b2["-ve"] += 1
    else: b2["gate_hold"] += 1

# ---- B4 Scale-Up: 4wk-aggregate ROI >= 155, existing ----
scale = []
for ce in CES:
    wk = ce.get("weekly") or []
    if not is_existing(ce): continue
    agg = roi_agg4(wk)
    w0roi = wk[-1].get('roi_pct') if wk else None
    wm1roi = wk[-2].get('roi_pct') if len(wk) >= 2 else None
    cliffed = (wm1roi is not None and w0roi is not None and (wm1roi - w0roi) > 30)  # dropped >30pp this wk
    if roi_3of4(wk, SCALE_AGG) and not cliffed:  # ≥3 of 4 wks ≥155 (consistency) + not currently cliffing
        tro = TRO.get(ce["ce_id"]) or 145.0
        scale.append((ce["ce_name"][:22], round(agg), round(agg - tro)))

# ---- anomalies ----
anom = []
# data artifacts flagged anywhere (near-zero clicks/spend)
for r in FL:
    ce = CEID.get(r["ce_id"]); wk = (ce.get("weekly") if ce else []) or []
    if wk and (wk[-1].get("clicks") or 0) < 50 and (wk[-1].get("spend") or 0) < 50:
        anom.append(f"artifact-in-B2: {r['ce_name'][:20]} (clicks<50,spend<50)")
for nm, agg, pp in scale:
    if agg < SCALE_AGG: anom.append(f"scale-below-thresh: {nm}")

print(f"===== {MKT.upper()} — FINAL bucket stress test =====")
print(f"CEs total: {len(CES)} | existing: {sum(1 for c in CES if is_existing(c))}")
print(f"B1 DEFEND (losers only): {b1_losers}  [EXITs split to Recovered: {b1_exits}] | moves={b1_moves}")
print(f"B2 Fluct:    {len(FL)} rows | +ve→Comp: {b2['+ve']} · −ve→Def: {b2['-ve']} · gate-hold: {b2['gate_hold']} · new-excluded: {b2['new_excluded']}")
print(f"B4 Scale-Up: {len(scale)} CEs (≥3-of-4 wks ROI≥155)  {[(n,a) for n,a,p in scale[:8]]}")
if b2_new_leak: print(f"  new-excluded from seasonality: {b2_new_leak}")
print(f"ANOMALIES ({len(anom)}): {anom[:6] if anom else 'none'}")
