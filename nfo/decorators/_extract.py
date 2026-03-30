"""Metadata extraction helpers for nfo decorators."""

from __future__ import annotations

from typing import Any, Dict, Optional


def _should_extract(extract_meta_flag: bool) -> bool:
    """Determine if metadata extraction should be performed."""
    if extract_meta_flag:
        return True
    from nfo.configure import get_global_auto_extract_meta
    return get_global_auto_extract_meta()


def _get_effective_policy(meta_policy: Any) -> Any:
    """Get the effective metadata policy."""
    if meta_policy is not None:
        return meta_policy
    from nfo.configure import get_global_meta_policy
    result = get_global_meta_policy()
    if result is not None:
        return result
    from nfo.meta import ThresholdPolicy
    return ThresholdPolicy()


def _extract_args_meta(args: tuple, policy: Any) -> list:
    """Extract metadata from positional arguments."""
    from nfo.extractors import extract_meta as _extract
    from nfo.meta import sizeof

    args_meta = []
    for arg in args:
        if policy.should_extract_meta(arg):
            meta = _extract(arg)
            args_meta.append(meta or {"type": type(arg).__name__, "size": sizeof(arg)})
        else:
            args_meta.append(repr(arg)[:256])
    return args_meta


def _extract_kwargs_meta(kwargs: dict, policy: Any) -> dict:
    """Extract metadata from keyword arguments."""
    from nfo.extractors import extract_meta as _extract
    from nfo.meta import sizeof

    kwargs_meta = {}
    for k, v in kwargs.items():
        if policy.should_extract_meta(v):
            meta = _extract(v)
            kwargs_meta[k] = meta or {"type": type(v).__name__, "size": sizeof(v)}
        else:
            kwargs_meta[k] = repr(v)[:256]
    return kwargs_meta


def _extract_return_meta(result: Any, policy: Any) -> Optional[Dict[str, Any]]:
    """Extract metadata from return value if applicable."""
    if result is None or not policy.should_extract_return_meta(result):
        return None

    from nfo.extractors import extract_meta as _extract
    from nfo.meta import sizeof
    meta = _extract(result)
    return meta or {"type": type(result).__name__, "size": sizeof(result)}


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
    if not _should_extract(extract_meta_flag):
        return None

    policy = _get_effective_policy(meta_policy)

    args_meta = _extract_args_meta(args, policy)
    kwargs_meta = _extract_kwargs_meta(kwargs, policy)
    return_meta = _extract_return_meta(result, policy)

    extra: Dict[str, Any] = {
        "args_meta": args_meta,
        "kwargs_meta": kwargs_meta,
        "meta_log": True,
    }
    if return_meta is not None:
        extra["return_meta"] = return_meta
    return extra
