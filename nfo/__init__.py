"""
nfo — Automatic function logging with decorators.

Output to SQLite, CSV, and Markdown.
"""

from nfo.decorators import log_call, catch, decision_log
from nfo.logger import Logger
from nfo.sinks import SQLiteSink, CSVSink, MarkdownSink
from nfo.configure import configure
from nfo.logged import logged, skip
from nfo.env import EnvTagger, DynamicRouter, DiffTracker
from nfo.llm import LLMSink, detect_prompt_injection, scan_entry_for_injection
from nfo.redact import is_sensitive_key, redact_value, redact_kwargs, redact_string, redact_args
from nfo.auto import auto_log, auto_log_by_name
from nfo.json_sink import JSONSink
from nfo.webhook import WebhookSink
from nfo.meta import ThresholdPolicy
from nfo.extractors import extract_meta, register_extractor
from nfo.meta_decorators import meta_log
from nfo.binary_router import BinaryAwareRouter
from nfo.buffered_sink import AsyncBufferedSink
from nfo.ring_buffer_sink import RingBufferSink
from nfo.terminal import TerminalSink
from nfo.pipeline_sink import PipelineSink
from nfo.log_flow import LogFlowParser, build_log_flow_graph, compress_logs_for_llm
import logging as _logging


def get_logger(name: str) -> _logging.Logger:
    """Return a stdlib logger bridged to nfo sinks via configure().

    Drop-in replacement for ``logging.getLogger(name)``.  When
    ``configure(modules=[...])`` has been called, the returned logger's
    records are automatically forwarded to every configured nfo sink
    (SQLite, CSV, …) through the :class:`_StdlibBridge` handler.
    """
    return _logging.getLogger(name)


def _direct_emit(level: str, message: str, **extra) -> None:
    """
    Log a plain message as a structured LogEntry without a decorator.

    Emits directly to all configured nfo sinks.  Falls back to stdlib
    logging when ``configure()`` has not been called yet.

    Usage::

        import nfo
        nfo.configure(sinks=["sqlite:app.db"])
        nfo.info("Server started", port=8888)
        nfo.event("user.login", user_id=42, role="admin")
    """
    from nfo.configure import _last_logger
    from nfo.models import LogEntry

    if _last_logger is None:
        _logging.getLogger("nfo").log(
            getattr(_logging, level.upper(), _logging.INFO), message
        )
        return

    entry = LogEntry(
        timestamp=LogEntry.now(),
        level=level.upper(),
        function_name="nfo.event",
        module="nfo",
        args=(),
        kwargs=extra,
        arg_types=[],
        kwarg_types={},
        return_value=message,
        return_type="str",
        exception=None,
        exception_type=None,
        traceback=None,
        duration_ms=None,
        extra={"message": message, **extra},
    )
    _last_logger.emit(entry)


def debug(message: str, **extra) -> None:
    """Log a DEBUG-level event directly to nfo sinks."""
    _direct_emit("DEBUG", message, **extra)


def info(message: str, **extra) -> None:
    """Log an INFO-level event directly to nfo sinks."""
    _direct_emit("INFO", message, **extra)


def warning(message: str, **extra) -> None:
    """Log a WARNING-level event directly to nfo sinks."""
    _direct_emit("WARNING", message, **extra)


def error(message: str, **extra) -> None:
    """Log an ERROR-level event directly to nfo sinks."""
    _direct_emit("ERROR", message, **extra)


def event(name: str, **extra) -> None:
    """Log a named business event at INFO level with structured kwargs."""
    _direct_emit("INFO", name, event=name, **extra)


# Lazy import for optional click dependency
def _lazy_click():
    from nfo.click import NfoGroup, NfoCommand, nfo_options
    return NfoGroup, NfoCommand, nfo_options


# Lazy import for optional dependencies
def __getattr__(name: str):
    if name == "PrometheusSink":
        from nfo.prometheus import PrometheusSink
        return PrometheusSink
    if name in ("NfoGroup", "NfoCommand", "nfo_options"):
        from nfo import click as _click
        return getattr(_click, name)
    if name == "FastAPIMiddleware":
        from nfo.fastapi_middleware import FastAPIMiddleware
        return FastAPIMiddleware
    raise AttributeError(f"module 'nfo' has no attribute {name!r}")

__version__ = "0.2.20"

__all__ = [
    "log_call",
    "catch",
    "logged",
    "skip",
    "configure",
    "Logger",
    "SQLiteSink",
    "CSVSink",
    "MarkdownSink",
    "JSONSink",
    "LLMSink",
    "PrometheusSink",
    "WebhookSink",
    "EnvTagger",
    "DynamicRouter",
    "DiffTracker",
    "detect_prompt_injection",
    "scan_entry_for_injection",
    "auto_log",
    "auto_log_by_name",
    "ThresholdPolicy",
    "extract_meta",
    "register_extractor",
    "meta_log",
    "BinaryAwareRouter",
    "AsyncBufferedSink",
    "RingBufferSink",
    "TerminalSink",
    "PipelineSink",
    "LogFlowParser",
    "build_log_flow_graph",
    "compress_logs_for_llm",
    "get_logger",
    "decision_log",
    "NfoGroup",
    "NfoCommand",
    "nfo_options",
    "debug",
    "info",
    "warning",
    "error",
    "event",
    "FastAPIMiddleware",
    "is_sensitive_key",
    "redact_value",
    "redact_kwargs",
    "redact_string",
    "redact_args",
]
