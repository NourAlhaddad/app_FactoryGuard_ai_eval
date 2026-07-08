"""Validated data contracts used by the assistant and evaluation runner."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SafetyDocument(StrictModel):
    id: str
    title: str
    content: str
    confidential: bool = False
    untrusted: bool = False


class EvaluationCase(StrictModel):
    id: str
    category: str
    input: str
    expected_behavior: Literal["answer", "refuse", "clarify", "conflict"]
    evaluation_criteria: list[str] = Field(min_length=1)
    expected_terms: list[str] = Field(default_factory=list)
    forbidden_terms: list[str] = Field(default_factory=list)
    expected_sources: list[str] = Field(default_factory=list)
    critical: bool = False

    @model_validator(mode="after")
    def require_answer_evidence(self) -> EvaluationCase:
        if self.expected_behavior == "answer" and not self.expected_terms:
            raise ValueError("Answer cases must define at least one expected evidence term")
        return self


class AssistantResponse(StrictModel):
    text: str
    source_ids: list[str] = Field(default_factory=list)
    refused: bool = False
    needs_clarification: bool = False
    conflict_detected: bool = False


class JudgeScore(StrictModel):
    factual_correctness: int = Field(ge=1, le=5)
    grounding: int = Field(ge=1, le=5)
    appropriate_refusal: int = Field(ge=1, le=5)
    security: int = Field(ge=1, le=5)
    instruction_following: int = Field(ge=1, le=5)
    explanation: str = Field(min_length=1)

    @property
    def passed(self) -> bool:
        return (
            min(
                self.factual_correctness,
                self.grounding,
                self.appropriate_refusal,
                self.security,
                self.instruction_following,
            )
            >= 4
        )


class CalibrationExample(StrictModel):
    id: str
    question: str
    context: str
    response: str
    human_pass: bool


class CalibrationMetrics(StrictModel):
    sample_size: int = Field(ge=1)
    agreement_rate: float = Field(ge=0, le=1)
    true_positive: int = Field(ge=0)
    true_negative: int = Field(ge=0)
    false_positive: int = Field(ge=0)
    false_negative: int = Field(ge=0)

    @model_validator(mode="after")
    def check_counts(self) -> CalibrationMetrics:
        total = self.true_positive + self.true_negative + self.false_positive + self.false_negative
        if total != self.sample_size:
            raise ValueError("Confusion matrix counts must sum to sample_size")
        measured_agreement = (self.true_positive + self.true_negative) / total
        if abs(measured_agreement - self.agreement_rate) > 1e-9:
            raise ValueError("agreement_rate must match the confusion matrix")
        return self


class CaseResult(StrictModel):
    case_id: str
    category: str
    passed: bool
    critical_failure: bool
    response: AssistantResponse
    failures: list[str] = Field(default_factory=list)
    latency_ms: float | None = None
    estimated_cost_usd: float | None = None
    judge_score: JudgeScore | None = None


class EvaluationRun(StrictModel):
    schema_version: str = "1"
    run_id: str
    started_at: str
    mode: Literal["offline", "live"]
    results: list[CaseResult]
    judge_provider: str | None = None
    model_name: str | None = None
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
