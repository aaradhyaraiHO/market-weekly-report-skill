"""Levers disclosure changes presentation, never source rows or metrics."""
import json
import shutil
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / 'scripts/weekly_report/template/report_v2_template.html'


class Tags(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class LeversDisclosure(unittest.TestCase):
    def render(self, item):
        template = TEMPLATE.read_text()
        helpers = template[template.index('      const money = '):template.index('      const el = ')]
        renderer = template[template.index('      const legacyCe='):template.index('      const NOTES_URL=')]
        harness = """
const vm = require('node:vm');
const input = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const root = {innerHTML: ''};
const before = JSON.stringify(input.item);
vm.runInNewContext(input.code + '\\nrenderLevers(item);', {
  item: input.item, Intl, document: {getElementById: id => {
    if (id !== 'levers-section') throw new Error('Unexpected render target');
    return root;
  }}
});
if (JSON.stringify(input.item) !== before) throw new Error('Source data mutated');
process.stdout.write(root.innerHTML);
"""
        result = subprocess.run([shutil.which('node'), '-e', harness], input=json.dumps({
            'code': helpers + renderer, 'item': item,
        }), capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_default_closed_native_disclosure_keeps_both_empty_sections(self):
        html = self.render({})
        tags = Tags(html).tags
        self.assertEqual(tags[0], ('details', {'class': 'legacy-card legacy-disclosure'}))
        self.assertEqual(tags[1], ('summary', {'class': 'legacy-card-head'}))
        self.assertEqual(sum(tag == 'section' for tag, _ in tags), 2)
        self.assertIn('0 tagged · 0 PP CEs', html)
        self.assertIn('No CEs currently tagged', html)
        self.assertIn('No active prepurchase allotments', html)

    def test_populated_disclosure_retains_all_rows_counts_and_values(self):
        html = self.render({'post_diagnostic': {
            'levers': [{'ce_id': '1', 'ce_name': 'Test <lever>', 'lever': 'marketing_budget',
                        'weekly_perf_summary': {'revenue_wk': 1234, 'roi_pct': 142, 'wow_pct': -5}}],
            'prepurchase': [{'ce_id': str(i), 'ce': f'PP CE {i}', 'open_ct': 2107,
                            'dated': 0, 'loss_liab_dated': 0, 'sold_last_wk': 0,
                            'net_roi': 142, 'cvr': 2.5, 'cvr_wow': -21.7} for i in range(22)],
        }})
        self.assertIn('1 tagged · 22 PP CEs', html)
        self.assertEqual(html.count('data-post-ce='), 23)
        self.assertIn('Test &lt;lever&gt;', html)
        self.assertIn('$1.2K', html)
        self.assertIn('142%', html)
        self.assertIn('2.5%', html)
        self.assertIn('−21.7%', html)
        self.assertIn('Source &amp; definitions', html)

    def test_disclosure_has_focus_indicator_mobile_target_and_static_chevron(self):
        template = TEMPLATE.read_text()
        self.assertIn('.legacy-disclosure > summary { min-height:44px; flex-wrap:wrap;', template)
        self.assertIn('.legacy-disclosure > summary:focus-visible', template)
        self.assertIn('.legacy-disclosure:not([open]) > summary { border-bottom:0; }', template)
        self.assertIn(".legacy-disclosure[open] > summary .bucket-count::after { content:'▾'; }", template)


if __name__ == '__main__':
    unittest.main()
