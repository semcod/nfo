"""@catch decorator for logging calls and suppressing exceptions."""

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
def catch(func: F) -> F: ...


@overload
def catch(
    *,
    level: str = "DEBUG",
    logger: Any = None,
    default: Any = None,
    max_repr_length: Optional[int] = DEFAULT_MAX_REPR_LENGTH,
    extract_meta: bool = False,
    meta_policy: Any = None,
    sample_rate: Optional[float] = None,
) -> Callable[[F], F]: ...


def catch(
    func: Optional[F] = None,
    *,
    level: str = "DEBUG",
    logger: Any = None,
    default: Any = None,
    max_repr_length: Optional[int] = DEFAULT_MAX_REPR_LENGTH,
    extract_meta: bool = False,
    meta_policy: Any = None,
    sample_rate: Optional[float] = None,
) -> Any:
    """
    Decorator that logs calls **and** suppresses exceptions.

    On exception the decorated function returns *default* instead of raising.
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
                    return default
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
                return default

        return wrapper  # type: ignore[return-value]

    if func is not None:
        return decorator(func)
    return decorator
