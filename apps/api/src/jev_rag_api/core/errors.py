from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from jev_rag_api.api.schemas.errors import ErrorDetail, ErrorResponse, ValidationDetail
from jev_rag_api.application.errors import ServiceUnavailableError
from jev_rag_api.core.logging import request_id_context

ERRORS = {
    400: ("BAD_REQUEST", "Invalid request"),
    401: ("UNAUTHORIZED", "Authentication required"),
    403: ("FORBIDDEN", "Access denied"),
    404: ("NOT_FOUND", "Resource not found"),
    405: ("METHOD_NOT_ALLOWED", "Method not allowed"),
    422: ("VALIDATION_ERROR", "Invalid request"),
    503: ("SERVICE_UNAVAILABLE", "Service unavailable"),
    500: ("INTERNAL_ERROR", "Internal server error"),
}


def error_response(
    status: int,
    details: list[ValidationDetail] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    code, message = ERRORS.get(status, ("HTTP_ERROR", "Request failed"))
    body = ErrorResponse(
        error=ErrorDetail(code=code, message=message, details=details),
        request_id=request_id_context.get() or "unavailable",
    )
    return JSONResponse(body.model_dump(), status_code=status, headers=headers)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def handle_http(request: Request, exc: HTTPException) -> JSONResponse:
        headers = {}
        if exc.headers and "Allow" in exc.headers:
            headers["Allow"] = exc.headers["Allow"]
        return error_response(exc.status_code, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Dynamic dictionary keys and original input values may contain secrets.
        details = [
            ValidationDetail(field=str(error["loc"][0]), code=error["type"])
            for error in exc.errors()
            if error["loc"] and error["loc"][0] in {"body", "query", "path", "header", "cookie"}
        ]
        return error_response(422, details)

    @app.exception_handler(ServiceUnavailableError)
    async def handle_unavailable(request: Request, exc: ServiceUnavailableError) -> JSONResponse:
        return error_response(503)

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        return error_response(500)
