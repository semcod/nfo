"""Metadata extractors for binary and large data types.

Instead of logging ``repr()`` of a 5 MB PNG, extract useful diagnostics:
format, dimensions, size, hash prefix, entropy, etc.
"""

from __future__ import annotations

import hashlib
import math
import struct
from collections import Counter
from typing import Any, Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Magic byte signatures for common formats
# ---------------------------------------------------------------------------

MAGIC_SIGNATURES: List[Tuple[bytes, str]] = [
    (b"\x89PNG", "PNG"),
    (b"\xff\xd8\xff", "JPEG"),
    (b"GIF87a", "GIF87"),
    (b"GIF89a", "GIF89"),
    (b"%PDF", "PDF"),
    (b"PK\x03\x04", "ZIP/DOCX/XLSX"),
    (b"\x1f\x8b", "GZIP"),
    (b"BM", "BMP"),
    (b"RIFF", "RIFF/WAV/AVI"),
    (b"\x00\x00\x00\x1cftyp", "MP4"),
    (b"\x1aE\xdf\xa3", "MKV/WebM"),
    (b"OggS", "OGG"),
    (b"fLaC", "FLAC"),
    (b"\xff\xfb", "MP3"),
    (b"SQLite format 3", "SQLite"),
    (b"\x7fELF", "ELF"),
]


def detect_format(data: bytes) -> Optional[str]:
    """Detect file format from magic bytes."""
    for magic, fmt in MAGIC_SIGNATURES:
        if data[: len(magic)] == magic:
            return fmt
    return None


# ---------------------------------------------------------------------------
# Per-type extractors
# ---------------------------------------------------------------------------


def extract_image_meta(data: bytes) -> Dict[str, Any]:
    """Extract metadata from an image without external dependencies."""
    meta: Dict[str, Any] = {"type": "image", "size_bytes": len(data)}
    fmt = detect_format(data)
    meta["format"] = fmt

    if fmt == "PNG" and len(data) >= 24:
        w = struct.unpack(">I", data[16:20])[0]
        h = struct.unpack(">I", data[20:24])[0]
        meta["width"], meta["height"] = w, h

    elif fmt == "JPEG" and len(data) > 2:
        i = 2
        while i < len(data) - 9:
            if data[i] == 0xFF and data[i + 1] in (0xC0, 0xC2):
                h = struct.unpack(">H", data[i + 5 : i + 7])[0]
                w = struct.unpack(">H", data[i + 7 : i + 9])[0]
                meta["width"], meta["height"] = w, h
                break
            i += 1

    elif fmt == "BMP" and len(data) >= 26:
        w = struct.unpack("<I", data[18:22])[0]
        h = struct.unpack("<I", data[22:26])[0]
        meta["width"], meta["height"] = w, h

    meta["hash_sha256_prefix"] = hashlib.sha256(data).hexdigest()[:16]
    return meta


def extract_binary_meta(data: bytes) -> Dict[str, Any]:
    """General metadata for arbitrary binary data."""
    meta: Dict[str, Any] = {
        "type": "binary",
        "size_bytes": len(data),
        "format": detect_format(data) or "unknown",
        "hash_sha256_prefix": hashlib.sha256(data).hexdigest()[:16],
    }

    if len(data) > 0:
        freq = Counter(data)
        total = len(data)
        entropy = -sum((c / total) * math.log2(c / total) for c in freq.values())
        meta["entropy"] = round(entropy, 2)  # max 8.0
        meta["is_compressed_or_encrypted"] = entropy > 7.5

    return meta


def extract_file_meta(file_obj: Any) -> Dict[str, Any]:
    """Metadata from a file-like object (without reading its contents)."""
    meta: Dict[str, Any] = {"type": "file_handle"}
    if hasattr(file_obj, "name"):
        meta["name"] = str(file_obj.name)
    if hasattr(file_obj, "mode"):
        meta["mode"] = file_obj.mode
    pos = file_obj.tell() if hasattr(file_obj, "tell") else None
    if pos is not None:
        meta["position"] = pos
    if hasattr(file_obj, "seek"):
        try:
            file_obj.seek(0, 2)  # end
            meta["size_bytes"] = file_obj.tell()
            file_obj.seek(pos)  # restore
        except (OSError, IOError):
            pass
    return meta


def extract_numpy_meta(arr: Any) -> Dict[str, Any]:
    """Metadata from a numpy ndarray (duck-typed)."""
    meta: Dict[str, Any] = {
        "type": "ndarray",
        "shape": list(arr.shape),
        "dtype": str(arr.dtype),
        "size_bytes": int(arr.nbytes),
    }
    if arr.size > 0:
        try:
            meta["min"] = float(arr.min())
            meta["max"] = float(arr.max())
            meta["mean"] = float(arr.mean())
        except (TypeError, ValueError):
            pass
    return meta


