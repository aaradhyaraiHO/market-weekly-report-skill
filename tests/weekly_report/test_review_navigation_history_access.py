from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VIEW = (ROOT / "scripts/weekly_report/review/review-view.js").read_text()
BACKEND = (ROOT / "scripts/weekly_report/notes/review_apps_script.js").read_text()
INJECTOR = (ROOT / "scripts/weekly_report/inject_review_view.py").read_text()
TEMPLATE = (ROOT / "scripts/weekly_report/template/report_v2_template.html").read_text()
CHANNEL_DOC = (ROOT / "docs/weekly-review/MARKET_CHANNEL_MAPPING.md").read_text()
CHANNELS = json.loads((ROOT / "alert/market_channels.json").read_text())["markets"]


class ReviewNavigationHistoryAccessContract(unittest.TestCase):
    def test_review_to_existing_drawer_uses_stable_ce_id(self):
        self.assertIn("ctx.openCeDrawer(String(ce.ce_id))", VIEW)
        self.assertIn('data-open-drawer-ce=', VIEW)
        self.assertNotIn("ctx.openCeDrawer(ce)", VIEW)
        self.assertIn("openCeDrawer:(typeof openCeDrawer", INJECTOR)

    def test_existing_drawer_returns_to_review_with_ce_context(self):
        self.assertIn('id="ce-open-review"', TEMPLATE)
        self.assertIn("window.__openReviewCe(String(ce.ce_id))", TEMPLATE)
        for fragment in ('searchParams.set("market"', 'searchParams.set("week"', 'searchParams.set("ce_id"', "focusCe:"):
            self.assertIn(fragment, VIEW)

    def test_unsaved_drafts_are_keyed_by_ce(self):
        self.assertIn("drafts: {}", VIEW)
        self.assertIn("S.drafts[S.selected]=S.noteDraft", VIEW)
        self.assertIn("Object.prototype.hasOwnProperty.call(S.drafts", VIEW)
        self.assertIn("S.editingNote = S.noteDraft != null", VIEW)

    def test_access_fails_closed_and_roles_are_explicit(self):
        self.assertIn('Review access enforcement is not configured', BACKEND)
        self.assertIn('["bgm","gm","admin"]', BACKEND)
        self.assertIn('authenticated BGM identity required', BACKEND)
        self.assertNotIn('enforcement:"off"', BACKEND)
        access = BACKEND.split("function reviewAccessDecision", 1)[1].split("function reviewTrustedAuthor", 1)[0]
        self.assertNotIn("review_slack_people", access)

    def test_all_market_primary_channels_match_authoritative_alert_map(self):
        self.assertEqual(len(CHANNELS), 18)
        for market, channel in CHANNELS.items():
            if market == "headout":
                continue
            if market == "north_america":
                channel = "C0BQHT29WMB"
            self.assertRegex(BACKEND, rf"{re.escape(market)}:\[\"{re.escape(channel)}\"")
            self.assertIn(f'{market}:{{id:"{channel}"', VIEW)
            self.assertIn(f"`{channel}`", CHANNEL_DOC)
        self.assertIn("Slack channel does not match Review market routing", BACKEND)
        self.assertIn('S.market_slug === "north_america" ? MARKET_CHANNELS.north_america', VIEW)
        self.assertIn("Headout/global", CHANNEL_DOC)
        self.assertIn("no Review tab", CHANNEL_DOC)

    def test_history_is_read_only_ce_id_scoped_and_fail_soft(self):
        self.assertIn("reviewStableCeId", BACKEND)
        self.assertIn('String(row.market_slug) !== String(market)', BACKEND)
        self.assertIn("row.ce_id !== wanted", BACKEND)
        self.assertIn('return {rows:[], unavailable:true, error:"historical source unavailable"}', BACKEND)
        self.assertNotRegex(BACKEND, r"historical.*(?:appendRow|setValues|setValue)")
        self.assertIn("historical_comments", BACKEND)
        self.assertIn("perf_history", BACKEND)

    def test_duplicate_history_is_collapsed_with_audit_count(self):
        self.assertIn("seen[signature]._duplicate_count++", BACKEND)
        self.assertIn("duplicates:duplicates", BACKEND)
        self.assertIn("duplicate_count", VIEW)

    def test_sparse_dense_and_global_shapes_remain_fail_soft(self):
        for fixture in ("sparse", "dense", "global"):
            path = ROOT / f"tests/weekly_report/fixtures/captured/snapshot_{fixture}_2026-08-02.json.gz"
            self.assertTrue(path.is_file())
        self.assertNotIn('headout:{id:', VIEW)
        self.assertIn("Missing history never blocks this report", VIEW)

    def test_navigation_paints_before_remote_review_state(self):
        load_queue = VIEW.split("function loadQueue()", 1)[1].split("function loadCe", 1)[0]
        self.assertLess(load_queue.index("buildQueue();"), load_queue.index("Promise.all(["))
        self.assertLess(load_queue.index("S.selected = (S.queue[0]"), load_queue.index("Promise.all(["))
        self.assertLess(load_queue.index("S.loaded = true; render();"), load_queue.index("Promise.all(["))
        self.assertIn("setTimeout(function(){window.__rv&&window.__rv.prefetch", INJECTOR)

    def test_review_reads_are_cached_and_deduplicated(self):
        client = (ROOT / "scripts/weekly_report/notes/review_client.js").read_text()
        self.assertIn("cache[url]", client)
        self.assertIn("inflight[url]", client)
        self.assertIn('ttl: 300000', client)
        self.assertIn("ceLoadedAt", VIEW)
        self.assertIn("memoryCache", VIEW)
        self.assertIn("memoryInflight", VIEW)

    def test_historical_sheet_scan_is_market_cached(self):
        self.assertIn("CacheService.getScriptCache()", BACKEND)
        self.assertIn('"review-history-v2:"', BACKEND)
        self.assertIn("cache.put(cacheKey, JSON.stringify(payload), 300)", BACKEND)
        self.assertEqual(BACKEND.count('getRange(2, 1, last - 1, schema.length).getValues()'), 1)

    def test_save_and_slack_have_immediate_async_feedback(self):
        for fragment in ('btn.textContent="Saving…"', 'btn.textContent="Posting…"', 'button.textContent = "Summarizing…"'):
            self.assertIn(fragment, VIEW)


if __name__ == "__main__":
    unittest.main()
