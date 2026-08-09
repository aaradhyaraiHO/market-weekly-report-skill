#!/bin/bash
# Perf-sheet GM-comment re-export.
#
# The perf Weekly Flagged sheet is a POINT-IN-TIME export of GM actions/comments — it only
# refreshes when export_perf_sheet runs (on publish-all, or here). GM comments added in the
# reports mid-week don't reach perf until a re-export. This job pulls them 3x/day.
#
# Scheduled via launchd (11:00 / 15:00 / 19:00 IST): com.headout.weekly-perf-reexport
#   plist: ~/Library/LaunchAgents/com.headout.weekly-perf-reexport.plist
#   (a committed copy lives beside this script). launchd re-runs a MISSED calendar fire on
#   the next wake — a Mac asleep at the fire time still re-exports when it wakes.
#
# Runs under launchd's minimal env — PATH set explicitly for homebrew python3 + gws. Writes
# ONLY the GM columns of the perf sheet (perf's 3 columns are never touched); the write is
# main-checkout-guarded inside export_perf_sheet. No Vercel deploy — this is a Sheet write only.
set -uo pipefail

export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
REPO="$HOME/market-weekly-report-skill"
LOG="$REPO/.cache/weekly_report/perf_reexport_cron.log"
# Reuse the failure webhook already stored in the analytics OKR job (single source of truth).
WEBHOOK="$(grep -oE 'https://hooks\.slack\.com/services/[A-Za-z0-9/_-]+' "$HOME/analytics/run_kr_update.py" 2>/dev/null | head -1)"

alert() {  # best-effort Slack failure ping — never blocks or fails the run
  [ -n "$WEBHOOK" ] || return 0
  curl -sf -X POST -H 'Content-type: application/json' \
    --data "{\"text\":\"🔴 *Perf-sheet re-export FAILED* — $1\nHost: $(hostname -s) · $(date '+%Y-%m-%d %H:%M %Z')\nLog: \`$LOG\`\"}" \
    "$WEBHOOK" >/dev/null 2>&1 || true
}

mkdir -p "$(dirname "$LOG")"

{
  echo "──────────────────────────────────────────────────────────────"
  echo "$(date '+%Y-%m-%d %H:%M:%S %Z') · perf re-export START"
  cd "$REPO" || { echo "FATAL: cannot cd $REPO"; alert "cannot cd $REPO on the runner"; exit 1; }

  BR="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
  if [ "$BR" != "main" ]; then
    echo "· not on main (on '$BR') — refusing (publish-only-from-main). Soft skip."
    exit 0
  fi

  # Week defaults to config.latest_complete_week() inside the exporter.
  OUT="$(python3 scripts/weekly_report/export_perf_sheet.py --write 2>&1)"; RC=$?
  echo "$OUT"
  if [ "$RC" -ne 0 ]; then
    # Pre-Monday-build window: the new week's snapshots don't exist yet — not a real failure.
    if echo "$OUT" | grep -qi "no snapshot"; then
      echo "· no snapshot for the current week yet (pre-build) — soft skip."
      echo "$(date '+%Y-%m-%d %H:%M:%S %Z') · perf re-export SKIPPED"
      exit 0
    fi
    echo "✗ FAIL: export_perf_sheet exited $RC (auth / gws / sheet error)."
    alert "export_perf_sheet exited $RC — GM comments may be stale in the perf sheet. See log."
    exit 1
  fi
  echo "$(date '+%Y-%m-%d %H:%M:%S %Z') · perf re-export DONE"
} >> "$LOG" 2>&1
