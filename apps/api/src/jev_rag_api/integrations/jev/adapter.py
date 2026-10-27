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


class TypeSafeDecisionAdapter:
    def __init__(self, client: sdk.AsyncTypeSafeClient) -> None:
        configure_sdk_logging()
        self.client = client

    async def evaluate(self, request: DecisionRequest) -> DecisionResult:
        started = time.perf_counter()
        try:
            response = await self.client.system_one(
                state=request.state, questions=map_questions(request)
            )
            result = map_response(request, response)
        except sdk.TypeSafeAPITimeoutError:
            error: DecisionError = DecisionTimeoutError()
        except sdk.TypeSafeAPIResponseValidationError:
            error = DecisionInvalidResponseError()
        except sdk.TypeSafeAPIError as exc:
            status = exc.status_code if hasattr(exc, "status_code") else exc.status
            error_type = {
                400: DecisionInvalidRequestError,
                422: DecisionInvalidRequestError,
                401: DecisionAuthenticationError,
                403: DecisionAuthenticationError,
                429: DecisionRateLimitedError,
            }.get(status, DecisionUnavailableError)
            error = error_type()
        except sdk.TypeSafeAPIConnectionError:
            error = DecisionUnavailableError()
        except sdk.TypeSafeError:
            error = DecisionInvalidRequestError()
        except DecisionError as exc:
            error = exc
        else:
            logger.info(
                "jev_decision_completed",
                extra={
                    "model": result.model,
                    "provider_request_id": result.provider_request_id,
                    "question_count": len(request.questions),
                    "question_types": [q.type for q in request.questions.values()],
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                    "input_tokens": result.input_tokens,
                },
            )
            return result
        logger.warning(
            "jev_decision_failed",
            extra={
                "error_code": error.code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "question_count": len(request.questions),
            },
        )
        raise error from None
