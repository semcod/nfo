#!/usr/bin/env python3
"""nfo example — logging to SQLite database."""

import sqlite3
from pathlib import Path

from nfo import Logger, log_call, catch, SQLiteSink
from nfo.decorators import set_default_logger

DB_PATH = Path(__file__).parent / "demo_logs.db"


def setup_logger() -> Logger:
    sink = SQLiteSink(db_path=DB_PATH, table="logs")
    logger = Logger(name="sqlite-demo", sinks=[sink], propagate_stdlib=True)
    set_default_logger(logger)
    return logger


@log_call
def fetch_user(user_id: int) -> dict:
    if user_id <= 0:
        raise ValueError(f"Invalid user_id: {user_id}")
    return {"id": user_id, "name": "Alice", "role": "admin"}


@catch(default={})
def parse_config(raw: str) -> dict:
    """Parse config string. Returns empty dict on failure."""
    import json
    return json.loads(raw)


if __name__ == "__main__":
    logger = setup_logger()

    # Successful calls
    user = fetch_user(42)
    print(f"User: {user}")

    config = parse_config('{"debug": true}')
    print(f"Config: {config}")

    # Failing calls
    config_bad = parse_config("not json!")
    print(f"Bad config (caught): {config_bad}")

    try:
        fetch_user(-1)
    except ValueError:
        print("ValueError caught (logged to SQLite)")

    logger.close()

    # Query the database
    print(f"\n--- Logs in {DB_PATH} ---")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT timestamp, level, function_name, return_value, exception FROM logs").fetchall()
    for row in rows:
        print(f"  {row['timestamp'][:19]} | {row['level']:5s} | {row['function_name']} | ret={row['return_value'][:30] if row['return_value'] else ''} | exc={row['exception'][:40] if row['exception'] else ''}")
    conn.close()

    # Cleanup
    DB_PATH.unlink(missing_ok=True)
