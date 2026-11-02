"""ASGI middleware for measuring WebSocket authentication setup time."""

from time import perf_counter_ns

from channels.auth import AuthMiddlewareStack


class WebSocketAuthTimingMiddleware:
    """Measure Cookie/Session/Auth setup before the consumer runs."""

    def __init__(self, app):
        self.app = app
        self.auth_app = AuthMiddlewareStack(self._call_after_auth)

    async def __call__(self, scope, receive, send):
        # Scope is unique to each ASGI connection, so concurrent connections
        # keep independent start times.
        scope["chat_auth_middleware_started_ns"] = perf_counter_ns()
        return await self.auth_app(scope, receive, send)

    async def _call_after_auth(self, scope, receive, send):
        started_ns = scope.pop("chat_auth_middleware_started_ns")
        scope["chat_auth_middleware_ms"] = (
            perf_counter_ns() - started_ns
        ) / 1_000_000
        return await self.app(scope, receive, send)
