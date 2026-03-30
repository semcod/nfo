"""
nfo CLI — universal command proxy with automatic logging.

Usage:
    nfo run -- bash deploy.sh prod
    nfo run -- go run main.go
    nfo run -- docker build .
    nfo run --sink sqlite:logs.db -- ./test.sh --suite=unit
    nfo logs logs.db --level ERROR --last 24h
    nfo version

Can also be invoked as:
    python -m nfo run -- bash deploy.sh prod
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

# Import Pydantic for HTTP service models (conditionally for optional dashboard feature)
try:
    from pydantic import BaseModel
except ImportError:
    BaseModel = None  # type: ignore


def _setup_logger(sink_specs: list[str], env: str | None = None):
    """Build nfo Logger from CLI sink specs."""
    from nfo import Logger, SQLiteSink, CSVSink, MarkdownSink, JSONSink
    from nfo.configure import _parse_sink_spec
    from nfo.decorators import set_default_logger

    sinks = []
    for spec in sink_specs:
        sinks.append(_parse_sink_spec(spec))

    if not sinks:
        # Default: SQLite in current dir
        db_path = os.environ.get("NFO_DB", "nfo_logs.db")
        sinks.append(SQLiteSink(db_path=db_path))

    logger = Logger(name="nfo-cli", sinks=sinks, propagate_stdlib=True)
    set_default_logger(logger)
    return logger


def _build_log_entry(
    cmd: list[str],
    result: subprocess.CompletedProcess | None,
    start_time: float,
    env_name: str,
    stdout: str,
    stderr: str,
    exception: str | None = None,
    exception_type: str | None = None,
) -> Any:
    """Build a LogEntry from command execution results."""
    from nfo.models import LogEntry

    duration_ms = (time.time() - start_time) * 1000
    success = result.returncode == 0 if result else False

    return LogEntry(
        timestamp=LogEntry.now(),
        level="INFO" if success else "ERROR",
        function_name=cmd[0],
        module="cli",
        args=tuple(cmd[1:]),
        kwargs={"language": _detect_language(cmd[0]), "env": env_name},
        arg_types=[type(a).__name__ for a in cmd[1:]],
        kwarg_types={"language": "str", "env": "str"},
        return_value=stdout[:2000] if stdout else None,
        return_type="str" if stdout else None,
        exception=exception or (stderr[:2000] if not success and stderr else None),
        exception_type=exception_type or ("ProcessError" if not success else None),
        duration_ms=duration_ms,
        environment=env_name,
        extra={
            "returncode": result.returncode if result else -1,
            "cmd": " ".join(cmd),
        },
    )


def _emit_command_result(
    logger: Any,
    cmd: list[str],
    result: subprocess.CompletedProcess,
    start_time: float,
    env_name: str,
    passthrough: bool,
) -> None:
    """Emit log entry for command result and print output."""
    from nfo.models import LogEntry

    stdout = result.stdout if not passthrough else ""
    stderr = result.stderr if not passthrough else ""
    duration_ms = (time.time() - start_time) * 1000

    entry = LogEntry(
        timestamp=LogEntry.now(),
        level="INFO" if result.returncode == 0 else "ERROR",
        function_name=cmd[0],
        module="cli",
        args=tuple(cmd[1:]),
        kwargs={"language": _detect_language(cmd[0]), "env": env_name},
        arg_types=[type(a).__name__ for a in cmd[1:]],
        kwarg_types={"language": "str", "env": "str"},
        return_value=stdout[:2000] if stdout else None,
        return_type="str" if stdout else None,
        exception=stderr[:2000] if result.returncode != 0 and stderr else None,
        exception_type="ProcessError" if result.returncode != 0 else None,
        duration_ms=duration_ms,
        environment=env_name,
        extra={
            "returncode": result.returncode,
            "cmd": " ".join(cmd),
        },
    )
    logger.emit(entry)

    if not passthrough:
        if stdout:
            print(stdout, end="")
        if stderr:
            print(stderr, end="", file=sys.stderr)


def _emit_command_not_found(
    logger: Any,
    cmd: list[str],
    start_time: float,
    env_name: str,
) -> None:
    """Emit log entry for command not found error."""
    from nfo.models import LogEntry

    duration_ms = (time.time() - start_time) * 1000
    entry = LogEntry(
        timestamp=LogEntry.now(),
        level="ERROR",
        function_name=cmd[0],
        module="cli",
        args=tuple(cmd[1:]),
        kwargs={"language": _detect_language(cmd[0]), "env": env_name},
        arg_types=[type(a).__name__ for a in cmd[1:]],
        kwarg_types={"language": "str", "env": "str"},
        exception=f"Command not found: {cmd[0]}",
        exception_type="FileNotFoundError",
        duration_ms=duration_ms,
        environment=env_name,
    )
    logger.emit(entry)
    logger.close()
    print(f"nfo: command not found: {cmd[0]}", file=sys.stderr)


def cmd_run(args):
    """Run a command and log it through nfo."""
    from nfo.models import LogEntry

    if not args.command:
        print("Error: no command specified. Usage: nfo run -- <command> [args...]", file=sys.stderr)
        sys.exit(1)

    sink_specs = args.sink or os.environ.get("NFO_SINKS", "").split(",")
    sink_specs = [s.strip() for s in sink_specs if s.strip()]
    logger = _setup_logger(sink_specs, env=args.env)

    cmd = args.command
    env_name = args.env or os.environ.get("NFO_ENV", "local")

    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=not args.passthrough,
            text=True,
            env=os.environ,
        )
        _emit_command_result(logger, cmd, result, start, env_name, args.passthrough)
        logger.close()
        sys.exit(result.returncode)

    except FileNotFoundError:
        _emit_command_not_found(logger, cmd, start, env_name)
        sys.exit(127)


def _build_logs_query(args) -> tuple[str, list]:
    """Build SQL query and params for log filtering."""
    query = "SELECT * FROM logs WHERE 1=1"
    params: list = []

    if args.level:
        query += " AND level = ?"
        params.append(args.level.upper())

    if args.function:
        query += " AND function_name LIKE ?"
        params.append(f"%{args.function}%")

    if args.env:
        query += " AND environment = ?"
        params.append(args.env)

    if args.errors:
        query += " AND level = 'ERROR'"

    if args.last:
        hours = _parse_duration(args.last)
        query += " AND timestamp >= datetime('now', ?)"
        params.append(f"-{hours} hours")

    query += " ORDER BY timestamp DESC"
    query += f" LIMIT {args.limit}"

    return query, params


def _format_log_row(row: sqlite3.Row) -> str:
    """Format a single log row for display."""
    d = dict(row)
    ts = d.get("timestamp", "")[:19]
    level = d.get("level", "?")
    func = d.get("function_name", "?")
    dur = d.get("duration_ms")
    dur_str = f"{dur:.0f}ms" if dur else "—"
    exc = d.get("exception", "")
    env = d.get("environment", "")

    # Color: red for ERROR, green for INFO
    if level == "ERROR":
        prefix = "\033[31m"
        suffix = "\033[0m"
    else:
        prefix = "\033[32m" if sys.stdout.isatty() else ""
        suffix = "\033[0m" if sys.stdout.isatty() else ""

    line = f"{prefix}{ts} | {level:5s} | {func} | {dur_str}"
    if env:
        line += f" | env={env}"
    if exc:
        line += f" | {exc[:60]}"
    line += suffix
    return line


def cmd_logs(args):
    """Query nfo logs from SQLite database."""
    import sqlite3

    db_path = args.db or os.environ.get("NFO_DB", "nfo_logs.db")
    if not Path(db_path).exists():
        print(f"Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    query, params = _build_logs_query(args)
    rows = conn.execute(query, params).fetchall()
    conn.close()

    if not rows:
        print("No logs found.")
        return

    for row in rows:
        print(_format_log_row(row))

    print(f"\n({len(rows)} entries from {db_path})")


def cmd_version(args):
    """Print nfo version."""
    from nfo import __version__
    print(f"nfo {__version__}")


def cmd_serve(args):
    """Start nfo HTTP logging service."""
    try:
        import uvicorn
    except ImportError:
        print("nfo serve requires: pip install nfo[dashboard]", file=sys.stderr)
        sys.exit(1)

    # Import the http_service app
    # Set env vars before import
    if args.port:
        os.environ["NFO_PORT"] = str(args.port)
    if args.host:
        os.environ["NFO_HOST"] = args.host

    from nfo.models import LogEntry  # verify nfo works
    host = args.host or os.environ.get("NFO_HOST", "0.0.0.0")
    port = args.port or int(os.environ.get("NFO_PORT", "8080"))

    print(f"Starting nfo HTTP logging service on {host}:{port}")
    print(f"  POST /log        — log single entry")
    print(f"  POST /log/batch  — log multiple entries")
    print(f"  GET  /logs       — query logs")
    print(f"  GET  /health     — health check")
    print()

    # Inline minimal FastAPI app (no external file dependency)
    _run_inline_server(host, port)


# Pydantic models for HTTP service (must be at module level for Pydantic v2)
if BaseModel is not None:
    class _HttpLogEntry(BaseModel):
        cmd: str
        args: list = []
        language: str = "bash"
        env: str = "prod"
        success: bool | None = None
        duration_ms: float | None = None
        output: str | None = None
        error: str | None = None

    class _HttpBatchReq(BaseModel):
        entries: list[_HttpLogEntry]
else:
    # Dummy classes when pydantic is not installed
    class _HttpLogEntry:  # type: ignore
        pass

    class _HttpBatchReq:  # type: ignore
        pass


def _run_inline_server(host: str, port: int):
    """Run a minimal nfo HTTP service inline."""
    import uvicorn
    from nfo import Logger, SQLiteSink, CSVSink, JSONSink
    from nfo.models import LogEntry as NfoEntry

    try:
        from fastapi import FastAPI, Query as FQuery, Body
    except ImportError:
        print("nfo serve requires: pip install nfo[dashboard]", file=sys.stderr)
        sys.exit(1)

    log_dir = os.environ.get("NFO_LOG_DIR", ".")
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    db_path = f"{log_dir}/nfo_central.db"

    sinks_env = os.environ.get("NFO_SINKS", "").strip()
    if sinks_env:
        from nfo.configure import _parse_sink_spec
        sinks = [_parse_sink_spec(s.strip()) for s in sinks_env.split(",") if s.strip()]
    else:
        sinks = [SQLiteSink(db_path=db_path)]

    logger = Logger(name="nfo-service", sinks=sinks, propagate_stdlib=True)

    app = FastAPI(title="nfo Logging Service")

    def _store(e: _HttpLogEntry) -> dict:
        entry = NfoEntry(
            timestamp=NfoEntry.now(),
            level="INFO" if e.success is not False else "ERROR",
            function_name=e.cmd,
            module=e.language,
            args=tuple(e.args),
            kwargs={"language": e.language, "env": e.env},
            arg_types=[type(a).__name__ for a in e.args],
            kwarg_types={"language": "str", "env": "str"},
            return_value=e.output,
            return_type=type(e.output).__name__ if e.output else None,
            exception=e.error,
            exception_type="RemoteError" if e.error else None,
            duration_ms=e.duration_ms or 0.0,
            environment=e.env,
        )
        logger.emit(entry)
        return {"cmd": e.cmd, "language": e.language, "stored": True}

    @app.post("/log")
    async def log_call(entry: _HttpLogEntry = Body(...)):
        return _store(entry)

    @app.post("/log/batch")
    async def log_batch(batch: _HttpBatchReq = Body(...)):
        results = [_store(e) for e in batch.entries]
        return {"stored": len(results), "results": results}

    @app.get("/logs")
    async def get_logs(level: str | None = None, limit: int = FQuery(50, ge=1, le=1000)):
        import sqlite3
        if not Path(db_path).exists():
            return []
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        q = "SELECT * FROM logs WHERE 1=1"
        p: list = []
        if level:
            q += " AND level = ?"
            p.append(level.upper())
        q += " ORDER BY timestamp DESC LIMIT ?"
        p.append(limit)
        rows = conn.execute(q, p).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @app.get("/health")
    async def health():
        return {"status": "ok", "db": db_path}

    uvicorn.run(app, host=host, port=port)


def _detect_language(cmd: str) -> str:
    """Guess language from command name."""
    cmd_lower = cmd.lower()
    if cmd_lower in ("bash", "sh", "zsh"):
        return "bash"
    if cmd_lower.endswith(".sh"):
        return "bash"
    if cmd_lower in ("python", "python3"):
        return "python"
    if cmd_lower.endswith(".py"):
        return "python"
    if cmd_lower == "go" or cmd_lower.endswith(".go"):
        return "go"
    if cmd_lower in ("cargo", "rustc"):
        return "rust"
    if cmd_lower in ("node", "npm", "npx", "bun", "deno"):
        return "node"
    if cmd_lower in ("docker", "docker-compose", "podman"):
        return "docker"
    if cmd_lower in ("make", "cmake"):
        return "make"
    return "shell"


def _parse_duration(spec: str) -> float:
    """Parse duration like '24h', '30m', '7d' to hours."""
    spec = spec.strip().lower()
    if spec.endswith("h"):
        return float(spec[:-1])
    if spec.endswith("m"):
        return float(spec[:-1]) / 60
    if spec.endswith("d"):
        return float(spec[:-1]) * 24
    return float(spec)


def main():
    parser = argparse.ArgumentParser(
        prog="nfo",
        description="nfo — automatic function & command logging",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- nfo run ---
    run_parser = subparsers.add_parser(
        "run", help="Run a command with nfo logging"
    )
    run_parser.add_argument(
        "--sink", action="append", default=None,
        help="Sink spec (e.g. sqlite:logs.db). Repeatable. Default: NFO_SINKS env or nfo_logs.db"
    )
    run_parser.add_argument(
        "--env", default=None,
        help="Environment tag (default: NFO_ENV or 'local')"
    )
    run_parser.add_argument(
        "--passthrough", "-p", action="store_true",
        help="Pass stdout/stderr directly (don't capture)"
    )
    run_parser.add_argument(
        "cmd_args", nargs=argparse.REMAINDER,
        help="Command to run (after --)"
    )

    # --- nfo logs ---
    logs_parser = subparsers.add_parser(
        "logs", help="Query nfo logs from SQLite"
    )
    logs_parser.add_argument(
        "db", nargs="?", default=None,
        help="SQLite database path (default: NFO_DB or nfo_logs.db)"
    )
    logs_parser.add_argument("--level", help="Filter by level (ERROR, INFO, DEBUG)")
    logs_parser.add_argument("--function", "-f", help="Filter by function name (substring)")
    logs_parser.add_argument("--env", help="Filter by environment")
    logs_parser.add_argument("--errors", "-e", action="store_true", help="Show only errors")
    logs_parser.add_argument("--last", help="Time window (e.g. 24h, 30m, 7d)")
    logs_parser.add_argument("--limit", "-n", type=int, default=20, help="Max results (default: 20)")

    # --- nfo serve ---
    serve_parser = subparsers.add_parser(
        "serve", help="Start nfo HTTP logging service"
    )
    serve_parser.add_argument("--host", default=None, help="Bind host (default: 0.0.0.0)")
    serve_parser.add_argument("--port", type=int, default=None, help="Bind port (default: 8080)")

    # --- nfo version ---
    subparsers.add_parser("version", help="Print nfo version")

    args = parser.parse_args()

    if args.command == "run":
        # Strip leading '--' from REMAINDER
        cmd = args.cmd_args
        if cmd and cmd[0] == "--":
            cmd = cmd[1:]
        args.command_list = cmd
        args.command = "run"  # restore after nargs consumed it
        args_obj = argparse.Namespace(**vars(args))
        args_obj.command = cmd
        cmd_run(args_obj)
    elif args.command == "logs":
        cmd_logs(args)
    elif args.command == "serve":
        cmd_serve(args)
    elif args.command == "version":
        cmd_version(args)
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
