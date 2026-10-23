import typesafe_sdk as sdk
from pydantic import ValidationError

from jev_rag_api.domain.decisions.errors import DecisionInvalidResponseError
from jev_rag_api.domain.decisions.models import DecisionRequest, DecisionResult


def map_questions(request: DecisionRequest):
    types = {"choice": sdk.Choice, "score": sdk.Score, "noul": sdk.Noul}
    return {name: types[question.type](**question.model_dump(exclude={"type"}, exclude_none=True)) for name, question in request.questions.items()}


def map_response(request: DecisionRequest, response: sdk.SystemOneResponse) -> DecisionResult:
    try:
        answers = {name: answer.model_dump(exclude={"legend"}) for name, answer in response.answers.items()}
        request_id = response.raw_http_response.headers.get("x-typesafe-request-id")
        return DecisionResult(
            model=response.model, answers=answers, provider_request_id=request_id,
            input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens,
        ).validate_for(request)
    except (ValidationError, ValueError, TypeError, AttributeError, sdk.TypeSafeError):
        raise DecisionInvalidResponseError() from None
