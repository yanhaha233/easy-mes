import logging
import re
from time import perf_counter
from typing import Any

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.request_context import (
    REQUEST_ID_HEADER,
    TRACE_ID_HEADER,
    bind_request_context,
    generate_request_id,
    reset_request_context,
)

_SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:/+=,@-]{1,128}$")


def normalize_correlation_id(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized or not _SAFE_ID_PATTERN.fullmatch(normalized):
        return None
    return normalized


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.logger = logging.getLogger("app.request")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        request_id = normalize_correlation_id(headers.get(REQUEST_ID_HEADER)) or generate_request_id()
        trace_id = normalize_correlation_id(headers.get(TRACE_ID_HEADER)) or request_id
        tokens = bind_request_context(request_id, trace_id)
        scope.setdefault("state", {})
        scope["state"]["request_id"] = request_id
        scope["state"]["trace_id"] = trace_id

        start = perf_counter()
        status_code = 500

        async def send_with_request_context(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_headers = MutableHeaders(scope=message)
                response_headers[REQUEST_ID_HEADER] = request_id
                response_headers[TRACE_ID_HEADER] = trace_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_context)
        except Exception:
            self._log_request(scope, status_code, start, failed=True)
            raise
        else:
            self._log_request(scope, status_code, start, failed=False)
        finally:
            reset_request_context(tokens)

    def _log_request(self, scope: Scope, status_code: int, start: float, *, failed: bool) -> None:
        duration_ms = (perf_counter() - start) * 1000
        client = scope.get("client")
        client_host = client[0] if client else None
        log_context: dict[str, Any] = {
            "http_method": scope.get("method", "-"),
            "http_path": scope.get("path", "-"),
            "http_status_code": status_code,
            "duration_ms": round(duration_ms, 2),
            "client_host": client_host,
        }
        message = (
            "request failed method=%s path=%s status_code=%s duration_ms=%.2f client_host=%s"
            if failed
            else "request completed method=%s path=%s status_code=%s duration_ms=%.2f client_host=%s"
        )
        log_method = self.logger.exception if failed else self.logger.info
        log_method(
            message,
            scope.get("method", "-"),
            scope.get("path", "-"),
            status_code,
            duration_ms,
            client_host,
            extra=log_context,
        )
