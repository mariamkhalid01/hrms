"""Request correlation and a safe fallback for unhandled application errors."""

import logging
import time
from uuid import UUID, uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_response

logger = logging.getLogger("hr_process_mining.requests")


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        supplied_id = Headers(scope=scope).get("x-request-id", "")
        try:
            request_id = str(UUID(supplied_id))
        except (ValueError, AttributeError):
            request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        started = time.perf_counter()
        status_code = 500
        response_started = False

        async def send_with_context(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_context)
        except Exception:
            logger.exception("Unhandled request error request_id=%s", request_id)
            if response_started:
                raise
            response = error_response(
                500,
                "INTERNAL_ERROR",
                "An unexpected error occurred. Please try again.",
                request_id,
            )
            await response(scope, receive, send_with_context)
        finally:
            logger.info(
                "%s %s status=%s duration_ms=%.1f request_id=%s",
                scope["method"],
                scope["path"],
                status_code,
                (time.perf_counter() - started) * 1000,
                request_id,
            )
