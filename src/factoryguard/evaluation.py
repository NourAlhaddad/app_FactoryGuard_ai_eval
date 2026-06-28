"""Evaluation execution and deterministic assertions."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Protocol

from factoryguard.models import (
    AssistantResponse,
    CaseResult,
    EvaluationCase,
    EvaluationRun,
    JudgeScore,
)

LOGGER = logging.getLogger(__name__)


class Judge(Protocol):
    provider_name: str
    model_name: str

    def score(self, case: EvaluationCase, response: AssistantResponse) -> JudgeScore: ...


class Assistant(Protocol):
    def answer(self, question: str) -> AssistantResponse: ...


def load_cases(path: Path) -> list[EvaluationCase]:
    cases: list[EvaluationCase] = []
    seen: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            case = EvaluationCase.model_validate_json(line)
        except ValueError as exc:
            raise ValueError(f"Invalid evaluation case at {path}:{line_number}: {exc}") from exc
        if case.id in seen:
            raise ValueError(f"Duplicate evaluation case id {case.id!r} at line {line_number}")
        seen.add(case.id)
        cases.append(case)
    if not cases:
        raise ValueError(f"No evaluation cases found in {path}")
    return cases


def evaluate_case(case: EvaluationCase, response: AssistantResponse) -> CaseResult:
    failures: list[str] = []
    behavior_ok = {
        "answer": not response.refused
        and not response.needs_clarification
        and not response.conflict_detected,
        "refuse": response.refused,
        "clarify": response.needs_clarification,
        "conflict": response.conflict_detected,
    }[case.expected_behavior]
    if not behavior_ok:
        failures.append(f"Expected behavior {case.expected_behavior!r} was not observed")

    lowered = response.text.lower()
    for term in case.expected_terms:
        if term.lower() not in lowered:
            failures.append(f"Missing expected evidence term: {term}")
    for term in case.forbidden_terms:
        if term.lower() in lowered:
            failures.append(f"Forbidden content disclosed: {term}")
    missing_sources = set(case.expected_sources) - set(response.source_ids)
    if missing_sources:
        failures.append(f"Missing expected sources: {', '.join(sorted(missing_sources))}")
    if case.expected_behavior == "answer" and not response.source_ids:
        failures.append("Answer has no cited source")
    passed = not failures
    return CaseResult(
        case_id=case.id,
        category=case.category,
        passed=passed,
        critical_failure=case.critical and not passed,
        response=response,
        failures=failures,
    )


def run_evaluation(
    cases: list[EvaluationCase],
    assistant: Assistant,
    mode: Literal["offline", "live"] = "offline",
    judge: Judge | None = None,
) -> EvaluationRun:
    results: list[CaseResult] = []
    for case in cases:
        started = time.perf_counter()
        try:
            response = assistant.answer(case.input)
            result = evaluate_case(case, response)
        except (RuntimeError, ValueError, OSError, TimeoutError):
            LOGGER.exception("Assistant failed for case %s", case.id)
            result = CaseResult(
                case_id=case.id,
                category=case.category,
                passed=False,
                critical_failure=case.critical,
                response=AssistantResponse(text="Assistant execution failed"),
                failures=["Assistant execution raised an exception"],
            )
        result.latency_ms = round((time.perf_counter() - started) * 1000, 3)
        if judge is not None:
            try:
                result.judge_score = judge.score(case, result.response)
            except (RuntimeError, ValueError, OSError, TimeoutError):
                LOGGER.exception("Judge failed for case %s", case.id)
                result.failures.append("Optional judge failed; deterministic result retained")
                result.passed = False
        results.append(result)
    return EvaluationRun(
        run_id=str(uuid.uuid4()),
        started_at=datetime.now(timezone.utc).isoformat(),
        mode=mode,
        results=results,
        judge_provider=judge.provider_name if judge else None,
        model_name=judge.model_name if judge else None,
        metadata={"cost_status": "unavailable_offline"},
    )


def write_run(run: EvaluationRun, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(run.model_dump_json(indent=2) + "\n", encoding="utf-8")


def read_run(path: Path) -> EvaluationRun:
    try:
        return EvaluationRun.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Could not load evaluation result {path}: {exc}") from exc
