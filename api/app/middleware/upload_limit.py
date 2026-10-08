from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class UploadLimitMiddleware:
    """Reject oversized multipart uploads while ASGI is still receiving the body."""

    def __init__(self, app: ASGIApp, max_upload_bytes: int) -> None:
        self.app = app
        self.max_upload_bytes = max_upload_bytes
        self.max_upload_mb = max_upload_bytes // (1024 * 1024)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") != "/api/upload":
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        content_length = headers.get(b"content-length")
        if content_length:
            try:
                if int(content_length) > self.max_upload_bytes + 1024 * 1024:
                    await self._reject(scope, receive, send)
                    return
            except ValueError:
                pass

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_upload_bytes + 1024 * 1024:
                    await self._reject(scope, receive, send)
                    raise _UploadTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _UploadTooLarge:
            return

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = JSONResponse(
            {"detail": f"File is too large, max {self.max_upload_mb} MB"},
            status_code=413,
        )
        await response(scope, receive, send)


class _UploadTooLarge(Exception):
    pass
