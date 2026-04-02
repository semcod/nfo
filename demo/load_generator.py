#!/usr/bin/env python3
"""
Load generator for nfo demo — sends continuous requests to populate metrics.

Usage:
    python load_generator.py [--url http://localhost:8000] [--interval 1.0]
"""

import argparse
import random
import time
from typing import Any
from urllib import request, error


ENDPOINTS = [
    ("/demo/success", 5),   # weight 5 — most common
    ("/demo/error", 2),     # weight 2
    ("/demo/slow", 1),      # weight 1
    ("/demo/batch", 1),     # weight 1
]


def weighted_choice(endpoints: list[tuple[str, int]]) -> str:
    total = sum(w for _, w in endpoints)
    r = random.uniform(0, total)
    cumulative = 0
    for path, weight in endpoints:
        cumulative += weight
        if r <= cumulative:
            return path
    return endpoints[0][0]


def main() -> None:
    parser = argparse.ArgumentParser(description="nfo demo load generator")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL")
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between requests")
    parser.add_argument("--count", type=int, default=0, help="Number of requests (0=infinite)")
    args = parser.parse_args()

    print(f"🔄 Sending requests to {args.url} every {args.interval}s...")
    i = 0
    while True:
        path = weighted_choice(ENDPOINTS)
        url = f"{args.url}{path}"
        try:
            req = request.urlopen(url, timeout=10)
            status = req.getcode()
            print(f"  [{i+1}] {path} → {status}")
        except error.URLError as e:
            print(f"  [{i+1}] {path} → ERROR: {e}")

        i += 1
        if args.count and i >= args.count:
            break
        time.sleep(args.interval + random.uniform(-0.3, 0.3))

    print(f"✅ Done — sent {i} requests")


if __name__ == "__main__":
    main()
