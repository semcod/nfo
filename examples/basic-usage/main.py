#!/usr/bin/env python3
"""Basic nfo usage — automatic function logging with decorators."""

from nfo import log_call, catch

# --- Simple usage with default logger (prints to stderr) ---

@log_call
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


@log_call(level="INFO")
def greet(name: str) -> str:
    return f"Hello, {name}!"


@catch
def risky_divide(a: float, b: float) -> float:
    """Divides a by b. Returns None on error instead of raising."""
    return a / b


if __name__ == "__main__":
    print("=== @log_call ===")
    result = add(3, 7)
    print(f"add(3, 7) = {result}\n")

    greeting = greet("nfo")
    print(f"greet('nfo') = {greeting}\n")

    print("=== @catch (suppresses exceptions) ===")
    safe = risky_divide(10, 0)
    print(f"risky_divide(10, 0) = {safe}  (no crash!)\n")

    ok = risky_divide(10, 3)
    print(f"risky_divide(10, 3) = {ok}")
