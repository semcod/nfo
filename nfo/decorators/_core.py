"""Shared infrastructure for nfo decorators."""

from __future__ import annotations

import functools
import inspect
import random
import time
import traceback as tb_mod
from typing import Any, Callable, Dict, Optional, Tuple, TypeVar

from nfo.models import DEFAULT_MAX_REPR_LENGTH, LogEntry

F = TypeVar("F", bound=Callable[..., Any])

# ---------------------------------------------------------------------------
# Module-level default logger (lazy-initialised)
# ---------------------------------------------------------------------------

_default_logger: Optional[Any] = None  # nfo.logger.Logger


def _get_default_logger() -> Any:
    global _default_logger
    if _default_logger is None:
        from nfo.logger import Logger
        _default_logger = Logger()
    return _default_logger


# Public alias
get_default_logger = _get_default_logger


def set_default_logger(logger: Any) -> None:
    """Replace the module-level default logger used by decorators."""
    global _default_logger
    _default_logger = logger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _arg_types(args: tuple, kwargs: dict) -> Tuple[list, dict]:
    arg_types = [type(a).__name__ for a in args]
    kwarg_types = {k: type(v).__name__ for k, v in kwargs.items()}
    return arg_types, kwarg_types


def _module_of(func: Callable) -> str:
    return getattr(func, "__module__", "") or ""


def _should_sample(sample_rate: Optional[float]) -> bool:
    """Return True if this call should be logged based on *sample_rate*.

    - ``None`` or ``1.0`` → always log
    - ``0.0`` → never log (except errors, handled by caller)
    - ``0.01`` → log ~1% of calls
    """
    if sample_rate is None or sample_rate >= 1.0:
        return True
    if sample_rate <= 0.0:
        return False
    return random.random() < sample_rate
