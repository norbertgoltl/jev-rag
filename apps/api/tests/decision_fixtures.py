from typing import Any

from jev_rag_api.domain.decisions.models import DecisionRequest, DecisionResult


def request(language: Any = "en") -> DecisionRequest:
    return DecisionRequest.model_validate(
        dict(
            state="Please review this synthetic ticket."
            if language == "en"
            else "Kérlek vizsgáld meg ezt a mesterséges hibajegyet.",
            questions={
                "category": {
                    "type": "choice",
                    "instructions": "Select a category.",
                    "criteria": {"support": "Support", "other": None},
                },
                "urgency": {
                    "type": "score",
                    "instructions": "Rate urgency.",
                    "criteria": ["Low", "High"],
                },
                "needs_action": {
                    "type": "noul",
                    "instructions": "Does this need action?",
                    "criteria": {"true": "Needs action", "false": "No action"},
                },
            },
        )
    )


def body() -> dict[str, Any]:
    return {
        "model": "jev-1.13.0",
        "usage": {"input_tokens": 12, "output_tokens": 4},
        "answers": {
            "category": {
                "type": "choice",
                "choice": "support",
                "probabilities": {"support": 0.75, "other": 0.25},
                "confidence": 0.8,
            },
            "urgency": {
                "type": "score",
                "score": 0.75,
                "probabilities": {"0": 0.25, "1": 0.75},
                "legend": {"0": "Low", "1": "High"},
                "confidence": 0.8,
            },
            "needs_action": {"type": "noul", "noul": 0.9},
        },
    }


def result() -> DecisionResult:
    data = body()
    data["answers"]["urgency"].pop("legend")
    data["answers"]["urgency"]["probabilities"] = {0: 0.25, 1: 0.75}
    return DecisionResult(
        model=data["model"], answers=data["answers"], input_tokens=12, output_tokens=4
    )
