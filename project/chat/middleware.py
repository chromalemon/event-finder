"""ASGI middleware for measuring WebSocket authentication setup time."""

from time import perf_counter_ns

from channels.auth import AuthMiddlewareStack


class WebSocketAuthTimingMiddleware:
    """Measure Cookie/Session/Auth middleware setup before the consumer runs.

    The timer starts when the WebSocket scope reaches this middleware and ends
    immediately before the wrapped application (normally URLRouter) is called.
    It therefore includes Channels' cookie parsing, session loading, and user
    authentication setup.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        started_ns = perf_counter_ns()

        async def timed_app(inner_scope, inner_receive, inner_send):
            inner_scope["chat_auth_middleware_ms"] = (
                perf_counter_ns() - started_ns
            ) / 1_000_000
            return await self.app(inner_scope, inner_receive, inner_send)

        return await AuthMiddlewareStack(timed_app)(scope, receive, send)
