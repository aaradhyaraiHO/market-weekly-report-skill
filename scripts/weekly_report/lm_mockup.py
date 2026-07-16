# -*- coding: utf-8 -*-
"""Generate a standalone MOCKUP of the redesigned Losing Money table (real NA data).
Uses the report's Figtree + color tokens. No changes to the real report."""
import json, os

SNAP = os.path.expanduser("~/market-weekly-report-skill/.claude/worktrees/diagnostic/.cache/weekly_report/snapshot_north_america_2026-06-29.json")
OUT  = os.path.expanduser("~/market-weekly-report-skill/.claude/worktrees/diagnostic/thoughts/shared/weekly-report-v1/losing-money-mockup.html")
d = json.load(open(SNAP))
ces = {c["ce_id"]: c for c in d["ces"]}

def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs)/len(xs) if xs else None

def metrics(ce):
    wk = ce.get("weekly") or []
    w0 = wk[-1] if wk else {}
    prior = wk[-5:-1]                      # 4 weeks before current
    def g(k): return w0.get(k)
    def dpct(now, base):                   # % change vs prior-4wk avg
        b = mean([w.get(base_k) for w in prior]) if False else None
        return None
    spend_series=[w.get("spend") for w in wk]
    cm2_series=[( (w.get("cm1") or 0) - (w.get("spend") or 0) ) for w in wk]
    def vs_prior(key, pp=False):
        now = w0.get(key); base = mean([w.get(key) for w in prior])
        if now is None or base is None: return None
        return (now-base) if pp else (now/base-1)*100 if base else None
    sp4 = sum((w.get("spend") or 0) for w in wk[-4:])
    cm2_4w = sum(cm2_series[-4:])
    spend_avg4 = mean([w.get("spend") for w in wk[-4:]])
    spend_dvs4 = ((w0.get("spend")/spend_avg4 -1)*100) if (w0.get("spend") and spend_avg4) else None
    orders4 = sum((w.get("orders") or 0) for w in wk[-4:])
    return dict(
        roi=w0.get("roi_pct"), roi_dpp=(w0.get("roi_pct")-wk[-2].get("roi_pct")) if (len(wk)>1 and w0.get("roi_pct") is not None and wk[-2].get("roi_pct") is not None) else None,
        cm2_wk=round((w0.get("spend") or 0)*((w0.get("roi_pct") or 0)/100-1)) if w0.get("roi_pct") is not None else None,
        cm2_4w=round(cm2_4w), spend_wk=w0.get("spend"), spend_4w=round(sp4), spend_dvs4=spend_dvs4,
        roi_v4=vs_prior("roi_pct", pp=True), roi_prev=(wk[-2].get("roi_pct") if len(wk)>1 else None),
        spend_wow=((w0.get("spend")/wk[-2].get("spend")-1)*100) if (len(wk)>1 and w0.get("spend") and wk[-2].get("spend")) else None,
        rpc=w0.get("rpc"), rpc_v4=vs_prior("rpc"), cpc=w0.get("cpc"), cpc_v4=vs_prior("cpc"),
        clicks=w0.get("clicks"), clicks_v4=vs_prior("clicks"), tr=w0.get("tr_pct"), tr_v4=vs_prior("tr_pct", pp=True),
        cm2_series=cm2_series[-12:], cm2_weeks=[w.get("week") for w in wk][-12:], orders4=orders4,
        adconv4=sum((w.get("ad_conversions") or 0) for w in wk[-4:]),
    )

# Classify funded CEs (spend_4w>$1k):
#   FULL WASTE  = 0 paid conversions in 4w → spend, zero return = total loss (shows as ROI~0 or null)
#   TRACKING GAP= ROI null BUT has conversions → current-week CM1 feed gap (has bookings; NOT waste)
#   BLEEDER     = ROI<100 with material 4w bleed
bleeders=[]; full_waste=[]; tracking_gap=[]
for ce in d["ces"]:
    wk=ce.get("weekly") or []
    if len(wk)<4: continue
    sp4=sum((w.get("spend") or 0) for w in wk[-4:])
    if sp4<=1000: continue
    m=metrics(ce); roi=wk[-1].get("roi_pct")
    if m["adconv4"]==0:                       # spend, zero paid conversions = FULL WASTE
        full_waste.append((ce,m)); continue
    if roi is None:                           # has conversions but ROI didn't compute = feed gap
        tracking_gap.append((ce,m)); continue
    if roi<100 and (m["cm2_4w"] or 0) <= -200:   # material bleeder
        bleeders.append((ce,m))
