"""Zero revenue is explicit evidence; missing revenue must remain blocked."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'alert'))
spec = importlib.util.spec_from_file_location('weekly_zero_rca', ROOT / 'alert/weekly_rca_helper.py')
rca = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rca)


class WeeklyZeroBaselineTests(unittest.TestCase):
    def row(self, pre=0, post=12.4193):
        return dict(combined_entity_id='1011 - Medina', combined_entity_name='Medina',
                    pre_revenue=pre, post_revenue=post)

    def build(self, row):
        return rca.build_rca_entry(row, '2026-09-06', '2026-09-12')

    def test_real_zero_has_factual_amounts_dates_and_no_attribution(self):
        with patch.object(rca, 'analyze_ce_row') as analyze:
            result = self.build(self.row())
        analyze.assert_not_called()
        text = json.dumps(result, ensure_ascii=False)
        for expected in ('$0.00 → $12.42', '2026-08-30–2026-09-05',
                         '2026-09-06–2026-09-12', 'N/A — zero prior-week revenue',
                         'multiplicative comparison is undefined'):
            self.assertIn(expected, text)
        self.assertNotIn('insufficient data', result['fallback'])
        self.assertNotIn('100%', text)

    def test_missing_nonfinite_negative_and_nonpositive_post_stay_blocked(self):
        for pre, post in [(None, 12), (float('nan'), 12), (float('inf'), 12),
                          (-1, 12), (0, None), (0, float('nan')), (0, float('inf')),
                          (0, 0), (0, -1)]:
            with self.subTest(pre=pre, post=post):
                self.assertIn('insufficient data', self.build(self.row(pre, post))['fallback'])

    def test_positive_baseline_preserves_shared_engine_and_output(self):
        row = self.row(10, 12)
        alert = dict(pre_revenue=10, post_revenue=12)
        detail = [{'type': 'divider'}]
        with patch.object(rca, 'analyze_ce_row', return_value=alert) as analyze, \
             patch.object(rca, 'build_ce_thread_detail_blocks', return_value=detail) as build:
            result = self.build(row)
        analyze.assert_called_once_with(row, always=True, skip_floor_check=True, weekly=True)
        build.assert_called_once_with(alert, recent_label=rca.RECENT_LABEL, weekly=True)
        self.assertEqual(result['fallback'], 'Medina — WoW revenue diagnosis')
        self.assertEqual(result['blocks'][1], rca.revenue_line_block(alert))
        self.assertEqual(result['blocks'][3], detail[0])
