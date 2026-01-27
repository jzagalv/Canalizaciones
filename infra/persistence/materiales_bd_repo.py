# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from domain.materials.material_ids import normalize_material_library


class MaterialesBdError(Exception):
    pass


def _base_doc() -> Dict[str, Any]:
    return {
        "schema_version": "1.0",
        "kind": "material_library",
        "meta": {"name": "Materiales", "created": "", "source": ""},
        "conductors": [],
        "containments": {"ducts": [], "epc": [], "bpc": []},
        "rules": {},
    }

def _sorted_rect_items(items: list) -> list:
    return sorted(
        items,
        key=lambda it: (
            _coerce_float(it.get("inner_width_mm")),
            _coerce_float(it.get("inner_height_mm")),
            str(it.get("id") or ""),
        ),
    )


def _merge_rect_items(existing: list, incoming: list) -> list:
    out = list(existing or [])
    seen_ids = {str(it.get("id") or "").strip().lower() for it in out if it.get("id")}
    seen_names = {str(it.get("name") or "").strip().lower() for it in out if it.get("name")}
    for it in incoming or []:
        it_id = str(it.get("id") or "").strip().lower()
        it_name = str(it.get("name") or "").strip().lower()
        if (it_id and it_id in seen_ids) or (it_name and it_name in seen_names):
            continue
        out.append(dict(it))
        if it_id:
            seen_ids.add(it_id)
        if it_name:
            seen_names.add(it_name)
    return _sorted_rect_items(out)


def _migrate_trays(doc: Dict[str, Any]) -> Dict[str, Any]:
    cont = doc.get("containments") or {}
    trays = list(cont.get("trays") or [])
    if not trays:
        cont.pop("trays", None)
        doc["containments"] = cont
        return doc
    cont["epc"] = _merge_rect_items(cont.get("epc") or [], trays)
    cont["bpc"] = _merge_rect_items(cont.get("bpc") or [], trays)
    cont.pop("trays", None)
    doc["containments"] = cont
    return doc


def load_materiales_bd(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise MaterialesBdError(f"No existe el archivo: {path}")
    try:
        data: Dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise MaterialesBdError(f"JSON inválido en {path}: {e}")

    if str(data.get("schema_version", "")) != "1.0":
        raise MaterialesBdError("schema_version esperado 1.0")
    if str(data.get("kind", "")) != "material_library":
        raise MaterialesBdError("kind esperado material_library")

    # Ensure required structure exists without removing unknown fields
    base = _base_doc()
    data.setdefault("meta", base["meta"])
    data.setdefault("conductors", [])
    data.setdefault("containments", base["containments"])
    data.setdefault("rules", base["rules"])

    cont = data.get("containments") or {}
    cont.setdefault("ducts", [])
    cont.setdefault("epc", [])
    cont.setdefault("bpc", [])
    data["containments"] = cont

    data = _migrate_trays(data)
    normalize_material_library(data)
    return data


def save_materiales_bd(path: str, data: Dict[str, Any]) -> None:
    p = Path(path)
    doc = dict(data or {})
    base = _base_doc()
    doc["schema_version"] = "1.0"
    doc["kind"] = "material_library"
    doc.setdefault("meta", base["meta"])
    doc.setdefault("conductors", [])
    doc.setdefault("containments", base["containments"])
    doc.setdefault("rules", base["rules"])

    doc = _migrate_trays(doc)
    normalize_material_library(doc)
    cont = doc.get("containments") or {}
    cont.setdefault("ducts", [])
    cont.setdefault("epc", [])
    cont.setdefault("bpc", [])
    doc["containments"] = cont

    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def _coerce_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0
