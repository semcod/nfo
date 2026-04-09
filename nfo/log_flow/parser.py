"""Log flow parser for JSONL and entry processing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Union

from nfo.models import LogEntry

from .graph import build_flow_graph, group_by_trace_id
from .normalizer import normalize_entry
from .types import FlowGraph, NormalizedEvent
from .utils import read_lines


class LogFlowParser:
    """Parse logs, group by trace_id, and build compressed flow graphs."""

    def __init__(self, *, missing_trace_id: str = "no-trace") -> None:
        self.missing_trace_id = missing_trace_id

    def parse_jsonl(
        self,
        source: Union[str, Path, Iterable[str]],
        *,
        strict: bool = False,
    ) -> List[NormalizedEvent]:
        """Parse JSON Lines into normalized events.

        Args:
            source: Path to a jsonl file, raw jsonl text, or iterable of lines.
            strict: If True, invalid JSON lines raise ``ValueError``.
        """
        lines = read_lines(source)
        events: List[NormalizedEvent] = []

        for line_no, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped:
                continue

            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                if strict:
                    raise ValueError(f"Invalid JSON on line {line_no}: {exc}") from exc
                continue

            if not isinstance(payload, Mapping):
                if strict:
                    raise ValueError(f"JSON line {line_no} is not an object")
                continue

            events.append(normalize_entry(payload, missing_trace_id=self.missing_trace_id))

        return events

    def from_jsonl(
        self,
        source: Union[str, Path, Iterable[str]],
        *,
        strict: bool = False,
    ) -> List[NormalizedEvent]:
        """Alias for :meth:`parse_jsonl`."""
        return self.parse_jsonl(source, strict=strict)

    def parse_logs(
        self,
        source: Union[str, Path, Iterable[str]],
        *,
        strict: bool = False,
    ) -> List[NormalizedEvent]:
        """Alias for :meth:`parse_jsonl`."""
        return self.parse_jsonl(source, strict=strict)

    def parse(
        self,
        source: Union[str, Path, Iterable[str]],
        *,
        strict: bool = False,
    ) -> List[NormalizedEvent]:
        """Alias for :meth:`parse_jsonl`."""
        return self.parse_jsonl(source, strict=strict)

    def group_by_trace_id(
        self,
        entries: Iterable[Union[LogEntry, Mapping[str, Any]]],
    ) -> Dict[str, List[NormalizedEvent]]:
        """Group log events by ``trace_id`` and sort each trace chronologically."""
        return group_by_trace_id(entries, missing_trace_id=self.missing_trace_id)

    def build_flow_graph(
        self,
        entries_or_grouped: Union[
            Iterable[Union[LogEntry, Mapping[str, Any]]],
            Mapping[str, Sequence[Union[LogEntry, Mapping[str, Any]]]],
        ],
    ) -> FlowGraph:
        """Build a node/edge graph from grouped trace logs."""
        return build_flow_graph(entries_or_grouped, missing_trace_id=self.missing_trace_id)

    def to_graph(
        self,
        entries_or_grouped: Union[
            Iterable[Union[LogEntry, Mapping[str, Any]]],
            Mapping[str, Sequence[Union[LogEntry, Mapping[str, Any]]]],
        ],
    ) -> FlowGraph:
        """Alias for :meth:`build_flow_graph`."""
        return self.build_flow_graph(entries_or_grouped)

    def parse_to_graph(
        self,
        source: Union[str, Path, Iterable[str]],
        *,
        strict: bool = False,
    ) -> FlowGraph:
        """Parse JSONL and directly return the flow graph."""
        events = self.parse_jsonl(source, strict=strict)
        return self.build_flow_graph(events)

    def _ensure_graph(
        self,
        graph_or_entries: Union[
            FlowGraph,
            Iterable[Union[LogEntry, Mapping[str, Any]]],
            Mapping[str, Sequence[Union[LogEntry, Mapping[str, Any]]]],
        ],
    ) -> FlowGraph:
        """Ensure input is a FlowGraph, converting if necessary."""
        if (
            isinstance(graph_or_entries, Mapping)
            and "stats" in graph_or_entries
            and "nodes" in graph_or_entries
            and "edges" in graph_or_entries
        ):
            return graph_or_entries  # type: ignore[return-value]
        return self.build_flow_graph(graph_or_entries)

    def compress_for_llm(
        self,
        graph_or_entries: Union[
            FlowGraph,
            Iterable[Union[LogEntry, Mapping[str, Any]]],
            Mapping[str, Sequence[Union[LogEntry, Mapping[str, Any]]]],
        ],
        *,
        max_nodes: int = 60,
        max_edges: int = 80,
        max_traces: int = 8,
        max_events_per_trace: int = 12,
    ) -> str:
        """Compress graph data into an LLM-friendly textual summary."""
        from .formatters import compress_for_llm

        graph = self._ensure_graph(graph_or_entries)
        return compress_for_llm(
            graph,
            missing_trace_id=self.missing_trace_id,
            max_nodes=max_nodes,
            max_edges=max_edges,
            max_traces=max_traces,
            max_events_per_trace=max_events_per_trace,
        )

    def to_llm_context(
        self,
        graph_or_entries: Union[
            FlowGraph,
            Iterable[Union[LogEntry, Mapping[str, Any]]],
            Mapping[str, Sequence[Union[LogEntry, Mapping[str, Any]]]],
        ],
        **kwargs: Any,
    ) -> str:
        """Alias for :meth:`compress_for_llm`."""
        return self.compress_for_llm(graph_or_entries, **kwargs)
