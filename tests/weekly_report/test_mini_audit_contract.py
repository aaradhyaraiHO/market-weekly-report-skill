"""Contracts for the simplified, reachable Mini Audit surface."""
from pathlib import Path
import importlib.util
import unittest
ROOT=Path(__file__).resolve().parents[2]
VIEW=(ROOT/'scripts/weekly_report/review/review-view.js').read_text()
CSS=(ROOT/'scripts/weekly_report/review/review-view.css').read_text()
INJECT=(ROOT/'scripts/weekly_report/inject_review_view.py').read_text()

def function(name,next_name):
    return VIEW.split('function '+name,1)[1].split('function '+next_name,1)[0]

class MiniAuditContract(unittest.TestCase):
    def test_retired_render_paths_are_not_shipped(self):
        for name in ('renderMemoryDrawer','renderRoleNote','renderLegacyCommentaryCard','renderGranolaDock','renderFinishBar','renderReconciliationCard'):
            self.assertNotIn('function '+name,VIEW)
        self.assertNotIn('if native:',INJECT)
        self.assertNotIn('ap.add_argument("--native"',INJECT)

    def test_main_surface_has_one_composer_actions_and_inline_memory(self):
        main=function('renderMain','completionBlockers')
        for item in ('renderCommentaryCard','renderActionsCard','renderMemoryRail'):
            self.assertIn(item,main)
        for item in ('renderFinishBar','renderTreatment','renderReconciliation','renderMemoryDrawer'):
            self.assertNotIn(item,main)
        composer=function('renderWriteup','normalizedSuggestionBody')
        self.assertEqual(composer.count('<textarea'),1)
        self.assertNotIn('rv-new-thread-reason',composer)
        self.assertIn('rv-thread-choice',composer)
        self.assertIn('rv-save-writeup',composer)
        self.assertIn('rv-send-writeup',composer)

    def test_queue_searches_catalogue_without_nomination_or_owner_form(self):
        picker=function('renderAuditQueueRows','renderPickerResults')
        self.assertIn('S.headline.all_ces',picker)
        self.assertNotIn('api.',picker)
        for item in ('rv-add-ce','rv-nomination-reason','rv-owner-filter'):
            self.assertNotIn(item,picker)
        self.assertIn('aria-label="Search CE"',picker)

    def test_real_drawer_is_mounted_and_restored(self):
        self.assertIn('host.appendChild(_rvAnalytics)',INJECT)
        self.assertIn('_rvAnalyticsHome.appendChild(_rvAnalytics)',INJECT)
        self.assertIn('renderCeDrawer(ce)',INJECT)
        self.assertIn('Open Mini Audit →',INJECT)
        self.assertIn('SWITCH_PREVIOUS',INJECT)
        self.assertIn('grid-template-columns:minmax(0,1fr) minmax(0,1fr)',CSS)

    def test_approved_summary_is_saved_once_and_read_in_memory(self):
        sync=function('syncThread','decideSummary')
        self.assertIn('decision:"approved"',sync)
        self.assertIn('["ok","no_new_source","current"]',sync)
        summary=function('renderWeeklySummary','renderCommentaryCard')
        self.assertIn('if(approved)return',summary)
        memory=function('renderMemoryRail','renderMeetingInput')+VIEW.split('function ceMemoryEntries',1)[1].split('global.weeklyCeMemoryEntries',1)[0]
        for item in ('weekly_commentary','performance','slack_summary','ceMemoryWeeks'):
            self.assertIn(item,memory)

    def test_meetings_enter_once_and_link_to_ce_suggestions(self):
        meeting=function('renderMeetingInput','sameReport')
        self.assertIn('rv-process-text',meeting)
        self.assertNotIn('rv-granola-link',VIEW)
        self.assertNotIn('ingestGranolaLink',VIEW)
        self.assertIn('Paste the meeting transcript',meeting)
        self.assertIn('data-meeting-ce',meeting)
        self.assertIn('review_extract_api.js',INJECT)

    def test_resource_loading_is_independent_and_scope_guarded(self):
        load=function('loadCe','select')
        for resource in ('resource("notes"','resource("comments"','resource("suggestions"','resource("threads"'):
            self.assertIn(resource,load)
        self.assertIn('S.ceRequestSeq[ceId]===seq',load)
        self.assertIn('api.weeklyCommentary({market_slug:market,ce_id:ceId,week:week}',load)
        self.assertIn('timeoutMs:45000',load)
        self.assertIn('return pending.then',load)
        self.assertIn('sameReport(id)',function('saveWriteup','ensureAuthor'))

    def test_failed_reads_are_not_reported_as_empty_or_complete(self):
        discussion=function('renderCommentaryCard','normalizedSuggestionBody')
        self.assertIn('Saved discussion could not load.',discussion)
        self.assertIn('Loading saved discussion…',discussion)
        self.assertIn('rv-retry-discussion',discussion)
        self.assertIn('weeklyError||weeklyLoading',discussion)
        actions=function('renderActionsCard','workRow')
        self.assertIn("count='Suggestions unavailable'",actions)
        self.assertIn("count='Actions unavailable'",actions)

if __name__=='__main__':unittest.main()
