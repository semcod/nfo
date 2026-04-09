"""Tests for log flow parsing and LLM compression."""

from __future__ import annotations

import json

from nfo.log_flow.parser import LogFlowParser


def test_parse_jsonl_supports_full_and_compact_entries(tmp_path):
    log_file = tmp_path / "logs.jsonl"
    log_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-02-15T10:00:00+00:00",
                        "level": "INFO",
                        "function_name": "load",
                        "module": "pipeline",
                        "trace_id": "trace-1",
                        "duration_ms": 3.2,
                    }
                ),
                json.dumps(
                    {
                        "ts": "2026-02-15T10:00:01+00:00",
                        "lvl": "ERROR",
                        "fn": "transform",
                        "mod": "pipeline",
                        "tid": "trace-1",
                        "ms": 9.1,
                        "err": "bad value",
                        "et": "ValueError",
                    }
                ),
                "this is not json",
            ]
        ),
        encoding="utf-8",
    )

    parser = LogFlowParser()
    events = parser.parse_jsonl(log_file)

    assert len(events) == 2
    assert events[0]["function_name"] == "load"
    assert events[1]["function_name"] == "transform"
    assert events[1]["exception_type"] == "ValueError"


def test_group_by_trace_id_uses_fallback_bucket():
    parser = LogFlowParser(missing_trace_id="unknown")

    grouped = parser.group_by_trace_id(
        [
            {
                "timestamp": "2026-02-15T10:00:00+00:00",
                "function_name": "start",
                "module": "svc",
                "trace_id": "trace-a",
            },
            {
                "timestamp": "2026-02-15T10:00:01+00:00",
                "function_name": "step",
                "module": "svc",
                "trace_id": "trace-a",
            },
            {
                "timestamp": "2026-02-15T10:00:02+00:00",
                "function_name": "orphan",
                "module": "svc",
                "trace_id": "",
            },
        ]
    )

    assert set(grouped) == {"trace-a", "unknown"}
    assert len(grouped["trace-a"]) == 2
    assert len(grouped["unknown"]) == 1


def test_build_flow_graph_creates_edges_and_error_counts():
    parser = LogFlowParser()

    graph = parser.build_flow_graph(
        [
            {
                "timestamp": "2026-02-15T10:00:00+00:00",
                "function_name": "start",
                "module": "svc",
                "trace_id": "trace-1",
            },
            {
                "timestamp": "2026-02-15T10:00:01+00:00",
                "function_name": "process",
                "module": "svc",
                "trace_id": "trace-1",
            },
            {
                "timestamp": "2026-02-15T10:00:02+00:00",
                "function_name": "finish",
                "module": "svc",
                "trace_id": "trace-1",
                "exception": "boom",
                "exception_type": "RuntimeError",
            },
        ]
    )

    assert graph["stats"]["trace_count"] == 1
    assert graph["stats"]["node_count"] == 3
    assert graph["stats"]["edge_count"] == 2
    assert graph["stats"]["error_count"] == 1

    edges = {(e["source"], e["target"]): e for e in graph["edges"]}
    assert edges[("svc.start", "svc.process")]["count"] == 1
    assert edges[("svc.process", "svc.finish")]["error_count"] == 1


def test_compress_for_llm_includes_summary_graph_and_timeline():
    parser = LogFlowParser()

    context = parser.compress_for_llm(
        [
            {
                "timestamp": "2026-02-15T10:00:00+00:00",
                "function_name": "a",
                "module": "svc",
                "trace_id": "trace-1",
            },
            {
                "timestamp": "2026-02-15T10:00:01+00:00",
                "function_name": "b",
                "module": "svc",
                "trace_id": "trace-1",
            },
            {
                "timestamp": "2026-02-15T10:00:02+00:00",
                "function_name": "c",
                "module": "svc",
                "trace_id": "trace-1",
            },
        ],
        max_traces=1,
        max_events_per_trace=2,
        max_edges=1,
        max_nodes=2,
    )

    assert "# nfo Log Flow Compression" in context
    assert "## Top Nodes" in context
    assert "## Top Edges" in context
    assert "## Trace Timelines" in context
    assert "### trace_id=trace-1" in context
    assert "... 1 more events in this trace" in context
