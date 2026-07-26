from pathlib import Path

import pytest
from pydantic import ValidationError

from factoryguard.assistant import SafetyAssistant
from factoryguard.evaluation import evaluate_case, load_cases, run_evaluation, write_run
from factoryguard.models import AssistantResponse, EvaluationCase
from factoryguard.regression import compare_runs
from factoryguard.reporting import calibration_metrics, markdown_report, summarize

ROOT = Path(__file__).resolve().parents[1]


def make_case(**overrides: object) -> EvaluationCase:
    data: dict[str, object] = {
        "id": "test",
        "category": "test",
        "input": "test question",
        "expected_behavior": "answer",
        "evaluation_criteria": ["demonstrate evidence"],
        "expected_terms": ["evidence"],
    }
    data.update(overrides)
    return EvaluationCase.model_validate(data)


def test_dataset_has_at_least_40_unique_valid_cases() -> None:
    cases = load_cases(ROOT / "data" / "cases.jsonl")
    assert len(cases) >= 40
    assert len({case.id for case in cases}) == len(cases)
    assert {"normal", "insufficient_evidence", "ambiguous", "conflicting_sources"} <= {
        case.category for case in cases
    }


def test_bundled_offline_evaluation_passes_every_assertion() -> None:
    assistant = SafetyAssistant.from_file(ROOT / "data" / "documents.json")
    run = run_evaluation(load_cases(ROOT / "data" / "cases.jsonl"), assistant)
    summary = summarize(run)
    assert summary["total"] >= 40
    assert summary["passed"] == summary["total"], summary["failures"]
    assert summary["critical_failures"] == 0
    assert all(result.latency_ms is not None for result in run.results)


def test_nonempty_but_unsupported_answer_does_not_pass() -> None:
    case = make_case(expected_terms=["zero energy"], expected_sources=["DOC-LOTO-01"])
    result = evaluate_case(case, AssistantResponse(text="Always use common sense."))
    assert not result.passed
    assert any("Missing expected evidence" in failure for failure in result.failures)
    assert any("no cited source" in failure for failure in result.failures)


def test_answer_case_without_evidence_assertions_is_rejected() -> None:
    with pytest.raises(ValidationError, match="expected evidence term"):
        make_case(expected_terms=[])


def test_confidential_disclosure_is_a_critical_failure() -> None:
    case = make_case(
        expected_behavior="refuse",
        forbidden_terms=["FGUARD-TEST-7391"],
        critical=True,
    )
    result = evaluate_case(
        case,
        AssistantResponse(
            text="The code is FGUARD-TEST-7391.",
            refused=False,
        ),
    )
    assert not result.passed
    assert result.critical_failure


def test_duplicate_case_ids_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "duplicates.jsonl"
    case_json = make_case().model_dump_json()
    path.write_text(f"{case_json}\n{case_json}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate evaluation case id"):
        load_cases(path)


def test_saved_run_can_be_loaded_and_regression_detects_introduced_failure(
    tmp_path: Path,
) -> None:
    assistant = SafetyAssistant.from_file(ROOT / "data" / "documents.json")
    cases = load_cases(ROOT / "data" / "cases.jsonl")[:3]
    baseline = run_evaluation(cases, assistant)

    class BrokenAssistant:
        def answer(self, question: str) -> AssistantResponse:
            return AssistantResponse(text="Unsupported answer")

    current = run_evaluation(cases, BrokenAssistant())
    baseline_path = tmp_path / "baseline.json"
    write_run(baseline, baseline_path)
    from factoryguard.evaluation import read_run

    comparison = compare_runs(read_run(baseline_path), current)
    assert not comparison["passed"]
    assert comparison["newly_failing_cases"] == sorted(case.id for case in cases)


def test_regression_detects_new_critical_failure() -> None:
    case = make_case(critical=True)
    assistant = type(
        "GoodAssistant",
        (),
        {
            "answer": lambda self, question: AssistantResponse(
                text="evidence [Source: DOC-LOTO-01]", source_ids=["DOC-LOTO-01"]
            )
        },
    )()
    baseline = run_evaluation([case], assistant)
    unsafe = type(
        "UnsafeAssistant",
        (),
        {"answer": lambda self, question: AssistantResponse(text="unsafe answer")},
    )()
    current = run_evaluation([case], unsafe)
    result = compare_runs(baseline, current)
    assert not result["passed"]
    assert result["new_critical_failures"] == ["test"]


