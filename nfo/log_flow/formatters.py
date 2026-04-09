"""Output formatting for LLM compression."""

from __future__ import annotations

from typing import Any, Dict, List

from .types import FlowGraph


def format_header(stats: Dict[str, Any]) -> List[str]:
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


def format_nodes(nodes: List[Dict[str, Any]], max_nodes: int) -> List[str]:
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


def format_edges(edges: List[Dict[str, Any]], max_edges: int) -> List[str]:
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


def format_event(event: Dict[str, Any]) -> str:
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


def format_traces(
    traces: List[Dict[str, Any]],
    max_traces: int,
    max_events: int,
    missing_trace_id: str = "no-trace",
) -> List[str]:
    """Format trace timelines section."""
    lines: List[str] = ["", "## Trace Timelines"]
    for trace in traces[:max_traces]:
        trace_id = trace.get("trace_id", missing_trace_id)
        event_count = trace.get("event_count", 0)
        error_count = trace.get("error_count", 0)
        lines.append(
            f"### trace_id={trace_id} (events={event_count}, errors={error_count})"
        )

        for event in trace.get("events", [])[:max_events]:
            lines.append(format_event(event))

        if event_count > max_events:
            lines.append(
                f"- ... {event_count - max_events} more events in this trace"
            )

    if len(traces) > max_traces:
        lines.append(f"- ... {len(traces) - max_traces} more traces")
    return lines


def compress_for_llm(
    graph: FlowGraph,
    *,
    missing_trace_id: str = "no-trace",
    max_nodes: int = 60,
    max_edges: int = 80,
    max_traces: int = 8,
    max_events_per_trace: int = 12,
) -> str:
    """Compress graph data into an LLM-friendly textual summary."""
    stats = graph.get("stats", {})
    nodes = list(graph.get("nodes", []))
    edges = list(graph.get("edges", []))
    traces = list(graph.get("traces", []))

    lines: List[str] = format_header(stats)
    lines.extend(format_nodes(nodes, max_nodes))
    lines.extend(format_edges(edges, max_edges))
    lines.extend(format_traces(traces, max_traces, max_events_per_trace, missing_trace_id))

    return "\n".join(lines)
