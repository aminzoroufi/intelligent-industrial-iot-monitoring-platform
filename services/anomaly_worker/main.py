# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""Train, evaluate, or continuously run the per-device anomaly worker."""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from services.anomaly_worker.demo_data import demo_evaluation_samples, demo_training_samples
from services.anomaly_worker.evaluation import evaluate_detectors, write_evaluation
from services.anomaly_worker.modeling import train_model
from services.api.app.settings import get_settings


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("timestamp must include an offset or Z")
    return parsed.astimezone(UTC)


def _train(args: argparse.Namespace) -> None:
    from services.anomaly_worker.worker import train_and_register
    from services.api.app.database import SessionLocal

    settings = get_settings()
    with SessionLocal() as session:
        registry = train_and_register(
            session,
            settings,
            device_id=args.device_id,
            baseline_start=args.start,
            baseline_end=args.end,
            contamination=args.contamination,
        )
    print(
        json.dumps(
            {
                "status": registry.status,
                "device_id": registry.device_id,
                "model_version": registry.model_version,
                "training_sample_count": registry.training_sample_count,
                "validation_sample_count": registry.validation_sample_count,
            },
            sort_keys=True,
        )
    )


def _evaluate_demo(args: argparse.Namespace) -> None:
    training = demo_training_samples()
    bundle = train_model(
        training,
        device_id="motor-01",
        asset_class="dc-motor",
        baseline_start=training[0].timestamp,
        baseline_end=training[-1].timestamp,
        created_at=datetime(2026, 8, 11, 0, 0, tzinfo=UTC),
    )
    report = evaluate_detectors(bundle, demo_evaluation_samples())
    write_evaluation(report, args.output)
    print(json.dumps({"status": "written", "output": str(args.output)}, sort_keys=True))


def _run() -> None:
    from services.anomaly_worker.worker import run_once
    from services.api.app.database import SessionLocal

    settings = get_settings()
    ready = Path("run/anomaly-worker-ready")
    marked_ready = False
    while True:
        try:
            with SessionLocal() as session:
                run_once(session, settings)
            if not marked_ready:
                ready.parent.mkdir(parents=True, exist_ok=True)
                ready.write_text("ready\n", encoding="utf-8")
                marked_ready = True
        except Exception as exc:
            print(json.dumps({"level": "error", "error": type(exc).__name__, "detail": str(exc)}))
        time.sleep(settings.anomaly_poll_interval_s)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    train = commands.add_parser("train", help="train from a reviewed healthy database window")
    train.add_argument("--device-id", required=True)
    train.add_argument("--start", type=_timestamp, required=True)
    train.add_argument("--end", type=_timestamp, required=True)
    train.add_argument("--contamination", type=float, default=0.02)
    evaluate = commands.add_parser(
        "evaluate-demo", help="write the deterministic synthetic comparison report"
    )
    evaluate.add_argument(
        "--output", type=Path, default=Path("data/demo/anomaly-evaluation.v1.json")
    )
    commands.add_parser("run", help="poll for unscored telemetry")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "train":
        _train(args)
    elif args.command == "evaluate-demo":
        _evaluate_demo(args)
    else:
        _run()


if __name__ == "__main__":
    main()
