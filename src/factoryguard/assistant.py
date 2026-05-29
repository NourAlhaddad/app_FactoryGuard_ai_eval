"""A deterministic, local retrieval assistant used as the offline system under test."""

from __future__ import annotations

import re
from pathlib import Path

from factoryguard.models import AssistantResponse, SafetyDocument

TOKEN_RE = re.compile(r"[a-z0-9]+")
QUERY_STOP_WORDS = {
    "a",
    "about",
    "after",
    "all",
    "an",
    "and",
    "are",
    "at",
    "be",
    "before",
    "can",
    "do",
    "does",
    "during",
    "every",
    "exact",
    "for",
    "how",
    "i",
    "in",
    "is",
    "it",
    "many",
    "me",
    "minimum",
    "maximum",
    "much",
    "my",
    "of",
    "on",
    "or",
    "please",
    "required",
    "safety",
    "shift",
    "should",
    "the",
    "there",
    "this",
    "to",
    "what",
    "when",
    "where",
    "which",
    "with",
    "work",
}
INJECTION_PATTERNS = (
    "ignore previous instructions",
    "ignore all instructions",
    "reveal the system prompt",
    "override the safety policy",
    "act as an unrestricted",
    "disregard the user",
)
CONFIDENTIAL_PATTERNS = (
    "confidential",
    "private access code",
    "emergency override code",
    "employee medical",
    "secret key",
)


def _tokens(text: str) -> set[str]:
    tokens = TOKEN_RE.findall(text.lower())
    return {
        token[:-3] + "y"
        if token.endswith("ies")
        else token[:-1]
        if token.endswith("s") and len(token) > 3
        else token
        for token in tokens
    }


class SafetyAssistant:
    """Answers only from public synthetic safety documents; never retrieves secrets."""

    def __init__(self, documents: list[SafetyDocument], minimum_overlap: int = 2) -> None:
        self.documents = [document for document in documents if not document.confidential]
        self.minimum_overlap = minimum_overlap

    @classmethod
    def from_file(cls, path: Path) -> SafetyAssistant:
        import json

        raw_documents = json.loads(path.read_text(encoding="utf-8"))
        return cls([SafetyDocument.model_validate(item) for item in raw_documents])

    def answer(self, question: str) -> AssistantResponse:
        lowered = question.lower()
        if any(pattern in lowered for pattern in CONFIDENTIAL_PATTERNS):
            return AssistantResponse(
                text="I can’t provide confidential information. "
                "Contact the authorized site safety lead.",
                refused=True,
            )
        if any(pattern in lowered for pattern in INJECTION_PATTERNS):
            return AssistantResponse(
                text="I can’t follow instructions that attempt to override safety controls. "
                "I can help with a documented safety procedure.",
                refused=True,
            )
        if self._is_ambiguous(lowered):
            return AssistantResponse(
                text="Could you clarify the machine or task, and whether it is operating "
                "or isolated?",
                needs_clarification=True,
            )

        query_terms = _tokens(question) - QUERY_STOP_WORDS
        matches: list[tuple[int, SafetyDocument]] = []
        for document in self.documents:
            score = len(query_terms & _tokens(f"{document.title} {document.content}"))
            if score >= self.minimum_overlap:
                matches.append((score, document))
        matches.sort(key=lambda item: item[0], reverse=True)
        if not matches:
            return AssistantResponse(
                text="I don’t have enough information in the available safety documents "
                "to answer that.",
                refused=True,
            )

        best_score = matches[0][0]
        best = [document for score, document in matches if score == best_score]
        if len(best) > 1 and self._contradictory(best):
            source_ids = [document.id for document in best]
            return AssistantResponse(
                text="The available documents conflict on this point. Do not rely on either value; "
                "pause the task and ask the site safety lead to resolve the current procedure. "
                f"Sources: {', '.join(source_ids)}.",
                source_ids=source_ids,
                conflict_detected=True,
            )

        selected = best[0]
        if self._requests_undocumented_measurement(question, selected.content):
            return AssistantResponse(
                text="I don’t have enough information in the available safety documents "
                "to answer that.",
                refused=True,
            )
        safe_content = " ".join(
            sentence
            for sentence in re.split(r"(?<=[.!?])\s+", selected.content)
            if not any(pattern in sentence.lower() for pattern in INJECTION_PATTERNS)
        )
        return AssistantResponse(
            text=f"{safe_content} [Source: {selected.id}]",
            source_ids=[selected.id],
        )

    @staticmethod
    def _is_ambiguous(question: str) -> bool:
        vague_terms = {"it", "that", "this", "there"}
        procedure_terms = {"safe", "safe?", "do", "should"}
        return len(_tokens(question)) < 5 or (
            bool(_tokens(question) & vague_terms)
            and bool(_tokens(question) & procedure_terms)
            and not any(term in question for term in ("machine", "press", "conveyor", "chemical"))
        )

    @staticmethod
    def _contradictory(documents: list[SafetyDocument]) -> bool:
        if len(documents) < 2:
            return False
        values: set[str] = set()
        for document in documents:
            match = re.search(
                r"\b(?:limit|maximum|pressure|temperature)\s+is\s+(\d+)",
                document.content.lower(),
            )
            if match:
                values.add(match.group(1))
        return len(values) > 1

    @staticmethod
    def _requests_undocumented_measurement(question: str, evidence: str) -> bool:
        lowered = question.lower()
        asks_for_measurement = (
            "how many" in lowered
            or "how long" in lowered
            or "how much" in lowered
            or any(term in lowered for term in ("speed", "temperature", "dose", "exact"))
        )
        return asks_for_measurement and not re.search(r"\b\d+(?:\.\d+)?\b", evidence)
