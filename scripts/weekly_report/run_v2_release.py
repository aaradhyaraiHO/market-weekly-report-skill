#!/usr/bin/env python3
"""Build, verify, stage, and optionally publish a complete Weekly V2 release.

The default invocation is deliberately no-write outside the repository: it builds
all market reports plus Headout, runs compatibility gates, stages a self-contained
notebook, and dry-runs alerts. Production deployment and Slack posting require
explicit flags.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts" / "weekly_report"
CACHE = ROOT / ".cache" / "weekly_report"
V2_REPORTS = ROOT / "thoughts" / "shared" / "weekly-report-v2"

sys.path.insert(0, str(SCRIPTS))
import config  # noqa: E402


@dataclass(frozen=True)
class Step:
    name: str
    command: tuple[str, ...]
    cwd: str
    env: Mapping[str, str] | None = None
    external_write: bool = False

    def public(self) -> dict[str, Any]:
        data = asdict(self)
        data["command"] = list(self.command)
        return data


def validate_week(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("week must be YYYY-MM-DD") from exc
    expected_weekday = {"MONDAY": 0, "SUNDAY": 6}[config.WEEK_START_DAY]
    if parsed.weekday() != expected_weekday:
        raise argparse.ArgumentTypeError("week must be a Sunday (the report week start)")
    return value


def snapshot_paths(week: str) -> list[Path]:
    return [CACHE / f"snapshot_{slug}_{week}.json" for slug in (*config.MARKETS, "headout")]


def build_plan(
    week: str,
    notebook_dir: Path,
    *,
    deploy: bool = False,
    post_alerts: bool = False,
    base_notebook: Path | None = None,
    verification_mode: str = 'browser',
) -> list[Step]:
    if post_alerts and not deploy:
        raise ValueError("--post-alerts requires --deploy")

    python = sys.executable
    combined_manifest = CACHE / f"v2_release_full_{week}.json"
    okr_results = CACHE / f"okr_results_v2_{week}.json"
    base_notebook = base_notebook or Path(os.environ.get('WEEKLY_BASE_NOTEBOOK', 'VERIFIED_BASE_NOTEBOOK_REQUIRED'))
    integrity = str(SCRIPTS / 'release_integrity.py')
    package = CACHE / f'v2_package_{week}'
    bundle = package / 'delivery.json'
    artifact = package / 'artifact.json'
    release_command = (
        python,
        str(SCRIPTS / "release_v2.py"),
        *(str(path) for path in snapshot_paths(week)),
        "--out-dir",
        str(V2_REPORTS),
        "--fetch-goals",
        "--okr-results",
        str(okr_results),
        "--manifest",
        str(combined_manifest),
    )

    steps = [
        Step("baseline", (python, str(SCRIPTS / "verify_baseline.py")), str(ROOT)),
        Step('seed-notebook', (python, integrity, 'seed', '--base', str(base_notebook),
                              '--target', str(notebook_dir), '--week', week), str(ROOT)),
        Step(
            "build-markets",
            (
                python,
                str(SCRIPTS / "weekly_market_report.py"),
                "all",
                "--week",
                week,
                "--renderer",
                "both",
                "--no-open",
            ),
            str(ROOT),
        ),
        Step(
            "build-headout",
            (
                python,
                str(SCRIPTS / "weekly_market_report.py"),
                "headout",
                "--week",
                week,
                "--renderer",
                "both",
                "--no-open",
            ),
            str(ROOT),
        ),
        Step(
            "build-market-okrs",
            (
                python,
                str(ROOT / "alert" / "v2" / "build_market_okr_results.py"),
                "--week-start",
                week,
                "--out",
                str(okr_results),
            ),
            str(ROOT),
        ),
        Step("combined-v2-gate", release_command, str(ROOT)),
        Step(
            "build-shared-market-report",
            (
                python,
                str(SCRIPTS / "render_v2.py"),
                str(CACHE / f"snapshot_csee_{week}.json"),
                str(CACHE / f"snapshot_nordics_{week}.json"),
                "--goals",
                str(V2_REPORTS / "goals_v2.json"),
                "--okr-results",
                str(okr_results),
                "--group-slug",
                "csee_nordics",
                "--group-name",
                "CSEE + Nordics",
                "--out",
                str(V2_REPORTS / f"report_csee_nordics_{week}.html"),
            ),
            str(ROOT),
        ),
        Step(
            "alert-readiness",
            (python, str(ROOT / "alert" / "v2" / "check_readiness.py"), '--include-headout'),
            str(ROOT),
        ),
        Step(
            "stage-notebook",
            (
                python,
                str(SCRIPTS / "publish_weekly.py"),
                "all",
                "--week",
                week,
                "--renderer",
                "v2",
                "--skip-perf-sheet",
            ),
            str(ROOT),
            env={"MMR_NOTEBOOK_DIR": str(notebook_dir)},
        ),
        Step(
            "alerts-dry-run",
            (
                python,
                str(ROOT / 'alert' / 'v2' / 'prepare_delivery.py'),
                '--week', week, '--reports', str(V2_REPORTS),
                '--okrs', str(okr_results), '--out', str(bundle),
            ),
            str(ROOT),
        ),
        Step('artifact-integrity', (python, integrity, 'artifact', '--base', str(base_notebook),
                                   '--target', str(notebook_dir), '--week', week,
                                   '--manifest', str(artifact)), str(ROOT)),
    ]

    if deploy:
        steps.insert(1, Step('slack-access-preflight',
                            (python, str(ROOT / 'alert' / 'v2' / 'delivery_access.py')), str(ROOT)))
        steps.append(
            Step(
                "deploy-vercel",
                ("vercel", "deploy", "--prod", "--yes", "--cwd", str(notebook_dir)),
                str(ROOT),
                external_write=True,
            )
        )
        verify_command = (python, integrity, 'browser' if verification_mode == 'browser' else 'live',
                          '--manifest', str(artifact), '--out', str(package / 'live_verification.json'))
        if verification_mode == 'browser':
            verify_command += ('--observations', str(package / 'browser_observations.json'))
        steps.append(Step('verify-live-reports', verify_command, str(ROOT)))
    if post_alerts:
        steps.append(
            Step(
                "post-alerts",
                (
                    python,
                    str(ROOT / 'alert' / 'v2' / 'safe_delivery.py'),
                    '--bundle', str(bundle), '--ledger', str(ROOT / 'alert' / 'posted_ledger.json'),
                    '--state-dir', str(CACHE / 'delivery_state'),
                    '--verified-release', str(package / 'live_verification.json'),
                    '--artifact', str(artifact),
                ),
                str(ROOT),
                external_write=True,
            )
        )
    return steps


def git_metadata() -> dict[str, Any]:
    def output(*args: str) -> str:
        result = subprocess.run(
            ("git", *args), cwd=ROOT, text=True, capture_output=True, check=False
        )
        return result.stdout.strip()

    return {
        "commit": output("rev-parse", "HEAD"),
        "branch": output("branch", "--show-current"),
        "status": output("status", "--short").splitlines(),
    }


def write_receipt(path: Path, receipt: dict[str, Any]) -> None:
    from release_integrity import atomic_json
    atomic_json(path, receipt)


def execute(plan: Sequence[Step], week: str, notebook_dir: Path) -> Path:
    from release_integrity import completed_week
    completed_week(week)
    package_dir = CACHE / f"v2_package_{week}"
    receipt_path = CACHE / f"v2_run_{week}.json"
    notebook_dir.mkdir(parents=True, exist_ok=True)
    package_dir.mkdir(parents=True, exist_ok=True)

    receipt: dict[str, Any] = {
        "schema": "weekly-v2-run/v1",
        "status": "running",
        "week": week,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "markets": [*config.MARKETS, "headout"],
        "notebook_dir": str(notebook_dir),
        "git": git_metadata(),
        # Keep unexecuted commands available when browser verification pauses.
        # This is a plan, not evidence that any step has passed.
        "planned_steps": [step.public() for step in plan],
        "steps": [],
    }
    write_receipt(receipt_path, receipt)

    for step in plan:
        started = time.monotonic()
        record: dict[str, Any] = {**step.public(), "status": "running"}
        receipt["steps"].append(record)
        write_receipt(receipt_path, receipt)
        if step.name == 'verify-live-reports' and '--observations' in step.command:
            observations = Path(step.command[step.command.index('--observations') + 1])
            if not observations.exists():
                record['status'] = 'awaiting_browser_verification'
                receipt['status'] = 'awaiting_browser_verification'
                write_receipt(receipt_path, receipt)
                print('Deployment is not workflow completion. Capture fresh signed-in browser observations for every manifest route, '
                      'run the verify-live-reports command, then resume the frozen safe_delivery command. No alerts sent.')
                return receipt_path
        env = os.environ.copy()
        if step.env:
            env.update(step.env)
        try:
            subprocess.run(step.command, cwd=step.cwd, env=env, check=True)
        except (subprocess.CalledProcessError, OSError) as exc:
            record.update(
                status="failed",
                exit_code=getattr(exc, 'returncode', None),
                duration_seconds=round(time.monotonic() - started, 3),
            )
            receipt.update(
                status="failed", finished_at=datetime.now(timezone.utc).isoformat()
            )
            write_receipt(receipt_path, receipt)
            raise
        record.update(
            status="passed", duration_seconds=round(time.monotonic() - started, 3)
        )
        write_receipt(receipt_path, receipt)

    receipt.update(status="passed", finished_at=datetime.now(timezone.utc).isoformat())
    write_receipt(receipt_path, receipt)
    packaged_receipt = package_dir / "run_receipt.json"
    write_receipt(packaged_receipt, receipt)
    return receipt_path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week", required=True, type=validate_week)
    parser.add_argument(
        "--notebook-dir",
        type=Path,
        help="Staging/deployment target (defaults to a repository-local release package)",
    )
    parser.add_argument("--plan", action="store_true", help="Print the plan; make no changes")
    parser.add_argument('--base-notebook', type=Path, help='Verified complete notebook used as the preservation baseline')
    parser.add_argument('--verification-mode', choices=['browser', 'http'], default='browser')
    parser.add_argument("--deploy", action="store_true", help="Deploy the staged notebook to Vercel")
    parser.add_argument(
        "--post-alerts",
        action="store_true",
        help="Post V2 market alerts after a successful deployment",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.post_alerts and not args.deploy:
        raise SystemExit("--post-alerts requires --deploy")

    package_dir = CACHE / f"v2_package_{args.week}"
    notebook_dir = (args.notebook_dir or package_dir / "notebook").expanduser().resolve()
    plan = build_plan(
        args.week,
        notebook_dir,
        deploy=args.deploy,
        post_alerts=args.post_alerts,
        base_notebook=args.base_notebook,
        verification_mode=args.verification_mode,
    )
    if args.plan:
        print(
            json.dumps(
                {
                    "week": args.week,
                    "notebook_dir": str(notebook_dir),
                    "markets": [*config.MARKETS, "headout"],
                    "steps": [step.public() for step in plan],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if not args.base_notebook and not os.environ.get('WEEKLY_BASE_NOTEBOOK'):
        raise SystemExit('--base-notebook or WEEKLY_BASE_NOTEBOOK is required; never deploy an empty notebook')
    sys.path.insert(0, str(ROOT / 'alert' / 'v2'))
    from safe_delivery import locked
    with locked(CACHE / 'v2_release.lock'):
        receipt = execute(plan, args.week, notebook_dir)
    print(f"Weekly V2 package {json.loads(receipt.read_text())['status']}: {receipt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
