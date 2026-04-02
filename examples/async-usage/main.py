#!/usr/bin/env python3
"""
nfo example — async function logging.

Demonstrates transparent async support: @log_call and @catch
automatically detect async def functions — no separate decorator needed.

Usage:
    python examples/async_usage.py
"""

import asyncio

from nfo import Logger, SQLiteSink, log_call, catch
from nfo.decorators import set_default_logger

from pathlib import Path

DB_PATH = Path(__file__).parent / "async_logs.db"

HTTP_OK = 200
TIMESTAMP_SLICE = 19  # Length of timestamp for display (YYYY-MM-DD HH:MM:SS)


def setup_logger() -> Logger:
    logger = Logger(
        name="async-demo",
        sinks=[SQLiteSink(db_path=DB_PATH)],
        propagate_stdlib=True,
    )
    set_default_logger(logger)
    return logger


@log_call
async def fetch_data(url: str) -> dict:
    """Simulate an async HTTP fetch."""
    await asyncio.sleep(0.05)
    return {"url": url, "status": HTTP_OK, "data": "ok"}


@log_call(level="INFO")
async def process_batch(items: list) -> int:
    """Process items concurrently."""
    await asyncio.sleep(0.02 * len(items))
    return len(items)


@catch(default={})
async def risky_fetch(url: str) -> dict:
    """Fetch that may fail — returns {} on error instead of raising."""
    await asyncio.sleep(0.01)
    if "bad" in url:
        raise ConnectionError(f"Cannot connect to {url}")
    return {"url": url, "data": "ok"}


async def main():
    logger = setup_logger()

    print("=== Async @log_call ===")
    result = await fetch_data("https://api.example.com/users")
    print(f"fetch_data -> {result}\n")

    count = await process_batch(["task1", "task2", "task3"])
    print(f"process_batch -> {count}\n")

    print("=== Async @catch (suppresses exceptions) ===")
    ok = await risky_fetch("https://api.example.com/data")
    print(f"risky_fetch (ok) -> {ok}\n")

    fail = await risky_fetch("https://bad.example.com")
    print(f"risky_fetch (fail) -> {fail}  (no crash!)\n")

    print("=== Concurrent execution (all logged) ===")
    results = await asyncio.gather(
        fetch_data("https://api.example.com/a"),
        fetch_data("https://api.example.com/b"),
        fetch_data("https://api.example.com/c"),
    )
    print(f"gather -> {len(results)} results\n")

    logger.close()

    # Show logs from SQLite
    import sqlite3
    print(f"--- Logs in {DB_PATH} ---")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    for row in conn.execute(
        "SELECT timestamp, level, function_name, duration_ms FROM logs ORDER BY timestamp"
    ):
        print(
            f"  {row['timestamp'][:TIMESTAMP_SLICE]} | {row['level']:5s} | "
            f"{row['function_name']} | {row['duration_ms']:.1f}ms"
        )
    conn.close()

    DB_PATH.unlink(missing_ok=True)


if __name__ == "__main__":
    asyncio.run(main())
