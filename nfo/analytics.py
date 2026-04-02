"""
nfo.analytics — log analysis and aggregation functions.

Provides trend analysis, aggregation queries, and statistical functions
for nfo SQLite logs without external dependencies.

Usage::

    from nfo.analytics import LogAnalytics
    from nfo import SQLiteSink

    sink = SQLiteSink("app.db")
    analytics = LogAnalytics(sink)

    # Get error rate by hour
    errors = analytics.count_by(level="ERROR", group_by="hour")

    # Find slowest functions
    slow = analytics.slowest_functions(n=10, min_calls=5)

    # Detect anomalies
    anomalies = analytics.find_anomalies("process_order", threshold=3.0)
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean, stdev
from typing import Any


@dataclass
class LogStats:
    """Statistics for a single function/metric."""

    function_name: str
    count: int
    total_duration_ms: float
    avg_duration_ms: float
    min_duration_ms: float
    max_duration_ms: float
    error_count: int
    error_rate: float


class LogAnalytics:
    """Analytics engine for nfo SQLite logs."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        """Create database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def count_by(
        self,
        level: str | None = None,
        function_name: str | None = None,
        since: datetime | None = None,
        group_by: str = "day",
    ) -> list[dict[str, Any]]:
        """Count logs grouped by time period.

        Args:
            level: Filter by log level (INFO, ERROR, etc.)
            function_name: Filter by specific function
            since: Only include logs since this datetime
            group_by: Time grouping - "hour", "day", or "month"
        """
        group_formats = {
            "hour": "%Y-%m-%d %H:00",
            "day": "%Y-%m-%d",
            "month": "%Y-%m",
        }
        fmt = group_formats.get(group_by, group_formats["day"])

        query = f"""
            SELECT strftime('{fmt}', timestamp) as period, COUNT(*) as count
            FROM logs
            WHERE 1=1
        """
        params = []

        if level:
            query += " AND level = ?"
            params.append(level)
        if function_name:
            query += " AND function_name = ?"
            params.append(function_name)
        if since:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())

        query += f" GROUP BY strftime('{fmt}', timestamp) ORDER BY period"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [{"period": r["period"], "count": r["count"]} for r in rows]

    def slowest_functions(
        self,
        n: int = 10,
        min_calls: int = 5,
        since: datetime | None = None,
    ) -> list[LogStats]:
        """Find slowest functions by average duration.

        Args:
            n: Number of results to return
            min_calls: Minimum number of calls to include
            since: Only include logs since this datetime
        """
        query = """
            SELECT
                function_name,
                COUNT(*) as count,
                SUM(duration_ms) as total_duration_ms,
                AVG(duration_ms) as avg_duration_ms,
                MIN(duration_ms) as min_duration_ms,
                MAX(duration_ms) as max_duration_ms,
                SUM(CASE WHEN exception IS NOT NULL THEN 1 ELSE 0 END) as error_count
            FROM logs
            WHERE 1=1
        """
        params = []

        if since:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())

        query += """
            GROUP BY function_name
            HAVING count >= ?
            ORDER BY avg_duration_ms DESC
            LIMIT ?
        """
        params.extend([min_calls, n])

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                LogStats(
                    function_name=r["function_name"],
                    count=r["count"],
                    total_duration_ms=r["total_duration_ms"] or 0,
                    avg_duration_ms=r["avg_duration_ms"] or 0,
                    min_duration_ms=r["min_duration_ms"] or 0,
                    max_duration_ms=r["max_duration_ms"] or 0,
                    error_count=r["error_count"],
                    error_rate=r["error_count"] / r["count"] if r["count"] > 0 else 0,
                )
                for r in rows
            ]

    def error_rate(
        self,
        since: datetime | None = None,
        window_hours: int = 24,
    ) -> dict[str, Any]:
        """Calculate overall error rate and trends.

        Args:
            since: Start time for analysis (default: 24h ago)
            window_hours: Time window for analysis
        """
        if since is None:
            since = datetime.now() - timedelta(hours=window_hours)

        query = """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN exception IS NOT NULL THEN 1 ELSE 0 END) as errors
            FROM logs
            WHERE timestamp >= ?
        """

        with self._connect() as conn:
            row = conn.execute(query, (since.isoformat(),)).fetchone()
            total = row["total"]
            errors = row["errors"]
            return {
                "total_logs": total,
                "error_count": errors,
                "error_rate": errors / total if total > 0 else 0,
                "window_hours": window_hours,
            }

    def find_anomalies(
        self,
        function_name: str,
        threshold: float = 3.0,
        since: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Find anomalous executions based on duration outliers.

        Uses z-score to detect outliers (threshold = standard deviations).

        Args:
            function_name: Function to analyze
            threshold: Z-score threshold (default 3.0)
            since: Only include logs since this datetime
        """
        query = """
            SELECT timestamp, duration_ms, args, kwargs, return_value
            FROM logs
            WHERE function_name = ?
        """
        params = [function_name]

        if since:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())

        query += " AND duration_ms IS NOT NULL ORDER BY timestamp"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        if len(rows) < 10:
            return []  # Not enough data

        durations = [r["duration_ms"] for r in rows]
        avg = mean(durations)
        try:
            std = stdev(durations)
        except:
            return []  # All values same

        if std == 0:
            return []

        anomalies = []
        for row in rows:
            z_score = (row["duration_ms"] - avg) / std
            if abs(z_score) > threshold:
                anomalies.append({
                    "timestamp": row["timestamp"],
                    "duration_ms": row["duration_ms"],
                    "z_score": z_score,
                    "args": row["args"],
                    "kwargs": row["kwargs"],
                    "return_value": row["return_value"],
                })

        return anomalies

    def top_errors(self, n: int = 10, since: datetime | None = None) -> list[dict[str, Any]]:
        """Find most frequent errors.

        Args:
            n: Number of results to return
            since: Only include logs since this datetime
        """
        query = """
            SELECT
                exception_type,
                exception,
                COUNT(*) as count
            FROM logs
            WHERE exception IS NOT NULL
        """
        params = []

        if since:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())

        query += """
            GROUP BY exception_type, exception
            ORDER BY count DESC
            LIMIT ?
        """
        params.append(n)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                {
                    "exception_type": r["exception_type"],
                    "exception": r["exception"][:200] if r["exception"] else None,
                    "count": r["count"],
                }
                for r in rows
            ]

    def hourly_summary(self, hours: int = 24) -> list[dict[str, Any]]:
        """Get hourly summary of log activity.

        Args:
            hours: Number of hours to look back
        """
        since = datetime.now() - timedelta(hours=hours)

        query = """
            SELECT
                strftime('%Y-%m-%d %H:00', timestamp) as hour,
                COUNT(*) as total,
                SUM(CASE WHEN level = 'ERROR' THEN 1 ELSE 0 END) as errors,
                SUM(CASE WHEN level = 'WARNING' THEN 1 ELSE 0 END) as warnings,
                AVG(duration_ms) as avg_duration
            FROM logs
            WHERE timestamp >= ?
            GROUP BY strftime('%Y-%m-%d %H:00', timestamp)
            ORDER BY hour
        """

        with self._connect() as conn:
            rows = conn.execute(query, (since.isoformat(),)).fetchall()
            return [
                {
                    "hour": r["hour"],
                    "total": r["total"],
                    "errors": r["errors"],
                    "warnings": r["warnings"],
                    "avg_duration_ms": r["avg_duration"],
                }
                for r in rows
            ]


def create_analytics(db_path: str | None = None) -> LogAnalytics:
    """Factory function to create LogAnalytics instance.

    Args:
        db_path: Path to SQLite database (default: uses NFO_DB env var or "nfo_logs.db")
    """
    import os

    if db_path is None:
        db_path = os.environ.get("NFO_DB", "nfo_logs.db")

    return LogAnalytics(db_path)