full_waste.sort(key=lambda x:-(x[1]["spend_4w"] or 0))
bleeders.sort(key=lambda x: x[1]["cm2_4w"])   # worst 4wk bleed first

def status_of(ce):
    wk=ce.get("weekly") or []; series=[w.get("roi_pct") for w in wk]
    s=0
    for r in reversed(series):
        if r is not None and r<100: s+=1
        else: break
    dpp=(series[-1]-series[-2]) if (len(series)>1 and series[-1] is not None and series[-2] is not None) else 0
    if dpp<-30: return ("ESCALATING","red", f"{s}w bleeding")
    if s>=6: return ("CHRONIC","red", f"{s}w bleeding")
    if s==1: return ("NEW","blue","1w bleeding")
    return (f"{s}w","amber", f"{s}w bleeding")

GL={"peak":("☀","amber"),"pre":("↗","green"),"post":("↘","ghost"),"off":("❄","blue"),"unknown":("·","ghost")}
def money(v):
    if v is None: return "—"
    a=abs(v); s="−" if v<0 else ""
    return f"{s}${a/1000:.1f}K" if a>=1000 else f"{s}${a:.0f}"
def spark(series,weeks=None,w=104,h=26):
    weeks=weeks or []
    xs=[x for x in series if x is not None]
    if len(xs)<2: return ""
    lo,hi=min(xs),max(xs); rng=(hi-lo) or 1; n=len(series); pad=2
    def X(i): return pad+(w-2*pad)*i/(n-1)
    def Y(v): return h-pad-(h-2*pad)*(v-lo)/rng
    pts=[]; dots=""
    for i,v in enumerate(series):
        if v is None: continue
        x,y=X(i),Y(v); pts.append(f"{x:.1f},{y:.1f}")
        lbl=(str(weeks[i])[5:10] if i<len(weeks) and weeks[i] else f"wk{i+1}")
        # faint visible dot (affordance) + wide transparent hit-target (pointer-events:all) → hover tooltip
        dots+=(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="1.3" fill="{("var(--red)" if v<0 else "var(--green)")}" fill-opacity="0.45"/>'
               f'<circle cx="{x:.1f}" cy="{y:.1f}" r="8" fill="#000" fill-opacity="0" pointer-events="all"><title>{lbl}  CM2 {money(v)}</title></circle>')
    up = xs[-1]>=xs[0]; col="var(--green)" if up else "var(--red)"
    lx,ly=X(n-1),Y(series[-1]) if series[-1] is not None else (X(n-1),Y(xs[-1]))
    dot=f'<circle cx="{X(n-1):.1f}" cy="{Y([v for v in series if v is not None][-1]):.1f}" r="2" fill="{col}"/>'
    zero_y=h-pad-(h-2*pad)*(0-lo)/rng if lo<=0<=hi else None
    zl=f'<line x1="0" y1="{zero_y:.1f}" x2="{w}" y2="{zero_y:.1f}" stroke="var(--rule-dark)" stroke-width="1" stroke-dasharray="2 2"/>' if zero_y is not None else ""
    return f'<svg width="{w}" height="{h}" style="overflow:visible">{zl}<polyline fill="none" stroke="{col}" stroke-width="1.5" points="{" ".join(pts)}"/>{dot}{dots}</svg>'

# value-over-delta cell. gooddir: +1 up-good, -1 down-good(e.g. CPC/Spend)
def vd(val, delta, gooddir=1, pp=False, dp=0, prefix="", suffix=""):
    v = "—" if val is None else f"{prefix}{val:,.{dp}f}{suffix}"
    if delta is None: return f'<div class="v">{v}</div>'
    u = 'pp' if pp else '%'
    s = "+" if delta>0 else "−"
    if gooddir==0 or round(delta)==0:                    # neutral metric, or ~no change → gray, no favorability
        txt = f"0{u}" if round(delta)==0 else f"{s}{abs(delta):.0f}{u}"
        return f'<div class="v">{v}</div><div class="d mut">{txt}</div>'
    fav = (delta>0) if gooddir>0 else (delta<0)
    cls = "gp" if fav else "gn"
    return f'<div class="v">{v}</div><div class="d {cls}">{s}{abs(delta):.0f}{u}</div>'

