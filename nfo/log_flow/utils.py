"""Utility functions for log flow processing."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Union


def safe_float(value: Any) -> float:
    """Best-effort conversion to float."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def timestamp_sort_key(timestamp: str) -> float:
    """Parse an ISO timestamp into a sortable unix timestamp."""
    if not timestamp:
        return 0.0
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def first_present(raw: Mapping[str, Any], *keys: str) -> Any:
    """Return first non-None value from raw for given keys."""
    for key in keys:
        value = raw.get(key)
        if value is not None:
            return value
    return None


def extract_trace_id(
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


def extract_field(raw: Mapping[str, Any], primary: str, fallback: str) -> str:
    """Extract string field with fallback key."""
    return str(raw.get(primary) or raw.get(fallback) or "")


def read_lines(source: Union[str, Path, Iterable[str]]) -> List[str]:
    """Read source into a list of lines."""
    if isinstance(source, Path):
        return source.read_text(encoding="utf-8", errors="ignore").splitlines()

    if isinstance(source, str):
        candidate = Path(source)
        if "\n" not in source and candidate.exists():
            return candidate.read_text(encoding="utf-8", errors="ignore").splitlines()
        return source.splitlines()

    return [str(line) for line in source]