def extract_dataframe_meta(df: Any) -> Dict[str, Any]:
    """Metadata from a pandas DataFrame (duck-typed)."""
    return {
        "type": "DataFrame",
        "shape": list(df.shape),
        "columns": list(df.columns[:20]),
        "dtypes": {str(k): str(v) for k, v in list(df.dtypes.items())[:20]},
        "memory_bytes": int(df.memory_usage(deep=True).sum()),
        "null_counts": {
            str(k): int(v) for k, v in df.isnull().sum().items() if v > 0
        },
    }


def extract_wav_meta(data: bytes) -> Dict[str, Any]:
    """Extract metadata from WAV file header."""
    meta: Dict[str, Any] = {"type": "audio", "format": "WAV", "size_bytes": len(data)}
    if len(data) >= 44 and data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        channels = struct.unpack("<H", data[22:24])[0]
        sample_rate = struct.unpack("<I", data[24:28])[0]
        bits_per_sample = struct.unpack("<H", data[34:36])[0]
        data_size = struct.unpack("<I", data[40:44])[0]
        meta["channels"] = channels
        meta["sample_rate"] = sample_rate
        meta["bits_per_sample"] = bits_per_sample
        if sample_rate > 0 and channels > 0 and bits_per_sample > 0:
            duration = data_size / (sample_rate * channels * bits_per_sample / 8)
            meta["duration_seconds"] = round(duration, 2)
    return meta


# ---------------------------------------------------------------------------
# Custom extractor registry
# ---------------------------------------------------------------------------

_EXTRACTORS: Dict[Callable[[Any], bool], Callable[[Any], Dict[str, Any]]] = {}


def register_extractor(
    type_check: Callable[[Any], bool],
    extractor: Callable[[Any], Dict[str, Any]],
) -> None:
    """Register a custom metadata extractor.

    Args:
        type_check: Predicate — return True if *extractor* should handle the value.
        extractor: Callable returning a metadata dict for the value.
    """
    _EXTRACTORS[type_check] = extractor


def unregister_all_extractors() -> None:
    """Remove all custom extractors (useful in tests)."""
    _EXTRACTORS.clear()


# ---------------------------------------------------------------------------
# Unified entry point
# ---------------------------------------------------------------------------


def _try_custom_extractors(value: Any) -> Optional[Dict[str, Any]]:
    """Try custom extractors first."""
    for check_fn, extractor_fn in _EXTRACTORS.items():
        try:
            if check_fn(value):
                return extractor_fn(value)
        except Exception:
            continue
    return None


def _extract_bytes_meta(value: Union[bytes, bytearray]) -> Optional[Dict[str, Any]]:
    """Extract metadata from bytes/bytearray."""
    bdata = bytes(value)
    fmt = detect_format(bdata)
    if fmt in ("PNG", "JPEG", "GIF87", "GIF89", "BMP"):
        return extract_image_meta(bdata)
    if fmt == "RIFF/WAV/AVI" and len(bdata) >= 12 and bdata[8:12] == b"WAVE":
        return extract_wav_meta(bdata)
    return extract_binary_meta(bdata)


def _is_file_like(value: Any) -> bool:
    """Check if value is file-like."""
    return hasattr(value, "read") and hasattr(value, "tell")


def _is_numpy_array(value: Any) -> bool:
    """Check if value is numpy ndarray (duck-typed)."""
    return hasattr(value, "dtype") and hasattr(value, "shape")


def _is_pandas_dataframe(value: Any) -> bool:
    """Check if value is pandas DataFrame (duck-typed)."""
    return hasattr(value, "dtypes") and hasattr(value, "columns")


def extract_meta(value: Any) -> Optional[Dict[str, Any]]:
    """Auto-detect value type and extract metadata.

    Checks custom extractors first, then built-in handlers.
    Returns ``None`` if no extractor matches.
    """
    # Custom extractors take priority
    custom_result = _try_custom_extractors(value)
    if custom_result is not None:
        return custom_result

    # Built-in: bytes / bytearray
    if isinstance(value, (bytes, bytearray)):
        return _extract_bytes_meta(value)

    # memoryview
    if isinstance(value, memoryview):
        return extract_binary_meta(bytes(value))

    # file-like
    if _is_file_like(value):
        return extract_file_meta(value)

    # numpy (duck-typed)
    if _is_numpy_array(value):
        return extract_numpy_meta(value)

    # pandas (duck-typed)
    if _is_pandas_dataframe(value):
        try:
            return extract_dataframe_meta(value)
        except Exception:
            return None

    return None