# ROI headline cell: value + BOTH deltas (acute WoW · structural 4w), each labeled in-cell
def roi_cell(val, wow, v4):
    if val is None: return '<div class="v">—</div>'
    def seg(dv, lbl):
        if dv is None: return f'<span class="d mut">— {lbl}</span>'
        if round(dv)==0: return f'<span class="d mut">0pp {lbl}</span>'
        cls="gn" if dv<0 else "gp"; s="+" if dv>0 else "−"
        return f'<span class="d {cls}">{s}{abs(dv):.0f}pp {lbl}</span>'
    return f'<div class="v">{val:.0f}%</div><div style="line-height:1.35">{seg(wow,"WoW")}<br>{seg(v4,"4w")}</div>'

def roi_cell2(roi, prev):
    v = '—' if roi is None else f'{roi:.0f}%'
    if prev is None: return f'<div class="v">{v}</div>'
    return f'<div class="v">{v}</div><div class="d mut">was {prev:.0f}%</div>'

SPEND_RAMP=25   # spend jump >25% WoW on a bleeder → acute-ramp flag
def spend_cell(m):
    wk=m['spend_wk']; dvs4=m['spend_dvs4']; wow=m.get('spend_wow')
    val=money(wk) if wk is not None else "—"
    ramp=(wow is not None and wow>SPEND_RAMP)
    top=(f'<div class="v" style="color:var(--amber)" title="spend +{wow:.0f}% vs last week — ramping spend on a bleeder">↑ {val}</div>'
         if ramp else f'<div class="v">{val}</div>')
    if dvs4 is None: dh=''
    elif round(dvs4)==0: dh='<div class="d mut">0%</div>'
    else:
        cls='gn' if dvs4>0 else 'gp'; s='+' if dvs4>0 else '−'
        dh=f'<div class="d {cls}">{s}{abs(dvs4):.0f}%</div>'
    return top+dh

UNIT='<span style="font-weight:500;font-size:10px;color:var(--ink-faint)">/wk</span>'
def moneyd(val, four):
    return f'<div class="v neg">{money(val)}{UNIT}</div><div class="d mut">{money(four)} 4w</div>'

rows=""
# FULL WASTE at top (funded, 0 paid conversions in 4w = total loss)
for ce,m in full_waste:
    sea=ce.get("season") or {}; gi=GL.get(sea.get("phase"),("·","ghost"))
    seachip=f'<span class="chip {gi[1]}" title="{sea.get("note","")}">{gi[0]} {sea.get("note","")}</span>' if sea.get("note") else ""
    rows+=f'''<tr class="waste"><td><b>{ce["ce_name"]}</b> <span class="idbr">[{ce["ce_id"]}]</span> {seachip}<div class="sub">0 paid conversions on {money(m['spend_4w'])} (4w) — total loss</div></td>
    <td><span class="chip red">FULL WASTE</span></td><td class="num">{roi_cell(m['roi'] if m['roi'] is not None else 0, m['roi_dpp'], m['roi_v4'])}</td><td class="num">{moneyd(m['cm2_wk'] if m['cm2_wk'] is not None else -(m['spend_wk'] or 0), m['cm2_4w'])}</td>
    <td class="num">{spend_cell(m)}</td>
    <td class="num">{vd(m['rpc'],m['rpc_v4'],dp=2,prefix='$')}</td><td class="num">{vd(m['cpc'],m['cpc_v4'],gooddir=-1,dp=2,prefix='$')}</td>
    <td class="num">{vd(m['clicks'],m['clicks_v4'],gooddir=0)}</td><td class="num">{vd(m['tr'],m['tr_v4'],pp=True,dp=0,suffix='%')}</td>
    <td>{spark(m['cm2_series'], m['cm2_weeks'])}</td></tr>'''
if not full_waste:
    rows+='<tr><td colspan="10" style="padding:10px 12px;color:var(--ink-faint);font-size:12px">No full-waste CEs this week (spending with 0 conversions). ✅</td></tr>'
