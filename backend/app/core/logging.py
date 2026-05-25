import logging
from logging.config import dictConfig

from app.core.request_context import get_request_id, get_trace_id


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = getattr(record, "request_id", None) or get_request_id() or "-"
        record.trace_id = getattr(record, "trace_id", None) or get_trace_id() or "-"
        return True


def configure_logging(log_level: str) -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "request_context": {
                    "()": "app.core.logging.RequestContextFilter",
                },
            },
            "formatters": {
                "standard": {
                    "format": (
                        "%(asctime)s %(levelname)s %(name)s "
                        "request_id=%(request_id)s trace_id=%(trace_id)s %(message)s"
                    ),
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "filters": ["request_context"],
                    "formatter": "standard",
                },
            },
            "loggers": {
                "app": {
                    "handlers": ["console"],
                    "level": log_level.upper(),
                    "propagate": False,
                },
            },
        }
    )
