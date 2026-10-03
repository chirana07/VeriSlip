"""Early request-body limits for public document and image ingestion routes."""

from __future__ import annotations

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from core.security.image_sanitizer import MAX_IMAGE_UPLOAD_BYTES

MULTIPART_OVERHEAD_BYTES = 1024 * 1024
JSON_OVERHEAD_BYTES = 256 * 1024
MAX_BASE64_IMAGE_BYTES = ((MAX_IMAGE_UPLOAD_BYTES + 2) // 3) * 4

# Limits include multipart/JSON framing. Per-file limits are still enforced by
# the shared decoder after parsing; these caps protect the parser and spool.
UPLOAD_BODY_LIMITS = {
    "/api/v1/verify": MAX_IMAGE_UPLOAD_BYTES + MULTIPART_OVERHEAD_BYTES,
    "/api/v1/verify/jobs": MAX_IMAGE_UPLOAD_BYTES + MULTIPART_OVERHEAD_BYTES,
    "/api/v1/live/verify": MAX_IMAGE_UPLOAD_BYTES + MULTIPART_OVERHEAD_BYTES,
    "/api/v1/integrations/woocommerce/verify": (
        MAX_IMAGE_UPLOAD_BYTES + MULTIPART_OVERHEAD_BYTES
    ),
    "/api/v1/batch-verify": (25 * MAX_IMAGE_UPLOAD_BYTES) + MULTIPART_OVERHEAD_BYTES,
    "/api/v1/webhook/whatsapp": MAX_BASE64_IMAGE_BYTES + JSON_OVERHEAD_BYTES,
    "/api/v1/courier/verify": MAX_BASE64_IMAGE_BYTES + JSON_OVERHEAD_BYTES,
    "/api/v1/integrations/shopify/webhooks/orders-create": 1_000_000,
}


class _RequestBodyTooLarge(Exception):
    pass


class UploadBodyLimitMiddleware:
    """Reject oversized upload bodies before multipart or JSON parsing.

    Both declared ``Content-Length`` and streamed bytes are checked, so clients
    cannot bypass the limit by omitting or falsifying the header.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return

        limit = UPLOAD_BODY_LIMITS.get(scope.get("path", ""))
        if limit is None:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", ()))
        declared = headers.get(b"content-length")
        if declared is not None:
            try:
                declared_size = int(declared)
            except (TypeError, ValueError):
                await self._respond(send, 400, "Upload request is malformed.")
                return
            if declared_size < 0:
                await self._respond(send, 400, "Upload request is malformed.")
                return
            if declared_size > limit:
                await self._respond(
                    send, 413, "Upload request exceeds the permitted size."
                )
                return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _RequestBodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _RequestBodyTooLarge:
            await self._respond(send, 413, "Upload request exceeds the permitted size.")

    @staticmethod
    async def _respond(send: Send, status_code: int, detail: str) -> None:
        body = json.dumps({"detail": detail}, separators=(",", ":")).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": status_code,
                "headers": [
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"content-type", b"application/json"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
