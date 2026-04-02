"""
nfo.metrics — lightweight metrics collection for function logging.

Provides counter, gauge, and histogram metrics without external dependencies.
Works alongside existing nfo sinks for unified observability.

Usage::

    from nfo.metrics import Counter, Gauge, Histogram

    requests = Counter("http_requests", labels=["method", "status"])
    requests.inc(method="GET", status=200)
    requests.inc(method="POST", status=201)

    queue_size = Gauge("queue_size")
    queue_size.set(42)

    latency = Histogram("request_latency", buckets=[0.1, 0.5, 1.0, 5.0])
    latency.observe(0.23)
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MetricValue:
    """Single metric value with timestamp."""

    value: float
    timestamp: float = field(default_factory=time.time)


class Counter:
    """Monotonically increasing counter metric.

    Supports labeled counters for multi-dimensional metrics.
    """

    def __init__(self, name: str, labels: list[str] | None = None):
        self.name = name
        self.labels = labels or []
        self._values: dict[tuple[str, ...], float] = defaultdict(float)
        self._lock = threading.Lock()

    def inc(self, amount: float = 1, **label_values) -> None:
        """Increment counter by amount (default 1)."""
        key = self._make_key(**label_values)
        with self._lock:
            self._values[key] += amount

    def get(self, **label_values) -> float:
        """Get current counter value."""
        key = self._make_key(**label_values)
        with self._lock:
            return self._values[key]

    def _make_key(self, **label_values) -> tuple[str, ...]:
        """Create tuple key from label values."""
        if not self.labels:
            return ()
        return tuple(str(label_values.get(k, "")) for k in self.labels)

    def snapshot(self) -> dict[tuple[str, ...], float]:
        """Return copy of all counter values."""
        with self._lock:
            return dict(self._values)


class Gauge:
    """Gauge metric for values that can go up or down.

    Supports labeled gauges for multi-dimensional metrics.
    """

    def __init__(self, name: str, labels: list[str] | None = None):
        self.name = name
        self.labels = labels or []
        self._values: dict[tuple[str, ...], float] = defaultdict(float)
        self._lock = threading.Lock()

    def set(self, value: float, **label_values) -> None:
        """Set gauge to specific value."""
        key = self._make_key(**label_values)
        with self._lock:
            self._values[key] = value

    def inc(self, amount: float = 1, **label_values) -> None:
        """Increment gauge by amount."""
        key = self._make_key(**label_values)
        with self._lock:
            self._values[key] += amount

    def dec(self, amount: float = 1, **label_values) -> None:
        """Decrement gauge by amount."""
        key = self._make_key(**label_values)
        with self._lock:
            self._values[key] -= amount

    def get(self, **label_values) -> float:
        """Get current gauge value."""
        key = self._make_key(**label_values)
        with self._lock:
            return self._values[key]

    def _make_key(self, **label_values) -> tuple[str, ...]:
        """Create tuple key from label values."""
        if not self.labels:
            return ()
        return tuple(str(label_values.get(k, "")) for k in self.labels)

    def snapshot(self) -> dict[tuple[str, ...], float]:
        """Return copy of all gauge values."""
        with self._lock:
            return dict(self._values)


class Histogram:
    """Histogram metric for latency/distribution tracking.

    Observations are bucketed into predefined buckets.
    """

    def __init__(
        self,
        name: str,
        buckets: list[float] | None = None,
        labels: list[str] | None = None,
    ):
        self.name = name
        self.labels = labels or []
        # Default buckets: exponential from 0.005 to ~10s
        self.buckets = sorted(buckets or [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10])
        self._counts: dict[tuple[str, ...], dict[float, int]] = defaultdict(lambda: defaultdict(int))
        self._sums: dict[tuple[str, ...], float] = defaultdict(float)
        self._totals: dict[tuple[str, ...], int] = defaultdict(int)
        self._lock = threading.Lock()

    def observe(self, value: float, **label_values) -> None:
        """Observe a value and place it in appropriate bucket."""
        key = self._make_key(**label_values)
        with self._lock:
            self._totals[key] += 1
            self._sums[key] += value
            for bucket in self.buckets:
                if value <= bucket:
                    self._counts[key][bucket] += 1

    def snapshot(self, **label_values) -> dict[str, Any]:
        """Return histogram snapshot with buckets, sum, and count."""
        key = self._make_key(**label_values)
        with self._lock:
            return {
                "buckets": dict(self._counts[key]),
                "sum": self._sums[key],
                "count": self._totals[key],
            }

    def _make_key(self, **label_values) -> tuple[str, ...]:
        """Create tuple key from label values."""
        if not self.labels:
            return ()
        return tuple(str(label_values.get(k, "")) for k in self.labels)


class MetricsCollector:
    """Central metrics collector for registering and collecting all metrics."""

    def __init__(self):
        self._metrics: dict[str, Counter | Gauge | Histogram] = {}
        self._lock = threading.Lock()

    def register(self, metric: Counter | Gauge | Histogram) -> None:
        """Register a metric with the collector."""
        with self._lock:
            self._metrics[metric.name] = metric

    def counter(self, name: str, labels: list[str] | None = None) -> Counter:
        """Create or get existing counter."""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Counter(name, labels)
            return self._metrics[name]

    def gauge(self, name: str, labels: list[str] | None = None) -> Gauge:
        """Create or get existing gauge."""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Gauge(name, labels)
            return self._metrics[name]

    def histogram(self, name: str, buckets: list[float] | None = None, labels: list[str] | None = None) -> Histogram:
        """Create or get existing histogram."""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Histogram(name, buckets, labels)
            return self._metrics[name]

    def snapshot(self) -> dict[str, Any]:
        """Return snapshot of all metrics."""
        with self._lock:
            result = {}
            for name, metric in self._metrics.items():
                if isinstance(metric, Counter):
                    result[name] = {"type": "counter", "values": metric.snapshot()}
                elif isinstance(metric, Gauge):
                    result[name] = {"type": "gauge", "values": metric.snapshot()}
                elif isinstance(metric, Histogram):
                    result[name] = {"type": "histogram", "snapshots": {}}
                    # Collect histogram snapshots for all label combinations
                    for key in metric._counts.keys():
                        label_dict = {}
                        if key and metric.labels:
                            label_dict = dict(zip(metric.labels, key))
                        result[name]["snapshots"][str(key)] = metric.snapshot(**label_dict)
            return result

    def clear(self) -> None:
        """Clear all metrics."""
        with self._lock:
            self._metrics.clear()


# Global collector instance
collector = MetricsCollector()
