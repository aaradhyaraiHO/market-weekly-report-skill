"""Full-notebook preservation and authenticated exact-artifact release gates."""
import argparse
import datetime as dt
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import shutil
import sys
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'alert' / 'v2'))
import config
from weekly_alert_v2 import LEDGER_SLUG, _report_data
from safe_delivery import atomic_json, digest

IGNORED = {'.git', '.vercel', 'node_modules', '__pycache__'}


def browser_fingerprint(html, components=False):
    class Parser(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.entries = []
            self.active = None
        def handle_starttag(self, tag, attrs):
            if tag in ('script', 'style'):
                self.active = {'tag': tag, 'text': '', 'src': dict(attrs).get('src', '')}
                self.entries.append(self.active)
        def handle_endtag(self, tag):
            if tag in ('script', 'style'):
                self.active = None
        def handle_data(self, text):
            if self.active is not None:
                self.active['text'] += text
    parser = Parser()
    parser.feed(html)
    if components:
        counts = {}
        result = []
        for row in parser.entries:
            selector = ('script[src=' + json.dumps(row['src']) + ']' if row['src'] else
                        'script:not([src])' if row['tag'] == 'script' else 'style')
            index = counts.get(selector, 0)
            counts[selector] = index + 1
            result.append({'tag': row['tag'], 'src': row['src'], 'selector': selector, 'index': index})
        return result
    parts = [{'tag': row['tag'], 'sha256': hashlib.sha256(row['text'].encode()).hexdigest(), 'src': row['src']}
             for row in parser.entries]
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def verify_browser(manifest, observations):
    """Validate fresh observations captured via the user's signed-in browser.

    No cookie extraction or HTTP-auth bypass. The Codex browser agent visits
    each route and reads the DOM script/style text that drives the report UI.
    """
    if len(observations) != len(manifest['browser_files']):
        raise ValueError('Incomplete browser route coverage')
    seen = set()
    for row in observations:
        name = row['file']
        route = '/' if name == 'index.html' else '/' + name.removesuffix('.html')
        if name in seen or name not in manifest['browser_files']:
            raise ValueError('Unexpected/duplicate browser route')
        seen.add(name)
        if row['url'] != 'https://market-notebook.vercel.app' + route or row['sha256'] != manifest['browser_files'][name]:
            raise ValueError(f'Browser payload/code or route mismatch: {name}')
        if not row.get('visible_text'):
            raise ValueError(f'No visible browser evidence: {name}')
        observed = dt.datetime.fromisoformat(row['observed_at'])
        age = (dt.datetime.now(dt.timezone.utc) - observed).total_seconds()
        if not 0 <= age <= 3600:
            raise ValueError('Browser evidence must be captured within the last hour')
    return {'week': manifest['week'], 'status': 'verified', 'method': 'signed-in-browser',
            'manifest_sha256': hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
            'observations': observations, 'verified_at': dt.datetime.now(dt.timezone.utc).isoformat()}


def completed_week(week, today=None):
    start = dt.date.fromisoformat(week)
    today = today or dt.datetime.now(ZoneInfo('Asia/Kolkata')).date()
    if start.weekday() != 6 or start + dt.timedelta(days=7) > today:
        raise ValueError('Release requires a completed Sunday–Saturday week')


def files(root):
    result = {}
    for path in root.rglob('*'):
        rel = path.relative_to(root)
        if any(p in IGNORED or p.startswith('.env') for p in rel.parts):
            continue
        if path.is_symlink():
            raise ValueError(f'Symlink not allowed in release: {rel}')
        if path.is_file():
            result[rel.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def seed(base, target):
    base, target = base.resolve(), target.resolve()
    if base == target or base in target.parents or target in base.parents:
        raise ValueError('Use separate non-nested source and staging directories')
    for name in ('index.html', 'middleware.js', 'vercel.json', 'package.json', 'api/review.js', 'api/review-summary.js'):
        if not (base / name).is_file():
            raise ValueError(f'Incomplete base notebook: {name}')
    if target.exists() and any(target.iterdir()):
        raise ValueError('Staging directory must be empty; never overwrite a previous release')
    for name in files(base):
        dest = target / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(base / name, dest)
    # Project identity only, never copy credentials or build cache.
    project = base / '.vercel' / 'project.json'
    if project.exists():
        (target / '.vercel').mkdir(exist_ok=True)
        shutil.copy2(project, target / '.vercel' / 'project.json')


def report_names(week):
    routes = [LEDGER_SLUG[s] for s in (*config.MARKETS, 'headout')] + ['csee-nordics']
    return [f'weekly-report-{r}{suffix}.html' for r in routes for suffix in ('', '-' + week)]


def verify_artifact(base, target, week):
    completed_week(week)
    before, after = files(base), files(target)
    names = report_names(week)
    mutable = set(names) | {'weekly.html', 'weekly_state.json'}
    failures = [name for name, sha in before.items() if name not in mutable and after.get(name) != sha]
    if failures:
        raise ValueError(f'Notebook/history changed or removed outside this release: {failures}')
    additions = sorted(after.keys() - before.keys() - mutable)
    if additions:
        raise ValueError(f'Unexpected files added outside this release: {additions}')
    headlines = {}
    for slug in (*config.MARKETS, 'headout'):
        route = LEDGER_SLUG[slug]
        current = target / f'weekly-report-{route}.html'
        dated = target / f'weekly-report-{route}-{week}.html'
        if not current.exists() or not dated.exists() or current.read_bytes() != dated.read_bytes():
            raise ValueError(f'{slug}: latest and exact-week artifacts differ or are missing')
        rows = [r for r in _report_data(current)['headlines'] if r.get('market_slug') == slug]
        if not rows or max(r['week_start'] for r in rows) != week:
            raise ValueError(f'{slug}: latest report week differs')
        headlines[slug] = digest(next(r for r in rows if r['week_start'] == week))
    shared = target / 'weekly-report-csee-nordics.html'
    if shared.read_bytes() != (target / f'weekly-report-csee-nordics-{week}.html').read_bytes():
        raise ValueError('Shared CSEE/Nordics latest route differs')
    for slug in ('csee', 'nordics'):
        rows = [r for r in _report_data(shared)['headlines'] if r.get('market_slug') == slug]
        if not rows or max(r['week_start'] for r in rows) != week:
            raise ValueError(f'Shared report missing latest {slug}')
    return {'schema': 'weekly-v2-artifact/v1', 'week': week,
            'headlines': headlines,
            'browser_files': {name: browser_fingerprint((target / name).read_text())
                              for name in [*names, 'index.html', 'weekly.html']},
            'browser_components': {name: browser_fingerprint((target / name).read_text(), components=True)
                                   for name in [*names, 'index.html', 'weekly.html']},
            'preserved_files': len(before.keys() - mutable),
            'files': {name: after[name] for name in [*names, 'index.html', 'weekly.html', 'weekly_state.json']}}


def verify_live(manifest, base_url, cookie=None, session=None):
    if base_url.rstrip('/') != 'https://market-notebook.vercel.app':
        raise ValueError('Verify the canonical production hostname, not a preview alias')
    session = session or requests.Session()
    headers = {'Cookie': cookie} if cookie else {}
    verified = []
    for name, sha in manifest['files'].items():
        route = '/' if name == 'index.html' else '/' + name.removesuffix('.html')
        response = session.get(base_url.rstrip('/') + route, headers=headers,
                               allow_redirects=False, timeout=90)
        if response.status_code != 200 or hashlib.sha256(response.content).hexdigest() != sha:
            raise ValueError(f'Live artifact mismatch/authentication required: {route} (HTTP {response.status_code})')
        verified.append(route)
    return {'week': manifest['week'], 'status': 'verified', 'routes': verified,
            'manifest_sha256': hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
            'verified_at': dt.datetime.now(dt.timezone.utc).isoformat()}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['seed', 'artifact', 'live', 'browser'])
    p.add_argument('--base', type=Path)
    p.add_argument('--target', type=Path)
    p.add_argument('--week')
    p.add_argument('--manifest', type=Path)
    p.add_argument('--out', type=Path)
    p.add_argument('--observations', type=Path)
    args = p.parse_args()
    if args.mode == 'seed':
        completed_week(args.week)
        seed(args.base, args.target)
    elif args.mode == 'artifact':
        atomic_json(args.manifest, verify_artifact(args.base, args.target, args.week))
    elif args.mode == 'browser':
        atomic_json(args.out, verify_browser(json.loads(args.manifest.read_text()), json.loads(args.observations.read_text())))
    else:
        manifest = json.loads(args.manifest.read_text())
        result = verify_live(manifest, 'https://market-notebook.vercel.app', os.environ.get('WEEKLY_VERIFY_COOKIE'))
        atomic_json(args.out, result)


if __name__ == '__main__':
    main()
