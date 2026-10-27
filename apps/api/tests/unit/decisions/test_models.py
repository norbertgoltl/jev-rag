import pytest
from pydantic import ValidationError

from decision_fixtures import request, result
from jev_rag_api.domain.decisions.errors import DecisionInvalidResponseError
from jev_rag_api.domain.decisions.models import DecisionRequest, DecisionResult


@pytest.mark.parametrize(
    "patch",
    [
        {"state": None},
        {"state": 42},
        {"state": {"value": float("nan")}},
        {"questions": {}},
        {"questions": {"": {"type": "noul", "instructions": "x"}}},
        {"questions": {"q": {"type": "box", "instructions": "x"}}},
        {"questions": {"q": {"type": "choice", "instructions": "x", "criteria": {"a": None}}}},
        {"questions": {"q": {"type": "score", "instructions": "x", "criteria": ["one"]}}},
        {"questions": {"q": {"type": "score", "instructions": "x", "criteria": ["level"] * 11}}},
        {"questions": {"q": {"type": "noul", "instructions": " "}}},
        {"questions": {"q": {"type": "noul", "instructions": "x", "criteria": {"unknown": "x"}}}},
    ],
)
def test_invalid_request(patch):
    data = request().model_dump()
    data.update(patch)
    with pytest.raises(ValidationError):
        DecisionRequest.model_validate(data)


@pytest.mark.parametrize("value", [-0.1, 1.1, float("inf"), float("nan"), True, "0.5"])
def test_invalid_probability(value):
    data = result().model_dump()
    data["answers"]["needs_action"]["noul"] = value
    with pytest.raises(ValidationError):
        DecisionResult.model_validate(data)


@pytest.mark.parametrize(
    "change",
    ["missing", "extra", "type", "choice", "choice_distribution", "score", "score_distribution"],
)
def test_invalid_result_for_request(change):
    data = result().model_dump()
    if change == "missing":
        del data["answers"]["category"]
    if change == "extra":
        data["answers"]["extra"] = {"type": "noul", "noul": 0.5}
    if change == "type":
        data["answers"]["category"] = {"type": "noul", "noul": 0.5}
    if change == "choice":
        data["answers"]["category"]["choice"] = "unknown"
    if change == "choice_distribution":
        data["answers"]["category"]["probabilities"] = {"unknown": 1.0}
    if change == "score":
        data["answers"]["urgency"]["score"] = 2.0
    if change == "score_distribution":
        data["answers"]["urgency"]["probabilities"] = {2: 1.0}
    with pytest.raises(DecisionInvalidResponseError):
        DecisionResult.model_validate(data).validate_for(request())


def test_domain_and_application_have_no_sdk_imports():
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[3] / "src" / "jev_rag_api"
    for layer in ["domain", "application"]:
        for source in (root / layer).rglob("*.py"):
            for node in ast.walk(ast.parse(source.read_text())):
                if isinstance(node, ast.Import):
                    assert all(not item.name.startswith("typesafe_sdk") for item in node.names)
                if isinstance(node, ast.ImportFrom):
                    assert not (node.module or "").startswith("typesafe_sdk")
