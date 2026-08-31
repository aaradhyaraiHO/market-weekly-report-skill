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
) -> list[Step]:
    if post_alerts and not deploy:
        raise ValueError("--post-alerts requires --deploy")

    python = sys.executable
    combined_manifest = CACHE / f"v2_release_full_{week}.json"
    okr_results = CACHE / f"okr_results_v2_{week}.json"
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
            "alert-readiness",
            (python, str(ROOT / "alert" / "v2" / "check_readiness.py")),
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
                str(SCRIPTS / "run_weekly.py"),
                "all",
                "--week",
                week,
                "--stage",
                "alert",
                "--alert-version",
                "v2",
            ),
            str(ROOT),
        ),
    ]

    if deploy:
        steps.append(
            Step(
                "deploy-vercel",
                ("vercel", "deploy", "--prod", "--cwd", str(notebook_dir)),
                str(ROOT),
                external_write=True,
            )
        )
    if post_alerts:
        steps.append(
            Step(
                "post-alerts",
                (
                    python,
                    str(SCRIPTS / "run_weekly.py"),
                    "all",
                    "--week",
                    week,
                    "--stage",
                    "alert",
                    "--alert-version",
                    "v2",
                    "--post",
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")


def execute(plan: Sequence[Step], week: str, notebook_dir: Path) -> Path:
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
        "steps": [],
    }
    write_receipt(receipt_path, receipt)

    for step in plan:
        started = time.monotonic()
        record: dict[str, Any] = {**step.public(), "status": "running"}
        receipt["steps"].append(record)
        write_receipt(receipt_path, receipt)
        env = os.environ.copy()
        if step.env:
            env.update(step.env)
        try:
            subprocess.run(step.command, cwd=step.cwd, env=env, check=True)
        except subprocess.CalledProcessError as exc:
            record.update(
                status="failed",
                exit_code=exc.returncode,
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

    receipt = execute(plan, args.week, notebook_dir)
    print(f"Weekly V2 package passed: {receipt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
