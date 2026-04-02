#!/usr/bin/env python3
"""
nfo example — .env file configuration with python-dotenv.

Demonstrates how to load nfo settings from a .env file so that
configure() picks them up automatically via os.environ.

Setup:
    pip install nfo python-dotenv

    # Copy .env.example and adjust:
    cp examples/.env.example examples/.env

Usage:
    python examples/env_config_usage.py

How it works:
    1. python-dotenv loads .env into os.environ
    2. nfo.configure() reads NFO_LEVEL, NFO_SINKS, NFO_ENV, etc.
    3. All decorators use the configured sinks automatically
    4. No hardcoded paths or settings in code — everything in .env
"""

from __future__ import annotations

import os
from pathlib import Path

# Constants
DEFAULT_STOCK_COUNT = 42
ORDER_AMOUNT = 99.99
CSV_PREVIEW_LENGTH = 500

# ---------------------------------------------------------------------------
# 1. Load .env file (before importing/configuring nfo)
# ---------------------------------------------------------------------------

try:
    from dotenv import load_dotenv
except ImportError:
    raise SystemExit(
        "This example requires python-dotenv:\n"
        "  pip install python-dotenv\n"
    )

# Look for .env in the examples/ directory (parent of this example)
examples_dir = Path(__file__).parent.parent
env_path = examples_dir / ".env"

if not env_path.exists():
    # Fall back to .env.example for demo purposes
    env_example = examples_dir / ".env.example"
    if env_example.exists():
        print(f"No .env found, loading .env.example for demo...")
        env_path = env_example
    else:
        print("No .env or .env.example found. Using defaults.")
        env_path = None

if env_path:
    load_dotenv(env_path, override=True)
    print(f"Loaded: {env_path}")

# ---------------------------------------------------------------------------
# 2. Show what nfo will see from environment
# ---------------------------------------------------------------------------

print("\nEffective nfo config from environment:")
for key in ("NFO_LEVEL", "NFO_SINKS", "NFO_ENV", "NFO_VERSION",
            "NFO_LOG_DIR", "NFO_LLM_MODEL", "NFO_WEBHOOK_URL",
            "NFO_PROMETHEUS_PORT"):
    val = os.environ.get(key)
    if val:
        print(f"  {key}={val}")

print()

# ---------------------------------------------------------------------------
# 3. Configure nfo — reads NFO_* env vars automatically
# ---------------------------------------------------------------------------

from nfo import configure, log_call, catch, logged

# Ensure log directory exists
log_dir = os.environ.get("NFO_LOG_DIR", "./logs")
Path(log_dir).mkdir(parents=True, exist_ok=True)

# configure() reads NFO_LEVEL, NFO_SINKS, NFO_ENV, NFO_VERSION, NFO_LLM_MODEL
# from os.environ — no need to pass them explicitly
logger = configure(force=True)

print(f"Logger: name={logger.name}, level={logger.level}, "
      f"sinks={len(logger._sinks)}")
print()

# ---------------------------------------------------------------------------
# 4. Use decorators — all settings come from .env
# ---------------------------------------------------------------------------

@log_call
def create_order(order_id: str, amount: float) -> dict:
    return {"order_id": order_id, "amount": amount, "status": "created"}


@catch(default=None)
def parse_payload(raw: str) -> dict:
    import json
    return json.loads(raw)


@logged
class InventoryService:
    def check_stock(self, item_id: str) -> int:
        return DEFAULT_STOCK_COUNT

    def reserve(self, item_id: str, qty: int) -> bool:
        if qty > 100:
            raise ValueError(f"Cannot reserve {qty} items")
        return True


if __name__ == "__main__":
    print("=== .env-configured nfo in action ===\n")

    create_order("ORD-001", ORDER_AMOUNT)
    print("create_order -> logged")

    parse_payload('{"key": "value"}')
    print("parse_payload (ok) -> logged")

    parse_payload("not json!")
    print("parse_payload (error) -> caught, logged\n")

    svc = InventoryService()
    svc.check_stock("ITEM-42")
    svc.reserve("ITEM-42", 5)
    print("InventoryService methods -> logged\n")

    logger.close()

    # Show what was logged
    sinks_spec = os.environ.get("NFO_SINKS", "")
    for spec in sinks_spec.split(","):
        spec = spec.strip()
        if spec.startswith("sqlite:"):
            db_path = spec.split(":", 1)[1]
            if Path(db_path).exists():
                import sqlite3
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT level, function_name, duration_ms FROM logs ORDER BY timestamp"
                ).fetchall()
                print(f"--- Logs in {db_path} ({len(rows)} entries) ---")
                for row in rows:
                    print(f"  {row['level']:5s} | {row['function_name']} | "
                          f"{row['duration_ms']:.2f}ms")
                conn.close()
        elif spec.startswith("csv:"):
            csv_path = spec.split(":", 1)[1]
            if Path(csv_path).exists():
                print(f"\n--- CSV: {csv_path} ---")
                print(Path(csv_path).read_text()[:CSV_PREVIEW_LENGTH])

    print("\nDone. All settings loaded from .env — zero hardcoded config in code.")
