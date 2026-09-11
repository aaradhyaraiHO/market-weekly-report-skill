"""Read-only Slack access check for all markets, including private Headout."""
import json
import os
from pathlib import Path
from safe_delivery import Slack


def check_access(slack, channels, ledger):
    results = []
    for slug, channel in channels.items():
        try:
            slack.call('conversations.history', {'channel': channel, 'limit': 1})
            prior = next((rows[slug] for _, rows in sorted(ledger.items(), reverse=True)
                          if slug in rows and rows[slug].get('channel') == channel and rows[slug].get('msg2_ts')), None)
            if prior:
                slack.call('conversations.replies', {'channel': channel, 'ts': prior['msg2_ts'], 'limit': 1})
            results.append({'market': slug, 'readable': True})
        except Exception as exc:
            results.append({'market': slug, 'readable': False, 'error': str(exc)})
    return results


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[2]
    import sys
    sys.path.insert(0, str(root / 'scripts' / 'weekly_report'))
    import config
    channels = json.loads((root / 'alert' / 'market_channels.json').read_text())['markets']
    results = check_access(Slack(os.environ['REVENUE_ALERT_SLACK_TOKEN']),
                           {s: channels[s] for s in (*config.MARKETS, 'headout')},
                           json.loads((root / 'alert' / 'posted_ledger.json').read_text()))
    print(json.dumps(results, indent=2))
    raise SystemExit(0 if all(r['readable'] for r in results) else 1)
