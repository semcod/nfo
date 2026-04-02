#!/usr/bin/env python3
"""nfo example — logging to CSV file."""

from pathlib import Path

from nfo import Logger, log_call, CSVSink
from nfo.decorators import set_default_logger

CSV_PATH = Path(__file__).parent / "demo_logs.csv"

MULTIPLIER_SECOND = 14


def setup_logger() -> Logger:
    sink = CSVSink(file_path=CSV_PATH)
    logger = Logger(name="csv-demo", sinks=[sink], propagate_stdlib=True)
    set_default_logger(logger)
    return logger


@log_call
def multiply(a: int, b: int) -> int:
    return a * b


@log_call(level="INFO")
def process_items(items: list) -> int:
    """Process items and return count."""
    return len(items)


if __name__ == "__main__":
    logger = setup_logger()

    multiply(6, 7)
    multiply(3, MULTIPLIER_SECOND)
    process_items(["apple", "banana", "cherry"])

    logger.close()

    print(f"Logs written to: {CSV_PATH}")
    print()
    print(CSV_PATH.read_text())

    # Cleanup
    CSV_PATH.unlink(missing_ok=True)
