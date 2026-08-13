"""Observability: global Trace_ID + timestamped rolling log (Constitution Art. 4.1)."""
import logging
import os
import uuid

_configured = False


def generate_trace_id() -> str:
    """Generate a globally unique Trace_ID for one user request."""
    return uuid.uuid4().hex


def _get_logger(log_file: str) -> logging.Logger:
    global _configured
    logger = logging.getLogger("hydra")
    if not _configured:
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        _configured = True
    return logger


def log_event(trace_id: str, stage: str, message: str = "", log_file: str = "logs/hydra.log") -> None:
    """Record a lifecycle event tagged with Trace_ID. Any operator can grep trace_id to rebuild a request."""
    _get_logger(log_file).info(f"[{trace_id}] {stage}: {message}")