# bleeders
for ce,m in bleeders[:8]:
    st,stc,stsub=status_of(ce)
    sea=ce.get("season") or {}; gi=GL.get(sea.get("phase"),("·","ghost"))
    seachip=f'<span class="chip {gi[1]}" title="{sea.get("note","")}">{gi[0]} {sea.get("note","")}</span>' if sea.get("note") else ""
    rows+=f'''<tr><td><b>{ce["ce_name"]}</b> <span class="idbr">[{ce["ce_id"]}]</span> {seachip}</td>
    <td><span class="chip {stc}">{st}</span><div class="sub">{stsub}</div></td>
    <td class="num">{roi_cell(m['roi'], m['roi_dpp'], m['roi_v4'])}</td>
    <td class="num">{moneyd(m['cm2_wk'],m['cm2_4w'])}</td>
    <td class="num">{spend_cell(m)}</td>
    <td class="num">{vd(m['rpc'],m['rpc_v4'],dp=2,prefix='$')}</td>
    <td class="num">{vd(m['cpc'],m['cpc_v4'],gooddir=-1,dp=2,prefix='$')}</td>
    <td class="num">{vd(m['clicks'],m['clicks_v4'],gooddir=0)}</td>
    <td class="num">{vd(m['tr'],m['tr_v4'],pp=True,dp=0,suffix='%')}</td>
    <td>{spark(m['cm2_series'], m['cm2_weeks'])}</td></tr>'''


# real sub-$1k burn list (bleeding below the individual $1k/4w gate)
burn=[]
for ce in d["ces"]:
    wk=ce.get("weekly") or []
    if len(wk)<4: continue
    if sum(1 for w in wk[-4:] if (w.get("revenue") or 0)>0 or (w.get("spend") or 0)>0) < 3: continue
    sp4=sum((w.get("spend") or 0) for w in wk[-4:]); roi=wk[-1].get("roi_pct"); spw=wk[-1].get("spend") or 0
    if sp4<=1000 and roi is not None and roi<100 and spw>0:
        burn.append((ce["ce_name"], spw*(roi/100-1)))
burn_total=sum(b for _,b in burn)
burn_names=", ".join(n for n,_ in sorted(burn, key=lambda x:x[1]))   # worst-first, ALL names
tg_html=""
if tracking_gap:
    items=" · ".join(f"{c['ce_name']} ({m['orders4']:.0f} orders, ${m['spend_4w']:,} 4w)" for c,m in sorted(tracking_gap,key=lambda x:-(x[1]['spend_4w'] or 0)))
    tg_html=f'<br><span class="k" style="color:var(--amber)">⚠ {len(tracking_gap)} null-ROI — CM1 feed gap (has bookings, verify tracking):</span> {items} <span style="color:var(--ink-faint)">— current-week CM1 didn&rsquo;t populate, so ROI reads null; these ARE converting (see orders). NOT waste.</span>'
