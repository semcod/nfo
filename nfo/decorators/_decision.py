"""@decision_log decorator for logging decision outcomes."""

from __future__ import annotations

import functools
import inspect
import time
import traceback as tb_mod
from typing import Any, Callable, Dict, Optional

from nfo.models import LogEntry

from ._core import _get_default_logger, _module_of


def decision_log(
    func: Optional[Callable] = None,
    *,
    name: Optional[str] = None,
    level: str = "INFO",
    logger: Any = None,
) -> Any:
    """Decorator that logs decision outcomes with structured reasons.

    The decorated function **must** return a dict (or object with ``decision``
    and ``reason`` attributes).  At minimum the return value should contain::

        {"decision": "downgraded", "reason": "hourly_limit_80%", ...}

    Any extra keys in the returned dict are included in ``entry.extra``.
    If the return value is not a dict, it is stored as-is under the
    ``"decision"`` key.

    Args:
        name: Decision name for the log entry (defaults to function name).
        level: Log level (default ``"INFO"``).
        logger: Optional logger instance.

    Example::

        @decision_log(name="budget_check")
        def check_budget(requested_mode: str) -> dict:
            if over_budget:
                return {"decision": "downgraded", "reason": "hourly_80%",
                        "from_mode": requested_mode, "to_mode": "hybrid"}
            return {"decision": "ok", "reason": "within_limits"}
    """

    def decorator(fn: Callable) -> Callable:
        decision_name = name or fn.__qualname__

        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                _logger = logger or _get_default_logger()
                start = time.perf_counter()
                try:
                    result = await fn(*args, **kwargs)
                    duration = (time.perf_counter() - start) * 1000
                    extra = _build_decision_extra(decision_name, result)
                    entry = LogEntry(
                        timestamp=LogEntry.now(),
                        level=level.upper(),
                        function_name=decision_name,
                        module=_module_of(fn),
                        args=(),
                        kwargs={},
                        arg_types=[],
                        kwarg_types={},
                        return_value=extra.get("decision"),
                        return_type="decision",
                        duration_ms=round(duration, 3),
                        extra=extra,
                    )
                    _logger.emit(entry)
                    return result
                except Exception as exc:
                    duration = (time.perf_counter() - start) * 1000
                    entry = LogEntry(
                        timestamp=LogEntry.now(),
                        level="ERROR",
                        function_name=decision_name,
                        module=_module_of(fn),
                        args=(),
                        kwargs={},
                        arg_types=[],
                        kwarg_types={},
                        exception=str(exc),
                        exception_type=type(exc).__name__,
                        traceback=tb_mod.format_exc(),
                        duration_ms=round(duration, 3),
                        extra={"decision_name": decision_name},
                    )
                    _logger.emit(entry)
                    raise
            return async_wrapper

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            _logger = logger or _get_default_logger()
            start = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
                duration = (time.perf_counter() - start) * 1000
                extra = _build_decision_extra(decision_name, result)
                entry = LogEntry(
                    timestamp=LogEntry.now(),
                    level=level.upper(),
                    function_name=decision_name,
                    module=_module_of(fn),
                    args=(),
                    kwargs={},
                    arg_types=[],
                    kwarg_types={},
                    return_value=extra.get("decision"),
                    return_type="decision",
                    duration_ms=round(duration, 3),
                    extra=extra,
                )
                _logger.emit(entry)
                return result
            except Exception as exc:
                duration = (time.perf_counter() - start) * 1000
                entry = LogEntry(
                    timestamp=LogEntry.now(),
                    level="ERROR",
                    function_name=decision_name,
                    module=_module_of(fn),
                    args=(),
                    kwargs={},
                    arg_types=[],
                    kwarg_types={},
                    exception=str(exc),
                    exception_type=type(exc).__name__,
                    traceback=tb_mod.format_exc(),
                    duration_ms=round(duration, 3),
                    extra={"decision_name": decision_name},
                )
                _logger.emit(entry)
                raise

        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


def _build_decision_extra(decision_name: str, result: Any) -> Dict[str, Any]:
    """Extract decision/reason from the function return value."""
    extra: Dict[str, Any] = {"decision_name": decision_name}
    if isinstance(result, dict):
        extra["decision"] = result.get("decision", str(result))
        extra["decision_reason"] = result.get("reason", "")
        # Include all other keys as-is
        for k, v in result.items():
            if k not in ("decision", "reason"):
                extra[k] = v
    elif hasattr(result, "decision") and hasattr(result, "reason"):
        extra["decision"] = getattr(result, "decision")
        extra["decision_reason"] = getattr(result, "reason")
    else:
        extra["decision"] = str(result)
    return extra
