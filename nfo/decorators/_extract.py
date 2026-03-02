"""Metadata extraction helpers for nfo decorators."""

from __future__ import annotations

from typing import Any, Dict, Optional


def _maybe_extract(
    args: tuple,
    kwargs: dict,
    result: Any,
    extract_meta_flag: bool,
    meta_policy: Any,
) -> Optional[Dict[str, Any]]:
    """Build ``extra`` dict with metadata when *extract_meta_flag* is True.

    When *extract_meta_flag* is ``False``, falls back to the global
    ``auto_extract_meta`` setting from :func:`~nfo.configure.configure`.

    Returns ``None`` when metadata extraction is disabled.
    """
    effective = extract_meta_flag
    if not effective:
        from nfo.configure import get_global_auto_extract_meta
        effective = get_global_auto_extract_meta()
    if not effective:
        return None
    from nfo.extractors import extract_meta as _extract
    from nfo.meta import ThresholdPolicy, sizeof

    if meta_policy is None:
        from nfo.configure import get_global_meta_policy
        meta_policy = get_global_meta_policy()
    policy = meta_policy if meta_policy is not None else ThresholdPolicy()
    args_meta = []
    for arg in args:
        if policy.should_extract_meta(arg):
            meta = _extract(arg)
            args_meta.append(meta or {"type": type(arg).__name__, "size": sizeof(arg)})
        else:
            args_meta.append(repr(arg)[:256])
    kwargs_meta = {}
    for k, v in kwargs.items():
        if policy.should_extract_meta(v):
            meta = _extract(v)
            kwargs_meta[k] = meta or {"type": type(v).__name__, "size": sizeof(v)}
        else:
            kwargs_meta[k] = repr(v)[:256]
    return_meta = None
    if result is not None and policy.should_extract_return_meta(result):
        meta = _extract(result)
        return_meta = meta or {"type": type(result).__name__, "size": sizeof(result)}
    extra: Dict[str, Any] = {
        "args_meta": args_meta,
        "kwargs_meta": kwargs_meta,
        "meta_log": True,
    }
    if return_meta is not None:
        extra["return_meta"] = return_meta
    return extra
