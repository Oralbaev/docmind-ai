import asyncio
import json
import re
import time
import uuid
from collections import defaultdict, deque
from time import perf_counter

import structlog


class RequestSecurityMiddleware:
    """Apply lightweight per-process limits to authentication and RAG routes."""

    def __init__(self, app, auth_limit: int = 15, rag_limit: int = 30, window: int = 60):
        self.app = app
        self.auth_limit = auth_limit
        self.rag_limit = rag_limit
        self.window = window
        self.requests: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self.lock = asyncio.Lock()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        length = headers.get(b"content-length")
        max_body = 10 * 1024 * 1024 + 64 * 1024
        if length:
            try:
                oversized = int(length) > max_body
            except ValueError:
                oversized = True
            if oversized:
                await self._reject(send, 413, "Request body is too large")
                return

        path = scope.get("path", "")
        prefix = "/auth" if path.startswith("/auth/") else "/rag" if path.startswith("/rag/") else None
        if prefix:
            client = scope.get("client")
            ip = client[0] if client else "unknown"
            limit = self.auth_limit if prefix == "/auth" else self.rag_limit
            now = time.monotonic()
            async with self.lock:
                bucket = self.requests[(prefix, ip)]
                while bucket and now - bucket[0] >= self.window:
                    bucket.popleft()
                if len(bucket) >= limit:
                    await self._reject(send, 429, "Too many requests")
                    return
                bucket.append(now)
                if len(self.requests) > 10_000:
                    for key in list(self.requests):
                        if not self.requests[key] or now - self.requests[key][-1] >= self.window:
                            self.requests.pop(key, None)

        supplied = headers.get(b"x-request-id", b"").decode("latin1")
        request_id = (
            supplied
            if re.fullmatch(r"[A-Za-z0-9._-]{1,64}", supplied)
            else str(uuid.uuid4())
        )

        async def send_with_id(message):
            if message["type"] == "http.response.start":
                message["headers"].append((b"x-request-id", request_id.encode("ascii")))
            await send(message)

        started = perf_counter()
        status_code = 500

        async def capture_status(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send_with_id(message)

        try:
            await self.app(scope, receive, capture_status)
        finally:
            structlog.get_logger("docmind.http").info(
                "request.completed",
                request_id=request_id,
                method=scope.get("method"),
                path=path,
                status_code=status_code,
                duration_ms=round((perf_counter() - started) * 1000, 1),
            )

    @staticmethod
    async def _reject(send, status_code: int, detail: str) -> None:
        body = json.dumps({"detail": detail}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": status_code,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
