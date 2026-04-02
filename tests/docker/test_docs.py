"""Comprehensive test runner for nfo documentation commands.

This script tests all documented commands and examples in a controlled environment.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Test results storage
results: list[dict] = []
PYTHON = sys.executable


def run_command(cmd: list[str], cwd: Path | None = None, timeout: int = 30) -> dict:
    """Run a command and capture result."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
        )
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timeout", "stdout": "", "stderr": "Timeout"}
    except Exception as e:
        return {"success": False, "error": str(e), "stdout": "", "stderr": str(e)}


def test_nfo_version() -> dict:
    """Test: nfo version"""
    print("Testing: nfo version")
    result = run_command([PYTHON, "-m", "nfo", "version"])
    success = result["success"] and "nfo" in result["stdout"]
    return {"name": "nfo version", "success": success, **result}


def test_nfo_run_bash() -> dict:
    """Test: nfo run -- bash -c 'echo hello'"""
    print("Testing: nfo run -- bash -c 'echo hello'")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        result = run_command([
            PYTHON, "-m", "nfo", "run",
            "--sink", f"sqlite:{db_path}",
            "--", "bash", "-c", "echo hello"
        ])
        success = result["success"] and "hello" in result["stdout"]
        return {"name": "nfo run bash", "success": success, **result}


def test_nfo_run_python() -> dict:
    """Test: nfo run -- python3 -c 'print(42)'"""
    print("Testing: nfo run -- python3 -c 'print(42)'")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        result = run_command([
            PYTHON, "-m", "nfo", "run",
            "--sink", f"sqlite:{db_path}",
            "--", "python3", "-c", "print(42)"
        ])
        success = result["success"] and "42" in result["stdout"]
        return {"name": "nfo run python", "success": success, **result}


def test_nfo_logs() -> dict:
    """Test: nfo logs"""
    print("Testing: nfo logs")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        # First create a log entry
        run_command([
            PYTHON, "-m", "nfo", "run",
            "--sink", f"sqlite:{db_path}",
            "--", "echo", "test"
        ])
        # Then query logs
        result = run_command([
            PYTHON, "-m", "nfo", "logs",
            str(db_path), "--limit", "5"
        ])
        success = result["success"]
        return {"name": "nfo logs", "success": success, **result}


def test_basic_usage() -> dict:
    """Test: python examples/basic-usage/main.py"""
    print("Testing: basic-usage example")
    result = run_command(
        [PYTHON, "examples/basic-usage/main.py"],
        cwd=Path(".")
    )
    success = result["success"] and "add(3, 7) = 10" in result["stdout"]
    return {"name": "basic-usage example", "success": success, **result}


def test_sqlite_sink() -> dict:
    """Test: python examples/sqlite-sink/main.py"""
    print("Testing: sqlite-sink example")
    result = run_command(
        [PYTHON, "examples/sqlite-sink/main.py"],
        cwd=Path(".")
    )
    success = result["success"] and "User: {'id': 42" in result["stdout"]
    return {"name": "sqlite-sink example", "success": success, **result}


def test_csv_sink() -> dict:
    """Test: python examples/csv-sink/main.py"""
    print("Testing: csv-sink example")
    result = run_command(
        [PYTHON, "examples/csv-sink/main.py"],
        cwd=Path(".")
    )
    success = result["success"]
    return {"name": "csv-sink example", "success": success, **result}


def test_markdown_sink() -> dict:
    """Test: python examples/markdown-sink/main.py"""
    print("Testing: markdown-sink example")
    result = run_command(
        [PYTHON, "examples/markdown-sink/main.py"],
        cwd=Path(".")
    )
    success = result["success"]
    return {"name": "markdown-sink example", "success": success, **result}


def test_configure() -> dict:
    """Test: python examples/configure/main.py"""
    print("Testing: configure example")
    result = run_command(
        [PYTHON, "examples/configure/main.py"],
        cwd=Path(".")
    )
    success = result["success"]
    return {"name": "configure example", "success": success, **result}


def test_auto_log() -> dict:
    """Test: python examples/auto-log/main.py"""
    print("Testing: auto-log example")
    result = run_command(
        [PYTHON, "examples/auto-log/main.py"],
        cwd=Path(".")
    )
    success = result["success"]
    return {"name": "auto-log example", "success": success, **result}


def test_http_service() -> dict:
    """Test: Start HTTP service and send log entry"""
    print("Testing: HTTP service")
    import urllib.request
    import json

    # Start server in background
    server_proc = subprocess.Popen(
        [PYTHON, "-m", "nfo", "serve", "--port", "18080"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(2)  # Wait for server to start

    try:
        # Send test log entry - match Pydantic model exactly, only send required fields
        data = json.dumps({
            "cmd": "test",
            "args": ["arg1"],
            "language": "python",
            "env": "test",
            "success": True,
            "duration_ms": 100.0,
            "output": "test output",
        }).encode()

        req = urllib.request.Request(
            "http://localhost:18080/log",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=5) as response:
            response_data = response.read().decode()
            success = response.status == 200 and "stored" in response_data

        # Check health endpoint
        health_req = urllib.request.Request("http://localhost:18080/health")
        with urllib.request.urlopen(health_req, timeout=5) as response:
            health_data = response.read().decode()
            health_ok = response.status == 200 and "ok" in health_data

        return {
            "name": "HTTP service",
            "success": success and health_ok,
            "stdout": f"Log response: {response_data}, Health: {health_data}",
            "stderr": "",
        }
    except Exception as e:
        return {
            "name": "HTTP service",
            "success": False,
            "stdout": "",
            "stderr": str(e),
        }
    finally:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_proc.kill()


def main():
    """Run all tests and print report."""
    print("=" * 60)
    print("nfo Documentation Test Suite")
    print("=" * 60)

    tests = [
        test_nfo_version,
        test_nfo_run_bash,
        test_nfo_run_python,
        test_nfo_logs,
        test_basic_usage,
        test_sqlite_sink,
        test_csv_sink,
        test_markdown_sink,
        test_configure,
        test_auto_log,
        test_http_service,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
            status = "PASS" if result["success"] else "FAIL"
            print(f"  [{status}] {result['name']}")
        except Exception as e:
            results.append({"name": test.__name__, "success": False, "error": str(e)})
            print(f"  [FAIL] {test.__name__}: {e}")

    # Print summary
    print()
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for r in results if r["success"])
    failed = len(results) - passed

    print(f"Total: {len(results)}, Passed: {passed}, Failed: {failed}")
    print()

    if failed > 0:
        print("Failed tests:")
        for r in results:
            if not r["success"]:
                print(f"  - {r['name']}")
                if "stderr" in r and r["stderr"]:
                    print(f"    Error: {r['stderr'][:200]}")

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
