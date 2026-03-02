"""@log_call decorator for automatic function logging."""

from __future__ import annotations

import functools
import inspect
import time
import traceback as tb_mod
from typing import Any, Callable, Optional, TypeVar, Union, overload

from nfo.models import DEFAULT_MAX_REPR_LENGTH, LogEntry

from ._core import F, _arg_types, _get_default_logger, _module_of, _should_sample
from ._extract import _maybe_extract


@overload
def log_call(func: F) -> F: ...


@overload
def log_call(
    *,
    level: str = "DEBUG",
    logger: Any = None,
    max_repr_length: Optional[int] = DEFAULT_MAX_REPR_LENGTH,
    extract_meta: bool = False,
    meta_policy: Any = None,
    sample_rate: Optional[float] = None,
) -> Callable[[F], F]: ...


def log_call(
    func: Optional[F] = None,
    *,
    level: str = "DEBUG",
    logger: Any = None,
    max_repr_length: Optional[int] = DEFAULT_MAX_REPR_LENGTH,
    extract_meta: bool = False,
    meta_policy: Any = None,
    sample_rate: Optional[float] = None,
) -> Any:
    """
    Decorator that automatically logs function calls.

    Can be used bare (``@log_call``) or with parameters
    (``@log_call(level="INFO")``).

    Logs:
    - function name, module
    - positional and keyword arguments with their types
    - return value and type
    - exception details + traceback on failure
    - wall-clock duration in milliseconds

    Args:
        max_repr_length: Maximum repr length used by sink/stdout serialization.
            Set to ``None`` to disable truncation.
        extract_meta: If ``True``, large binary args are replaced with
            metadata dicts (format, size, hash) in ``entry.extra``.
        meta_policy: Optional :class:`~nfo.meta.ThresholdPolicy` controlling
            size thresholds. Only used when *extract_meta* is ``True``.
        sample_rate: Fraction of calls to log (0.0–1.0).  ``None`` or ``1.0``
            logs every call.  ``0.01`` logs ~1%.  Errors are **always** logged
            regardless of sampling.
    """

    def decorator(fn: F) -> F:
        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                _logger = logger or _get_default_logger()
                start = time.perf_counter()
                try:
                    result = await fn(*args, **kwargs)
                    if not _should_sample(sample_rate):
                        return result
                    duration = (time.perf_counter() - start) * 1000
                    arg_t, kwarg_t = _arg_types(args, kwargs)
                    meta_extra = _maybe_extract(args, kwargs, result, extract_meta, meta_policy)
                    entry = LogEntry(
                        timestamp=LogEntry.now(),
                        level=level.upper(),
                        function_name=fn.__qualname__,
                        module=_module_of(fn),
                        args=() if meta_extra else args,
                        kwargs={} if meta_extra else kwargs,
                        arg_types=arg_t,
                        kwarg_types=kwarg_t,
                        return_value=None if meta_extra else result,
                        return_type=type(result).__name__,
                        duration_ms=round(duration, 3),
                        max_repr_length=max_repr_length,
                        extra=meta_extra or {},
                    )
                    _logger.emit(entry)
                    return result
                except Exception as exc:
                    # Errors are always logged regardless of sample_rate
                    duration = (time.perf_counter() - start) * 1000
                    arg_t, kwarg_t = _arg_types(args, kwargs)
                    err_extra = _maybe_extract(args, kwargs, None, extract_meta, meta_policy)
                    entry = LogEntry(
                        timestamp=LogEntry.now(),
                        level="ERROR",
                        function_name=fn.__qualname__,
                        module=_module_of(fn),
                        args=() if err_extra else args,
                        kwargs={} if err_extra else kwargs,
                        arg_types=arg_t,
                        kwarg_types=kwarg_t,
                        exception=str(exc),
                        exception_type=type(exc).__name__,
                        traceback=tb_mod.format_exc(),
                        duration_ms=round(duration, 3),
                        max_repr_length=max_repr_length,
                        extra=err_extra or {},
                    )
                    _logger.emit(entry)
                    raise
            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            _logger = logger or _get_default_logger()
            start = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
                if not _should_sample(sample_rate):
                    return result
                duration = (time.perf_counter() - start) * 1000
                arg_t, kwarg_t = _arg_types(args, kwargs)
                meta_extra = _maybe_extract(args, kwargs, result, extract_meta, meta_policy)
                entry = LogEntry(
                    timestamp=LogEntry.now(),
                    level=level.upper(),
                    function_name=fn.__qualname__,
                    module=_module_of(fn),
                    args=() if meta_extra else args,
                    kwargs={} if meta_extra else kwargs,
                    arg_types=arg_t,
                    kwarg_types=kwarg_t,
                    return_value=None if meta_extra else result,
                    return_type=type(result).__name__,
                    duration_ms=round(duration, 3),
                    max_repr_length=max_repr_length,
                    extra=meta_extra or {},
                )
                _logger.emit(entry)
                return result
            except Exception as exc:
                # Errors are always logged regardless of sample_rate
                duration = (time.perf_counter() - start) * 1000
                arg_t, kwarg_t = _arg_types(args, kwargs)
                err_extra = _maybe_extract(args, kwargs, None, extract_meta, meta_policy)
                entry = LogEntry(
                    timestamp=LogEntry.now(),
                    level="ERROR",
                    function_name=fn.__qualname__,
                    module=_module_of(fn),
                    args=() if err_extra else args,
                    kwargs={} if err_extra else kwargs,
                    arg_types=arg_t,
                    kwarg_types=kwarg_t,
                    exception=str(exc),
                    exception_type=type(exc).__name__,
                    traceback=tb_mod.format_exc(),
                    duration_ms=round(duration, 3),
                    max_repr_length=max_repr_length,
                    extra=err_extra or {},
                )
                _logger.emit(entry)
                raise

        return wrapper  # type: ignore[return-value]

    if func is not None:
        return decorator(func)
    return decorator
