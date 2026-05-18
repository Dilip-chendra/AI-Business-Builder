import json
import logging
import logging.config
import sys


class _JSONFormatter(logging.Formatter):
    """Emit log records as single-line JSON for structured log aggregators."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Attach any extra fields passed via `extra=` kwarg
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "taskName",
            } and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, default=str)


def configure_logging(json_logs: bool = False) -> None:
    """Configure application logging.

    In development (``json_logs=False``) a human-readable format is used.
    In production set ``json_logs=True`` (or set ``APP_ENV=production``) to
    emit newline-delimited JSON suitable for log aggregators such as
    CloudWatch, Datadog, or Loki.
    """
    from app.core.config import settings  # local import to avoid circular deps

    use_json = json_logs or settings.is_production

    handler = logging.StreamHandler(sys.stdout)
    if use_json:
        handler.setFormatter(_JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s %(name)s  %(message)s")
        )

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Remove any handlers added by basicConfig before us
    root.handlers.clear()
    root.addHandler(handler)

    # Quieten noisy third-party loggers
    for noisy in ("httpx", "httpcore", "openai", "stripe"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
