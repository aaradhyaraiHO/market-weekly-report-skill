"""ROI presentation must not divide the bucket's rounded display values."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/weekly_report"))
import headline_v2


class BucketRoiPrecision(unittest.TestCase):
    def setUp(self):
        self.market = {"ces": [{"ce_id": "3111", "weekly": [
            {"week": "2026-08-23", "cm1_g": 27135.8601, "spend_g": 20064.0294, "roi_g": 135.25},
            {"week": "2026-08-30", "cm1_g": 19551.8507, "spend_g": 15400.4898, "roi_g": 126.96},
        ]}]}
        self.row = {"ce_id": "3111", "criteria": ["C2", "C3"], "label": "eroding", "weeks": [
            {"week": "2026-08-30", "roi": 127, "cm1": 19552, "spend": 15400},
            {"week": "2026-08-23", "roi": 135, "cm1": 27136, "spend": 20064},
        ]}

    def project(self):
        return headline_v2._losing_money_roi_precision(self.market, [self.row])[0]

    def test_kennedy_uses_unrounded_operands_without_changing_authority(self):
        before = copy.deepcopy((self.market, self.row))
        result = self.project()
        self.assertAlmostEqual(result.pop("roi_wow_pct"), -6.129765501149487)
        self.assertEqual(result, self.row)
        self.assertEqual((self.market, self.row), before)

    def test_google_scope_never_uses_business_roi(self):
        for week in self.market["ces"][0]["weekly"]:
            week.update(cm1=99999, spend=100, roi_pct=999)
        self.assertAlmostEqual(self.project()["roi_wow_pct"], -6.129765501149487)

    def test_pre_split_snapshot_uses_original_business_operands(self):
        for week in self.market["ces"][0]["weekly"]:
            for old, new in [("cm1_g", "cm1"), ("spend_g", "spend"), ("roi_g", "roi_pct")]:
                week[new] = week.pop(old)
        self.assertAlmostEqual(self.project()["roi_wow_pct"], -6.129765501149487)

    def test_missing_invalid_or_mismatched_evidence_is_unavailable(self):
        original = copy.deepcopy(self.market)
        for field, value in [("roi_g", None), ("cm1_g", None), ("cm1_g", float("inf")),
                             ("cm1_g", "invalid"), ("cm1_g", 1), ("spend_g", 0),
                             ("spend_g", -1), ("week", "2026-08-29")]:
            with self.subTest(field=field, value=value):
                self.market = copy.deepcopy(original)
                self.market["ces"][0]["weekly"][-1][field] = value
                self.assertIsNone(self.project()["roi_wow_pct"])

    def test_zero_baseline_and_missing_prior_do_not_invent_growth(self):
        self.market["ces"][0]["weekly"][0].update(cm1_g=0, roi_g=0)
        self.row["weeks"][1]["roi"] = 0
        self.assertIsNone(self.project()["roi_wow_pct"])
        self.row["weeks"].pop()
        self.assertIsNone(self.project()["roi_wow_pct"])

    def test_nonadjacent_weeks_are_not_called_wow(self):
        self.row["weeks"][1]["week"] = "2026-08-16"
        self.market["ces"][0]["weekly"][0]["week"] = "2026-08-16"
        self.assertIsNone(self.project()["roi_wow_pct"])

    def test_operand_drift_is_rejected_even_when_rounded_roi_matches(self):
        self.market["ces"][0]["weekly"][-1]["cm1_g"] += 1
        self.assertIsNone(self.project()["roi_wow_pct"])

    def test_both_losing_money_lanes_are_enriched_not_reclassified(self):
        self.market["buckets_final"] = {"defend": {"losing_money": {
            "existing": [self.row], "new": [self.row]}}}
        before = copy.deepcopy(self.market)
        result = headline_v2._diagnostic_bucket_view(self.market)["losing_money"]
        for lane in ("existing", "new"):
            self.assertAlmostEqual(result[lane][0].pop("roi_wow_pct"), -6.129765501149487)
            self.assertEqual(result[lane], [self.row])
        self.assertEqual(self.market, before)

    def test_real_cell_renderer_uses_precise_delta_and_respects_null(self):
        template = (ROOT / "scripts/weekly_report/template/report_v2_template.html").read_text()
        code = template[template.index("      function bucketMetricCell("):template.index("      function losingCriteria(")]
        script = """
const vm = require('node:vm');
const input = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const context = {row: input.row, tone: () => '', pct: v => v.toFixed(1)+'%',
  bucketWeekLines: () => '', bucketRelative: (a,b) => (a/b-1)*100};
vm.createContext(context);
vm.runInContext(input.code, context);
process.stdout.write(vm.runInContext("bucketMetricCell(row, 'roi', v => v+'%')", context));
"""
        for value, expected in [(-6.129765501149487, "-6.1% vs LW"), (0, "0.0% vs LW"), (None, "vs LW —")]:
            row = {**self.row, "roi_wow_pct": value}
            result = subprocess.run([shutil.which("node"), "-e", script], input=json.dumps({"code": code, "row": row}),
                                    text=True, capture_output=True, check=True, timeout=20)
            self.assertIn(expected, result.stdout)
            self.assertNotIn("-5.9%", result.stdout)


if __name__ == "__main__":
    unittest.main()
