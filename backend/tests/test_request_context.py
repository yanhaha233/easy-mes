import logging

from app.core.logging import RequestContextFilter
from app.core.request_context import bind_request_context, reset_request_context
from app.middleware.request_context import normalize_correlation_id


def test_request_context_filter_injects_bound_ids() -> None:
    logger = logging.getLogger("app.tests.request_context")
    record = logger.makeRecord(
        name=logger.name,
        level=logging.INFO,
        fn=__file__,
        lno=1,
        msg="test",
        args=(),
        exc_info=None,
    )
    tokens = bind_request_context("req-001", "trace-001")
    try:
        assert RequestContextFilter().filter(record)
    finally:
        reset_request_context(tokens)

    assert record.request_id == "req-001"
    assert record.trace_id == "trace-001"


def test_correlation_id_normalization_rejects_unsafe_values() -> None:
    assert normalize_correlation_id(" req-001 ") == "req-001"
    assert normalize_correlation_id("") is None
    assert normalize_correlation_id("a" * 129) is None
    assert normalize_correlation_id("bad value") is None
