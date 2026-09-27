"""Stdlib logging setup with structured `extra` fields appended to each line."""

import logging

_STANDARD_ATTRS = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
}


class _ExtraFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras = {k: v for k, v in record.__dict__.items() if k not in _STANDARD_ATTRS}
        if not extras:
            return base
        return base + " " + " ".join(f"{k}={v}" for k, v in extras.items())


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger once."""
    handler = logging.StreamHandler()
    handler.setFormatter(_ExtraFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
