# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Protocol, Tuple


class MaterialsRepository(Protocol):
    def get_duct_by_nominal(self, nominal_in: str) -> Optional[Dict[str, Any]]:
        ...

    def get_duct_by_id(self, duct_id: str) -> Optional[Dict[str, Any]]:
        ...

    def get_tray_by_size(self, size: str) -> Optional[Dict[str, Any]]:
        ...

    def get_epc_by_size(self, size: str) -> Optional[Dict[str, Any]]:
        ...

    def get_bpc_by_size(self, size: str) -> Optional[Dict[str, Any]]:
        ...

    def get_cable_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        ...

    def list_conductors(self, service: Optional[str] = None) -> List[Dict[str, Any]]:
        ...

    def list_duct_nominals(self) -> List[str]:
        ...

    def list_duct_standards(self) -> List[str]:
        ...

    def list_ducts_by_standard(self, standard: Optional[str]) -> List[Dict[str, Any]]:
        ...

    def list_rect_sizes(self, kind: str) -> List[str]:
        ...


class MaterialService:
    def __init__(self, repo: MaterialsRepository):
        self._repo = repo

    def get_duct_material(self, nominal_in: str) -> Dict[str, Any]:
        item = None
        try:
            item = self._repo.get_duct_by_nominal(nominal_in)
        except Exception:
            item = None
        return dict(item) if item else {}

    def get_duct_material_by_id(self, duct_id: str) -> Dict[str, Any]:
        item = None
        try:
            item = self._repo.get_duct_by_id(duct_id)
        except Exception:
            item = None
        return dict(item) if item else {}

    def get_rect_material(self, kind: str, size: str) -> Dict[str, Any]:
        kind_norm = str(kind or "").strip().lower()
        item = None
        try:
            if kind_norm in ("tray", "trays", "bandeja"):
                item = self._repo.get_epc_by_size(size)
            elif kind_norm == "epc":
                item = self._repo.get_epc_by_size(size)
            elif kind_norm == "bpc":
                item = self._repo.get_bpc_by_size(size)
        except Exception:
            item = None
        return dict(item) if item else {}

    def list_duct_nominals(self) -> List[str]:
        try:
            return list(self._repo.list_duct_nominals() or [])
        except Exception:
            return []

    def list_duct_standards(self) -> List[str]:
        try:
            return list(self._repo.list_duct_standards() or [])
        except Exception:
            return []

    def list_ducts_by_standard(self, standard: Optional[str]) -> List[Dict[str, Any]]:
        try:
            return list(self._repo.list_ducts_by_standard(standard) or [])
        except Exception:
            return []

    def list_conductors(self, service: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            return list(self._repo.list_conductors(service) or [])
        except Exception:
            return []

    def list_rect_sizes(self, kind: str) -> List[str]:
        try:
            return list(self._repo.list_rect_sizes(kind) or [])
        except Exception:
            return []

    def list_duct_sizes(self) -> List[str]:
        return self.list_duct_nominals()

    def list_epc_sizes(self) -> List[str]:
        return self.list_rect_sizes("epc")

    def list_bpc_sizes(self) -> List[str]:
        return self.list_rect_sizes("bpc")

    def list_sizes_by_type(self, conduit_type: str) -> List[str]:
        kind = str(conduit_type or "").strip().lower()
        if kind == "ducto":
            return self.list_duct_sizes()
        if kind == "epc":
            return self.list_epc_sizes()
        if kind == "bpc":
            return self.list_bpc_sizes()
        return []

    def get_duct_dimensions(self, nominal_in: str) -> Dict[str, float]:
        item = None
        try:
            item = self._repo.get_duct_by_nominal(nominal_in)
        except Exception:
            item = None
        inner = _coerce_mm(item.get("inner_diameter_mm") if item else None)
        outer = _coerce_mm(item.get("outer_diameter_mm") if item else None)
        if inner <= 0:
            inner = _fallback_duct_inner_mm(nominal_in)
        if outer <= 0:
            outer = _estimate_duct_outer_mm(inner)
        if outer < inner + 1.0:
            outer = inner + 1.0
        return {
            "inner_diameter_mm": inner,
            "outer_diameter_mm": outer,
            "found": bool(item),
        }

    def get_duct_dimensions_by_id(self, duct_id: str) -> Dict[str, float]:
        item = None
        try:
            item = self._repo.get_duct_by_id(duct_id)
        except Exception:
            item = None
        inner = _coerce_mm(item.get("inner_diameter_mm") if item else None)
        outer = _coerce_mm(item.get("outer_diameter_mm") if item else None)
        if inner <= 0 and item:
            inner = _fallback_duct_inner_mm(item.get("nominal") or "")
        if inner <= 0:
            inner = 50.0
        if outer <= 0:
            outer = _estimate_duct_outer_mm(inner)
        if outer < inner + 1.0:
            outer = inner + 1.0
        return {
            "inner_diameter_mm": inner,
            "outer_diameter_mm": outer,
            "found": bool(item),
        }
    def get_rect_dimensions(self, kind: str, size: str) -> Dict[str, float]:
        kind_norm = str(kind or "").strip().lower()
        item = None
        try:
            if kind_norm in ("tray", "trays", "bandeja"):
                item = self._repo.get_epc_by_size(size)
            elif kind_norm == "epc":
                item = self._repo.get_epc_by_size(size)
            elif kind_norm == "bpc":
                item = self._repo.get_bpc_by_size(size)
        except Exception:
            item = None

        w = _coerce_mm(item.get("inner_width_mm") if item else None)
        h = _coerce_mm(item.get("inner_height_mm") if item else None)
        if w <= 0 or h <= 0:
            w, h = _fallback_rect_mm(size)
        return {
            "inner_width_mm": w,
            "inner_height_mm": h,
            "found": bool(item),
        }

    def get_cable_outer_diameter(self, code: str) -> float:
        item = None
        try:
            item = self._repo.get_cable_by_code(code)
        except Exception:
            item = None
        return max(0.0, _coerce_mm(item.get("outer_diameter_mm") if item else None))


def _coerce_mm(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _fallback_duct_inner_mm(nominal: str) -> float:
    nominal_mm = _parse_nominal_mm(nominal)
    if nominal_mm > 0:
        return nominal_mm
    return 50.0


def _estimate_duct_outer_mm(inner_mm: float) -> float:
    if inner_mm <= 0:
        return 60.0
    wall = max(1.5, inner_mm * 0.05)
    return inner_mm + (2.0 * wall)


def _fallback_rect_mm(text: str) -> Tuple[float, float]:
    parsed = _parse_rect_size_mm(text)
    if parsed:
        return parsed
    return 160.0, 80.0


def _parse_rect_size_mm(text: str) -> Optional[Tuple[float, float]]:
    s = str(text or "").strip().lower()
    if not s:
        return None
    unit = None
    if "cm" in s:
        unit = "cm"
    elif "mm" in s:
        unit = "mm"
    elif '"' in s or "in" in s:
        unit = "in"
    nums = re.findall(r"\d+(?:[.,]\d+)?", s)
    if len(nums) < 2:
        return None
    try:
        w = float(nums[0].replace(",", "."))
        h = float(nums[1].replace(",", "."))
    except Exception:
        return None
    if unit == "cm":
        w *= 10.0
        h *= 10.0
    elif unit == "in":
        w *= 25.4
        h *= 25.4
    return w, h


def _parse_nominal_mm(text: str) -> float:
    s = str(text or "").strip().lower()
    if "mm" in s:
        m = re.search(r"\d+(?:[.,]\d+)?", s)
        if not m:
            return 0.0
        try:
            return float(m.group(0).replace(",", "."))
        except Exception:
            return 0.0
    if '"' in s or "in" in s or "/" in s:
        inches = _parse_mixed_fraction(s.replace("in", "").replace("\"", "").strip())
        return 0.0 if inches is None else inches * 25.4
    m = re.search(r"\d+(?:[.,]\d+)?", s)
    if not m:
        return 0.0
    try:
        return float(m.group(0).replace(",", "."))
    except Exception:
        return 0.0


def _parse_mixed_fraction(text: str) -> Optional[float]:
    if not text:
        return None
    text = text.replace("-", " ")
    parts = [p for p in text.split() if p]
    if not parts:
        return None
    try:
        if len(parts) == 1:
            return _parse_fraction(parts[0])
        whole = float(parts[0])
        frac = _parse_fraction(parts[1])
        if frac is None:
            return whole
        return whole + frac
    except Exception:
        return None


def _parse_fraction(text: str) -> Optional[float]:
    if "/" in text:
        num, den = text.split("/", 1)
        try:
            return float(num) / float(den)
        except Exception:
            return None
    try:
        return float(text)
    except Exception:
        return None
