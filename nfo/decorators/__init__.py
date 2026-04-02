"""Decorators for automatic function logging.

This package provides decorators for automatic function call logging:
- @log_call: Log function entry/exit with timing
- @catch: Log and suppress exceptions (returns default)
- @decision_log: Log structured decision outcomes

All exports are backward-compatible with the original nfo.decorators module.
"""

from __future__ import annotations

# Core infrastructure
from ._core import (
    F,
    _arg_types,
    _get_default_logger,
    _module_of,
    _should_sample,
    get_default_logger,
    set_default_logger,
)

# Decorators
from ._catch import catch
from ._decision import decision_log, _build_decision_extra
from ._extract import _maybe_extract
from ._log_call import log_call

__all__ = [
    # Decorators
    "log_call",
    "catch",
    "decision_log",
    # Public API
    "set_default_logger",
    "get_default_logger",
    # Internal helpers (for backward compatibility)
    "_arg_types",
    "_build_decision_extra",
    "_get_default_logger",
    "_maybe_extract",
    "_module_of",
    "_should_sample",
]
