from contextvars import ContextVar, Token
from dataclasses import dataclass
from uuid import uuid4

REQUEST_ID_HEADER = "X-Request-Id"
TRACE_ID_HEADER = "X-Trace-Id"

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)


@dataclass(frozen=True)
class RequestContextTokens:
    request_id: Token[str | None]
    trace_id: Token[str | None]


def generate_request_id() -> str:
    return str(uuid4())


def bind_request_context(request_id: str, trace_id: str) -> RequestContextTokens:
    return RequestContextTokens(
        request_id=_request_id.set(request_id),
        trace_id=_trace_id.set(trace_id),
    )


def reset_request_context(tokens: RequestContextTokens) -> None:
    _request_id.reset(tokens.request_id)
    _trace_id.reset(tokens.trace_id)


def get_request_id() -> str | None:
    return _request_id.get()


def get_trace_id() -> str | None:
    return _trace_id.get()
