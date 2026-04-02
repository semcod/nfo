"""
nfo DevOps Demo App

A FastAPI application demonstrating all nfo sinks working together:
- PrometheusSink → Prometheus scrapes /metrics
- JSONSink → logs.jsonl for Grafana Loki / ELK
- SQLiteSink → queryable logs
- WebhookSink → Slack/Discord alerts on ERROR
- EnvTagger → auto-tags env/trace/version

Endpoints:
    GET  /              → health check
    GET  /demo/success  → call decorated functions that succeed
    GET  /demo/error    → call decorated functions that fail
    GET  /demo/slow     → call a slow function (measures duration)
    GET  /demo/batch    → run a batch of mixed calls
    GET  /metrics       → Prometheus metrics (via prometheus_client)
    GET  /logs          → browse latest SQLite logs as JSON
"""

from __future__ import annotations

from typing import Dict, Any

import os
import random
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse

import nfo
from nfo import (
    log_call,
    catch,
    logged,
    configure,
    Logger,
    SQLiteSink,
    JSONSink,
    EnvTagger,
)
from nfo.prometheus import PrometheusSink
from nfo.webhook import WebhookSink

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

LOG_DIR = os.environ.get("NFO_LOG_DIR", "/tmp/nfo-demo-logs")
Path(LOG_DIR).mkdir(parents=True, exist_ok=True)

DB_PATH = f"{LOG_DIR}/demo.db"
JSONL_PATH = f"{LOG_DIR}/demo.jsonl"

PROMETHEUS_PORT = int(os.environ.get("NFO_PROMETHEUS_PORT", "9090"))
WEBHOOK_URL = os.environ.get("NFO_WEBHOOK_URL", "")
ENVIRONMENT = os.environ.get("NFO_ENV", "demo")
VERSION = os.environ.get("NFO_VERSION", nfo.__version__)

# ---------------------------------------------------------------------------
# Build sink pipeline
# ---------------------------------------------------------------------------

sqlite_sink = SQLiteSink(db_path=DB_PATH)
json_sink = JSONSink(file_path=JSONL_PATH)
prom_sink = PrometheusSink(port=PROMETHEUS_PORT, delegate=sqlite_sink)

# Composable pipeline: EnvTagger → Prometheus+SQLite + JSON
sinks = [
    EnvTagger(prom_sink, environment=ENVIRONMENT, version=VERSION),
    EnvTagger(json_sink, environment=ENVIRONMENT, version=VERSION),
]

# Optional webhook for ERROR alerts
if WEBHOOK_URL:
    webhook_sink = WebhookSink(
        url=WEBHOOK_URL,
        delegate=sqlite_sink,
        levels=["ERROR"],
        format="slack",
    )
    sinks.append(EnvTagger(webhook_sink, environment=ENVIRONMENT, version=VERSION))

logger = Logger(name="nfo-demo", level="DEBUG", sinks=sinks, propagate_stdlib=True)
nfo.configure(
    name="nfo-demo",
    sinks=sinks,
    environment=ENVIRONMENT,
    version=VERSION,
    force=True,
)

DEFAULT_FIB_N_SMALL = 10
DEFAULT_FIB_N_LARGE = 20
BATCH_COUNT_FIB = 20
BATCH_COUNT_ORDERS = 5
BATCH_COUNT_DIVISIONS = 5
BATCH_COUNT_USERS = 3
MAX_LOGS_LIMIT = 50
DEFAULT_PORT = 8000


@log_call
def compute_fibonacci(n: int) -> int:
    """Compute fibonacci number (intentionally slow for large n)."""
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b


@log_call(level="INFO")
def process_order(order_id: str, amount: float) -> dict:
    """Simulate order processing."""
    time.sleep(random.uniform(0.01, 0.05))
    return {"order_id": order_id, "amount": amount, "status": "completed"}


@catch(default=None)
def risky_division(a: float, b: float) -> float:
    """Division that may fail."""
    return a / b


@log_call
def slow_operation(duration: float) -> str:
    """Simulate a slow operation."""
    time.sleep(duration)
    return f"completed in {duration}s"


@logged
class UserService:
    def create_user(self, name: str, email: str) -> dict:
        time.sleep(random.uniform(0.005, 0.02))
        return {"name": name, "email": email, "id": random.randint(1000, 9999)}

    def delete_user(self, user_id: int) -> bool:
        if user_id < 0:
            raise ValueError(f"Invalid user_id: {user_id}")
        return True


user_service = UserService()

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="nfo DevOps Demo", version=nfo.__version__)


@app.get("/")
def health() -> Dict[str, Any]:
    return {"status": "ok", "version": nfo.__version__, "environment": ENVIRONMENT}


@app.get("/demo/success")
def demo_success() -> Dict[str, Any]:
    """Run several successful decorated function calls."""
    results = {
        "fibonacci_small": compute_fibonacci(DEFAULT_FIB_N_SMALL),
        "fibonacci_large": compute_fibonacci(DEFAULT_FIB_N_LARGE),
        "order": process_order("ORD-001", 99.99),
        "division": risky_division(100, 7),
        "user": user_service.create_user("Alice", "alice@example.com"),
    }
    return {"status": "ok", "results": results}


@app.get("/demo/error")
def demo_error() -> Dict[str, Any]:
    """Trigger error-level log entries."""
    results = {
        "division_by_zero": risky_division(1, 0),  # caught, returns None
    }
    try:
        user_service.delete_user(-1)  # raises ValueError
    except ValueError as e:
        results["delete_error"] = str(e)

    return {"status": "errors_triggered", "results": results}


@app.get("/demo/slow")
def demo_slow() -> Dict[str, Any]:
    """Trigger a slow operation to demonstrate duration histograms."""
    duration = random.uniform(0.1, 0.5)
    result = slow_operation(duration)
    return {"status": "ok", "result": result, "target_duration": duration}


@app.get("/demo/batch")
def demo_batch() -> Dict[str, Any]:
    """Run a batch of mixed calls (success + errors) for load simulation."""
    count = {"success": 0, "error": 0}
    for i in range(BATCH_COUNT_FIB):
        compute_fibonacci(random.randint(5, 30))
        count["success"] += 1

    for i in range(BATCH_COUNT_ORDERS):
        process_order(f"ORD-{i:03d}", random.uniform(10, 500))
        count["success"] += 1

    for i in range(BATCH_COUNT_DIVISIONS):
        result = risky_division(random.uniform(1, 100), random.choice([0, 1, 2, 3]))
        if result is None:
            count["error"] += 1
        else:
            count["success"] += 1

    for i in range(BATCH_COUNT_USERS):
        user_service.create_user(f"User-{i}", f"user{i}@test.com")
        count["success"] += 1

    return {"status": "batch_complete", "counts": count}


@app.get("/metrics")
def metrics():
    """Expose Prometheus metrics (alternative to prom_sink auto-server)."""
    return PlainTextResponse(
        prom_sink.get_metrics().decode(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.get("/logs")
def browse_logs(level: str = "", limit: int = MAX_LOGS_LIMIT) -> JSONResponse:
    """Browse latest logs from SQLite."""
    import sqlite3

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    query = "SELECT * FROM logs"
    params = []
    if level:
        query += " WHERE level = ?"
        params.append(level.upper())
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    return JSONResponse([dict(r) for r in rows])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=DEFAULT_PORT)
