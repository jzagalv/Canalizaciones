# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


class MaterialesBdError(Exception):
    pass


def _base_doc() -> Dict[str, Any]:
    return {
        "schema_version": "1.0",
        "kind": "material_library",
        "meta": {"name": "Materiales", "created": "", "source": ""},
        "conductors": [],
        "containments": {"ducts": [], "trays": [], "epc": [], "bpc": []},
        "rules": {},
    }


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
    cont.setdefault("trays", [])
    cont.setdefault("epc", [])
    cont.setdefault("bpc", [])
    data["containments"] = cont

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

    cont = doc.get("containments") or {}
    cont.setdefault("ducts", [])
    cont.setdefault("trays", [])
    cont.setdefault("epc", [])
    cont.setdefault("bpc", [])
    doc["containments"] = cont

    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
