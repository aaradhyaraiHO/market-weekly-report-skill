"""Navigation-only full-notebook staging; never regenerates data or deploys.

Requires a verified preservation inventory. Inserts markup without replacing any
existing bytes, and checks that removing those insertions restores each original.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from notebook_tools import render_tools_nav
from release_integrity import files, seed, browser_fingerprint


def patch_page(html):
    if 'id="notebook-tools"' in html:
        raise ValueError('Tools menu already exists; refusing duplicate patch')
    edits = []
    menu = render_tools_nav()
    if '<header class="topbar"' in html:
        start = html.index('<header class="topbar"')
        edits.append((html.index('</header>', start), menu))
        css = '''<style id="notebook-tools-layout">
.topbar{position:sticky;top:0;z-index:10}.topbar>.filters{margin-left:auto}
@media(max-width:560px){.topbar{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;padding:12px 18px}.topbar>div:first-child{grid-column:1/-1}.topbar>.filters{min-width:0;margin:0}.topbar .filter-field{min-width:0}}
</style>'''
        edits.append((html.index('</head>'), css))
        kind = 'weekly-v2'
    elif '<!-- NAV -->' in html or 'The Weekly Ledger' in html:
        start = html.index('<!-- NAV -->') if '<!-- NAV -->' in html else html.index('<body>')
        outer = re.search(r'<div\b[^>]*>', html[start:])
        row_start = html.index('<div', start + outer.end())
        row_end = html.index('>', row_start)
        tag = html[row_start:row_end]
        cls = re.search(r'class="([^"]*)"', tag)
        if cls:
            edits.append((row_start + cls.end(1), ' notebook-nav-row'))
        else:
            edits.append((row_end, ' class="notebook-nav-row"'))
        depth = 1
        for match in re.finditer(r'</?div\b[^>]*>', html[row_end + 1:]):
            depth += -1 if match.group().startswith('</') else 1
            if depth == 0:
                edits.append((row_end + 1 + match.start(), menu))
                break
        else:
            raise ValueError('Navbar row closing tag missing')
        kind = 'ledger-or-monthly'
    elif 'id="report-data"' in html and '<div class="page">' in html:
        # V1 archives have no static navbar; retain their original report intact.
        toolbar = '<style id="notebook-tools-archive-layout">.jumpnav{top:61px;z-index:9}</style><nav aria-label="Notebook tools" style="position:sticky;top:0;z-index:10;display:flex;justify-content:flex-end;padding:8px 16px;background:#fff;border-bottom:1px solid #E7E1F1">' + menu + '</nav>'
        edits.append((html.index('<body>') + len('<body>'), toolbar))
        kind = 'weekly-v1-archive'
    else:
        raise ValueError('Unknown notebook page layout')
    output = html
    for offset, addition in sorted(edits, reverse=True):
        output = output[:offset] + addition + output[offset:]
    restored = output
    for offset, addition in sorted(edits):
        assert restored[offset:offset + len(addition)] == addition
        restored = restored[:offset] + restored[offset + len(addition):]
    assert restored == html
    assert output.count('id="notebook-tools"') == 1
    return output, kind


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    expected = json.loads(args.inventory.read_text())
    before = files(args.base)
    if before != expected['files']:
        raise ValueError('Base notebook differs from verified inventory')
    identity = json.loads((args.base / '.vercel/project.json').read_text())
    if identity['projectId'] != 'prj_BSPLExXUAkqYlGKYp4LYCH4vAak7' or identity['projectName'] != 'market-notebook':
        raise ValueError('Wrong deployment project; expected market-notebook')
    seed(args.base, args.out)
    changed = {}
    for page in sorted(args.out.glob('*.html')):
        original = page.read_text()
        output, kind = patch_page(original)
        page.write_text(output)
        changed[page.name] = {'kind': kind, 'sha256': hashlib.sha256(output.encode()).hexdigest(),
                              'browser_sha256': browser_fingerprint(output),
                              'browser_components': browser_fingerprint(output, components=True)}
    after = files(args.out)
    assert before.keys() == after.keys()
    assert all(before[name] == after[name] for name in before if name not in changed)
    receipt = {'schema': 'notebook-tools-navigation/v1', 'base_deployment_id': expected['deployment_id'],
               'base_notebook': str(args.base.resolve()), 'notebook': str(args.out.resolve()),
               'project': identity, 'changed': changed, 'unchanged_files': len(before) - len(changed),
               'original_page_bytes_preserved': True, 'files': after}
    (args.out.parent / 'preservation.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'pages': len(changed), 'unchanged_files': receipt['unchanged_files'],
                      'layouts': dict(Counter(row['kind'] for row in changed.values()))}))


if __name__ == '__main__':
    main()
