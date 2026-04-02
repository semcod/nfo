"""
nfo.context — temporary context management for logging.

Provides context managers for temporarily changing log settings,
adding contextual metadata, and scoping log output.

Usage::

    from nfo.context import log_context, temp_level, temp_sink

    # Add context to all logs within block
    with log_context(user_id="123", request_id="abc"):
        result = process_order()  # logs will include user_id and request_id

    # Temporarily change log level
    with temp_level("DEBUG"):
        debug_operation()  # logs at DEBUG level

    # Temporarily add a sink
    with temp_sink("markdown:temp.md"):
        generate_report()  # also logs to temp.md
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Generator

from nfo.configure import configure, get_config
from nfo.logger import Logger
from nfo.decorators import get_default_logger, set_default_logger

# Thread-local storage for context stack
_context_stack: ContextVar[list[dict[str, Any]]] = ContextVar("_context_stack", default=[])


def get_current_context() -> dict[str, Any]:
    """Get merged context from all active context managers."""
    stack = _context_stack.get()
    merged = {}
    for ctx in stack:
        merged.update(ctx)
    return merged


@contextmanager
def log_context(**metadata) -> Generator[dict[str, Any], None, None]:
    """Temporarily add metadata context to all log entries.

    All logs within this context manager will include the specified
    metadata in their extra field.

    Args:
        **metadata: Key-value pairs to add to log context

    Example::

        with log_context(user_id="123", trace_id="abc"):
            result = process_data()  # logs include user_id and trace_id
    """
    stack = _context_stack.get()
    new_stack = stack + [metadata]
    token = _context_stack.set(new_stack)

    # Inject context into current logger
    logger = get_default_logger()
    if logger and hasattr(logger, '_context_hooks'):
        logger._context_hooks.append(lambda: metadata)

    try:
        yield metadata
    finally:
        _context_stack.reset(token)


@contextmanager
def temp_level(level: str) -> Generator[None, None, None]:
    """Temporarily change the log level for the current logger.

    Args:
        level: Log level to use (DEBUG, INFO, WARNING, ERROR)

    Example::

        with temp_level("DEBUG"):
            debug_info = get_debug_data()  # DEBUG logs enabled
    """
    logger = get_default_logger()
    if logger is None:
        yield
        return

    original_level = logger.level
    logger.level = level

    try:
        yield
    finally:
        logger.level = original_level


@contextmanager
def temp_sink(sink_spec: str) -> Generator[Any, None, None]:
    """Temporarily add a sink for the duration of the context.

    Args:
        sink_spec: Sink specification (e.g., "sqlite:temp.db", "csv:temp.csv")

    Example::

        with temp_sink("markdown:debug.md"):
            run_debug()  # logs also go to debug.md
    """
    from nfo.configure import _parse_sink_spec

    logger = get_default_logger()
    if logger is None:
        yield None
        return

    sink = _parse_sink_spec(sink_spec)
    logger._sinks.append(sink)

    try:
        yield sink
    finally:
        if sink in logger._sinks:
            logger._sinks.remove(sink)
        sink.close()


@contextmanager
def silence() -> Generator[None, None, None]:
    """Temporarily silence all logging within this context.

    Useful for suppressing expected noisy operations.

    Example::

        with silence():
            noisy_check()  # no logs emitted
    """
    logger = get_default_logger()
    if logger is None:
        yield
        return

    original_sinks = logger._sinks.copy()
    logger._sinks.clear()

    try:
        yield
    finally:
        logger._sinks = original_sinks


@contextmanager
def temp_config(**kwargs) -> Generator[None, None, None]:
    """Temporarily reconfigure nfo with new settings.

    Original configuration is restored after the context.

    Args:
        **kwargs: Configuration options (sinks, level, name, etc.)

    Example::

        with temp_config(sinks=["csv:temp.csv"], level="DEBUG"):
            run_with_temp_config()  # uses temp config
    """
    # Save original config
    original_logger = get_default_logger()
    original_config = get_config() if get_config() else {}

    # Apply new config
    configure(force=True, **kwargs)

    try:
        yield
    finally:
        # Restore original
        if original_config:
            configure(force=True, **original_config)
        else:
            # No original config, clear current
            logger = get_default_logger()
            if logger:
                logger._sinks.clear()


@contextmanager
def span(name: str, **attributes) -> Generator[dict[str, Any], None, None]:
    """Create a tracing span for a block of code.

    Similar to log_context but specifically for tracing/span semantics.
    Records duration and optionally success/failure.

    Args:
        name: Span name
        **attributes: Additional span attributes

    Example::

        with span("process_order", order_id="123") as span_data:
            process_order()  # span tracks duration
            span_data["status"] = "success"
    """
    import time
    from nfo.models import LogEntry

    logger = get_default_logger()
    start_time = time.time()

    span_data = {
        "name": name,
        "start_time": start_time,
        "attributes": attributes,
    }

    # Merge with existing context
    with log_context(**{f"span.{name}.{k}": v for k, v in attributes.items()}):
        try:
            yield span_data
            span_data["status"] = "success"
        except Exception as e:
            span_data["status"] = "error"
            span_data["error"] = str(e)
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            span_data["duration_ms"] = duration_ms

            if logger:
                entry = LogEntry(
                    level="INFO",
                    function_name=f"span:{name}",
                    module="nfo.context",
                    duration_ms=duration_ms,
                    extra={
                        "span_name": name,
                        "span_attributes": attributes,
                        **span_data,
                    },
                )
                logger.emit(entry)


def with_context(**metadata):
    """Decorator to add context to a function.

    Args:
        **metadata: Key-value pairs to add to log context

    Example::

        @with_context(operation="process", critical=True)
        def process_data(data):
            # All logs include operation="process", critical=True
            return transform(data)
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            with log_context(**metadata):
                return func(*args, **kwargs)
        return wrapper
    return decorator
