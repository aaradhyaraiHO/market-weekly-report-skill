"""Frozen V2 delivery with write-ahead state and read-back verification.

Never overwrites an existing Slack message. Ambiguous sends are reconciled by
stable client IDs; absence after an ambiguous send is not permission to resend.
The caller must persist BOTH the existing ledger and this journal on its runner.
"""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import uuid

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from post_message import expand_blocks, chunk_blocks, normalize_to_messages, validate_payload


# Only the emoji emitted by this alert/RCA format. Unknown rewrites fail closed.
# Slack returns Unicode emoji as colon aliases and escapes &, <, > on read-back:
# https://docs.slack.dev/messaging/formatting-message-text/
SLACK_EMOJI = {
    '📊': ':bar_chart:', '📈': ':chart_with_upwards_trend:',
    '📉': ':chart_with_downwards_trend:', '📋': ':clipboard:',
    '📝': ':memo:', '🎯': ':dart:', '🧵': ':thread:',
    '🚦': ':vertical_traffic_light:', '🔴': ':red_circle:',
    '🟢': ':large_green_circle:', '🟡': ':large_yellow_circle:',
    '⚪': ':white_circle:', '⭐': ':star:',
    '🔻': ':small_red_triangle_down:', '🔺': ':small_red_triangle:',
    '➖': ':heavy_minus_sign:', '🛠️': ':hammer_and_wrench:',
    '📎': ':paperclip:',
}


def slack_text(value):
    """Compare display-equivalent text without changing frozen payload hashes.

    Decode only Slack's three supported entities, once. Do not strip markup,
    whitespace, mentions, numbers, or link destinations to force a match.
    """
    entities = {'&amp;': '&', '&lt;': '<', '&gt;': '>'}
    value = re.sub(r'&(?:amp|lt|gt);', lambda m: entities[m[0]], value)
    for unicode, alias in SLACK_EMOJI.items():
        value = value.replace(unicode, alias)
    return value


def stable(value):
    if isinstance(value, dict):
        return {k: stable(v) for k, v in value.items() if k != 'block_id'}
    if isinstance(value, list):
        return [stable(v) for v in value]
    return value


def digest(value):
    return hashlib.sha256(json.dumps(stable(value), sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def matches(expected, actual):
    """Slack may add defaults/IDs; all authored fields must still match."""
    expected, actual = stable(expected), stable(actual)
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        for key, value in expected.items():
            if key not in actual:
                return False
            if key == 'text' and isinstance(value, str) and expected.get('type') in ('mrkdwn', 'plain_text', 'text'):
                if not isinstance(actual[key], str) or slack_text(value) != slack_text(actual[key]):
                    return False
            elif not matches(value, actual[key]):
                return False
        return True
    if isinstance(expected, list):
        return isinstance(actual, list) and len(expected) == len(actual) and all(matches(a, b) for a, b in zip(expected, actual))
    return expected == actual


def compile_market(slug, week, channel, payload, rca):
    validate_payload(payload)
    if len(payload.get('messages', [])) != 2:
        raise ValueError(f'{slug}: expected the two approved parent alerts')
    handoff = payload.get('_rca') or {}
    if handoff.get('week_start') != week:
        raise ValueError(f'{slug}: RCA week mismatch')
    refs = [str(t['$rca']) for m in payload.get('messages', []) for t in m.get('threads', []) if '$rca' in t]
    if set(refs) != set(map(str, handoff.get('ce_ids', []))):
        raise ValueError(f'{slug}: CE/RCA handoff mismatch')
    for ce in refs:
        entry = rca.get(ce)
        if (not isinstance(entry, dict) or not entry.get('blocks') or entry.get('error')
                or 'insufficient data' in entry.get('fallback', '').lower()):
            raise ValueError(f'{slug}: missing/failed RCA for {ce}')
    operations = []
    for index, message in enumerate(normalize_to_messages(payload, None)):
        parent = f'msg{index+1}'
        pieces = [(parent, None, message)]
        for ti, thread in enumerate(message.get('threads', [])):
            pieces.append((f'{parent}/reply{ti}', parent, rca[str(thread['$rca'])] if '$rca' in thread else thread))
        for key, anchor, entry in pieces:
            blocks = expand_blocks(entry['blocks'])
            if not blocks:
                raise ValueError(f'{slug}: empty message {key}')
            for ci, chunk in enumerate(chunk_blocks(blocks)):
                opkey = key if ci == 0 else f'{key}/chunk{ci}'
                operations.append({'key': opkey, 'anchor': anchor if ci == 0 else (anchor or parent),
                                   'blocks': chunk, 'text': entry.get('fallback', 'Weekly market alert'),
                                   'client_msg_id': str(uuid.uuid5(uuid.NAMESPACE_URL, f'weekly-v2:{channel}:{slug}:{week}:{opkey}'))})
    return {'slug': slug, 'week': week, 'channel': channel, 'operations': operations}


def read_json(path, default):
    if not path.exists():
        return default
    value = json.loads(path.read_text())  # Corrupt state must never become an empty ledger.
    if not isinstance(value, dict):
        raise ValueError(f'Invalid state: {path}')
    return value


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False, mode='w') as out:
        temp = Path(out.name)
        try:
            json.dump(value, out, indent=2)
            out.flush(); os.fsync(out.fileno()); out.close()
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)


