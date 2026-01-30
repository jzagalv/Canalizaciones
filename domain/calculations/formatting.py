# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any


DEFAULT_MAX_FILL_PERCENT = 40.0


def round2(value: Any) -> float:
    try:
        return round(float(value), 2)
    except Exception:
        return 0.0


def fmt2(value: Any) -> str:
    num = round2(value)
    text = f"{num:.2f}".rstrip("0").rstrip(".")
    return text or "0"


def fmt_percent(value: Any) -> str:
    return f"{fmt2(value)} %"


def util_color(fill_percent: Any, max_allowed: Any) -> str:
    try:
        fill = float(fill_percent or 0.0)
    except Exception:
        fill = 0.0
    try:
        max_val = float(max_allowed or 0.0)
    except Exception:
        max_val = 0.0
    if max_val <= 0:
        max_val = DEFAULT_MAX_FILL_PERCENT
    ratio = fill / max_val if max_val > 0 else 0.0
    if ratio <= 0.8:
        return "ok"
    if ratio <= 1.0:
        return "warn"
    return "over"
