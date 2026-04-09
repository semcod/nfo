"""Log entry normalization logic."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Union

from nfo.models import LogEntry

from .types import NormalizedEvent
from .utils import extract_trace_id, first_present, safe_float, timestamp_sort_key


def get_raw_data(entry: Union[LogEntry, Mapping[str, Any]]) -> Dict[str, Any]:
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


def extract_event_fields(
    raw: Mapping[str, Any],
    extra: Mapping[str, Any],
    missing_trace_id: str,
) -> Dict[str, str]:
    """Extract core string fields with fallbacks."""
    return {
        "function_name": str(first_present(raw, "function_name", "fn") or "?"),
        "module": str(first_present(raw, "module", "mod") or ""),
        "timestamp": str(first_present(raw, "timestamp", "ts") or ""),
        "level": str(first_present(raw, "level", "lvl") or "INFO").upper(),
        "trace_id": extract_trace_id(raw, extra, missing_trace_id),
        "exception": str(first_present(raw, "exception", "err") or ""),
        "exception_type": str(first_present(raw, "exception_type", "et") or ""),
    }


def build_computed_fields(
    fields: Dict[str, str], raw: Mapping[str, Any]
) -> Dict[str, Any]:
    """Build computed fields from extracted data."""
    duration_ms = safe_float(first_present(raw, "duration_ms", "ms") or 0.0)
    node = f"{fields['module']}.{fields['function_name']}" if fields["module"] else fields["function_name"]
    return {
        "duration_ms": duration_ms,
        "node": node,
        "sort_key": timestamp_sort_key(fields["timestamp"]),
    }


def normalize_entry(
    entry: Union[LogEntry, Mapping[str, Any]],
    *,
    missing_trace_id: str = "no-trace",
) -> NormalizedEvent:
    """Normalize supported log entry formats into a single event schema."""
    raw = get_raw_data(entry)
    extra_raw = raw.get("extra", {})
    extra = dict(extra_raw) if isinstance(extra_raw, Mapping) else {}

    fields = extract_event_fields(raw, extra, missing_trace_id)
    computed = build_computed_fields(fields, raw)

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
