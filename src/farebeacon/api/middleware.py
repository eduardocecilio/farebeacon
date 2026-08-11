from __future__ import annotations

import re

from fastapi.responses import JSONResponse
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from farebeacon.ids import new_id

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        supplied = headers.get("X-Request-ID", "")
        request_id = supplied if REQUEST_ID_PATTERN.fullmatch(supplied) else new_id("req")
        scope.setdefault("state", {})["request_id"] = request_id
        max_body_bytes = int(scope["app"].state.settings.max_request_body_bytes)

        async def secure_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_headers = MutableHeaders(scope=message)
                response_headers["X-Request-ID"] = request_id
                response_headers["X-Content-Type-Options"] = "nosniff"
                response_headers["X-Frame-Options"] = "DENY"
                response_headers["Referrer-Policy"] = "no-referrer"
                response_headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
            await send(message)

        content_length = headers.get("Content-Length")
        if content_length is not None:
            try:
                declared_size = int(content_length)
            except ValueError:
                declared_size = 0
            if declared_size > max_body_bytes:
                await self._reject(scope, receive, secure_send, request_id, max_body_bytes)
                return

        buffered_messages: list[Message] = []
        received_size = 0
        while True:
            message = await receive()
            buffered_messages.append(message)
            if message["type"] == "http.request":
                received_size += len(message.get("body", b""))
                if received_size > max_body_bytes:
                    await self._reject(scope, receive, secure_send, request_id, max_body_bytes)
                    return
                if not message.get("more_body", False):
                    break
            elif message["type"] == "http.disconnect":
                break

        message_index = 0

        async def replay_receive() -> Message:
            nonlocal message_index
            if message_index < len(buffered_messages):
                message = buffered_messages[message_index]
                message_index += 1
                return message
            return await receive()

        await self.app(scope, replay_receive, secure_send)

    @staticmethod
    async def _reject(
        scope: Scope,
        receive: Receive,
        send: Send,
        request_id: str,
        max_body_bytes: int,
    ) -> None:
        response = JSONResponse(
            status_code=413,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "The request body is too large.",
                    "details": {"max_bytes": max_body_bytes},
                },
                "meta": {"request_id": request_id},
            },
        )
        await response(scope, receive, send)
