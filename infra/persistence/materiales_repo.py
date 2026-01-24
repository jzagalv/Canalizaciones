# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from infra.persistence.materiales_bd_repo import load_materiales_bd


class MaterialesRepo:
    def __init__(self, path: Optional[str] = None):
        self._path = str(path or "")
        self._doc: Optional[Dict[str, Any]] = None
        self._last_mtime: Optional[float] = None

    def set_path(self, path: Optional[str]) -> None:
        self._path = str(path or "")
        self.refresh()

    def refresh(self) -> None:
        self._doc = None
        self._last_mtime = None

    def _load(self) -> Dict[str, Any]:
        if not self._path:
            return {}
        p = Path(self._path)
        if not p.exists():
            return {}
        try:
            mtime = p.stat().st_mtime
        except Exception:
            mtime = None
        if self._doc is None or (mtime is not None and mtime != self._last_mtime):
            try:
                self._doc = load_materiales_bd(self._path)
            except Exception:
                self._doc = {}
            self._last_mtime = mtime
        return self._doc or {}

    def _containments(self) -> Dict[str, List[Dict[str, Any]]]:
        doc = self._load()
        cont = doc.get("containments") or {}
        return {
            "ducts": list(cont.get("ducts") or []),
            "epc": list(cont.get("epc") or []),
            "bpc": list(cont.get("bpc") or []),
        }

    def get_duct_by_nominal(self, nominal_in: str) -> Optional[Dict[str, Any]]:
        target = _normalize_nominal(nominal_in)
        target_in = _parse_nominal_inches(nominal_in)
        target_mm = _parse_nominal_mm(nominal_in)
        for item in self._containments().get("ducts", []):
            nominal = str(item.get("nominal") or "")
            if target and _normalize_nominal(nominal) == target:
                return dict(item)
            item_in = _parse_nominal_inches(nominal)
            if target_in is not None and item_in is not None and abs(target_in - item_in) <= 0.01:
                return dict(item)
            item_mm = _parse_nominal_mm(nominal)
            if target_mm is not None and item_mm is not None and abs(target_mm - item_mm) <= 0.5:
                return dict(item)
        return None

    def get_tray_by_size(self, size: str) -> Optional[Dict[str, Any]]:
        return self._get_rect_by_size("epc", size)

    def get_epc_by_size(self, size: str) -> Optional[Dict[str, Any]]:
        return self._get_rect_by_size("epc", size)

    def get_bpc_by_size(self, size: str) -> Optional[Dict[str, Any]]:
        return self._get_rect_by_size("bpc", size)

    def get_cable_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        doc = self._load()
        code_norm = str(code or "").strip().lower()
        if not code_norm:
            return None
        for item in (doc.get("conductors") or []):
            if str(item.get("id") or "").lower() == code_norm:
                return dict(item)
            if str(item.get("code") or "").lower() == code_norm:
                return dict(item)
            if str(item.get("name") or "").lower() == code_norm:
                return dict(item)
        return None

    def list_duct_nominals(self) -> List[str]:
        items = [str(i.get("nominal") or "").strip() for i in self._containments().get("ducts", [])]
        items = [i for i in items if i]
        return sorted(set(items))

    def list_rect_sizes(self, kind: str) -> List[str]:
        key = _normalize_kind(kind)
        items = self._containments().get(key, [])
        sizes: List[str] = []
        for item in items:
            w = _coerce_float(item.get("inner_width_mm"))
            h = _coerce_float(item.get("inner_height_mm"))
            if w <= 0 or h <= 0:
                continue
            sizes.append(_format_rect_size(w, h))
        return sorted(set(sizes))

    def _get_rect_by_size(self, key: str, size: str) -> Optional[Dict[str, Any]]:
        target = _parse_rect_size_mm(size)
        if not target:
            return None
        t_w, t_h = target
        for item in self._containments().get(key, []):
            w = _coerce_float(item.get("inner_width_mm"))
            h = _coerce_float(item.get("inner_height_mm"))
            if _rect_match(w, h, t_w, t_h):
                return dict(item)
        return None


def _coerce_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _normalize_kind(kind: str) -> str:
    k = str(kind or "").strip().lower()
    if k in ("tray", "trays", "bandeja"):
        return "epc"
    if k in ("epc",):
        return "epc"
    if k in ("bpc",):
        return "bpc"
    return k


def _normalize_nominal(text: str) -> str:
    s = str(text or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _parse_nominal_inches(text: str) -> Optional[float]:
    s = str(text or "").strip().lower()
    if "mm" in s:
        return None
    if '"' in s or "in" in s or "/" in s:
        s = s.replace("in", "").replace("\"", "").strip()
        return _parse_mixed_fraction(s)
    m = re.search(r"\d+(\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except Exception:
        return None


def _parse_nominal_mm(text: str) -> Optional[float]:
    s = str(text or "").strip().lower()
    if "mm" not in s:
        return None
    m = re.search(r"\d+(\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except Exception:
        return None


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


def _rect_match(w: float, h: float, tw: float, th: float) -> bool:
    if w <= 0 or h <= 0:
        return False
    tol = 0.6
    return (
        (abs(w - tw) <= tol and abs(h - th) <= tol)
        or (abs(w - th) <= tol and abs(h - tw) <= tol)
    )


def _format_rect_size(w: float, h: float) -> str:
    def _fmt(n: float) -> str:
        if abs(n - round(n)) < 1e-6:
            return str(int(round(n)))
        return f"{n:.1f}".rstrip("0").rstrip(".")

    return f"{_fmt(w)}x{_fmt(h)}"
