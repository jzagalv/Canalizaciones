# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from typing import Dict, Iterable

DEFAULT_DUCT_MAX_FILL_PERCENT = 40.0
DEFAULT_TRAY_MAX_FILL_PERCENT = 50.0
DEFAULT_TRAY_SEPARATOR_FACTOR = 0.5


def calc_duct_fill(duct_material: Dict[str, object], cables: Iterable[Dict[str, object]]) -> float:
    """Return duct fill percent based on cable areas."""
    usable_area = _duct_usable_area_mm2(duct_material)
    if usable_area <= 0:
        return 0.0
    cable_area = _cables_area_mm2(cables)
    return (cable_area / usable_area) * 100.0


def calc_tray_fill(
    tray_material: Dict[str, object],
    cables: Iterable[Dict[str, object]],
    has_separator: bool,
) -> float:
    """Return tray fill percent based on cable areas."""
    usable_area = _tray_usable_area_mm2(tray_material, has_separator)
    if usable_area <= 0:
        return 0.0
    cable_area = _cables_area_mm2(cables)
    return (cable_area / usable_area) * 100.0


def get_material_max_fill_percent(material: Dict[str, object], default_value: float) -> float:
    value = _coerce_float(material.get("max_fill_percent"))
    if value <= 0:
        return float(default_value)
    return value


def _cables_area_mm2(cables: Iterable[Dict[str, object]]) -> float:
    total = 0.0
    for cable in cables:
        area = _coerce_float(cable.get("area_mm2"))
        if area <= 0:
            area = _cable_area_mm2(_coerce_float(cable.get("outer_diameter_mm")))
        if area > 0:
            total += area
    return total


def _cable_area_mm2(outer_diameter_mm: float) -> float:
    if outer_diameter_mm <= 0:
        return 0.0
    r = outer_diameter_mm / 2.0
    return math.pi * r * r


def _duct_usable_area_mm2(duct_material: Dict[str, object]) -> float:
    usable_area = _coerce_float(duct_material.get("usable_area_mm2"))
    if usable_area > 0:
        return usable_area
    inner_d = _coerce_float(duct_material.get("inner_diameter_mm"))
    if inner_d <= 0:
        return 0.0
    r = inner_d / 2.0
    return math.pi * r * r


def _tray_usable_area_mm2(tray_material: Dict[str, object], has_separator: bool) -> float:
    usable_area = _coerce_float(tray_material.get("usable_area_mm2"))
    if usable_area <= 0:
        w = _coerce_float(tray_material.get("inner_width_mm"))
        h = _coerce_float(tray_material.get("inner_height_mm"))
        usable_area = w * h
    if usable_area <= 0:
        return 0.0
    if has_separator:
        usable_area *= DEFAULT_TRAY_SEPARATOR_FACTOR
    return usable_area


def _coerce_float(value: object) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0
