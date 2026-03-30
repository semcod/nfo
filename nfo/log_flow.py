"""Log flow parsing and compression utilities for nfo.

This module turns raw nfo logs into a compact, trace-aware flow graph that can
be sent to an LLM with much lower token usage.

Supported inputs:
- :class:`nfo.models.LogEntry`
- dictionaries from SQLite rows / JSON exports
- JSON Lines strings/files (both full and compact nfo formats)
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Union

from nfo.models import LogEntry


NormalizedEvent = Dict[str, Any]
FlowGraph = Dict[str, Any]


def _safe_float(value: Any) -> float:
    """Best-effort conversion to float."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _timestamp_sort_key(timestamp: str) -> float:
    """Parse an ISO timestamp into a sortable unix timestamp."""
    if not timestamp:
        return 0.0
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _first_present(raw: Mapping[str, Any], *keys: str) -> Any:
    """Return first non-None value from raw for given keys."""
    for key in keys:
        value = raw.get(key)
        if value is not None:
            return value
    return None


def _extract_trace_id(
    raw: Mapping[str, Any],
    extra: Mapping[str, Any],
    missing_trace_id: str,
) -> str:
    """Extract trace_id from multiple possible locations."""
    trace_id = (
        raw.get("trace_id")
        or raw.get("tid")
        or extra.get("trace_id")
        or extra.get("tid")
        or missing_trace_id
    )
    return str(trace_id).strip() or missing_trace_id


def _extract_field(raw: Mapping[str, Any], primary: str, fallback: str) -> str:
    """Extract string field with fallback key."""
    return str(raw.get(primary) or raw.get(fallback) or "")


