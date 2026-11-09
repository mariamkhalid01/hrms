"""Bound the request stream before Starlette parses or spools multipart data."""

from starlette.datastructures import Headers
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_response


class BodyLimitExceeded(HTTPException):
    def __init__(self) -> None:
        super().__init__(413, "The upload exceeds the allowed file size.")


class UploadSizeLimitMiddleware:
    def __init__(self, app: ASGIApp, max_body_bytes: int) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") != "/api/v1/datasets/upload":
            await self.app(scope, receive, send)
            return

        async def reject() -> None:
            response = error_response(
                413,
                "UPLOAD_TOO_LARGE",
                "The upload exceeds the allowed file size.",
                scope.get("state", {}).get("request_id", ""),
            )
            await response(scope, receive, send)

        length = Headers(scope=scope).get("content-length")
        if length:
            try:
                too_large = int(length) > self.max_body_bytes
            except ValueError:
                too_large = False
            if too_large:
                await reject()
                return

        received = 0

        async def bounded_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_body_bytes:
                    raise BodyLimitExceeded
            return message

        try:
            await self.app(scope, bounded_receive, send)
        except BodyLimitExceeded:
            await reject()
