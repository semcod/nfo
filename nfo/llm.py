"""
LLM-powered log analysis via the public SubLLM policy boundary.

Provides:
- LLMSink: analyzes ERROR/EXCEPTION logs through LLM and appends root-cause
  suggestions directly to the log entry.
- PromptInjectionDetector: scans log args for prompt injection patterns.

Requires: pip install nfo[llm]  (installs subactor-subllm)
"""

from __future__ import annotations

import os
import re
import threading
from collections.abc import Callable

from nfo.models import LogEntry
from nfo.sinks import Sink

# ---------------------------------------------------------------------------
# Prompt injection detection
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(previous|above|all)\s+(instructions|prompts|rules)", re.IGNORECASE),
    re.compile(r"ignore\s+all\s+previous\s+(instructions|prompts|rules)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(a|an|the)\s+", re.IGNORECASE),
    re.compile(r"system\s*:\s*", re.IGNORECASE),
    re.compile(r"<\|?(system|im_start|endoftext)\|?>", re.IGNORECASE),
    re.compile(r"(?:do\s+not|don'?t)\s+follow\s+(your|the)\s+(rules|instructions)", re.IGNORECASE),
    re.compile(r"reveal\s+(your|the)\s+(system|initial)\s+(prompt|instructions)", re.IGNORECASE),
    re.compile(r"act\s+as\s+(if|though)\s+you", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"DAN\s+mode", re.IGNORECASE),
]


def detect_prompt_injection(text: str) -> str | None:
    """
    Scan text for common prompt injection patterns.

    Returns the matched pattern description if detected, None otherwise.
    """
    if not text:
        return None
    for pattern in _INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            return f"PROMPT_INJECTION_DETECTED: '{match.group()}' in input"
    return None


def scan_entry_for_injection(entry: LogEntry) -> str | None:
    """Scan a LogEntry's args/kwargs for prompt injection attempts."""
    texts_to_scan: list[str] = []

    for arg in (entry.args or ()):
        if isinstance(arg, str):
            texts_to_scan.append(arg)

    for val in (entry.kwargs or {}).values():
        if isinstance(val, str):
            texts_to_scan.append(val)

    extra_msg = (entry.extra or {}).get("message")
    if isinstance(extra_msg, str):
        texts_to_scan.append(extra_msg)

    for text in texts_to_scan:
        result = detect_prompt_injection(text)
        if result:
            return result
    return None


# ---------------------------------------------------------------------------
# LLM Sink — analyzes error logs via SubLLM
# ---------------------------------------------------------------------------

_DEFAULT_SYSTEM_PROMPT = (
    "You are a log analysis assistant. Given a log entry with an exception, "
    "provide a concise root-cause analysis and a suggested fix. "
    "Be specific and actionable. Max 2-3 sentences."
)


class LLMSink(Sink):
    """
    Sink that sends ERROR-level log entries to an LLM for root-cause analysis.

    The LLM response is stored in entry.llm_analysis and also forwarded
    to an optional delegate sink (e.g. SQLiteSink) for persistence.

    Uses public SubLLM routing by default. Provider and model selection are
    centrally governed; direct Z.AI GLM 5.3 is the preferred route.

    Args:
        model: Legacy LiteLLM model string. Ignored by the default SubLLM path.
        delegate: Optional sink to forward the enriched entry to.
        system_prompt: Custom system prompt for analysis.
        analyze_levels: Log levels to analyze (default: ERROR only).
        on_analysis: Callback receiving (entry, analysis_text).
        async_mode: If True, run LLM calls in background threads.
        detect_injection: If True, scan entries for prompt injection.
    """

    def __init__(
        self,
        model: str = "glm-5.3",
        *,
        delegate: Sink | None = None,
        system_prompt: str = _DEFAULT_SYSTEM_PROMPT,
        analyze_levels: list[str] | None = None,
        on_analysis: Callable[[LogEntry, str], None] | None = None,
        async_mode: bool = True,
        detect_injection: bool = True,
    ) -> None:
        self.model = model
        self.delegate = delegate
        self.system_prompt = system_prompt
        self.analyze_levels = [l.upper() for l in (analyze_levels or ["ERROR"])]
        self.on_analysis = on_analysis
        self.async_mode = async_mode
        self.detect_injection = detect_injection
        self._lock = threading.Lock()

    def _build_user_prompt(self, entry: LogEntry) -> str:
        parts = [
            f"Function: {entry.function_name}",
            f"Module: {entry.module}",
            f"Args: {entry.args_repr()}",
            f"Kwargs: {entry.kwargs_repr()}",
        ]
        if entry.exception:
            parts.append(f"Exception: {entry.exception_type}: {entry.exception}")
        if entry.traceback:
            tb_lines = entry.traceback.strip().split("\n")
            parts.append("Traceback (last 10 lines):\n" + "\n".join(tb_lines[-10:]))
        if entry.environment:
            parts.append(f"Environment: {entry.environment}")
        if entry.version:
            parts.append(f"Version: {entry.version}")
        return "\n".join(parts)

    def _analyze(self, entry: LogEntry) -> str:
        """Call the centrally governed SubLLM route and return analysis text."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self._build_user_prompt(entry)},
        ]

        if os.environ.get("NFO_USE_LEGACY_LITELLM", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            return self._analyze_legacy(messages)

        try:
            from subllm import complete

            response = complete(
                "semcod-nfo",
                "analyze",
                messages,
                timeout_seconds=30,
            )
            return response.content.strip()
        except ImportError:
            return "[nfo] subactor-subllm not installed. Run: pip install nfo[llm]"
        except Exception as e:
            return f"[nfo] SubLLM analysis failed: {type(e).__name__}: {e}"

    def _analyze_legacy(self, messages: list[dict[str, str]]) -> str:
        """Use LiteLLM only when the operator explicitly enables legacy mode."""
        try:
            from litellm import completion

            response = completion(
                model=self.model,
                messages=messages,
                max_tokens=200,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except ImportError:
            return "[nfo] litellm not installed. Run: pip install nfo[llm-legacy]"
        except Exception as e:
            return f"[nfo] legacy LLM analysis failed: {type(e).__name__}: {e}"

    def _process(self, entry: LogEntry) -> None:
        """Analyze entry and enrich it."""
        # Prompt injection detection
        if self.detect_injection:
            injection = scan_entry_for_injection(entry)
            if injection:
                entry.extra["prompt_injection"] = injection
                entry.llm_analysis = (entry.llm_analysis or "") + f" | {injection}"

        # LLM analysis for error-level entries
        if entry.level.upper() in self.analyze_levels and entry.exception:
            analysis = self._analyze(entry)
            entry.llm_analysis = analysis
            if self.on_analysis:
                try:
                    self.on_analysis(entry, analysis)
                except Exception:
                    pass

        # Forward to delegate
        if self.delegate:
            self.delegate.write(entry)

    def write(self, entry: LogEntry) -> None:
        if self.async_mode:
            thread = threading.Thread(target=self._process, args=(entry,), daemon=True)
            thread.start()
        else:
            self._process(entry)

    def close(self) -> None:
        if self.delegate:
            self.delegate.close()