@contextmanager
def locked(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


class Slack:
    def __init__(self, token):
        self.session = requests.Session()
        self.session.headers['Authorization'] = 'Bearer ' + token

    def call(self, method, payload, write=False):
        response = (self.session.post('https://slack.com/api/'+method, json=payload, timeout=30)
                    if write else self.session.get('https://slack.com/api/'+method, params=payload, timeout=30))
        if response.status_code != 200:
            raise RuntimeError(f'Slack {method}: HTTP {response.status_code}; no automatic send retry')
        result = response.json()
        if not result.get('ok'):
            raise RuntimeError(f"Slack {method}: {result.get('error', 'unknown error')}")
        return result

    def messages(self, channel, week, parent=None):
        import datetime as dt
        payload = {'channel': channel, 'limit': 100}
        method = 'conversations.replies' if parent else 'conversations.history'
        if parent:
            payload['ts'] = parent
        else:
            payload['oldest'] = str(dt.datetime.fromisoformat(week).replace(tzinfo=dt.timezone.utc).timestamp())
        rows = []
        for _ in range(200):
            result = self.call(method, payload)
            rows.extend(result.get('messages', []))
            cursor = (result.get('response_metadata') or {}).get('next_cursor')
            if not cursor:
                if result.get('has_more'):
                    raise RuntimeError('Slack pagination incomplete')
                return rows
            payload['cursor'] = cursor
        raise RuntimeError('Slack history exceeded bounded scan; no send permitted')

    def post(self, channel, operation, parent=None):
        payload = {k: operation[k] for k in ('blocks', 'text', 'client_msg_id')}
        payload['channel'] = channel
        if parent:
            payload['thread_ts'] = parent
        return self.call('chat.postMessage', payload, write=True)['ts']


def deliver_market(market, slack, ledger_path, state_dir, verify_only=False):
    slug, week, channel = (market[k] for k in ('slug', 'week', 'channel'))
    state_path = state_dir / f'{week}_{slug}.json'
    ledger = read_json(ledger_path, {})
    prior = ledger.get(week, {}).get(slug, {})
    if prior.get('channel') and prior['channel'] != channel:
        raise ValueError(f'{slug}: existing ledger channel differs')
    had_journal = state_path.exists()
    state = read_json(state_path, {'plan_hash': digest(market), 'operations': {}})
    if state.get('plan_hash') != digest(market):
        raise ValueError(f'{slug}: frozen delivery plan changed; use the original prepared bundle')
    anchors, found = {}, {}
    cache = {None: slack.messages(channel, week)}
    # A legacy ledger has no per-reply journal. Reconcile every parent before
    # allowing any missing reply; never create a replacement legacy parent.
    if prior and not had_journal:
        for op in market['operations']:
            if op['anchor'] is not None:
                continue
            ts = prior.get(op['key'] + '_ts')
            rows = [m for m in cache[None] if ts and m.get('ts') == ts]
            if len(rows) != 1 or not matches(op['blocks'], rows[0].get('blocks')):
                raise ValueError(f'{slug}: incomplete or changed legacy parents require reconciliation')
    for operation in market['operations']:
        key = operation['key']
        parent = anchors.get(operation['anchor']) if operation['anchor'] else None
        if operation['anchor'] and not parent:
            raise ValueError(f'{slug}: parent not resolved for {key}')
        if parent not in cache:
            cache[parent] = slack.messages(channel, week, parent)
        rows = cache[parent]
        record = state['operations'].get(key, {})
        ts = record.get('ts') or (prior.get(key+'_ts') if operation['anchor'] is None else None)
        candidates = [m for m in rows if (ts and m.get('ts') == ts) or m.get('client_msg_id') == operation['client_msg_id']]
        if not candidates and not ts and not record:
            candidates = [m for m in rows if matches(operation['blocks'], m.get('blocks'))
                          and isinstance(m.get('text'), str) and slack_text(m['text']) == slack_text(operation['text'])]
        if len(candidates) > 1:
            raise ValueError(f'{slug}/{key}: duplicate matching messages; manual reconciliation required')
        if candidates:
            message = candidates[0]
            if not matches(operation['blocks'], message.get('blocks')):
                raise ValueError(f'{slug}/{key}: existing Slack content differs; not overwriting')
            ts = message['ts']
        else:
            if ts or record.get('status') == 'sending' or verify_only:
                raise ValueError(f'{slug}/{key}: missing or ambiguous Slack receipt; not resending')
            # All legacy parents must be present and matching before adding any reply.
            if prior and not had_journal and operation['anchor'] is None:
                raise ValueError(f'{slug}/{key}: incomplete legacy ledger requires reconciliation')
            state['operations'][key] = {'status': 'sending'}
            atomic_json(state_path, state)
            ts = slack.post(channel, operation, parent)
            cache[parent].append({**operation, 'ts': ts})
        anchors[key] = ts
        found[key] = ts
        if not verify_only:
            state['operations'][key] = {'status': 'acknowledged', 'ts': ts}
            atomic_json(state_path, state)
            if operation['anchor'] is None:
                ledger = read_json(ledger_path, {})
                entry = ledger.setdefault(week, {}).setdefault(slug, {})
                entry.update(channel=channel, **{key+'_ts': ts})
                atomic_json(ledger_path, ledger)
    # Fresh API reads, not just chat.postMessage acknowledgements, close the run.
    verified = {}
    for operation in market['operations']:
        parent = anchors.get(operation['anchor']) if operation['anchor'] else None
        if parent not in verified:
            verified[parent] = slack.messages(channel, week, parent)
        matches_ts = [m for m in verified[parent] if m.get('ts') == found[operation['key']]]
        duplicates = [m for m in verified[parent] if m.get('client_msg_id') == operation['client_msg_id']]
        if len(duplicates) > 1 or len(matches_ts) != 1 or not matches(operation['blocks'], matches_ts[0].get('blocks')):
            raise ValueError(f"{slug}/{operation['key']}: final Slack verification failed")
    if not verify_only:
        state['status'] = 'verified'
        atomic_json(state_path, state)
    return {'market': slug, 'status': 'verified', 'messages': len(found)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--ledger', type=Path, required=True)
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--verified-release', type=Path, required=True)
    parser.add_argument('--artifact', type=Path, required=True)
    args = parser.parse_args()
    bundle = json.loads(args.bundle.read_text())
    validate_bundle(bundle)
    proof = json.loads(args.verified_release.read_text())
    artifact = json.loads(args.artifact.read_text())
    artifact_hash = hashlib.sha256(json.dumps(artifact, sort_keys=True).encode()).hexdigest()
    if (proof.get('status') != 'verified' or proof.get('week') != bundle['week']
            or proof.get('manifest_sha256') != artifact_hash):
        raise ValueError('Exact-week live deployment has not been verified')
    for market in bundle['markets']:
        if not market.get('headline_sha256') or artifact.get('headlines', {}).get(market['slug']) != market['headline_sha256']:
            raise ValueError(f"{market['slug']}: prepared alert does not match the deployed headline")
    # Recheck now, including on delivery retries. A prior receipt is not proof
    # that production still serves this artifact.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts' / 'weekly_report'))
    from release_integrity import verify_live, verify_browser
    if proof.get('method') == 'signed-in-browser':
        verify_browser(artifact, proof.get('observations', []))
    else:
        verify_live(artifact, 'https://market-notebook.vercel.app', os.environ.get('WEEKLY_VERIFY_COOKIE'))
    token = os.environ.get('REVENUE_ALERT_SLACK_TOKEN')
    if not token:
        raise ValueError('REVENUE_ALERT_SLACK_TOKEN is required')
    slack = Slack(token)
    from delivery_access import check_access
    access = check_access(slack, {m['slug']: m['channel'] for m in bundle['markets']}, read_json(args.ledger, {}))
    if not all(row['readable'] for row in access):
        raise ValueError(f'Slack read-back preflight failed; no messages sent: {access}')
    with locked(args.ledger.with_suffix('.lock')):
        results = [deliver_market(m, slack, args.ledger, args.state_dir, args.verify_only) for m in bundle['markets']]
    print(json.dumps(results))


def validate_bundle(bundle):
    if bundle.get('schema') != 'weekly-v2-delivery/v1' or not bundle.get('markets'):
        raise ValueError('Invalid frozen delivery bundle')
    if bundle.get('sha256') != digest(bundle['markets']):
        raise ValueError('Frozen delivery bundle checksum differs')
    scopes = [m['slug'] for m in bundle['markets']]
    if len(scopes) != len(set(scopes)):
        raise ValueError('Duplicate market in delivery bundle')
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts' / 'weekly_report'))
    import config
    if set(scopes) != {*config.MARKETS, 'headout'}:
        raise ValueError('Delivery bundle must include all 17 markets and Headout')
    import datetime as dt
    from zoneinfo import ZoneInfo
    week = dt.date.fromisoformat(bundle['week'])
    if week.weekday() != 6 or week + dt.timedelta(days=7) > dt.datetime.now(ZoneInfo('Asia/Kolkata')).date():
        raise ValueError('Only completed Sunday–Saturday weeks may be delivered')
    for market in bundle['markets']:
        if market['week'] != bundle['week'] or not market.get('channel'):
            raise ValueError('Market week/channel mismatch')


if __name__ == '__main__':
    main()
