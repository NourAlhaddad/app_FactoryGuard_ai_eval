"""Command-line interface for running and reporting evaluations."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from factoryguard.assistant import SafetyAssistant
from factoryguard.evaluation import load_cases, read_run, run_evaluation, write_run
from factoryguard.judge import OpenAICompatibleJudge
from factoryguard.live import OpenAICompatibleAssistant
from factoryguard.models import (
    AssistantResponse,
    CalibrationExample,
    CalibrationMetrics,
    EvaluationCase,
)
from factoryguard.regression import compare_runs
from factoryguard.reporting import calibration_metrics, markdown_report

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = ROOT / "data"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="factoryguard")
    subparsers = parser.add_subparsers(dest="command", required=True)
    evaluate = subparsers.add_parser("evaluate", help="Run the evaluation dataset")
    evaluate.add_argument("--cases", type=Path, default=DEFAULT_DATA / "cases.jsonl")
    evaluate.add_argument("--documents", type=Path, default=DEFAULT_DATA / "documents.json")
    evaluate.add_argument("--output", type=Path, default=ROOT / "results" / "latest.json")
    evaluate.add_argument("--judge", action="store_true", help="Use optional live LLM judge")
    evaluate.add_argument("--live", action="store_true", help="Evaluate an optional live model")
    evaluate.add_argument("--baseline", type=Path)
    evaluate.add_argument("--max-pass-rate-drop", type=float, default=0.0)

    compare = subparsers.add_parser("compare", help="Compare a result with a baseline")
    compare.add_argument("baseline", type=Path)
    compare.add_argument("current", type=Path)
    compare.add_argument("--max-pass-rate-drop", type=float, default=0.0)

    report = subparsers.add_parser("report", help="Render a markdown report from a run")
    report.add_argument("result", type=Path)
    report.add_argument("--output", type=Path, default=ROOT / "reports" / "latest.md")
    report.add_argument("--repeat", type=Path, action="append", default=[])
    report.add_argument("--calibration", type=Path)

    calibrate = subparsers.add_parser("calibrate", help="Measure live judge against human labels")
    calibrate.add_argument("--examples", type=Path, default=DEFAULT_DATA / "calibration.jsonl")
    calibrate.add_argument("--output", type=Path, default=ROOT / "results" / "calibration.json")
    return parser


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _parser().parse_args()
    try:
        if args.command == "evaluate":
            judge = OpenAICompatibleJudge.from_environment() if args.judge else None
            cases = load_cases(args.cases)
            local_assistant = SafetyAssistant.from_file(args.documents)
            assistant = (
                OpenAICompatibleAssistant.from_environment(local_assistant)
                if args.live
                else local_assistant
            )
            run = run_evaluation(
                cases, assistant, mode="live" if args.live else "offline", judge=judge
            )
            write_run(run, args.output)
            print(markdown_report(run))
            print(f"\nMachine-readable results: {args.output}")
            if args.baseline:
                comparison = compare_runs(
                    read_run(args.baseline), run, max_pass_rate_drop=args.max_pass_rate_drop
                )
                print(json.dumps(comparison, indent=2))
                if not comparison["passed"]:
                    return 1
            return 0 if all(result.passed for result in run.results) else 1
        if args.command == "calibrate":
            judge = OpenAICompatibleJudge.from_environment()
            examples: list[CalibrationExample] = []
            for line_number, line in enumerate(
                args.examples.read_text(encoding="utf-8").splitlines(), 1
            ):
                if line.strip():
                    try:
                        examples.append(CalibrationExample.model_validate_json(line))
                    except ValueError as exc:
                        raise ValueError(
                            f"Invalid calibration example at line {line_number}: {exc}"
                        ) from exc
            if not examples:
                raise ValueError(f"No calibration examples found in {args.examples}")
            pairs = []
            for example in examples:
                case = EvaluationCase(
                    id=example.id,
                    category="calibration",
                    input=example.question,
                    expected_behavior="answer",
                    evaluation_criteria=[example.context],
                    expected_terms=[example.context],
                )
                pairs.append(
                    (
                        example.human_pass,
                        judge.score(case, AssistantResponse(text=example.response)).passed,
                    )
                )
            metrics = calibration_metrics(pairs)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(metrics, indent=2))
            print(f"Calibration results: {args.output}")
            return 0
        if args.command == "compare":
            comparison = compare_runs(
                read_run(args.baseline), read_run(args.current), args.max_pass_rate_drop
            )
            print(json.dumps(comparison, indent=2))
            return 0 if comparison["passed"] else 1
        run = read_run(args.result)
        repeat_runs = [read_run(path) for path in args.repeat]
        calibration = (
            CalibrationMetrics.model_validate_json(
                args.calibration.read_text(encoding="utf-8")
            ).model_dump()
            if args.calibration
            else None
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            markdown_report(run, repeated_runs=repeat_runs, calibration=calibration),
            encoding="utf-8",
        )
        print(f"Report written to {args.output}")
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"factoryguard: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
