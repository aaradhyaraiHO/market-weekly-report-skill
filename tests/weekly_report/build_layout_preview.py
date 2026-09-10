"""Local-only layout preview from the frozen published page. No live integration."""
import argparse
import hashlib
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/weekly_report'))
import inject_review_view

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('source', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
original = args.source.read_text()
template = (ROOT / 'scripts/weekly_report/template/report_v2_template.html').read_text()
start = '      function updateFloatingHeader(){'
end = '      function scheduleFloatingHeader()'
new_start = '      function floatingTableBounds('
html = original[:original.index(start)] + template[template.index(new_start):template.index(end)] + original[original.index(end):]
# Apply only the navigation shell changes to the frozen report. Keep the original
# nav buttons so the live-review injector retains its existing compatibility.
css_start = '    /* Collapsible report navigation:'
css_end = '    /* End collapsible report navigation. */'
css = template[template.index(css_start):template.index(css_end) + len(css_end)]
html = html.replace('    .main { min-width:0; }', css + '\n    .main { min-width:0; }', 1)
html = html.replace('<aside class="rail">', '<aside class="rail" id="report-sidebar">', 1)
toggle = next(line for line in template.splitlines() if '<button class="rail-toggle"' in line)
html = html.replace('      <nav class="nav"', toggle + '\n      <nav class="nav"', 1)
js_start = '      function toggleReportSidebar()'
js_end = '      payload.headlines.forEach((item,index)=>'
html = html.replace(js_end, template[template.index(js_start):template.index(js_end)] + js_end, 1)
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(html)
assert inject_review_view.inject(args.output, args.output.parent)
data = re.compile(r'<script id="report-data" type="application/json">(.*?)</script>', re.S)
old_payload = data.search(original).group(1)
assert data.search(args.output.read_text()).group(1) == old_payload
print('Frozen report JSON byte-preserved: ' + hashlib.sha256(old_payload.encode()).hexdigest())
