import json
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StringConstraints, model_validator

from .errors import DecisionInvalidResponseError

Text = Annotated[str, StringConstraints(strict=True, min_length=1, pattern=r"\S")]
Probability = Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class ChoiceQuestionSpec(Model):
    type: Literal["choice"] = "choice"
    instructions: Text
    criteria: dict[Text, str | None] = Field(min_length=2)


class ScoreQuestionSpec(Model):
    type: Literal["score"] = "score"
    instructions: Text
    criteria: list[Text] = Field(min_length=2, max_length=10)


class NoulQuestionSpec(Model):
    type: Literal["noul"] = "noul"
    instructions: Text
    criteria: dict[Literal["true", "false"], str | None] | None = None


QuestionSpec = Annotated[
    ChoiceQuestionSpec | ScoreQuestionSpec | NoulQuestionSpec, Field(discriminator="type")
]


class DecisionRequest(Model):
    state: str | dict[str, JsonValue] | list[JsonValue]
    questions: dict[Text, QuestionSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_json_state(self) -> Self:
        json.dumps(self.state, allow_nan=False)
        return self


class ChoiceAnswer(Model):
    type: Literal["choice"] = "choice"
    choice: Text
    probabilities: dict[Text, Probability] = Field(min_length=1)
    confidence: Probability


class ScoreAnswer(Model):
    type: Literal["score"] = "score"
    score: Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
    probabilities: dict[Annotated[int, Field(strict=True, ge=0)], Probability] = Field(min_length=1)
    confidence: Probability


class NoulAnswer(Model):
    type: Literal["noul"] = "noul"
    noul: Probability


DecisionAnswer = Annotated[ChoiceAnswer | ScoreAnswer | NoulAnswer, Field(discriminator="type")]


class DecisionResult(Model):
    model: Text
    answers: dict[Text, DecisionAnswer] = Field(min_length=1)
    provider_request_id: str | None = None
    input_tokens: Annotated[int, Field(strict=True, ge=0)] | None = None
    output_tokens: Annotated[int, Field(strict=True, ge=0)] | None = None

    def validate_for(self, request: DecisionRequest) -> Self:
        """Raise DecisionInvalidResponseError unless every answer fits its question."""
        if self.answers.keys() != request.questions.keys():
            raise DecisionInvalidResponseError()
        for name, question in request.questions.items():
            if not _answer_fits(question, self.answers[name]):
                raise DecisionInvalidResponseError()
        return self


def _choice_answer_fits(question: ChoiceQuestionSpec, answer: ChoiceAnswer) -> bool:
    return answer.choice in question.criteria and set(answer.probabilities) == set(
        question.criteria
    )


def _score_answer_fits(question: ScoreQuestionSpec, answer: ScoreAnswer) -> bool:
    last_level = len(question.criteria) - 1
    return answer.score <= last_level and set(answer.probabilities) == set(range(last_level + 1))


def _answer_fits(
    question: ChoiceQuestionSpec | ScoreQuestionSpec | NoulQuestionSpec, answer: DecisionAnswer
) -> bool:
    """Check the answer type and its consistency with the question definition."""
    if isinstance(question, ChoiceQuestionSpec):
        return isinstance(answer, ChoiceAnswer) and _choice_answer_fits(question, answer)
    if isinstance(question, ScoreQuestionSpec):
        return isinstance(answer, ScoreAnswer) and _score_answer_fits(question, answer)
    # A noul answer has no question-specific constraint beyond its type; the probability
    # range is already enforced by NoulAnswer.
    return isinstance(answer, NoulAnswer)
