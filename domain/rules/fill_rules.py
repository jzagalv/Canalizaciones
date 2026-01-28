# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple


def get_preset_rules(presets_doc: Dict[str, Any], preset_id: str) -> Dict[str, Any]:
    presets = list(presets_doc.get("presets") or [])
    wanted = str(preset_id or "")
    if wanted:
        for p in presets:
            if str(p.get("id") or "") == wanted:
                return dict(p.get("rules") or {})
    default_id = str(presets_doc.get("active_default_preset_id") or "")
    for p in presets:
        if str(p.get("id") or "") == default_id:
            return dict(p.get("rules") or {})
    if presets:
        return dict(presets[0].get("rules") or {})
    return {}


def get_fill_limit_pct(kind: str, conductor_count: int, rules: Dict[str, Any]) -> float:
    kind_norm = str(kind or "").strip().lower()
    if kind_norm in ("duct", "ducto"):
        duct = (rules or {}).get("duct") or {}
        ranges = list(duct.get("fill_by_conductors") or [])
        for r in ranges:
            try:
                min_v = int(r.get("min") or 0)
                max_v = int(r.get("max") or 0)
                pct = float(r.get("fill_max_pct") or 0)
            except Exception:
                continue
            if min_v <= conductor_count <= max_v and pct > 0:
                return pct
        if ranges:
            try:
                return float(ranges[-1].get("fill_max_pct") or 0.0) or 0.0
            except Exception:
                return 0.0
        return 0.0

    block = (rules or {}).get(kind_norm) or {}
    try:
        return float(block.get("fill_max_pct") or 0.0)
    except Exception:
        return 0.0


def get_layers_rule(kind: str, rules: Dict[str, Any]) -> Tuple[bool, int]:
    kind_norm = str(kind or "").strip().lower()
    block = (rules or {}).get(kind_norm) or {}
    enabled = bool(block.get("layers_enabled"))
    try:
        max_layers = int(block.get("max_layers") or 1)
    except Exception:
        max_layers = 1
    max_layers = max(1, max_layers)
    return enabled, max_layers


def count_conductors_for_edge(edge_id: str, edge_to_circuits: Dict[str, List[str]], circuits_data: List[Dict[str, Any]]) -> int:
    cid_list = list(edge_to_circuits.get(str(edge_id), []) or [])
    if not cid_list:
        return 0
    by_id = {str(c.get("id") or ""): c for c in circuits_data if c.get("id")}
    total = 0
    for cid in cid_list:
        c = by_id.get(str(cid))
        if not c:
            continue
        try:
            qty = int(c.get("qty", 1) or 1)
        except Exception:
            qty = 1
        total += max(1, qty)
    return total


def required_layers(width_used: float, width_clear: float) -> int:
    if width_clear <= 0:
        return 1
    if width_used <= 0:
        return 1
    return int(math.ceil(width_used / width_clear))