class LogFlowParser:
    """Parse logs, group by trace_id, and build compressed flow graphs."""

    def __init__(self, *, missing_trace_id: str = "no-trace") -> None:
        self.missing_trace_id = missing_trace_id

    def _get_raw_data(self, entry: Union[LogEntry, Mapping[str, Any]]) -> Dict[str, Any]:
        """Extract raw dict from LogEntry or Mapping."""
        if isinstance(entry, LogEntry):
            raw = entry.as_dict()
            if entry.extra:
                raw["extra"] = dict(entry.extra)
        elif isinstance(entry, Mapping):
            raw = dict(entry)
        else:
            raise TypeError(f"Unsupported entry type: {type(entry).__name__}")
        return raw

    def _extract_event_fields(
        self, raw: Mapping[str, Any], extra: Mapping[str, Any]
    ) -> Dict[str, str]:
        """Extract core string fields with fallbacks."""
        return {
            "function_name": str(_first_present(raw, "function_name", "fn") or "?"),
            "module": str(_first_present(raw, "module", "mod") or ""),
            "timestamp": str(_first_present(raw, "timestamp", "ts") or ""),
            "level": str(_first_present(raw, "level", "lvl") or "INFO").upper(),
            "trace_id": _extract_trace_id(raw, extra, self.missing_trace_id),
            "exception": str(_first_present(raw, "exception", "err") or ""),
            "exception_type": str(_first_present(raw, "exception_type", "et") or ""),
        }

    def _build_computed_fields(
        self, fields: Dict[str, str], raw: Mapping[str, Any]
    ) -> Dict[str, Any]:
        """Build computed fields from extracted data."""
        duration_ms = _safe_float(_first_present(raw, "duration_ms", "ms") or 0.0)
        node = f"{fields['module']}.{fields['function_name']}" if fields["module"] else fields["function_name"]
        return {
            "duration_ms": duration_ms,
            "node": node,
            "sort_key": _timestamp_sort_key(fields["timestamp"]),
        }

    def normalize_entry(self, entry: Union[LogEntry, Mapping[str, Any]]) -> NormalizedEvent:
        """Normalize supported log entry formats into a single event schema."""
        raw = self._get_raw_data(entry)
        extra_raw = raw.get("extra", {})
        extra = dict(extra_raw) if isinstance(extra_raw, Mapping) else {}

        fields = self._extract_event_fields(raw, extra)
        computed = self._build_computed_fields(fields, raw)

        return {
            "timestamp": fields["timestamp"],
            "sort_key": computed["sort_key"],
            "trace_id": fields["trace_id"],
            "function_name": fields["function_name"],
            "module": fields["module"],
            "node": computed["node"],
            "level": fields["level"],
            "duration_ms": computed["duration_ms"],
            "exception": fields["exception"],
            "exception_type": fields["exception_type"],
            "extra": extra,
        }

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
        lines = self._read_lines(source)
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

            events.append(self.normalize_entry(payload))

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
        grouped: Dict[str, List[NormalizedEvent]] = defaultdict(list)

        for entry in entries:
            event = self.normalize_entry(entry)
            grouped[event["trace_id"]].append(event)

        for trace_id in grouped:
            grouped[trace_id].sort(
                key=lambda e: (e["sort_key"], e["function_name"], e["module"])
            )

        return dict(sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])))

    def _prepare_grouped_data(
        self,
        entries_or_grouped: Union[
            Iterable[Union[LogEntry, Mapping[str, Any]]],
            Mapping[str, Sequence[Union[LogEntry, Mapping[str, Any]]]],
        ],
    ) -> Dict[str, List[NormalizedEvent]]:
        """Normalize input into grouped trace data."""
        if isinstance(entries_or_grouped, Mapping):
            grouped: Dict[str, List[NormalizedEvent]] = {}
            for trace_id, trace_entries in entries_or_grouped.items():
                grouped[str(trace_id)] = [self.normalize_entry(e) for e in trace_entries]
                grouped[str(trace_id)].sort(
                    key=lambda e: (e["sort_key"], e["function_name"], e["module"])
                )
            return grouped
        return self.group_by_trace_id(entries_or_grouped)

    def _process_trace_events(
        self,
        trace_id: str,
        events: List[NormalizedEvent],
        nodes: Dict[str, Dict[str, Any]],
        edges: Dict[tuple, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Process events for a single trace, updating nodes and edges."""
        prev_node: str | None = None
        trace_errors = 0

        for event in events:
            has_error = bool(event["exception"])
            if has_error:
                trace_errors += 1

            node_id = event["node"]
            node = nodes.setdefault(
                node_id,
                {
                    "id": node_id,
                    "module": event["module"],
                    "function_name": event["function_name"],
                    "calls": 0,
                    "errors": 0,
                    "total_duration_ms": 0.0,
                    "trace_ids": set(),
                },
            )
            node["calls"] += 1
            if has_error:
                node["errors"] += 1
            node["total_duration_ms"] += event["duration_ms"]
            node["trace_ids"].add(trace_id)

            if prev_node is not None:
                edge_key = (prev_node, node_id)
                edge = edges.setdefault(
                    edge_key,
                    {
                        "source": prev_node,
                        "target": node_id,
                        "count": 0,
                        "error_count": 0,
                        "trace_ids": set(),
                    },
                )
                edge["count"] += 1
                if has_error:
                    edge["error_count"] += 1
                edge["trace_ids"].add(trace_id)

            prev_node = node_id

        return {
            "trace_id": trace_id,
            "event_count": len(events),
            "error_count": trace_errors,
            "start_timestamp": events[0]["timestamp"] if events else "",
            "end_timestamp": events[-1]["timestamp"] if events else "",
            "events": events,
        }

    def _build_node_rows(self, nodes: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert node dicts to sorted row format."""
        rows: List[Dict[str, Any]] = []
        for node in nodes.values():
            calls = node["calls"] or 1
            rows.append(
                {
                    "id": node["id"],
                    "module": node["module"],
                    "function_name": node["function_name"],
                    "calls": node["calls"],
                    "errors": node["errors"],
                    "total_duration_ms": round(node["total_duration_ms"], 3),
                    "avg_duration_ms": round(node["total_duration_ms"] / calls, 3),
                    "trace_ids": sorted(node["trace_ids"]),
                }
            )
        rows.sort(key=lambda n: (-n["calls"], -n["errors"], n["id"]))
        return rows

    def _build_edge_rows(self, edges: Dict[tuple, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert edge dicts to sorted row format."""
        rows: List[Dict[str, Any]] = []
        for edge in edges.values():
            rows.append(
                {
                    "source": edge["source"],
                    "target": edge["target"],
                    "count": edge["count"],
                    "error_count": edge["error_count"],
                    "trace_ids": sorted(edge["trace_ids"]),
                }
            )
        rows.sort(key=lambda e: (-e["count"], -e["error_count"], e["source"], e["target"]))
        return rows

    def build_flow_graph(
        self,
        entries_or_grouped: Union[
            Iterable[Union[LogEntry, Mapping[str, Any]]],
            Mapping[str, Sequence[Union[LogEntry, Mapping[str, Any]]]],
        ],
    ) -> FlowGraph:
        """Build a node/edge graph from grouped trace logs."""
        grouped = self._prepare_grouped_data(entries_or_grouped)

        nodes: Dict[str, Dict[str, Any]] = {}
        edges: Dict[tuple, Dict[str, Any]] = {}
        traces: List[Dict[str, Any]] = []

        total_events = 0
        total_errors = 0

        for trace_id, events in grouped.items():
            total_events += len(events)
            total_errors += sum(1 for e in events if e["exception"])
            trace_info = self._process_trace_events(trace_id, events, nodes, edges)
            traces.append(trace_info)

        node_rows = self._build_node_rows(nodes)
        edge_rows = self._build_edge_rows(edges)
        traces.sort(key=lambda t: (-t["event_count"], t["trace_id"]))

        return {
            "stats": {
                "trace_count": len(grouped),
                "event_count": total_events,
                "node_count": len(node_rows),
                "edge_count": len(edge_rows),
                "error_count": total_errors,
            },
            "nodes": node_rows,
            "edges": edge_rows,
            "traces": traces,
        }

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

    def _format_header(self, stats: Dict[str, Any]) -> List[str]:
        """Format summary statistics section."""
        return [
            "# nfo Log Flow Compression",
            "## Summary",
            f"- traces: {stats.get('trace_count', 0)}",
            f"- events: {stats.get('event_count', 0)}",
            f"- nodes: {stats.get('node_count', 0)}",
            f"- edges: {stats.get('edge_count', 0)}",
            f"- errors: {stats.get('error_count', 0)}",
            "",
            "## Top Nodes",
        ]

    def _format_nodes(self, nodes: List[Dict[str, Any]], max_nodes: int) -> List[str]:
        """Format node list section."""
        lines: List[str] = []
        for node in nodes[:max_nodes]:
            lines.append(
                "- "
                f"{node.get('id', '?')}: calls={node.get('calls', 0)}, "
                f"errors={node.get('errors', 0)}, "
                f"avg_ms={node.get('avg_duration_ms', 0)}"
            )
        if len(nodes) > max_nodes:
            lines.append(f"- ... {len(nodes) - max_nodes} more nodes")
        return lines

    def _format_edges(self, edges: List[Dict[str, Any]], max_edges: int) -> List[str]:
        """Format edge list section."""
        lines: List[str] = ["", "## Top Edges"]
        for edge in edges[:max_edges]:
            lines.append(
                "- "
                f"{edge.get('source', '?')} -> {edge.get('target', '?')}: "
                f"count={edge.get('count', 0)}, "
                f"error_count={edge.get('error_count', 0)}"
            )
        if len(edges) > max_edges:
            lines.append(f"- ... {len(edges) - max_edges} more edges")
        return lines

    def _format_event(self, event: Dict[str, Any]) -> str:
        """Format a single event line."""
        status = "ERR" if event.get("exception") else "OK"
        duration = event.get("duration_ms", 0.0)
        ts = event.get("timestamp") or "unknown-ts"
        line = (
            f"- {ts} | {status} | {event.get('node', '?')} "
            f"| {duration:.2f}ms"
        )
        if event.get("exception_type"):
            line += f" | {event.get('exception_type')}"
        return line

    def _format_traces(
        self, traces: List[Dict[str, Any]], max_traces: int, max_events: int
    ) -> List[str]:
        """Format trace timelines section."""
        lines: List[str] = ["", "## Trace Timelines"]
        for trace in traces[:max_traces]:
            trace_id = trace.get("trace_id", self.missing_trace_id)
            event_count = trace.get("event_count", 0)
            error_count = trace.get("error_count", 0)
            lines.append(
                f"### trace_id={trace_id} (events={event_count}, errors={error_count})"
            )

            for event in trace.get("events", [])[:max_events]:
                lines.append(self._format_event(event))

            if event_count > max_events:
                lines.append(
                    f"- ... {event_count - max_events} more events in this trace"
                )

        if len(traces) > max_traces:
            lines.append(f"- ... {len(traces) - max_traces} more traces")
        return lines

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
        graph = self._ensure_graph(graph_or_entries)
        stats = graph.get("stats", {})
        nodes = list(graph.get("nodes", []))
        edges = list(graph.get("edges", []))
        traces = list(graph.get("traces", []))

        lines: List[str] = self._format_header(stats)
        lines.extend(self._format_nodes(nodes, max_nodes))
        lines.extend(self._format_edges(edges, max_edges))
        lines.extend(self._format_traces(traces, max_traces, max_events_per_trace))

        return "\n".join(lines)

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

    @staticmethod
    def _read_lines(source: Union[str, Path, Iterable[str]]) -> List[str]:
        """Read source into a list of lines."""
        if isinstance(source, Path):
            return source.read_text(encoding="utf-8", errors="ignore").splitlines()

        if isinstance(source, str):
            candidate = Path(source)
            if "\n" not in source and candidate.exists():
                return candidate.read_text(encoding="utf-8", errors="ignore").splitlines()
            return source.splitlines()

        return [str(line) for line in source]


def build_log_flow_graph(
    entries_or_grouped: Union[
        Iterable[Union[LogEntry, Mapping[str, Any]]],
        Mapping[str, Sequence[Union[LogEntry, Mapping[str, Any]]]],
    ],
    *,
    missing_trace_id: str = "no-trace",
) -> FlowGraph:
    """Convenience wrapper for building a flow graph without manual parser setup."""
    parser = LogFlowParser(missing_trace_id=missing_trace_id)
    return parser.build_flow_graph(entries_or_grouped)


def compress_logs_for_llm(
    entries_or_graph: Union[
        FlowGraph,
        Iterable[Union[LogEntry, Mapping[str, Any]]],
        Mapping[str, Sequence[Union[LogEntry, Mapping[str, Any]]]],
    ],
    *,
    missing_trace_id: str = "no-trace",
    **kwargs: Any,
) -> str:
    """Convenience wrapper for LLM-ready compression output."""
    parser = LogFlowParser(missing_trace_id=missing_trace_id)
    return parser.compress_for_llm(entries_or_graph, **kwargs)
