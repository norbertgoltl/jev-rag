import re
from time import perf_counter
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from jev_rag_api.core.logging import logger, request_id_context

REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,64}", re.ASCII)


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        values = [
            value.decode("latin-1")
            for key, value in scope["headers"]
            if key.lower() == b"x-request-id"
        ]
        request_id = (
            values[0]
            if len(values) == 1 and REQUEST_ID_PATTERN.fullmatch(values[0])
            else str(uuid4())
        )
        token = request_id_context.set(request_id)
        started = perf_counter()
        status_code = 500
        completed = False
        exception_type = None

        async def send_response(message: Message) -> None:
            nonlocal status_code, completed
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() != b"x-request-id"
                ]
                message["headers"] = headers + [(b"x-request-id", request_id.encode("ascii"))]
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                completed = True

        try:
            await self.app(scope, receive, send_response)
        except Exception as exc:
            exception_type = type(exc).__name__
            # ServerErrorMiddleware re-raises after sending the sanitized 500.
            # Do not let Uvicorn print the original exception and its contents.
            if not completed:
                raise
        finally:
            logger.info(
                "http_request_completed",
                extra={
                    "method": scope["method"],
                    "path": scope["path"],
                    "status_code": status_code,
                    "duration_ms": round((perf_counter() - started) * 1000, 3),
                    "exception_type": exception_type,
                },
            )
            request_id_context.reset(token)
