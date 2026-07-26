"""Readable evaluation and calibration summaries."""

from __future__ import annotations

from collections import defaultdict
from statistics import mean, pstdev
from typing import Any

from factoryguard.models import EvaluationRun


def summarize(
    run: EvaluationRun, repeated_runs: list[EvaluationRun] | None = None
) -> dict[str, Any]:
    total = len(run.results)
    passed = sum(result.passed for result in run.results)
    categories: dict[str, list[bool]] = defaultdict(list)
    for result in run.results:
        categories[result.category].append(result.passed)
    judge_scores = [result.judge_score for result in run.results if result.judge_score]
    latencies = [result.latency_ms for result in run.results if result.latency_ms is not None]
    all_runs = [run, *(repeated_runs or [])]
    primary_case_ids = set(result.case_id for result in run.results)
    if any(
        set(result.case_id for result in item.results) != primary_case_ids for item in all_runs[1:]
    ):
        raise ValueError("Repeated runs must contain the same case IDs to measure variability")
    pass_rates = [
        sum(result.passed for result in item.results) / len(item.results) if item.results else 0.0
        for item in all_runs
    ]
    variability: dict[str, Any] = (
        {
            "status": "available",
            "sample_size": len(pass_rates),
            "pass_rate_mean": mean(pass_rates),
            "pass_rate_population_stddev": pstdev(pass_rates),
            "pass_rate_min": min(pass_rates),
            "pass_rate_max": max(pass_rates),
        }
        if len(pass_rates) > 1
        else {
            "status": "unavailable",
            "sample_size": 1,
            "reason": "Only one run is summarized; repeated comparable runs are required.",
        }
    )
    return {
        "run_id": run.run_id,
        "mode": run.mode,
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": passed / total if total else 0.0,
        "critical_failures": sum(result.critical_failure for result in run.results),
        "by_category": {
            category: {
                "total": len(outcomes),
                "passed": sum(outcomes),
                "pass_rate": sum(outcomes) / len(outcomes),
            }
            for category, outcomes in sorted(categories.items())
        },
        "failures": [
            {"case_id": result.case_id, "category": result.category, "details": result.failures}
            for result in run.results
            if not result.passed
        ],
        "latency_ms": {
            "sample_size": len(latencies),
            "mean": sum(latencies) / len(latencies) if latencies else None,
            "max": max(latencies) if latencies else None,
        },
        "estimated_cost_usd": {
            "status": "unavailable"
            if not any(r.estimated_cost_usd is not None for r in run.results)
            else "estimated",
            "total": sum(r.estimated_cost_usd or 0 for r in run.results)
            if any(r.estimated_cost_usd is not None for r in run.results)
            else None,
        },
        "run_to_run_variability": variability,
        "judge": {
            "sample_size": len(judge_scores),
            "pass_rate": sum(score.passed for score in judge_scores) / len(judge_scores)
            if judge_scores
            else None,
        },
    }


def markdown_report(
    run: EvaluationRun,
    repeated_runs: list[EvaluationRun] | None = None,
    calibration: dict[str, int | float] | None = None,
) -> str:
    summary = summarize(run, repeated_runs)
    variability = summary["run_to_run_variability"]
    variability_line = (
        f"- Pass-rate run-to-run variability: mean {variability['pass_rate_mean']:.1%}, "
        f"population SD {variability['pass_rate_population_stddev']:.1%} "
        f"(n={variability['sample_size']} runs)."
        if variability["status"] == "available"
        else "- Run-to-run variability: unavailable (one run; repeated comparable runs required)."
    )
    lines = [
        "# FactoryGuard Evaluation Report",
        "",
        f"- Run: `{run.run_id}`",
        f"- Mode: **{run.mode}**",
        f"- Cases: **{summary['passed']}/{summary['total']} passed** "
        f"({summary['pass_rate']:.1%}; n={summary['total']})",
        f"- Critical failures: **{summary['critical_failures']}**",
        f"- Mean latency: **{summary['latency_ms']['mean']:.3f} ms** "
        f"(n={summary['latency_ms']['sample_size']})"
        if summary["latency_ms"]["mean"] is not None
        else "- Mean latency: unavailable (n=0)",
        "- Cost: unavailable for offline runs; no provider usage was measured.",
        variability_line,
        "",
        "## Pass rate by category",
        "",
        "| Category | Passed | Cases | Pass rate |",
        "|---|---:|---:|---:|",
    ]
    for category, values in summary["by_category"].items():
        lines.append(
            f"| {category} | {values['passed']} | {values['total']} | {values['pass_rate']:.1%} |"
        )
    lines.extend(["", "## Failures", ""])
    failures = summary["failures"]
    if failures:
        for failure in failures[:10]:
            lines.append(
                f"- `{failure['case_id']}` ({failure['category']}): "
                + "; ".join(failure["details"])
            )
    else:
        lines.append("No deterministic assertion failures.")
    lines.extend(["", "## Judge calibration", ""])
    if calibration is None:
        lines.append("Agreement is unavailable; no live calibration result was supplied.")
    else:
        lines.extend(
            [
                f"- Human-labeled sample size: **{int(calibration['sample_size'])}**",
                f"- Agreement rate: **{calibration['agreement_rate']:.1%}**",
                "- Confusion matrix counts: "
                f"TP={int(calibration['true_positive'])}, "
                f"TN={int(calibration['true_negative'])}, "
                f"FP={int(calibration['false_positive'])}, "
                f"FN={int(calibration['false_negative'])}.",
            ]
        )
    judge_note = (
        "The listed judge agreement is measured only on the supplied small calibration set; "
        "it is not evidence of general model reliability."
        if calibration is not None
        else "Judge agreement is unavailable unless a judge run and labeled calibration run "
        "are explicitly performed."
    )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This is a deterministic test of the bundled synthetic assistant and finite test set. "
            "It is not evidence of general model reliability. " + judge_note,
            "",
        ]
    )
    return "\n".join(lines)


def calibration_metrics(pairs: list[tuple[bool, bool]]) -> dict[str, int | float]:
    """Return agreement and binary confusion matrix (human label, judge decision)."""
    tp = tn = fp = fn = 0
    for human, judge in pairs:
        if human and judge:
            tp += 1
        elif not human and not judge:
            tn += 1
        elif judge:
            fp += 1
        else:
            fn += 1
    total = len(pairs)
    return {
        "sample_size": total,
        "agreement_rate": (tp + tn) / total if total else 0.0,
        "true_positive": tp,
        "true_negative": tn,
        "false_positive": fp,
        "false_negative": fn,
    }
