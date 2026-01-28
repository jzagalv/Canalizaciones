# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict


class LibWriteError(Exception):
    pass


def read_json(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise LibWriteError(f"No existe la libreria: {path}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        raise LibWriteError(f"JSON invalido en {path}: {exc}")


def write_json_atomic(path: str, doc: Dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(str(tmp), str(p))
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


def normalize_equipment_id(name: str) -> str:
    raw = str(name or "").strip().lower()
    raw = raw.replace("-", "_").replace(" ", "_")
    raw = re.sub(r"[^a-z0-9_]+", "", raw)
    raw = re.sub(r"_+", "_", raw).strip("_")
    return raw or "user_equipo"


def _ensure_equipment_library_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(doc, dict):
        raise LibWriteError("Documento de libreria invalido")
    if doc.get("schema_version") != "1.0":
        raise LibWriteError("schema_version esperado 1.0")
    if doc.get("kind") != "equipment_library":
        raise LibWriteError("kind esperado equipment_library")
    doc.setdefault("items", [])
    if not isinstance(doc.get("items"), list):
        raise LibWriteError("items debe ser lista")
    return doc


def upsert_equipment_item(lib_path: str, item: Dict[str, Any]) -> Dict[str, Any]:
    p = Path(lib_path)
    if p.exists():
        doc = read_json(str(p))
    else:
        doc = {
            "schema_version": "1.0",
            "kind": "equipment_library",
            "meta": {"name": "Equipos Usuario"},
            "items": [],
        }
    doc = _ensure_equipment_library_doc(doc)

    item_id = str(item.get("id") or "").strip()
    if not item_id:
        raise LibWriteError("item.id es obligatorio")
    payload = {
        "id": item_id,
        "name": str(item.get("name") or item_id),
        "category": str(item.get("category") or "Usuario"),
        "equipment_type": item.get("equipment_type"),
        "template_ref": item.get("template_ref"),
    }

    items = list(doc.get("items") or [])
    updated = False
    for idx, existing in enumerate(items):
        if str(existing.get("id") or "") == item_id:
            items[idx] = dict(existing, **payload)
            updated = True
            break
    if not updated:
        items.append(payload)
    doc["items"] = items
    write_json_atomic(str(p), doc)
    return payload


def delete_equipment_item(lib_path: str, item_id: str) -> None:
    p = Path(lib_path)
    if not p.exists():
        raise LibWriteError(f"No existe la libreria: {lib_path}")
    doc = read_json(str(p))
    doc = _ensure_equipment_library_doc(doc)
    items = list(doc.get("items") or [])
    before = len(items)
    items = [it for it in items if str(it.get("id") or "") != str(item_id or "")]
    if len(items) == before:
        raise LibWriteError(f"Item no encontrado: {item_id}")
    doc["items"] = items
    write_json_atomic(str(p), doc)
