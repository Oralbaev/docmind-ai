import asyncio
import uuid

from app.core.middleware import RequestSecurityMiddleware


def test_rag_rate_limit_is_scoped_per_ip_and_route_family():
    statuses = []

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    middleware = RequestSecurityMiddleware(app, auth_limit=1, rag_limit=1)

    async def request(path):
        sent = []

        async def send(message):
            sent.append(message)

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        scope = {
            "type": "http",
            "path": path,
            "headers": [],
            "client": ("127.0.0.1", 1234),
        }
        await middleware(scope, receive, send)
        statuses.append(sent[0]["status"])
        return sent

    async def run():
        first = await request("/rag/ask")
        second = await request("/rag/agent")
        other = await request("/auth/login")
        headers = dict(first[0]["headers"])
        uuid.UUID(headers[b"x-request-id"].decode())
        assert second[-1]["body"] == b'{"detail": "Too many requests"}'
        assert other[0]["status"] == 200

    asyncio.run(run())
    assert statuses == [200, 429, 200]


def test_rejects_declared_oversized_request_before_app():
    async def app(*args):
        raise AssertionError("app should not be called")

    middleware = RequestSecurityMiddleware(app)
    sent = []

    async def send(message):
        sent.append(message)

    async def receive():
        raise AssertionError("body should not be read")

    async def run():
        await middleware(
            {"type": "http", "path": "/auth/login", "headers": [(b"content-length", b"999999999")]},
            receive,
            send,
        )

    asyncio.run(run())
    assert sent[0]["status"] == 413
