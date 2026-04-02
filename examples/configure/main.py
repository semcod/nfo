#!/usr/bin/env python3
"""
nfo example — configure() one-liner setup with all features.

Demonstrates the configure() function for quick project-wide setup:
- Sink specs as strings ("sqlite:path", "csv:path", "md:path")
- Environment tagging
- stdlib logger bridging
- LLM model integration (optional)

Usage:
    python examples/configure_usage.py
"""

from pathlib import Path
from nfo import configure, log_call, catch, logged

OUT = Path(__file__).parent
DB_PATH = OUT / "configure_demo.db"
CSV_PATH = OUT / "configure_demo.csv"

# Constants
ORDER_AMOUNT = 99.99
CHARGE_AMOUNT = 50.0
CSV_PREVIEW_LENGTH = 500

# ---------------------------------------------------------------------------
# One-liner setup — replaces manual Logger + Sink + set_default_logger
# ---------------------------------------------------------------------------

configure(
    name="my-app",
    sinks=[f"sqlite:{DB_PATH}", f"csv:{CSV_PATH}"],
    environment="dev",
    version="1.0.0",
    force=True,
)


# ---------------------------------------------------------------------------
# All decorators now use the configured logger automatically
# ---------------------------------------------------------------------------

@log_call
def process_order(order_id: str, amount: float) -> dict:
    return {"order_id": order_id, "amount": amount, "status": "completed"}


@catch(default=None)
def parse_config(raw: str) -> dict:
    import json
    return json.loads(raw)


@logged
class PaymentService:
    def charge(self, amount: float) -> bool:
        return amount > 0

    def refund(self, tx_id: str) -> dict:
        return {"tx_id": tx_id, "refunded": True}


if __name__ == "__main__":
    print("=== configure() one-liner setup ===\n")

    process_order("ORD-001", ORDER_AMOUNT)
    print("process_order -> logged")

    parse_config('{"debug": true}')
    print("parse_config (ok) -> logged")

    parse_config("bad json!")
    print("parse_config (error) -> logged, returned None\n")

    svc = PaymentService()
    svc.charge(CHARGE_AMOUNT)
    svc.refund("TX-123")
    print("PaymentService methods -> logged\n")

    # Show logs
    import sqlite3
    print(f"--- Logs in {DB_PATH} ---")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    for row in conn.execute(
        "SELECT level, function_name, duration_ms FROM logs ORDER BY timestamp"
    ):
        print(f"  {row['level']:5s} | {row['function_name']} | {row['duration_ms']:.2f}ms")
    conn.close()

    print(f"\n--- CSV content ---")
    print(CSV_PATH.read_text()[:CSV_PREVIEW_LENGTH])

    # Cleanup
    DB_PATH.unlink(missing_ok=True)
    CSV_PATH.unlink(missing_ok=True)
