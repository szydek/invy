# util.py
from __future__ import annotations

import re
import unicodedata
from typing import Any, Optional


def safe_filename(text: str, max_length: int = 120) -> str:
    """Convert text into a filesystem-safe filename."""
    if not text:
        return "file"
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[\\/\\\\]+", "_", text)
    text = re.sub(r"[^a-zA-Z0-9._-]+", "_", text)
    return text.strip("_")[:max_length]


def _clean(v: Any) -> str:
    return (v or "").strip()


def _int(v: Any) -> Optional[int]:
    s = _clean(v)
    if not s:
        return None
    return int(s)


def _float(v: Any) -> Optional[float]:
    s = _clean(v).replace("$", "").replace(",", "")
    if not s:
        return None
    return float(s)
