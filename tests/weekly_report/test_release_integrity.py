import datetime as dt
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts' / 'weekly_report'))
import release_integrity as gate


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base, self.target = self.root / 'base', self.root / 'target'
        for name in ('index.html', 'middleware.js', 'vercel.json', 'package.json', 'api/review.js', 'api/review-summary.js', 'old-report.html'):
            path = self.base / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(name)

    def test_seed_preserves_site_but_does_not_copy_secrets(self):
        (self.base / '.env.local').write_text('secret')
        gate.seed(self.base, self.target)
        self.assertEqual(gate.files(self.base), gate.files(self.target))
        self.assertFalse((self.target / '.env.local').exists())

    def test_seed_rejects_overwrite_and_incomplete_base(self):
        gate.seed(self.base, self.target)
        with self.assertRaisesRegex(ValueError, 'empty'):
            gate.seed(self.base, self.target)
        with self.assertRaisesRegex(ValueError, 'non-nested'):
            gate.seed(self.base, self.base)

    def test_history_mutation_fails_before_report_validation(self):
        gate.seed(self.base, self.target)
        (self.target / 'old-report.html').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'history changed'):
            gate.verify_artifact(self.base, self.target, '2026-08-30')

    def test_completed_week_boundary_ist(self):
        with self.assertRaises(ValueError):
            gate.completed_week('2026-09-06', dt.date(2026, 9, 12))
        gate.completed_week('2026-09-06', dt.date(2026, 9, 13))

    def test_new_api_or_archive_files_require_separate_approval(self):
        gate.seed(self.base, self.target)
        for name in ('api/unapproved.js', 'unrelated-archive.html'):
            with self.subTest(name=name):
                path = self.target / name
                path.write_text('unexpected')
                with self.assertRaisesRegex(ValueError, 'Unexpected files added'):
                    gate.verify_artifact(self.base, self.target, '2026-08-30')
                path.unlink()

    def test_login_redirect_and_wrong_week_are_not_success(self):
        manifest = {'week': '2026-08-30', 'files': {'weekly-report-headout.html': hashlib.sha256(b'correct').hexdigest()}}
        session = Mock()
        for code, body in ((302, b'login'), (200, b'old report')):
            session.get.return_value = Mock(status_code=code, content=body)
            with self.assertRaisesRegex(ValueError, 'mismatch'):
                gate.verify_live(manifest, 'https://market-notebook.vercel.app', session=session)
        session.get.return_value = Mock(status_code=200, content=b'correct')
        result = gate.verify_live(manifest, 'https://market-notebook.vercel.app', session=session)
        self.assertEqual(result['status'], 'verified')
        self.assertFalse(session.get.call_args.kwargs['allow_redirects'])

    def test_all_18_scopes_and_shared_routes_are_required(self):
        names = gate.report_names('2026-08-30')
        self.assertEqual(len(names), 38)
        self.assertIn('weekly-report-headout-2026-08-30.html', names)
        self.assertIn('weekly-report-csee-nordics-2026-08-30.html', names)

    def test_browser_requires_complete_matching_fresh_evidence(self):
        manifest = {'week': '2026-08-30', 'browser_files': {'weekly-report-headout.html': 'correct'}}
        row = {'file': 'weekly-report-headout.html', 'url': 'https://market-notebook.vercel.app/weekly-report-headout',
               'sha256': 'correct', 'visible_text': 'Headout 30 Aug–5 Sept 2026',
               'observed_at': dt.datetime.now(dt.timezone.utc).isoformat()}
        self.assertEqual(gate.verify_browser(manifest, [row])['method'], 'signed-in-browser')
        for bad in ([], [row, row], [{**row, 'sha256': 'old'}], [{**row, 'url': 'https://accounts.google.com'}],
                    [{**row, 'observed_at': '2026-01-01T00:00:00+00:00'}]):
            with self.assertRaises(ValueError):
                gate.verify_browser(manifest, bad)

    def test_browser_fingerprint_and_component_selectors(self):
        html = '<style>a{}</style><script id="report-data">{"week":"new"}</script>'
        expected = [{'tag': 'style', 'sha256': hashlib.sha256(b'a{}').hexdigest(), 'src': ''},
                    {'tag': 'script', 'sha256': hashlib.sha256(b'{"week":"new"}').hexdigest(), 'src': ''}]
        self.assertEqual(gate.browser_fingerprint(html), hashlib.sha256(json.dumps(expected, separators=(',', ':')).encode()).hexdigest())
        self.assertEqual(gate.browser_fingerprint(html, components=True)[1]['selector'], 'script:not([src])')
