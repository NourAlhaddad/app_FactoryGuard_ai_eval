"""Baseline comparison with explicit non-regression thresholds."""

from __future__ import annotations

from factoryguard.models import EvaluationRun
from factoryguard.reporting import summarize


def compare_runs(
    baseline: EvaluationRun,
    current: EvaluationRun,
    max_pass_rate_drop: float = 0.0,
) -> dict[str, object]:
    if not 0.0 <= max_pass_rate_drop <= 1.0:
        raise ValueError("max_pass_rate_drop must be between 0 and 1")
    old = summarize(baseline)
    new = summarize(current)
    old_by_id = {result.case_id: result for result in baseline.results}
    new_by_id = {result.case_id: result for result in current.results}
    newly_failing = sorted(
        case_id
        for case_id, result in new_by_id.items()
        if not result.passed and (case_id not in old_by_id or old_by_id[case_id].passed)
    )
    new_critical_failures = sorted(
        case_id
        for case_id, result in new_by_id.items()
        if result.critical_failure
        and (old_by_id.get(case_id) is None or not old_by_id[case_id].critical_failure)
    )
    pass_rate_delta = float(new["pass_rate"]) - float(old["pass_rate"])
    reasons = []
    if pass_rate_delta < -max_pass_rate_drop:
        reasons.append("pass rate dropped beyond configured threshold")
    if new_critical_failures:
        reasons.append("new critical safety failure")
    return {
        "passed": not reasons,
        "baseline_pass_rate": old["pass_rate"],
        "current_pass_rate": new["pass_rate"],
        "pass_rate_delta": pass_rate_delta,
        "max_pass_rate_drop": max_pass_rate_drop,
        "newly_failing_cases": newly_failing,
        "new_critical_failures": new_critical_failures,
        "reasons": reasons,
    }
