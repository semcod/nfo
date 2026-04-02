#!/usr/bin/env python3
"""
nfo example — auto_log() for zero-decorator module-wide logging.

Demonstrates patching all public functions in a module with a single call.
No need to add @log_call to every function.

Usage:
    python examples/auto_log_usage.py
"""

from pathlib import Path

from nfo import configure, auto_log, skip

DB_PATH = Path(__file__).parent / "auto_log_demo.db"

# Constants
USER_ID_ALICE = 1001
PRICE_BOOK = 9.99
PRICE_COURSE = 19.99
PRICE_SNACK = 4.99
USER_ID_TEST = 42

# ---------------------------------------------------------------------------
# Configure nfo with SQLite sink
# ---------------------------------------------------------------------------

configure(sinks=[f"sqlite:{DB_PATH}"], name="auto-log-demo", force=True)


# ---------------------------------------------------------------------------
# Business logic — no decorators needed
# ---------------------------------------------------------------------------

def create_user(name: str, email: str) -> dict:
    """Create a new user."""
    return {"name": name, "email": email, "id": USER_ID_ALICE}


def delete_user(user_id: int) -> bool:
    """Delete user by ID."""
    if user_id <= 0:
        raise ValueError(f"Invalid user_id: {user_id}")
    return True


def calculate_total(prices: list) -> float:
    """Sum a list of prices."""
    return sum(prices)


@skip
def health_check() -> str:
    """Excluded from auto_log — called frequently, not interesting."""
    return "ok"


def _internal_helper():
    """Private function — auto_log skips these by default."""
    pass


# ---------------------------------------------------------------------------
# One call patches all public functions above
# ---------------------------------------------------------------------------

auto_log()

# ---------------------------------------------------------------------------
# Now every call is automatically logged
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== auto_log() — all public functions logged automatically ===\n")

    user = create_user("Alice", "alice@example.com")
    print(f"create_user -> {user}")

    total = calculate_total([PRICE_BOOK, PRICE_COURSE, PRICE_SNACK])
    print(f"calculate_total -> {total}")

    ok = delete_user(USER_ID_TEST)
    print(f"delete_user -> {ok}")

    # This is NOT logged (has @skip)
    status = health_check()
    print(f"health_check -> {status} (not logged)")

    # This is NOT logged (private)
    _internal_helper()
    print(f"_internal_helper (not logged)\n")

    # Error case — auto-logged with traceback
    try:
        delete_user(-1)
    except ValueError as e:
        print(f"delete_user(-1) raised: {e} (logged with traceback)\n")

    # Show SQLite logs
    import sqlite3
    print(f"--- Logs in {DB_PATH} ---")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    for row in conn.execute(
        "SELECT timestamp, level, function_name, args, return_value, exception FROM logs"
    ):
        exc = f" | exc={row['exception'][:40]}" if row['exception'] else ""
        ret = f" | ret={row['return_value'][:40]}" if row['return_value'] else ""
        print(f"  {row['level']:5s} | {row['function_name']}{ret}{exc}")
    conn.close()

    DB_PATH.unlink(missing_ok=True)
