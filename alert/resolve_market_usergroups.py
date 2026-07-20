#!/usr/bin/env python3
"""Resolve each market's growth/team Slack usergroup → subteam ID (needs usergroups:read).

Run once after `usergroups:read` is added to the bot token + the app reinstalled.
Lists all usergroups, then for each market slug prints the best-matching group's
handle + ID so you can paste a real-mention map into weekly_alert.py
(MARKET_TEAM → "<!subteam^ID>").

A <!subteam^ID> mention in a Block Kit block DOES notify the group (unlike @handle text).

Usage:
    REVENUE_ALERT_SLACK_TOKEN="xoxb-…" python3 resolve_market_usergroups.py
"""
import json, os, sys, urllib.request, urllib.parse

API = "https://slack.com/api/"

# candidate handle fragments per market slug (growth team first, then market shorthand)
MARKET_HINTS = {
    "north_america":  ["growth-north-america", "growth-usa", "growth-us", "usa", "us"],
    "italy":          ["growth-italy", "growth-it", "italy", "it"],
    "oceania":        ["growth-oceania", "oceania", "anz", "australia"],
    "france":         ["growth-france", "growth-fr", "france", "fr"],
    "united_kingdom": ["growth-uk", "growth-united-kingdom", "uk", "united-kingdom"],
    "iberia":         ["growth-iberia", "iberia", "spain", "es"],
    "csee":           ["growth-csee", "csee"],
    "east_asia":      ["growth-east-asia", "east-asia", "japan", "jp", "korea"],
    "sea":            ["growth-sea", "sea", "singapore", "sin"],
    "uae":            ["growth-uae", "uae", "mena", "gcc"],
}


def call(method, token, **params):
    url = API + method + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())


def main():
    token = os.environ.get("REVENUE_ALERT_SLACK_TOKEN")
    if not token:
        sys.exit("Set REVENUE_ALERT_SLACK_TOKEN")
    r = call("usergroups.list", token)
    if not r.get("ok"):
        sys.exit(f"usergroups.list failed: {r.get('error')} "
                 "(need usergroups:read scope + app reinstall)")
    groups = [(g["handle"].lower(), g["id"], g.get("name", "")) for g in r.get("usergroups", [])]
    print(f"# {len(groups)} usergroups found. Suggested MARKET_TEAM subteam map:\n")
    for slug, hints in MARKET_HINTS.items():
        match = None
        for h in hints:
            match = next((g for g in groups if g[0] == h), None) or \
                    next((g for g in groups if h in g[0]), None)
            if match:
                break
        if match:
            print(f'    "{slug}": ("<!subteam^{match[1]}>", ""),   # @{match[0]} — {match[2]}')
        else:
            print(f'    "{slug}": (?, ""),   # NO MATCH — candidates: '
                  + ", ".join(f"@{h}({i})" for h, i, _ in groups if slug.split("_")[0][:3] in h)[:120])


if __name__ == "__main__":
    main()
