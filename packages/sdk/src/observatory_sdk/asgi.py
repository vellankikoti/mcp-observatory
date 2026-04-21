from __future__ import annotations

from typing import Any

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest


def metrics_asgi_app(registry: CollectorRegistry) -> Any:
    async def app(scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            return
        body = generate_latest(registry)
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", CONTENT_TYPE_LATEST.encode())],
            }
        )
        await send({"type": "http.response.body", "body": body})

    return app