def test_regression_detects_a_newly_added_failing_case() -> None:
    assistant = type(
        "BrokenAssistant",
        (),
        {"answer": lambda self, question: AssistantResponse(text="unsupported")},
    )()
    old = run_evaluation(
        [make_case(id="old")],
        type(
            "PassAssistant",
            (),
            {
                "answer": lambda self, question: AssistantResponse(
                    text="evidence supported [Source: DOC-LOTO-01]", source_ids=["DOC-LOTO-01"]
                )
            },
        )(),
    )
    current = run_evaluation([make_case(id="old"), make_case(id="new")], assistant)
    comparison = compare_runs(old, current)
    assert comparison["newly_failing_cases"] == ["new", "old"]


def test_regression_rejects_invalid_drop_threshold() -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        compare_runs(
            run_evaluation(
                [make_case()],
                type(
                    "Assistant",
                    (),
                    {
                        "answer": lambda self, question: AssistantResponse(
                            text="evidence supported [Source: DOC-LOTO-01]",
                            source_ids=["DOC-LOTO-01"],
                        )
                    },
                )(),
            ),
            run_evaluation(
                [make_case()],
                type(
                    "Assistant",
                    (),
                    {
                        "answer": lambda self, question: AssistantResponse(
                            text="evidence supported [Source: DOC-LOTO-01]",
                            source_ids=["DOC-LOTO-01"],
                        )
                    },
                )(),
            ),
            max_pass_rate_drop=1.1,
        )


def test_calibration_matrix_reports_sample_and_disagreement() -> None:
    result = calibration_metrics([(True, True), (True, False), (False, True), (False, False)])
    assert result == {
        "sample_size": 4,
        "agreement_rate": 0.5,
        "true_positive": 1,
        "true_negative": 1,
        "false_positive": 1,
        "false_negative": 1,
    }


def test_report_measures_variability_for_repeated_comparable_runs() -> None:
    case = make_case()
    assistant = type(
        "Assistant",
        (),
        {
            "answer": lambda self, question: AssistantResponse(
                text="evidence [Source: DOC-LOTO-01]", source_ids=["DOC-LOTO-01"]
            )
        },
    )()
    first = run_evaluation([case], assistant)
    second = run_evaluation([case], assistant)
    summary = summarize(first, [second])
    assert summary["run_to_run_variability"]["status"] == "available"
    assert summary["run_to_run_variability"]["sample_size"] == 2
    assert summary["run_to_run_variability"]["pass_rate_population_stddev"] == 0
    assert "population SD 0.0%" in markdown_report(first, [second])


def test_report_rejects_noncomparable_repeated_runs() -> None:
    assistant = type(
        "Assistant",
        (),
        {
            "answer": lambda self, question: AssistantResponse(
                text="evidence [Source: DOC-LOTO-01]", source_ids=["DOC-LOTO-01"]
            )
        },
    )()
    with pytest.raises(ValueError, match="same case IDs"):
        summarize(
            run_evaluation([make_case(id="one")], assistant),
            [run_evaluation([make_case(id="two")], assistant)],
        )


def test_report_includes_calibration_sample_and_confusion_counts() -> None:
    assistant = type(
        "Assistant",
        (),
        {
            "answer": lambda self, question: AssistantResponse(
                text="evidence [Source: DOC-LOTO-01]", source_ids=["DOC-LOTO-01"]
            )
        },
    )()
    run = run_evaluation([make_case()], assistant)
    report = markdown_report(
        run,
        calibration={
            "sample_size": 30,
            "agreement_rate": 0.8,
            "true_positive": 12,
            "true_negative": 12,
            "false_positive": 3,
            "false_negative": 3,
        },
    )
    assert "Human-labeled sample size: **30**" in report
    assert "TP=12, TN=12, FP=3, FN=3" in report


def test_calibration_dataset_has_30_human_labels() -> None:
    import json

    rows = [
        json.loads(line)
        for line in (ROOT / "data" / "calibration.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 30
    assert sum(row["human_pass"] for row in rows) == 15


def test_assistant_timeout_is_recorded_as_case_failure() -> None:
    class TimeoutAssistant:
        def answer(self, question: str) -> AssistantResponse:
            raise TimeoutError("provider timeout")

    result = run_evaluation([make_case(critical=True)], TimeoutAssistant()).results[0]
    assert not result.passed
    assert result.critical_failure
    assert result.failures == ["Assistant execution raised an exception"]


def test_invalid_judge_score_is_rejected() -> None:
    from pydantic import ValidationError

    from factoryguard.models import JudgeScore

    with pytest.raises(ValidationError):
        JudgeScore(
            factual_correctness=6,
            grounding=4,
            appropriate_refusal=4,
            security=4,
            instruction_following=4,
            explanation="out of bounds",
        )
