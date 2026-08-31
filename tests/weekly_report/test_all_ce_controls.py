from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "scripts" / "weekly_report" / "template" / "report_v2_template.html"


class AllCeControlsContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = TEMPLATE.read_text()

    def test_uses_one_report_wide_country_control(self):
        self.assertIn('id="country-select"', self.html)
        self.assertNotIn('id="ce-country"', self.html)
        self.assertNotIn("ceState.country", self.html)

    def test_category_is_available_as_a_portfolio_filter(self):
        self.assertIn("{key:'category',label:'Category'}", self.html)

    def test_filtering_collapses_active_groups(self):
        self.assertIn("function collapseFilteredGroups()", self.html)
        self.assertIn("collapseFilteredGroups();renderAllCes(currentHeadline())", self.html)

    def test_all_ce_subtotals_preserve_actual_take_rate_basis(self):
        self.assertIn("actual_revenue:0", self.html)
        self.assertIn("(sums.actual_revenue||sums.revenue)/sums.gbv_completed", self.html)

    def test_portfolio_copy_avoids_internal_release_language(self):
        self.assertIn("Search, filter and compare the portfolio", self.html)
        self.assertNotIn("Every V1 All-CE metric", self.html)

    def test_okr_cohort_is_visible_and_clearable_in_all_ces(self):
        self.assertIn('id="okr-cohort-note"', self.html)
        self.assertIn('data-clear-okr-cohort', self.html)
        self.assertIn('class="ce-filter-group okr-filter-group"', self.html)
        self.assertIn("ceState.filtersOpen=true", self.html)
        self.assertIn("okrCohortLabel", self.html)
        self.assertIn("okrIds:null,okrCohortLabel:''", self.html)

    def test_selected_okrs_use_a_compact_four_up_desktop_layout(self):
        self.assertIn(".okr-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr));", self.html)
        self.assertIn(".okr-card { display:flex; flex-direction:column; min-width:0; min-height:162px;", self.html)

    def test_selected_okrs_have_one_section_level_tracker_link(self):
        self.assertEqual(self.html.count('href="https://okr.headout.com/okr-tracker"'), 1)
        self.assertNotIn("View details ↗", self.html)


if __name__ == "__main__":
    unittest.main()
