/* Native Eevee Weekly Review workspace — full parity.
 * Exposes window.initReviewView(ctx), a drop-in for vanilla review-view.js. Branded atoms use real
 * @headout/eevee components (styled by shipped pixie/styles.css); layout uses Eevee token CSS vars. */
import { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { Avatar, Button, Text } from "@headout/eevee";
import { getApi } from "./api";

type Ctx = { root: HTMLElement; getHeadline: () => any; getBaseHeadline?: () => any; openCeDrawer?: (ce: any) => void };
type Q = { ce_id: string; ce_name: string; reason: string; source: string };

const T: Record<string, string> = { not_scheduled: "Not scheduled", live: "Review live", async: "Review async", follow_up: "Follow-up only", skip: "Skip this week" };
const TORDER = ["not_scheduled", "live", "async", "follow_up", "skip"];
const WORK_STATUS: [string, string][] = [["needs_action", "Needs action"], ["already_actioned", "Already actioned"], ["self_recovering", "Self-recovering"], ["monitoring", "Monitoring"], ["no_action_needed", "No action needed"], ["complete", "Complete"]];
const CHECK_STATUS: [string, string][] = [["scheduled", "Scheduled"], ["monitoring", "Monitoring"], ["self_recovering", "Self-recovering"], ["complete", "Complete"]];
const CLOSED = ["complete", "cancelled", "no_action_needed"];
const V = (n: string, fb: string) => `var(--colors-core-${n}, ${fb})`;
const purps = V("primary-purps", "#8000ff"), purps10 = V("purps-10", "#f8f6ff"), purps20 = V("purps-20", "#f3e9ff"), purps700 = V("purps-700", "#6600cc"), purps200 = V("purps-200", "#c68cff");
const g200 = V("grey-200", "#f0f0f0"), g300 = V("grey-300", "#e2e2e2"), g400 = V("grey-400", "#c4c4c4"), g500 = V("grey-500", "#9f9f9f"), g700 = V("grey-700", "#666"), g800 = V("grey-800", "#444"), g900 = V("grey-900", "#222");
const green = V("okaygreen-700", "#078842"), green200 = V("okaygreen-200", "#deffee"), red = V("warningred-600", "#d60404");
const HT = "var(--fonts-ht, halyard-text, sans-serif)";
function author() { try { return localStorage.getItem("wr_author") || ""; } catch { return ""; } }
function toast(msg: string) { const el = document.getElementById("rv-native-toast"); if (!el) return; el.textContent = msg; el.style.opacity = "1"; clearTimeout((window as any).__rvt); (window as any).__rvt = setTimeout(() => (el.style.opacity = "0"), 2600); }

function useReview(ctx: Ctx) {
  const api = useMemo(getApi, []);
  const [, force] = useState(0); const rerender = () => force((n) => n + 1);
  const S = useMemo<any>(() => ({ headline: null, market: "", market_slug: "", week_start: "", channel: null, queue: [] as Q[], byId: {} as any, selected: null as string | null, setRows: {} as any, setRowsList: [] as any[], receipts: {} as any, weekly: {} as any, work: {} as any, sugg: {} as any, slackRequests: {} as any, editing: false, confirmDel: false, compose: "", adding: false, pickerQuery: "", addingGranola: false, processing: false, processSummary: "", workTab: "review", memoryOpen: false, memory: null }), []);
  const flagged = (h: any): Q[] => { const b = h?.diagnostic_buckets || {}, lm = b.losing_money || {}, fx = b.fluctuations || {}, o: Q[] = []; (lm.existing || []).forEach((r: any) => o.push({ ce_id: String(r.ce_id), ce_name: r.ce_name, reason: "Losing money", source: "flag" })); (lm.new || []).forEach((r: any) => o.push({ ce_id: String(r.ce_id), ce_name: r.ce_name, reason: "Losing money · new", source: "flag" })); (fx.down || []).forEach((r: any) => o.push({ ce_id: String(r.ce_id), ce_name: r.ce_name, reason: "RPC / CM1 drop", source: "flag" })); (fx.up || []).forEach((r: any) => o.push({ ce_id: String(r.ce_id), ce_name: r.ce_name, reason: "RPC / CM1 spike", source: "flag" })); return o; };
  const build = () => { const seen: any = {}, queue: Q[] = []; flagged(S.headline).forEach((r) => { if (!seen[r.ce_id]) { seen[r.ce_id] = 1; queue.push(r); } }); (S.setRowsList || []).forEach((r: any) => { const id = String(r.ce_id); if (!seen[id]) { seen[id] = 1; queue.push({ ce_id: id, ce_name: r.ce_name, reason: r.reason || "Added to review", source: "manual" }); } }); S.queue = queue; S.byId = {}; queue.forEach((q) => (S.byId[q.ce_id] = q)); };
  const treat = (id: string) => (S.setRows[id]?.treatment) || "not_scheduled";
  const reviewed = (id: string) => !!S.receipts[id];
  const workFor = (id: string) => (S.work[id] || []);
  const openWork = (id: string) => workFor(id).filter((w: any) => CLOSED.indexOf(w.status) < 0);
  const loadQueue = () => {
    const h = ctx.getHeadline(); if (!h) return;
    S.headline = h; S.market = h.market || h.market_slug; S.market_slug = h.market_slug || h.market; S.week_start = h.week_start || "";
    const rawChannel = (h.notes_channels || (ctx.getBaseHeadline?.() || {}).notes_channels || {})[S.market_slug];
    S.channel = typeof rawChannel === "string" ? rawChannel : rawChannel?.id || rawChannel?.channel_id || null;
    Promise.all([
      api.reviewSet({ market_slug: S.market_slug, week: S.week_start }).catch(() => ({ review_set: [] })),
      api.receipts({ market_slug: S.market_slug, week: S.week_start }).catch(() => ({ receipts: [] })),
      api.work({ market_slug: S.market_slug, week: S.week_start }).catch(() => ({ work_items: [] })),
    ]).then(([rs, rc, wk]: any) => {
      S.setRowsList = rs.review_set || []; S.setRows = {}; S.setRowsList.forEach((r: any) => (S.setRows[String(r.ce_id)] = r));
      S.receipts = {}; (rc.receipts || []).forEach((r: any) => (S.receipts[String(r.ce_id)] = r));
      S.work = {}; (wk.work_items || []).forEach((w: any) => { const k = String(w.ce_id); (S.work[k] = S.work[k] || []).push(w); });
      build(); if (!S.selected || !S.byId[S.selected]) S.selected = (S.queue.find((q) => !reviewed(q.ce_id)) || S.queue[0] || {}).ce_id || null;
      rerender(); if (S.selected) loadCe(S.selected);
    });
  };
  const loadCe = (id: string) => Promise.all([
    // The CE Memory endpoint is the canonical CE-scoped read: it returns the
    // current weekly note alongside history, work and source provenance. This
    // avoids a second, subtly different commentary-list shape in the live UI.
    api.memory({ market_slug: S.market_slug, ce_id: id }).catch((e: any) => { toast(e?.message || "Could not load CE history"); return { weekly_commentary: [] }; }),
    // The current-week list carries operational state (Slack post timestamp,
    // sync status and AI summary) used by the active Review surface.  Memory
    // remains the durable cross-week/history view.
    // `review_weekly_list` filters on `week` (the storage field remains
    // `week_start`). Send the API filter name so current Slack sync state is
    // not lost after a page refresh.
    api.weeklyCommentary({ market_slug: S.market_slug, ce_id: id, week: S.week_start }).catch(() => ({ weekly: [] })),
    api.suggestions({ market_slug: S.market_slug, ce_id: id, week: S.week_start } as any).catch(() => ({ suggestions: [] })),
  ]).then(([memory, current, s]: any) => { const rows = current.weekly || []; const history = memory.weekly_commentary || memory.weekly || []; S.weekly[id] = rows.find((r: any) => String(r.week_start) === String(S.week_start)) || history.find((r: any) => String(r.week_start) === String(S.week_start)) || null; S.sugg[id] = s.suggestions || []; rerender(); });
  const reloadWork = () => api.work({ market_slug: S.market_slug, week: S.week_start }).then((res: any) => { S.work = {}; (res.work_items || []).forEach((w: any) => { const k = String(w.ce_id); (S.work[k] = S.work[k] || []).push(w); }); rerender(); });
  useEffect(() => { loadQueue(); }, []);
  return {
    S, api, rerender, treat, reviewed, workFor, openWork, loadQueue, loadCe, build, reloadWork,
    select: (id: string) => { S.selected = id; S.editing = false; S.confirmDel = false; S.compose = ""; S.addingGranola = false; rerender(); if (!S.weekly[id]) loadCe(id); },
    addCe: (id: string) => { const ce = (S.headline.all_ces || []).find((c: any) => String(c.ce_id) === id) || { ce_id: id }; api.saveReviewSetItem({ market_slug: S.market_slug, week_start: S.week_start, ce_id: id, ce_name: ce.ce_name || "", treatment: "not_scheduled", reason: "Added to review", source: "manual" }).then(() => { S.adding = false; S.pickerQuery = ""; loadQueue(); toast("CE added"); }); },
    removeCe: (id: string) => { const ce = S.byId[id] || {}; api.saveReviewSetItem({ market_slug: S.market_slug, week_start: S.week_start, ce_id: id, ce_name: ce.ce_name || "", included: "false", source: "manual" }).then(() => { if (S.selected === id) S.selected = null; loadQueue(); toast("Removed"); }); },
    decide: (sid: string, decision: string, fields?: any) => api.decideSuggestion({ suggestion_id: sid, decision, decided_by: author() || "BGM", ...(fields || {}) }).then(() => { toast(decision === "approved" ? "Added" : "Ignored"); loadCe(S.selected); reloadWork(); }),
    attachGranola: (url: string) => { if (!/^https:\/\/([a-z0-9-]+\.)*granola\.ai\/t\//i.test(url)) { toast("Paste a valid Granola meeting link"); return; }
      const ces = (S.headline.all_ces || []).map((ce: any) => ({ ce_id: String(ce.ce_id), ce_name: ce.ce_name || "" })).filter((ce: any) => ce.ce_id && ce.ce_name);
      api.ingestGranolaLink({ market_slug: S.market_slug, week_start: S.week_start, source_url: url, ces }).then((result: any) => { S.addingGranola = false; toast(result.suggestions ? `${result.suggestions} Granola suggestion${result.suggestions === 1 ? "" : "s"} ready to review` : "Meeting queued for reconciliation"); loadCe(S.selected); }).catch((e: any) => toast(e?.message || "Could not extract meeting")); },
    saveWork: (item: any, msg: string) => api.saveWork(item).then(() => { toast(msg); reloadWork(); }).catch((e: any) => toast(e?.message || "Could not save action")),
    extract: (text: string) => { const ces = (S.headline.all_ces || []).map((c: any) => ({ ce_id: String(c.ce_id), ce_name: c.ce_name || "" })); return api.extractMeeting({ market_slug: S.market_slug, week: S.week_start, text, submitted_by: author() || "BGM", ces }); },
    openMemory: () => { const q = S.byId[S.selected]; S.memoryOpen = true; S.memory = null; rerender(); api.memory({ market_slug: S.market_slug, ce_id: q.ce_id }).then((res: any) => { S.memory = res; rerender(); }).catch(() => { S.memory = { error: 1 }; rerender(); }); },
  };
}

type R = ReturnType<typeof useReview>;
const card: React.CSSProperties = { border: `1px solid ${g300}`, borderRadius: 16, background: "#fff", boxShadow: "0 1px 6px 1px rgba(17,17,17,.1)", marginBottom: 20, overflow: "hidden" };
const cardHead: React.CSSProperties = { padding: "18px 20px", display: "flex", gap: 12, alignItems: "flex-start", borderBottom: `1px solid ${g200}` };
const step: React.CSSProperties = { width: 26, height: 26, flex: "none", display: "grid", placeItems: "center", borderRadius: "50%", background: g900, color: "#fff", fontSize: 12, fontWeight: 700 };
const sel: React.CSSProperties = { minHeight: 40, padding: "9px 14px", border: `1px solid ${g300}`, borderRadius: 10, background: "#fff", font: "inherit" };
const inp: React.CSSProperties = { minHeight: 40, padding: "9px 12px", border: `1px solid ${g400}`, borderRadius: 10, background: "#fff", font: "inherit" };
const link = (c: string): React.CSSProperties => ({ border: 0, background: "none", color: c, fontWeight: 600, fontSize: 13, cursor: "pointer", padding: 0 });
const chip: React.CSSProperties = { padding: "3px 8px", borderRadius: 8, background: g200, color: g700, fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: ".3px" };

function Toast() { return <div id="rv-native-toast" style={{ position: "fixed", right: 24, bottom: 84, zIndex: 80, padding: "12px 16px", borderRadius: 12, background: g900, color: "#fff", fontSize: 14, opacity: 0, transition: "opacity .2s", pointerEvents: "none" }} />; }

function Queue({ r }: { r: R }) {
  const { S } = r; const open = S.queue.filter((x: Q) => !r.reviewed(x.ce_id)).length; const total = S.queue.length;
  const allOpenWork: any[] = []; Object.keys(S.work).forEach((id) => r.openWork(id).forEach((w: any) => allOpenWork.push(w)));
  const matches = S.pickerQuery ? (S.headline.all_ces || []).filter((c: any) => !S.byId[String(c.ce_id)] && (`${c.ce_name} ${c.ce_id} ${c.city || ""}`).toLowerCase().includes(S.pickerQuery.toLowerCase())).slice(0, 20) : [];
  return (
    <aside style={{ padding: "24px 20px", borderRight: `1px solid ${g300}`, background: "#fff" }}>
      <div style={{ color: purps700, fontSize: 10, fontWeight: 600, letterSpacing: ".8px", textTransform: "uppercase" }}>Weekly review · w/c {S.week_start}</div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
        <Text as="h2" textStyle="heading.large">{open ? `${open} CE${open === 1 ? "" : "s"} to review` : "All caught up"}</Text>
        <button onClick={() => { S.adding = !S.adding; S.pickerQuery = ""; r.rerender(); }} style={{ display: "inline-flex", gap: 5, alignItems: "center", padding: "7px 12px", border: `1px solid ${purps200}`, borderRadius: 999, background: "#fff", color: purps700, fontSize: 13, fontWeight: 600, cursor: "pointer" }}>＋ Add CE</button>
      </div>
      <div style={{ color: g700, fontSize: 13 }}>{total - open} of {total} reviewed</div>
      {S.adding && <div style={{ margin: "12px 0", padding: 12, border: `1px solid ${purps200}`, borderRadius: 12, background: purps10 }}>
        <input autoFocus value={S.pickerQuery} onChange={(e) => { S.pickerQuery = e.target.value; r.rerender(); }} placeholder="Add a CE by name, id or city…" style={{ ...inp, width: "100%" }} />
        <div style={{ marginTop: 8, maxHeight: 240, overflow: "auto" }}>
          {!S.pickerQuery ? <div style={{ padding: 10, color: g700, fontSize: 12 }}>Type a CE name, id or city…</div> : matches.length ? matches.map((c: any) => <button key={c.ce_id} onClick={() => r.addCe(String(c.ce_id))} style={{ display: "block", width: "100%", textAlign: "left", padding: "9px 10px", border: 0, borderRadius: 8, background: "none", cursor: "pointer", fontSize: 13 }}><strong>{c.ce_name}</strong><small style={{ display: "block", color: g700, fontSize: 11 }}>CE {c.ce_id}{c.city ? ` · ${c.city}` : ""}</small></button>) : <div style={{ padding: 10, color: g700, fontSize: 12 }}>No unadded CE matches “{S.pickerQuery}”.</div>}
        </div>
      </div>}
      <button onClick={() => { S.processing = !S.processing; S.processSummary = ""; r.rerender(); }} style={{ width: "100%", marginTop: 12, minHeight: 40, display: "flex", alignItems: "center", justifyContent: "center", gap: 6, border: `1px solid ${purps200}`, borderRadius: 10, background: purps10, color: purps700, fontSize: 13, fontWeight: 600, cursor: "pointer" }}>✦ Process meeting notes</button>
      {S.processing && <ProcessPanel r={r} />}
      <div style={{ margin: "18px 0 12px", padding: 3, display: "grid", gridTemplateColumns: "1fr 1fr", borderRadius: 12, background: g200 }}>
        {["review", "work"].map((tab) => <button key={tab} onClick={() => { S.workTab = tab; r.rerender(); }} style={{ minHeight: 38, border: 0, borderRadius: 10, cursor: "pointer", background: S.workTab === tab ? "#fff" : "transparent", color: S.workTab === tab ? purps700 : g700, fontWeight: S.workTab === tab ? 600 : 400, fontSize: 13 }}>{tab === "review" ? "Review queue" : `Open work${allOpenWork.length ? ` (${allOpenWork.length})` : ""}`}</button>)}
      </div>
      {S.workTab === "review" ? S.queue.map((x: Q) => <QueueRow key={x.ce_id} r={r} x={x} />) : (allOpenWork.length ? allOpenWork.map((w: any) => <button key={w.work_id} onClick={() => r.select(String(w.ce_id))} style={{ width: "100%", marginBottom: 10, padding: "14px 16px", display: "flex", gap: 10, textAlign: "left", cursor: "pointer", border: `1px solid ${g300}`, borderRadius: 14, background: "#fff" }}><span style={{ width: 8, height: 8, marginTop: 6, borderRadius: "50%", background: "#9f6b00" }} /><span><strong style={{ display: "block", fontSize: 15, fontWeight: 600 }}>{w.text}</strong><small style={{ color: g700, fontSize: 12 }}>{w.ce_name} · {(w.status || "").replace(/_/g, " ")}</small></span></button>) : <div style={{ padding: 16, border: `1px dashed ${g400}`, borderRadius: 14, background: "#fafafa", textAlign: "center", color: g700, fontSize: 12 }}>No open work yet.</div>)}
    </aside>
  );
}
function QueueRow({ r, x }: { r: R; x: Q }) {
  const active = x.ce_id === r.S.selected, rev = r.reviewed(x.ce_id), t = r.treat(x.ce_id), ow = r.openWork(x.ce_id).length;
  return (
    <div style={{ position: "relative" }}>
      {x.source === "manual" && <button onClick={(e) => { e.stopPropagation(); r.removeCe(x.ce_id); }} title="Remove" style={{ position: "absolute", top: 10, right: 10, width: 22, height: 22, border: 0, borderRadius: "50%", background: "transparent", color: g500, cursor: "pointer" }}>×</button>}
      <button onClick={() => r.select(x.ce_id)} style={{ width: "100%", marginBottom: 10, padding: "14px 16px", display: "flex", gap: 10, alignItems: "flex-start", textAlign: "left", cursor: "pointer", border: `1px solid ${active ? purps200 : g300}`, borderRadius: 14, background: active ? purps20 : "#fff", opacity: rev ? 0.7 : 1 }}>
        <span style={{ width: 8, height: 8, marginTop: 6, flex: "none", borderRadius: "50%", background: rev ? green : "#9f6b00" }} />
        <span style={{ minWidth: 0, flex: 1 }}>
          <strong style={{ display: "block", fontSize: 15, fontWeight: 600 }}>{x.ce_name}</strong>
          <small style={{ display: "block", marginTop: 3, color: g700, fontSize: 12 }}>{x.reason} · CE {x.ce_id}</small>
          <span style={{ marginTop: 8, display: "inline-flex", gap: 6, flexWrap: "wrap" }}>
            <span style={{ ...chip, background: rev ? green200 : g200, color: rev ? green : g700 }}>{rev ? "Reviewed" : T[t]}</span>
            {ow ? <span style={chip}>{ow} open</span> : null}{x.source === "manual" ? <span style={chip}>manual</span> : null}
          </span>
        </span>
      </button>
    </div>
  );
}
function ProcessPanel({ r }: { r: R }) {
  const [text, setText] = useState(""); const [busy, setBusy] = useState(false);
  const run = () => { if (!text.trim()) { toast("Paste the notes first"); return; } setBusy(true); r.extract(text.trim()).then((res: any) => { const ces = res.ces || []; let total = 0; ces.forEach((c: any) => { const id = String(c.ce_id); const arr = c.suggestions || []; total += arr.length; if (arr.length) r.S.sugg[id] = (r.S.sugg[id] || []).concat(arr); if (!r.S.byId[id]) r.S.setRowsList.push({ ce_id: id, ce_name: c.ce_name, reason: "From meeting notes", source: "manual" }); }); r.build(); r.S.processSummary = `Extracted ${total} suggestion${total === 1 ? "" : "s"} across ${ces.length} CE${ces.length === 1 ? "" : "s"}. Open each to approve.`; setBusy(false); r.rerender(); toast(`Distributed to ${ces.length} CEs`); }).catch(() => { setBusy(false); toast("Extraction failed"); }); };
  return <div style={{ marginTop: 10, padding: 12, border: `1px solid ${purps200}`, borderRadius: 12, background: purps10 }}>
    <div style={{ color: g700, fontSize: 12, marginBottom: 8 }}>Paste a meeting’s notes/transcript. Claude extracts commentary + action items per CE — you approve each.</div>
    <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste the Granola meeting notes / transcript…" style={{ width: "100%", minHeight: 120, padding: "10px 12px", border: `1px solid ${g400}`, borderRadius: 10, fontFamily: HT, fontSize: 13 }} />
    {r.S.processSummary && <div style={{ marginTop: 8, padding: "8px 10px", borderRadius: 8, background: "#fff", color: green, fontSize: 12, fontWeight: 600 }}>{r.S.processSummary}</div>}
    <div style={{ marginTop: 10, display: "flex", gap: 8, justifyContent: "flex-end" }}>
      <Button size="small" variant="secondary" btnType="black" primaryText="Close" onClick={() => { r.S.processing = false; r.rerender(); }} />
      <Button size="small" variant="primary" btnType="primary" primaryText={busy ? "Extracting…" : "Extract & distribute"} disabled={busy} onClick={run} />
    </div>
  </div>;
}

function Workspace({ r }: { r: R }) {
  const { S } = r;
  if (!S.headline) return <div style={{ padding: 40, color: g700, fontFamily: HT }}>Loading review…</div>;
  const q = S.byId[S.selected];
  return (
    <div style={{ display: "grid", gridTemplateColumns: "312px minmax(0,1fr)", minHeight: "100vh", fontFamily: HT, color: g900, fontWeight: 300 }}>
      <Queue r={r} />
      <main style={{ minWidth: 0, display: "flex", flexDirection: "column" }}>{q ? <CEView r={r} q={q} /> : <div style={{ padding: 40, color: g700 }}>Nothing to review.</div>}</main>
      <Toast />
      {S.memoryOpen && <MemoryDrawer r={r} />}
    </div>
  );
}

function CEView({ r, q }: { r: R; q: Q }) {
  const { S, api } = r;
  const t = r.treat(q.ce_id), rev = r.reviewed(q.ce_id), weekly = S.weekly[q.ce_id];
  const [note, setNote] = useState(weekly?.bgm_note || "");
  useEffect(() => { setNote(weekly && !weekly.note_deleted_at ? weekly.bgm_note || "" : ""); }, [q.ce_id, weekly?.bgm_updated_at, weekly?.note_deleted_at]);
  const hasNote = !!(weekly && weekly.bgm_note && !weekly.note_deleted_at);
  const summary = (() => { try { return weekly?.summary_json ? JSON.parse(weekly.summary_json) : null; } catch { return null; } })();
  const sugg = (S.sugg[q.ce_id] || []);
  const commentPending = sugg.filter((s: any) => (s.kind === "comment" || !s.kind) && !s.decided_at && (s.status || "pending") === "pending");
  const commentAccepted = sugg.filter((s: any) => (s.kind === "comment" || !s.kind) && (s.status === "approved" || s.accepted_body));
  const workPending = sugg.filter((s: any) => (s.kind === "action" || s.kind === "check") && !s.decided_at && (s.status || "pending") === "pending");
  const allWork = r.workFor(q.ce_id); const openItems = allWork.filter((w: any) => CLOSED.indexOf(w.status) < 0); const doneItems = allWork.filter((w: any) => CLOSED.indexOf(w.status) >= 0);

  const setTreatment = (v: string) => api.saveReviewSetItem({ market_slug: S.market_slug, week_start: S.week_start, ce_id: q.ce_id, ce_name: q.ce_name, treatment: v, reason: q.reason, source: q.source }).then((res: any) => { S.setRows[q.ce_id] = res.review_set_item || { treatment: v }; r.rerender(); }).catch((e: any) => toast(e?.message || "Could not save review treatment"));
  const saveNote = () => { if (!note.trim()) { toast("Write an observation first"); return; } api.saveWeeklyNote({ market_slug: S.market_slug, ce_id: q.ce_id, ce_name: q.ce_name, week_start: S.week_start, bgm_note: note.trim(), bgm_author: author() || "BGM" }).then((res: any) => { S.weekly[q.ce_id] = res.weekly; S.editing = false; toast("Note saved"); r.rerender(); }).catch((e: any) => toast(e?.message || "Could not save note")); };
  const startSlackDiscussion = () => {
    if (!note.trim()) { toast("Write an observation first"); return; }
    if (!S.channel) { toast("Slack channel is unavailable for this market"); return; }
    const request_id = S.slackRequests[q.ce_id] || (S.slackRequests[q.ce_id] = `review-${S.market_slug}-${q.ce_id}-${S.week_start}-${Date.now()}`);
    api.startSlackDiscussion({ market_slug: S.market_slug, ce_id: q.ce_id, ce_name: q.ce_name,
      week_start: S.week_start, channel: S.channel, bgm_note: note.trim(),
      bgm_author: author() || "BGM", request_id, report_url: location.href })
      .then((res: any) => { S.weekly[q.ce_id] = res.weekly; S.editing = false; toast("Slack discussion started"); r.rerender(); })
      .catch((e: any) => toast(e?.message || "Could not start Slack discussion"));
  };
  const syncSlackDiscussion = () => api.syncWeeklyDiscussion({ market_slug: S.market_slug, ce_id: q.ce_id, week_start: S.week_start })
    .then((res: any) => { S.weekly[q.ce_id] = res.weekly || S.weekly[q.ce_id]; toast("Slack thread summarized"); r.rerender(); })
    .catch((e: any) => toast(e?.message || "Summary is not ready yet"));
  const delNote = () => api.deleteWeeklyNote({ market_slug: S.market_slug, ce_id: q.ce_id, week_start: S.week_start }, author() || "BGM").then((res: any) => { S.weekly[q.ce_id] = res.weekly || null; S.confirmDel = false; toast("Note deleted"); r.rerender(); }).catch((e: any) => toast(e?.message || "Could not delete note"));
  const toggle = (w: any) => r.saveWork({ ...w, status: CLOSED.indexOf(w.status) >= 0 ? (w.kind === "check" ? "scheduled" : "needs_action") : "complete" }, "Updated");
  const finish = () => api.finishReview({ market_slug: S.market_slug, ce_id: q.ce_id, ce_name: q.ce_name, week_start: S.week_start, treatment: t, reviewer: author() || "BGM", open_work_count: String(r.openWork(q.ce_id).length), summary: hasNote ? weekly.bgm_note : "" }).then((res: any) => { S.receipts[q.ce_id] = res.receipt || {}; toast("CE review finished"); r.rerender(); }).catch((e: any) => toast(e?.message || "Could not finish CE review"));
  const pillTxt = commentPending.length ? `${commentPending.length} to review` : commentAccepted.length ? `${commentAccepted.length} added` : "Waiting on meetings";

  return (
    <>
      <header style={{ padding: "26px 32px 22px", borderBottom: `1px solid ${g300}`, background: "#fff" }}>
        <div style={{ color: g700, fontSize: 12 }}>CE {q.ce_id} · {S.market}</div>
        <div style={{ marginTop: 6, display: "flex", justifyContent: "space-between", gap: 24, alignItems: "flex-start" }}>
          <div style={{ flex: 1 }}><Text as="h1" textStyle="display.small">{q.ce_name}</Text><div style={{ color: g700, marginTop: 4 }}>Record what you know, decide the follow-through, and mark it reviewed.</div></div>
          <div style={{ flex: "none" }}><Button size="small" variant="secondary" btnType="black" primaryText="Open CE drawer" onClick={() => { const ce = (S.headline.all_ces || []).find((c: any) => String(c.ce_id) === q.ce_id); if (ce) ctxOpen(ce); }} /></div>
        </div>
        <div style={{ marginTop: 16, display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <label style={{ color: g700, fontSize: 13 }}>Review as</label>
          <select style={sel} value={t} onChange={(e) => setTreatment(e.target.value)}>{TORDER.map((v) => <option key={v} value={v}>{T[v]}</option>)}</select>
          <span style={{ color: rev ? green : g700, fontSize: 13, fontWeight: rev ? 600 : 400 }}>{rev ? `✓ Reviewed by ${(S.receipts[q.ce_id] || {}).reviewer || author() || "BGM"}` : t !== "not_scheduled" ? "Ready to finish" : "Choose how you’ll review this CE"}</span>
        </div>
      </header>
      <div style={{ flex: 1, maxWidth: 1120, margin: "0 auto", width: "100%", padding: "24px 32px 120px" }}>
        {/* commentary */}
        <section style={card}>
          <div style={cardHead}><span style={step}>1</span><div style={{ flex: 1 }}><div style={{ fontSize: 16, fontWeight: 600 }}>Commentary &amp; observations</div><div style={{ marginTop: 2, color: g700, fontSize: 13 }}>One BGM note; discussion happens in Slack and is summarized back here</div></div><span style={{ color: g700, fontSize: 13 }}>{hasNote ? "BGM note saved" : "No note yet"}</span></div>
          <div style={{ padding: "8px 20px 16px" }}>
            {/* granola band */}
            <div style={{ margin: "12px 0 4px", padding: "14px 16px", display: "flex", gap: 12, alignItems: "flex-start", borderRadius: 12, background: purps10 }}>
              <span style={{ width: 34, height: 34, display: "grid", placeItems: "center", flex: "none", borderRadius: 10, background: purps20, color: purps700 }}>✦</span>
              <span style={{ flex: 1 }}><strong style={{ display: "block", fontSize: 14, fontWeight: 600 }}>Granola meeting capture</strong><span style={{ display: "block", marginTop: 2, color: g700, fontSize: 12 }}>Matched meetings surface here automatically. Commentary lands here; work in Actions below.</span></span>
              <span style={{ ...chip, marginLeft: "auto", alignSelf: "center", borderRadius: 999, background: commentPending.length ? purps20 : "#fff", color: commentPending.length ? purps700 : g700 }}>{pillTxt}</span>
              <button onClick={() => { S.addingGranola = !S.addingGranola; r.rerender(); }} style={{ ...link(purps700), marginLeft: 8, alignSelf: "center" }}>{S.addingGranola ? "Close" : "＋ Add link"}</button>
            </div>
            {S.addingGranola && <GranolaAdd r={r} />}
            {commentPending.map((s: any) => <SuggestionCard key={s.suggestion_id} r={r} s={s} kind="comment" />)}
            {commentAccepted.map((s: any) => <div key={s.suggestion_id} style={{ margin: "12px 0", display: "flex", gap: 12 }}><Avatar size="small" fallbackText="Granola" /><div><div style={{ fontWeight: 700, fontSize: 13 }}>Meeting pointer <span style={{ color: g700, fontWeight: 400 }}>· ✦ AI · Granola</span></div><div style={{ marginTop: 3, color: g800, fontSize: 14 }}>{s.accepted_body || s.body}</div></div></div>)}
            {/* note */}
            {hasNote && !S.editing ? (
              <div style={{ margin: "14px 0", display: "flex", gap: 12 }}>
                <Avatar size="small" fallbackText={weekly.bgm_author || author() || "BGM"} />
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                    <span style={{ fontWeight: 700, fontSize: 14 }}>{weekly.bgm_author || author() || "BGM"} · BGM</span>
                    <span style={{ color: g700, fontSize: 13 }}>{weekly.bgm_updated_at ? new Date(weekly.bgm_updated_at).toLocaleString() : ""} · original</span>
                    <span style={{ marginLeft: "auto", display: "flex", gap: 14 }}>{S.confirmDel ? <><button onClick={delNote} style={link(red)}>Confirm delete</button><button onClick={() => { S.confirmDel = false; r.rerender(); }} style={link(purps700)}>Cancel</button></> : <><button onClick={() => { S.editing = true; r.rerender(); }} style={link(purps700)}>Edit</button><button onClick={() => { S.confirmDel = true; r.rerender(); }} style={link(red)}>Delete</button></>}</span>
                  </div>
                  <div style={{ marginTop: 6, color: g800, fontSize: 15, lineHeight: "22px", whiteSpace: "pre-wrap" }}>{weekly.bgm_note}</div>
                </div>
              </div>
            ) : (
              <div style={{ margin: "14px 0" }}>
                <textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="What is happening with this CE that the data can’t see?" style={{ width: "100%", minHeight: 104, padding: "12px 14px", border: `1px solid ${g300}`, borderRadius: 12, fontFamily: HT, fontSize: 15, lineHeight: "22px", resize: "vertical" }} />
                <div style={{ marginTop: 10, display: "flex", gap: 8, justifyContent: "flex-end" }}>{hasNote && <Button size="small" variant="secondary" btnType="black" primaryText="Cancel" onClick={() => { S.editing = false; r.rerender(); }} />}<Button size="small" variant="secondary" btnType="black" primaryText="Save note" onClick={saveNote} /><Button size="small" variant="primary" btnType="primary" primaryText="Start Slack discussion" onClick={startSlackDiscussion} /></div>
              </div>
            )}
            {hasNote && weekly?.slack_post_ts && <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 10 }}><Button size="small" variant="secondary" btnType="black" primaryText="Summarize now" onClick={syncSlackDiscussion} /><span style={{ color: g700, fontSize: 12 }}>New replies are also summarized automatically every 5 minutes.</span></div>}
            {summary && <div style={{ border: `1px solid ${purps200}`, borderRadius: 12, padding: 14, background: "#fff", marginTop: 4 }}><div style={{ color: purps700, fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".4px", marginBottom: 8 }}>✦ Slack summary <span style={{ color: g700, fontWeight: 600, textTransform: "none", letterSpacing: 0 }}>· AI · source-linked</span></div>{[["Findings", summary.findings], ["Decisions", summary.decisions], ["Open points", summary.open_points]].map(([lab, arr]: any) => (arr && arr.length) ? <div key={lab} style={{ marginTop: 8 }}><div style={{ color: g700, fontSize: 11, fontWeight: 600, textTransform: "uppercase" }}>{lab}</div><ul style={{ margin: 0, paddingLeft: 18 }}>{arr.map((x: any, i: number) => <li key={i} style={{ color: g800, fontSize: 14, lineHeight: "20px", marginTop: 2 }}>{typeof x === "string" ? x : x.text || x.body}</li>)}</ul></div> : null)}</div>}
          </div>
        </section>
        {/* actions */}
        <section style={card}>
          <div style={cardHead}><span style={step}>2</span><div style={{ flex: 1 }}><div style={{ fontSize: 16, fontWeight: 600 }}>Actions &amp; follow-ups</div><div style={{ marginTop: 2, color: g700, fontSize: 13 }}>Every item carries its owner, source, status and next check</div></div><span style={{ color: g700, fontSize: 13 }}>{openItems.length ? `${openItems.length} open` : allWork.length ? "All done" : "No work yet"}</span></div>
          <div style={{ padding: "8px 20px 16px" }}>
            {workPending.map((s: any) => <SuggestionCard key={s.suggestion_id} r={r} s={s} kind={s.kind} />)}
            {openItems.map((w: any) => <WorkRow key={w.work_id} w={w} onToggle={() => toggle(w)} onStatus={(st) => r.saveWork({ ...w, status: st }, "Status updated")} />)}
            {!openItems.length && !workPending.length && <div style={{ padding: 20, border: `1px dashed ${g400}`, borderRadius: 12, background: "#fafafa", textAlign: "center", marginTop: 12 }}><strong>No open actions</strong><div style={{ color: g700, fontSize: 12, marginTop: 4 }}>Accept a suggestion or add one below.</div></div>}
            {doneItems.length ? <details style={{ marginTop: 4, borderTop: `1px solid ${g200}` }}><summary style={{ padding: "12px 0", cursor: "pointer", color: g700, fontSize: 13, fontWeight: 600 }}>Archived · {doneItems.length} done</summary>{doneItems.map((w: any) => <WorkRow key={w.work_id} w={w} onToggle={() => toggle(w)} onStatus={(st) => r.saveWork({ ...w, status: st }, "Status updated")} />)}</details> : null}
            {S.compose ? <Composer r={r} q={q} kind={S.compose} /> : null}
            <div style={{ marginTop: 14, display: "flex", gap: 8 }}>
              <Button size="small" variant="tertiary" btnType="transparent" primaryText="＋ Add action" onClick={() => { S.compose = S.compose === "action" ? "" : "action"; r.rerender(); }} />
              <Button size="small" variant="tertiary" btnType="transparent" primaryText="＋ Schedule check" onClick={() => { S.compose = S.compose === "check" ? "" : "check"; r.rerender(); }} />
            </div>
          </div>
        </section>
        <button onClick={r.openMemory} style={{ width: "100%", padding: 16, display: "flex", alignItems: "center", gap: 12, border: `1px solid ${purps200}`, borderRadius: 14, background: purps10, textAlign: "left", cursor: "pointer" }}><span style={{ width: 38, height: 38, display: "grid", placeItems: "center", borderRadius: 10, background: purps20, color: purps700, fontSize: 18 }}>↺</span><span style={{ flex: 1 }}><strong style={{ display: "block", fontSize: 14, fontWeight: 600 }}>CE Memory</strong><span style={{ color: g700, fontSize: 12 }}>Past weekly notes, work and source history</span></span><span style={{ color: purps700, fontSize: 18 }}>→</span></button>
      </div>
      <footer style={{ position: "sticky", bottom: 0, padding: "12px 32px", display: "flex", alignItems: "center", gap: 8, borderTop: `1px solid ${g300}`, background: "rgba(255,255,255,.97)", boxShadow: "0 -1px 8px rgba(17,17,17,.08)", backdropFilter: "blur(10px)" }}>
        <span style={{ color: g500, fontSize: 12, marginRight: "auto" }}>{rev ? "Review saved — open work carries forward" : t === "not_scheduled" ? "Set a treatment above to finish this CE" : "Finish when you’re done with this CE"}</span>
        <Button size="small" variant="secondary" btnType="black" primaryText="Next CE →" onClick={() => { const nx = S.queue.find((x: Q) => !r.reviewed(x.ce_id) && x.ce_id !== S.selected); nx ? r.select(nx.ce_id) : toast("Review queue complete 🎉"); }} />
        <Button size="small" variant="primary" btnType="primary" primaryText={rev ? "Reviewed ✓" : "Finish CE review"} disabled={t === "not_scheduled" || rev} onClick={finish} />
      </footer>
    </>
  );
}

function GranolaAdd({ r }: { r: R }) { const [url, setUrl] = useState(""); return <div style={{ margin: "10px 0" }}><div style={{ display: "flex", gap: 8 }}><input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://notes.granola.ai/t/… — paste a meeting link" style={{ ...inp, flex: 1 }} /><Button size="small" variant="primary" btnType="primary" primaryText="Extract meeting" onClick={() => r.attachGranola(url.trim())} /><Button size="small" variant="secondary" btnType="black" primaryText="Cancel" onClick={() => { r.S.addingGranola = false; r.rerender(); }} /></div><div style={{ marginTop: 6, color: g500, fontSize: 12 }}>The transcript is read securely, matched to discussed CEs, then returned as pending suggestions.</div></div>; }

function SuggestionCard({ r, s, kind }: { r: R; s: any; kind: string }) {
  const isCheck = kind === "check", isComment = kind === "comment";
  const [owner, setOwner] = useState(s.proposed_owner || ""); const [due, setDue] = useState(s.proposed_due_date || ""); const [status, setStatus] = useState(isCheck ? "scheduled" : "needs_action");
  const accept = () => { if (isComment) return r.decide(s.suggestion_id, "approved", { destination: "comment" }); if (kind === "action" && status === "needs_action" && !owner.trim()) { toast("Confirm an owner"); return; } if (isCheck && !due) { toast("Choose the next review date"); return; } r.decide(s.suggestion_id, "approved", { destination: kind, owner: owner.trim(), due_date: due, work_status: status }); };
  return <div style={{ margin: "12px 0", padding: "14px 16px", border: `1px solid ${purps200}`, borderRadius: 12, background: "#fff" }}>
    <div style={{ color: purps700, fontSize: 10, fontWeight: 700, letterSpacing: ".4px", textTransform: "uppercase" }}>✦ AI · {s.source_type === "slack" ? "Slack" : "Granola"} · {s.source_ref || s.source_author || "meeting"}</div>
    <p style={{ margin: "8px 0 12px", color: g900, fontSize: 14, lineHeight: "20px" }}>{s.body}</p>
    {!isComment && <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: 8, marginBottom: 10 }}><input value={owner} onChange={(e) => setOwner(e.target.value)} placeholder={isCheck ? "Owner (optional)" : "Owner"} style={inp} /><input type="date" value={due} onInput={(e) => setDue((e.target as HTMLInputElement).value)} onChange={(e) => setDue(e.target.value)} style={inp} /><select value={status} onChange={(e) => setStatus(e.target.value)} style={sel}>{(isCheck ? CHECK_STATUS : WORK_STATUS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>}
    <div style={{ display: "flex", gap: 8 }}><Button size="small" variant="primary" btnType="primary" primaryText={isComment ? "Add to commentary" : isCheck ? "Schedule check" : "Create action"} onClick={accept} /><Button size="small" variant="secondary" btnType="black" primaryText="Ignore" onClick={() => r.decide(s.suggestion_id, "rejected")} /></div>
  </div>;
}

function Composer({ r, q, kind }: { r: R; q: Q; kind: string }) {
  const isCheck = kind === "check"; const [text, setText] = useState(""); const [owner, setOwner] = useState(""); const [due, setDue] = useState(""); const [status, setStatus] = useState(isCheck ? "scheduled" : "needs_action");
  const save = () => { if (!text.trim()) { toast("Describe it first"); return; } if (kind === "action" && status === "needs_action" && !owner) { toast("Confirm an owner"); return; } if (isCheck && !due) { toast("Choose the next review date"); return; } r.saveWork({ market_slug: r.S.market_slug, ce_id: q.ce_id, ce_name: q.ce_name, origin_week: r.S.week_start, kind, text: text.trim(), owner, due_date: due, status, source_type: "bgm_manual" }, isCheck ? "Check scheduled" : "Action created"); r.S.compose = ""; };
  return <div style={{ marginTop: 14, padding: "14px 16px", border: `1px dashed ${purps200}`, borderRadius: 12, background: purps10 }}>
    <input value={text} onChange={(e) => setText(e.target.value)} placeholder={isCheck ? "What should we revisit next week?" : "What needs to happen?"} style={{ ...inp, width: "100%" }} />
    <div style={{ marginTop: 8, display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: 8 }}><input value={owner} onChange={(e) => setOwner(e.target.value)} placeholder={isCheck ? "Owner (optional)" : "Owner"} style={inp} /><input type="date" value={due} onInput={(e) => setDue((e.target as HTMLInputElement).value)} onChange={(e) => setDue(e.target.value)} style={inp} /><select value={status} onChange={(e) => setStatus(e.target.value)} style={sel}>{(isCheck ? CHECK_STATUS : WORK_STATUS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
    <div style={{ marginTop: 10, display: "flex", gap: 8, justifyContent: "flex-end" }}><Button size="small" variant="secondary" btnType="black" primaryText="Cancel" onClick={() => { r.S.compose = ""; r.rerender(); }} /><Button size="small" variant="primary" btnType="primary" primaryText={isCheck ? "Schedule check" : "Create action"} onClick={save} /></div>
  </div>;
}

function WorkRow({ w, onToggle, onStatus }: { w: any; onToggle: () => void; onStatus: (s: string) => void }) {
  const done = CLOSED.indexOf(w.status) >= 0, isCheck = w.kind === "check", opts = isCheck ? CHECK_STATUS : WORK_STATUS;
  return <div style={{ padding: "16px 0", borderTop: `1px solid ${g200}`, display: "flex", gap: 12, alignItems: "flex-start", opacity: done ? 0.55 : 1 }}>
    <button onClick={onToggle} style={{ width: 22, height: 22, marginTop: 1, flex: "none", border: `1.5px solid ${done ? green : g300}`, borderRadius: 6, background: done ? green : "#fff", color: "#fff", cursor: "pointer", display: "grid", placeItems: "center", fontSize: 14 }}>{done ? "✓" : ""}</button>
    <div style={{ flex: 1, minWidth: 0 }}>
      {isCheck && <div style={{ color: g700, fontSize: 11, fontWeight: 600, textTransform: "uppercase" }}>Next review check</div>}
      <div style={{ fontSize: 16, fontWeight: 600, textDecoration: done ? "line-through" : "none", color: done ? g700 : g900 }}>{w.text}</div>
      <div style={{ marginTop: 4, color: g700, fontSize: 13 }}>{[w.owner || (isCheck ? "" : "no owner"), w.due_date ? (isCheck ? "returns " : "due ") + w.due_date : "", w.source_type].filter(Boolean).join(" · ")}</div>
      <div style={{ marginTop: 10 }}><select style={{ ...sel, minHeight: 38, fontSize: 13 }} value={w.status} onChange={(e) => onStatus(e.target.value)}>{opts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}{opts.some(([v]) => v === w.status) ? null : <option value={w.status}>{w.status}</option>}</select></div>
    </div>
    <Avatar size="small" fallbackText={w.owner || "–"} />
  </div>;
}

function MemoryDrawer({ r }: { r: R }) {
  const [tab, setTab] = useState("story"); const m = r.S.memory; const q = r.S.byId[r.S.selected];
  const weeklyHistory = m?.weekly || m?.weekly_commentary || [];
  const workHistory = m?.work || m?.work_items || [];
  const sourceHistory = m?.source_suggestions || [];
  const summaryFor = (weekly: any) => { try { return weekly?.summary_json ? JSON.parse(weekly.summary_json) : null; } catch { return null; } };
  const sourceForWeek = (week: string) => sourceHistory.filter((s: any) => String(s.week_start) === String(week));
  const summaryLines = (summary: any) => [
    ["Finding", summary?.findings], ["Decision", summary?.decisions], ["Open point", summary?.open_points],
  ].flatMap(([label, values]: any) => (Array.isArray(values) ? values : []).map((value: any) => ({ label, text: typeof value === "string" ? value : value?.text || value?.body || "" }))).filter((x: any) => x.text);
  return <div onClick={(e) => { if (e.target === e.currentTarget) { r.S.memoryOpen = false; r.rerender(); } }} style={{ position: "fixed", inset: 0, zIndex: 60, display: "flex", justifyContent: "flex-end", background: "rgba(17,17,17,.42)" }}>
    <div style={{ width: "min(560px,100vw)", height: "100%", overflow: "auto", background: "#fafafa", fontFamily: HT }}>
      <header style={{ position: "sticky", top: 0, padding: 20, display: "flex", justifyContent: "space-between", gap: 16, borderBottom: `1px solid ${g300}`, background: "#fff" }}><div><div style={{ color: purps700, fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: ".8px" }}>CE {q.ce_id} · {r.S.market}</div><Text as="h2" textStyle="heading.regular">{q.ce_name} memory</Text></div><button onClick={() => { r.S.memoryOpen = false; r.rerender(); }} style={{ width: 40, height: 40, border: 0, borderRadius: 10, background: g200, fontSize: 22, cursor: "pointer" }}>×</button></header>
      <div style={{ padding: 16 }}>
        {!m ? <div style={{ padding: 20, textAlign: "center", color: g700 }}>Loading…</div> : m.error ? <div style={{ padding: 20, textAlign: "center", color: g700 }}>Could not load CE memory.</div> : <>
          <div style={{ marginBottom: 12, padding: 3, display: "grid", gridTemplateColumns: "1fr 1fr", borderRadius: 12, background: g200 }}>{["story", "work"].map((t) => <button key={t} onClick={() => setTab(t)} style={{ minHeight: 38, border: 0, borderRadius: 10, cursor: "pointer", background: tab === t ? "#fff" : "transparent", color: tab === t ? purps700 : g700, fontWeight: tab === t ? 600 : 400, fontSize: 13 }}>{t === "story" ? "Story" : "Work"}</button>)}</div>
          {tab === "story" ? (weeklyHistory.length || sourceHistory.length || (m.legacy_notes || []).length ? <>{weeklyHistory.map((w: any, i: number) => { const summary = summaryFor(w), lines = summaryLines(summary), sources = sourceForWeek(w.week_start); return <div key={i} style={{ marginTop: 12, border: `1px solid ${g300}`, borderRadius: 14, background: "#fff", overflow: "hidden" }}><div style={{ padding: "12px 16px", display: "flex", justifyContent: "space-between", borderBottom: `1px solid ${g200}`, fontWeight: 600, fontSize: 13 }}>w/c {w.week_start}<span style={{ color: g700, fontWeight: 400 }}>{w.bgm_author || "BGM"}</span></div><div style={{ padding: "14px 16px" }}><div style={{ color: purps700, fontSize: 10, fontWeight: 700, textTransform: "uppercase" }}>BGM note · original</div><p style={{ margin: "6px 0 0", color: g700, fontSize: 14 }}>{w.note_deleted_at ? "(deleted · audit retained)" : w.bgm_note || "—"}</p></div>{lines.length ? <div style={{ padding: "14px 16px", borderTop: `1px solid ${g200}`, background: purps10 }}><div style={{ color: purps700, fontSize: 10, fontWeight: 700, textTransform: "uppercase" }}>AI · Slack thread summary</div>{lines.map((line: any, index: number) => <p key={index} style={{ margin: "7px 0 0", color: g800, fontSize: 13, lineHeight: "19px" }}><strong>{line.label}:</strong> {line.text}</p>)}{w.slack_post_permalink ? <a href={w.slack_post_permalink} target="_blank" rel="noreferrer" style={{ display: "inline-block", marginTop: 9, color: purps700, fontSize: 12, fontWeight: 600 }}>Open source thread ↗</a> : null}</div> : null}{sources.length ? <div style={{ padding: "14px 16px", borderTop: `1px solid ${g200}` }}><div style={{ color: purps700, fontSize: 10, fontWeight: 700, textTransform: "uppercase" }}>Granola · source pointers</div>{sources.map((s: any) => <div key={s.suggestion_id} style={{ marginTop: 8, color: g800, fontSize: 13, lineHeight: "19px" }}><span style={{ color: g700 }}>{s.kind || "comment"} · {(s.status || "pending").replace(/_/g, " ")}</span><br />{s.accepted_body || s.body}{s.source_url ? <a href={s.source_url} target="_blank" rel="noreferrer" style={{ marginLeft: 6, color: purps700, fontWeight: 600 }}>Source ↗</a> : null}</div>)}</div> : null}</div>; })}</> : <div style={{ padding: 20, textAlign: "center", color: g700 }}>No commentary history yet.</div>) : (workHistory.length || (m.receipts || []).length ? <>{workHistory.map((w: any, i: number) => <div key={i} style={{ marginTop: 12, border: `1px solid ${g300}`, borderRadius: 14, background: "#fff", overflow: "hidden" }}><div style={{ padding: "12px 16px", display: "flex", justifyContent: "space-between", borderBottom: `1px solid ${g200}`, fontWeight: 600, fontSize: 13 }}>{w.kind === "check" ? "Scheduled check" : "Action"}<span style={{ color: g700, fontWeight: 400 }}>w/c {w.origin_week}</span></div><div style={{ padding: "14px 16px" }}><div style={{ color: purps700, fontSize: 10, fontWeight: 700, textTransform: "uppercase" }}>{(w.status || "").replace(/_/g, " ")}</div><p style={{ margin: "6px 0 0", color: g700, fontSize: 14 }}>{w.text}</p></div></div>)}</> : <div style={{ padding: 20, textAlign: "center", color: g700 }}>No work or receipts yet.</div>)}
        </>}
      </div>
    </div>
  </div>;
}

let ctxOpen: (ce: any) => void = () => {};
export function initReviewView(ctx: Ctx) {
  ctxOpen = (ce: any) => ctx.openCeDrawer && ctx.openCeDrawer(ce);
  const root = createRoot(ctx.root);
  function App() { const r = useReview(ctx); return <Workspace r={r} />; }
  root.render(<App />);
  return { onShow: () => {}, onWeekChange: () => {} };
}
(window as any).initReviewView = initReviewView;
