"""Graph building logic for trace analysis."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Union

from nfo.models import LogEntry

from .normalizer import normalize_entry
from .types import FlowGraph, NormalizedEvent


def prepare_grouped_data(
    entries_or_grouped: Union[
        Iterable[Union[LogEntry, Mapping[str, Any]]],
        Mapping[str, Sequence[Union[LogEntry, Mapping[str, Any]]]],
    ],
    *,
    missing_trace_id: str = "no-trace",
) -> Dict[str, List[NormalizedEvent]]:
    """Normalize input into grouped trace data."""
    if isinstance(entries_or_grouped, Mapping):
        grouped: Dict[str, List[NormalizedEvent]] = {}
        for trace_id, trace_entries in entries_or_grouped.items():
            grouped[str(trace_id)] = [
                normalize_entry(e, missing_trace_id=missing_trace_id) for e in trace_entries
            ]
            grouped[str(trace_id)].sort(
                key=lambda e: (e["sort_key"], e["function_name"], e["module"])
            )
        return grouped
    return group_by_trace_id(entries_or_grouped, missing_trace_id=missing_trace_id)


def group_by_trace_id(
    entries: Iterable[Union[LogEntry, Mapping[str, Any]]],
    *,
    missing_trace_id: str = "no-trace",
) -> Dict[str, List[NormalizedEvent]]:
    """Group log events by ``trace_id`` and sort each trace chronologically."""
    grouped: Dict[str, List[NormalizedEvent]] = defaultdict(list)

    for entry in entries:
        event = normalize_entry(entry, missing_trace_id=missing_trace_id)
        grouped[event["trace_id"]].append(event)

    for trace_id in grouped:
        grouped[trace_id].sort(
            key=lambda e: (e["sort_key"], e["function_name"], e["module"])
        )

    return dict(sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])))


def process_trace_events(
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


def build_node_rows(nodes: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
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


def build_edge_rows(edges: Dict[tuple, Dict[str, Any]]) -> List[Dict[str, Any]]:
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
    entries_or_grouped: Union[
        Iterable[Union[LogEntry, Mapping[str, Any]]],
        Mapping[str, Sequence[Union[LogEntry, Mapping[str, Any]]]],
    ],
    *,
    missing_trace_id: str = "no-trace",
) -> FlowGraph:
    """Build a node/edge graph from grouped trace logs."""
    grouped = prepare_grouped_data(entries_or_grouped, missing_trace_id=missing_trace_id)

    nodes: Dict[str, Dict[str, Any]] = {}
    edges: Dict[tuple, Dict[str, Any]] = {}
    traces: List[Dict[str, Any]] = []

    total_events = 0
    total_errors = 0

    for trace_id, events in grouped.items():
        total_events += len(events)
        total_errors += sum(1 for e in events if e["exception"])
        trace_info = process_trace_events(trace_id, events, nodes, edges)
        traces.append(trace_info)

    node_rows = build_node_rows(nodes)
    edge_rows = build_edge_rows(edges)
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
