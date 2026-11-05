import logging
import time

import typesafe_sdk as sdk

from jev_rag_api.domain.decisions.errors import (
    DecisionAuthenticationError,
    DecisionError,
    DecisionInvalidRequestError,
    DecisionInvalidResponseError,
    DecisionRateLimitedError,
    DecisionTimeoutError,
    DecisionUnavailableError,
)
from jev_rag_api.domain.decisions.models import DecisionRequest, DecisionResult

from .mapper import map_questions, map_response

logger = logging.getLogger(__name__)


class SafeSDKLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = "typesafe_sdk_warning"
        record.args = ()
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return True


def configure_sdk_logging() -> None:
    sdk_logger = logging.getLogger("typesafe_sdk")
    sdk_logger.setLevel(logging.WARNING)
    if not any(isinstance(item, SafeSDKLogFilter) for item in sdk_logger.filters):
        sdk_logger.addFilter(SafeSDKLogFilter())


_STATUS_ERRORS: tuple[tuple[type[sdk.TypeSafeError], type[DecisionError]], ...] = (
    (sdk.TypeSafeBadRequestError, DecisionInvalidRequestError),
    (sdk.TypeSafeUnprocessableEntityError, DecisionInvalidRequestError),
    (sdk.TypeSafeAuthenticationError, DecisionAuthenticationError),
    (sdk.TypeSafePermissionDeniedError, DecisionAuthenticationError),
    (sdk.TypeSafeRateLimitError, DecisionRateLimitedError),
)


def translate_sdk_error(error: sdk.TypeSafeError) -> DecisionError:
    """Map an SDK failure raised by the provider call to a sanitized domain error."""
    if isinstance(error, sdk.TypeSafeAPITimeoutError):
        return DecisionTimeoutError()
    if isinstance(error, sdk.TypeSafeAPIResponseValidationError):
        return DecisionInvalidResponseError()
    for sdk_type, domain_type in _STATUS_ERRORS:
        if isinstance(error, sdk_type):
            return domain_type()
    # Remaining API status errors, connection failures and unknown SDK errors are provider-side.
    return DecisionUnavailableError()


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)


class TypeSafeDecisionAdapter:
    def __init__(self, client: sdk.AsyncTypeSafeClient) -> None:
        configure_sdk_logging()
        self.client = client

    async def evaluate(self, request: DecisionRequest) -> DecisionResult:
        started = time.perf_counter()
        try:
            result = await self._call_provider(request)
        except DecisionError as error:
            logger.warning(
                "jev_decision_failed",
                extra={
                    "error_code": error.code,
                    "duration_ms": _elapsed_ms(started),
                    "question_count": len(request.questions),
                },
            )
            raise error from None
        logger.info(
            "jev_decision_completed",
            extra={
                "model": result.model,
                "provider_request_id": result.provider_request_id,
                "question_count": len(request.questions),
                "question_types": [q.type for q in request.questions.values()],
                "duration_ms": _elapsed_ms(started),
                "input_tokens": result.input_tokens,
            },
        )
        return result

    async def _call_provider(self, request: DecisionRequest) -> DecisionResult:
        try:
            questions = map_questions(request)
        except sdk.TypeSafeError, ValueError:
            raise DecisionInvalidRequestError() from None
        try:
            response = await self.client.system_one(state=request.state, questions=questions)
        except sdk.TypeSafeError as error:
            raise translate_sdk_error(error) from None
        return map_response(request, response)