HTML=f'''<!doctype html><html><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700;800;900&display=swap');
:root{{--purps:#8000FF;--paper:#fff;--card:#fff;--ink:#1A1526;--ink-soft:#5C5470;--ink-faint:#9B93AC;
--rule:#ECE6F8;--rule-dark:#DAD1EF;--red:#E5384F;--red-bg:#FDE7EA;--amber:#B5810B;--amber-bg:#FAF0D5;--green:#12A150;--green-bg:#E2F5EA;--blue:#2563eb;--blue-bg:#e7eefd;}}
body{{background:var(--paper);color:var(--ink);font-family:'Figtree',sans-serif;font-size:14px;margin:0;padding:28px 32px}}
h2{{font-weight:800;font-size:22px;letter-spacing:-.02em;margin:0 0 2px}}
.howto{{font-size:12.5px;color:var(--ink-soft);background:#FAF8FE;border:1px solid var(--rule);border-radius:10px;padding:9px 14px;margin:10px 0 6px;line-height:1.6}}
.howto b{{color:var(--ink)}}
.legend{{font-size:11.5px;color:var(--ink-faint);margin:2px 0 14px}}
.legend .chip{{margin-right:3px}}
.wrap{{border:1px solid var(--rule);border-radius:16px;overflow:hidden;box-shadow:0 1px 2px rgba(28,23,38,.05)}}
table{{width:100%;border-collapse:collapse;font-size:12.5px}}
thead th{{font-size:10px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--ink-soft);text-align:left;padding:12px 12px;background:#FBFAFE;border-bottom:1px solid var(--rule)}}
th.num,td.num{{text-align:right}}
tbody td{{padding:12px 12px;border-bottom:1px solid var(--rule);vertical-align:top;font-variant-numeric:tabular-nums}}
tbody tr:last-child td{{border-bottom:none}}
tr.waste{{background:#FDF3F4}}
.v{{font-weight:600}} .v.neg{{color:var(--red)}}
.d{{font-size:10.5px;font-weight:600;margin-top:1px}} .d.gp{{color:var(--green)}} .d.gn{{color:var(--red)}} .d.mut{{color:var(--ink-faint)}}
.idbr{{color:var(--ink-faint);font-weight:600;font-size:11.5px}}
.hb{{font-weight:600;font-size:9px;color:var(--ink-faint);text-transform:none;letter-spacing:0}}
.sub{{color:var(--ink-faint);font-size:11px;margin-top:3px}}
.chip{{display:inline-block;font-size:10px;font-weight:700;padding:2px 8px;border-radius:99px;white-space:nowrap}}
.chip.red{{background:var(--red-bg);color:var(--red)}} .chip.amber{{background:var(--amber-bg);color:var(--amber)}}
.chip.green{{background:var(--green-bg);color:var(--green)}} .chip.blue{{background:var(--blue-bg);color:var(--blue)}}
.chip.ghost{{background:#F2EEFA;color:var(--ink-soft)}}
.fn{{font-size:12px;color:var(--ink-soft);margin-top:12px;line-height:1.7}}
.fn .k{{font-weight:700}} .dashed{{border-bottom:1px dashed var(--ink-faint);cursor:help}}
</style></head><body>
<h2>🛡️ Losing Money <span style="font-weight:600;font-size:13px;color:var(--ink-faint)">— MOCKUP (North America)</span></h2>
<div class="howto"><b>How to read (BGM):</b> ranked worst-first by 4-week CM2 bled. <b>Full-waste</b> rows (spend, 0 conversions) are pure loss — kill first. Then: a bleeder that&rsquo;s <b>Escalating</b> or <b>Chronic</b> with rising spend and RPC decaying is the scale-down priority. Rule of thumb: <b>3–4 weeks bleeding with no recovery lever → scale down within the week.</b></div>
<div class="legend">
<span class="chip red">FULL WASTE</span>spend, 0 conversions &nbsp;·&nbsp;
<span class="chip blue">NEW</span>1st week &lt;100% &nbsp;·&nbsp;
<span class="chip amber">2–5w</span>weeks bleeding &nbsp;·&nbsp;
<span class="chip red">CHRONIC</span>≥6 weeks &nbsp;·&nbsp;
<span class="chip red">ESCALATING</span>ROI dropped &gt;30pp WoW (severity — can co-occur)
</div>
<div class="wrap"><table><thead><tr>
<th>Combined Entity</th><th>Status</th><th class="num">Paid ROI <span class="hb">WoW · 4w</span></th><th class="num">CM2 bleed <span class="hb">/wk · 4w</span></th>
<th class="num">Spend <span class="hb">Δ4w</span></th><th class="num">RPC <span class="hb">Δ4w</span></th><th class="num">CPC <span class="hb">Δ4w</span></th><th class="num">Clicks <span class="hb">Δ4w</span></th><th class="num">TR% <span class="hb">Δ4w</span></th><th>CM2 trend 12w</th>
</tr></thead><tbody>{rows}</tbody></table></div>
<div class="fn">
<span class="k" style="color:var(--green)">✅ 1 recovered:</span> Cruises - San Francisco (171%, was bleeding 2w){tg_html}<br>
<span class="k dashed" title="{burn_names}">+ {len(burn)} sub-$1k CEs bleeding {money(burn_total)}/wk below the individual gate</span> <span style="color:var(--ink-faint)">(hover for the full list)</span>
</div>
<div class="fn" style="color:var(--ink-faint)">value on top · <span style="color:var(--green)">green</span>/<span style="color:var(--red)">red</span> Δ below = favorable/unfavorable move · <b>ROI shows both</b> WoW (vs last week, acute) and 4w (vs 4-week avg, structural); every other metric Δ is <b>vs the prior-4-week average</b> (Clicks neutral — volume isn&rsquo;t good/bad on a bleeder); acute week-over-week cliffs are flagged by the <b>ESCALATING</b> status chip · CM2 = weekly rate <b>/wk</b> + 4-week total · <b style="color:var(--amber)">↑</b> on Spend = ramped &gt;25% WoW (over-investing on a bleeder) · spark = weekly CM2 (CM1−spend) over 12w, dashed line = 0, hover a point for its value</div>
</body></html>'''
open(OUT,"w").write(HTML)
print("wrote", OUT)
print(f"bleeders: {len(bleeders)} · full-waste: {len(full_waste)} · tracking-gap: {len(tracking_gap)} · burn: {len(burn)}")
