"""Log flow parsing and compression utilities for nfo.

This package turns raw nfo logs into a compact, trace-aware flow graph that can
be sent to an LLM with much lower token usage.

Supported inputs:
- :class:`nfo.models.LogEntry`
- dictionaries from SQLite rows / JSON exports
- JSON Lines strings/files (both full and compact nfo formats)
"""

from __future__ import annotations

from .formatters import compress_for_llm as _compress_for_llm
from .graph import build_flow_graph
from .parser import LogFlowParser
from .types import FlowGraph, NormalizedEvent

__all__ = [
    "LogFlowParser",
    "build_log_flow_graph",
    "compress_logs_for_llm",
    "FlowGraph",
    "NormalizedEvent",
]


def compress_logs_for_llm(
    entries_or_graph: Union[
        FlowGraph,
        Iterable[Union["LogEntry", Mapping[str, Any]]],
        Mapping[str, Sequence[Union["LogEntry", Mapping[str, Any]]]],
    ],
    *,
    missing_trace_id: str = "no-trace",
    **kwargs: Any,
) -> str:
    """Convenience wrapper for LLM-ready compression output."""
    parser = LogFlowParser(missing_trace_id=missing_trace_id)
    return parser.compress_for_llm(entries_or_graph, **kwargs)


def build_log_flow_graph(
    entries_or_grouped: Union[
        Iterable[Union["LogEntry", Mapping[str, Any]]],
        Mapping[str, Sequence[Union["LogEntry", Mapping[str, Any]]]],
    ],
    *,
    missing_trace_id: str = "no-trace",
) -> FlowGraph:
    """Convenience wrapper for building a flow graph without manual parser setup."""
    parser = LogFlowParser(missing_trace_id=missing_trace_id)
    return parser.build_flow_graph(entries_or_grouped)


# Delayed import to avoid circular dependency
from typing import Any, Mapping, Sequence, Union
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nfo.models import LogEntry
