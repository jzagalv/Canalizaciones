# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Dict, List


def calc_inputs_hash(project: object) -> str:
    payload = {
        "canvas": _normalized_canvas(getattr(project, "canvas", {}) or {}),
        "circuits": _normalized_circuits(getattr(project, "circuits", {}) or {}),
        "active_fill_rules_preset_id": str(getattr(project, "active_fill_rules_preset_id", "") or ""),
        "active_materiales_bd_path": str(getattr(project, "active_materiales_bd_path", "") or ""),
        "active_profile": str(getattr(project, "active_profile", "") or ""),
        "libraries": _normalized_libraries(getattr(project, "libraries", []) or []),
        "troncales": getattr(project, "troncales", []) or [],
    }
    data = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _normalized_canvas(canvas: Dict[str, Any]) -> Dict[str, Any]:
    c = deepcopy(canvas or {})
    c.pop("view", None)
    if isinstance(c.get("background"), dict):
        bg = dict(c.get("background") or {})
        bg.pop("image_data", None)
        bg.pop("image_format", None)
        c["background"] = bg
    nodes = list(c.get("nodes") or [])
    edges = list(c.get("edges") or [])
    c["nodes"] = [_normalize_node(n) for n in nodes]
    c["edges"] = [_normalize_edge(e) for e in edges]
    return c


def _normalize_node(node: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": node.get("id"),
        "type": node.get("type", node.get("kind")),
        "name": node.get("name"),
        "x": node.get("x"),
        "y": node.get("y"),
        "library_item_id": node.get("library_item_id"),
    }


def _normalize_edge(edge: Dict[str, Any]) -> Dict[str, Any]:
    props = dict(edge.get("props") or {}) if isinstance(edge.get("props"), dict) else {}
    for key in list(props.keys()):
        if str(key).startswith("fill_"):
            props.pop(key, None)
    return {
        "id": edge.get("id"),
        "from": edge.get("from", edge.get("from_node")),
        "to": edge.get("to", edge.get("to_node")),
        "kind": edge.get("kind"),
        "mode": edge.get("mode"),
        "runs": edge.get("runs") or [],
        "props": props,
    }


def _normalized_circuits(circuits: Dict[str, Any]) -> Dict[str, Any]:
    items = list(circuits.get("items") or [])
    return {"source": circuits.get("source"), "items": items}


def _normalized_libraries(libs: List[Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for lib in libs:
        out.append({
            "path": getattr(lib, "path", None) if not isinstance(lib, dict) else lib.get("path"),
            "enabled": getattr(lib, "enabled", None) if not isinstance(lib, dict) else lib.get("enabled"),
            "priority": getattr(lib, "priority", None) if not isinstance(lib, dict) else lib.get("priority"),
        })
    return out
