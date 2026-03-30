"""Terminal sink with configurable output formats.

Formats:
- "ascii"    — classic single-line (like current stderr)
- "color"    — ANSI colored (like loguru)
- "markdown" — Markdown rendered via rich (fallback to plain)
- "toon"     — compact machine+human readable
- "table"    — tabular via rich.table (fallback to ascii)
"""

from __future__ import annotations

import sys
import threading
from typing import Optional, TextIO

from nfo.models import LogEntry
from nfo.sinks import Sink


class TerminalSink(Sink):
    """Sink that displays log entries in the terminal with configurable format."""

    LEVEL_COLORS = {
        "DEBUG": "\033[36m",     # cyan
        "INFO": "\033[32m",      # green
        "WARNING": "\033[33m",   # yellow
        "ERROR": "\033[31m",     # red
        "CRITICAL": "\033[41m",  # red bg
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    def __init__(
        self,
        format: str = "color",
        stream: Optional[TextIO] = None,
        show_args: bool = True,
        show_return: bool = True,
        show_duration: bool = True,
        show_traceback: bool = True,
        max_width: int = 120,
        delegate: Optional[Sink] = None,
    ):
        self._format = format
        self._stream = stream or sys.stderr
        self._show_args = show_args
        self._show_return = show_return
        self._show_duration = show_duration
        self._show_traceback = show_traceback
        self._max_width = max_width
        self._delegate = delegate
        self._lock = threading.Lock()

    @property
    def format(self) -> str:
        return self._format

    def write(self, entry: LogEntry) -> None:
        with self._lock:
            formatter = {
                "ascii": self._write_ascii,
                "color": self._write_color,
                "markdown": self._write_markdown,
                "toon": self._write_toon,
                "table": self._write_table,
            }.get(self._format, self._write_ascii)
            formatter(entry)

            if self._delegate:
                self._delegate.write(entry)

    def _write_ascii(self, entry: LogEntry) -> None:
        """Classic single-line format."""
        ts = entry.timestamp.strftime("%H:%M:%S")
        line = f"{ts} | {entry.level:5} | {entry.function_name}()"
        if self._show_args and entry.args:
            line += f" | args={entry.args_repr()}"
        if entry.exception:
            line += f" | EXCEPTION {entry.exception_type}: {entry.exception}"
        elif self._show_return and entry.return_value is not None:
            line += f" | -> {entry.return_value_repr()}"
        if self._show_duration and entry.duration_ms is not None:
            line += f" | [{entry.duration_ms:.1f}ms]"
        self._stream.write(line + "\n")

    def _write_color(self, entry: LogEntry) -> None:
        """ANSI colored format — replaces typical CLI logs."""
        c = self.LEVEL_COLORS.get(entry.level, "")
        ts = f"{self.DIM}{entry.timestamp.strftime('%H:%M:%S')}{self.RESET}"
        level = f"{c}{self.BOLD}{entry.level:5}{self.RESET}"
        func = f"{self.BOLD}{entry.function_name}{self.RESET}"

        parts = [ts, level, f"{func}()"]

        if self._show_args and entry.args:
            args_str = entry.args_repr()[:80]
            parts.append(f"{self.DIM}args={args_str}{self.RESET}")

        if entry.exception:
            parts.append(
                f"{self.LEVEL_COLORS['ERROR']}"
                f"\u2717 {entry.exception_type}: {entry.exception}"
                f"{self.RESET}"
            )
        elif self._show_return and entry.return_value is not None:
            ret = entry.return_value_repr()[:60]
            parts.append(f"\u2192 {ret}")

        if self._show_duration and entry.duration_ms is not None:
            ms = entry.duration_ms
            if ms > 1000:
                dur = f"{self.LEVEL_COLORS['WARNING']}{ms / 1000:.1f}s{self.RESET}"
            elif ms > 100:
                dur = f"{self.LEVEL_COLORS['WARNING']}{ms:.0f}ms{self.RESET}"
            else:
                dur = f"{self.DIM}{ms:.1f}ms{self.RESET}"
            parts.append(dur)

        self._stream.write(" \u2502 ".join(parts) + "\n")

        if self._show_traceback and entry.traceback:
            for tb_line in entry.traceback.strip().split("\n")[-4:]:
                self._stream.write(f"  {self.DIM}{tb_line}{self.RESET}\n")

    def _write_markdown(self, entry: LogEntry) -> None:
        """Markdown format — rendered via rich or written as plain text."""
        status = "\u274c ERROR" if entry.exception else "\u2705 OK"
        lines = [
            f"### `{entry.function_name}()` \u2014 {status}",
            "",
        ]

        if self._show_args and entry.args:
            lines.append(f"- **args**: `{entry.args_repr()[:100]}`")
        if entry.kwargs:
            lines.append(f"- **kwargs**: `{entry.kwargs_repr()[:100]}`")

        if entry.exception:
            lines.append(f"- **exception**: `{entry.exception_type}: {entry.exception}`")
        elif self._show_return and entry.return_value is not None:
            lines.append(f"- **return**: `{entry.return_value_repr()[:100]}`")

        if self._show_duration and entry.duration_ms is not None:
            lines.append(f"- **duration**: `{entry.duration_ms:.1f}ms`")

        if entry.extra.get("args_meta"):
            lines.append(f"- **meta**: `{entry.extra['args_meta']}`")

        lines.append("")

        text = "\n".join(lines)

        try:
            from rich.console import Console
            from rich.markdown import Markdown

            console = Console(file=self._stream, width=self._max_width)
            console.print(Markdown(text))
        except ImportError:
            self._stream.write(text)

    def _format_args_str(self, entry: LogEntry) -> str:
        """Format function arguments for toon output."""
        args_parts = []
        if entry.args and self._show_args:
            for a in entry.args:
                args_parts.append(repr(a)[:30])
        if entry.kwargs and self._show_args:
            for k, v in entry.kwargs.items():
                args_parts.append(f"{k}={repr(v)[:20]}")
        return ",".join(args_parts) if args_parts else ""

    def _format_result(self, entry: LogEntry) -> str:
        """Format function result for toon output."""
        if entry.exception:
            return f"!{entry.exception_type}"
        if self._show_return and entry.return_value is not None:
            return f"->{repr(entry.return_value)[:40]}"
        return ""

    def _format_meta_str(self, entry: LogEntry) -> str:
        """Format binary metadata for toon output."""
        if not (entry.extra.get("meta_log") and entry.extra.get("args_meta")):
            return ""

        meta_parts = []
        for m in entry.extra["args_meta"]:
            if isinstance(m, dict):
                for _k, v in m.items():
                    if isinstance(v, dict):
                        fmt = v.get("format", "")
                        size = v.get("size_bytes", 0)
                        w = v.get("width", "")
                        h = v.get("height", "")
                        dims = f",{w}x{h}" if w and h else ""
                        sz = (
                            f"{size / 1048576:.1f}MB"
                            if size > 1048576
                            else f"{size / 1024:.0f}KB"
                        )
                        meta_parts.append(f"{fmt}{dims},{sz}")
        if meta_parts:
            return f" meta:{{{';'.join(meta_parts)}}}"
        return ""

    def _format_duration(self, entry: LogEntry) -> str:
        """Format duration string for toon output."""
        if not self._show_duration or entry.duration_ms is None:
            return ""
        ms = entry.duration_ms
        return f" [{ms / 1000:.1f}s]" if ms > 1000 else f" [{ms:.1f}ms]"

    def _write_toon(self, entry: LogEntry) -> None:
        """Compact TOON format — minimal, machine+human readable.

        Example:
            09:30:23 DEBUG add(3,7)->10 [0.0ms]
            09:30:23 ERROR risky(0) !ZeroDivisionError [0.0ms]
        """
        ts = entry.timestamp.strftime("%H:%M:%S")
        func = entry.function_name

        args_str = self._format_args_str(entry)
        result = self._format_result(entry)
        meta_str = self._format_meta_str(entry)
        dur = self._format_duration(entry)

        line = f"{ts} {entry.level:5} {func}({args_str}){result}{meta_str}{dur}"
        self._stream.write(line + "\n")

    def _write_table(self, entry: LogEntry) -> None:
        """Tabular format via rich.table (fallback to ascii)."""
        try:
            from rich.console import Console
            from rich.table import Table

            table = Table(show_header=False, box=None, padding=(0, 1))
            table.add_column(width=8)
            table.add_column(width=7)
            table.add_column()
            table.add_column()

            ts = entry.timestamp.strftime("%H:%M:%S")
            level_style = {
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
            }.get(entry.level, "white")

            result = ""
            if entry.exception:
                result = f"[red]\u2717 {entry.exception_type}[/red]"
            elif entry.return_value is not None:
                result = f"\u2192 {entry.return_value_repr()[:50]}"

            dur = (
                f"[dim]{entry.duration_ms:.1f}ms[/dim]"
                if entry.duration_ms
                else ""
            )

            table.add_row(
                f"[dim]{ts}[/dim]",
                f"[{level_style}]{entry.level}[/{level_style}]",
                f"[bold]{entry.function_name}()[/bold] {result}",
                dur,
            )

            Console(file=self._stream, width=self._max_width).print(table)
        except ImportError:
            self._write_ascii(entry)

    def close(self) -> None:
        if self._delegate:
            self._delegate.close()
