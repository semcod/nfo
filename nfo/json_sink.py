"""
JSON sink for nfo — structured JSON log output for ELK/Grafana Loki.

Writes one JSON object per line (JSON Lines format), suitable for
ingestion by Elasticsearch, Grafana Loki, Fluentd, etc.

Zero external dependencies — uses only stdlib ``json``.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, Optional, TextIO

from nfo.models import LogEntry
from nfo.sinks import Sink


class JSONSink(Sink):
    """
    Append log entries as JSON Lines (one JSON object per line).

    Compatible with:
    - Elasticsearch / ELK stack (Filebeat → Logstash → ES)
    - Grafana Loki (Promtail)
    - Fluentd / Fluent Bit
    - Any JSON Lines consumer

    Args:
        file_path: Path to the JSON Lines file (default: ``logs.jsonl``).
        pretty: If True, indent JSON for readability (not recommended for production).
        delegate: Optional downstream sink to forward entries to.
        max_bytes: Optional POSIX active-file byte budget. None reads
            NFO_JSONL_MAX_BYTES (unset means zero); explicit zero keeps legacy
            unbounded writes. All writers to a bounded path must cooperate.
    """

    def __init__(
        self,
        file_path: str | Path = "logs.jsonl",
        *,
        pretty: bool = False,
        compact: bool = False,
        delegate: Optional[Sink] = None,
        max_bytes: Optional[int] = None,
    ) -> None:
        self.file_path = str(file_path)
        self.pretty = pretty
        self.compact = compact
        self.delegate = delegate
        self._lock = threading.Lock()
        if max_bytes is None:
            raw = os.environ.get("NFO_JSONL_MAX_BYTES", "0")
            try:
                max_bytes = int(raw)
            except (ValueError, TypeError) as exc:
                raise ValueError("NFO_JSONL_MAX_BYTES must be a nonnegative integer") from exc
        if type(max_bytes) is not int or max_bytes < 0:
            raise ValueError("max_bytes must be a nonnegative integer")
        self._bounded = None
        if max_bytes:
            from nfo.json_rotation import BoundedJSONLWriter
            self._bounded = BoundedJSONLWriter(self.file_path, max_bytes)

    def write(self, entry: LogEntry) -> None:
        d = entry.as_compact() if self.compact else entry.as_dict()
        # Add extra fields if present
        if entry.extra:
            d["extra"] = {k: repr(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
                          for k, v in entry.extra.items()}

        indent = 2 if self.pretty else None
        line = json.dumps(d, ensure_ascii=False, default=str, indent=indent)

        with self._lock:
            if self._bounded is not None:
                self._bounded.write((line + "\n").encode("utf-8"))
            else:
                with open(self.file_path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")

        if self.delegate:
            self.delegate.write(entry)

    def close(self) -> None:
        if self.delegate:
            self.delegate.close()
