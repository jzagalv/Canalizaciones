# -*- coding: utf-8 -*-
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional


def material_display_label(item: Dict[str, Any]) -> str:
    return str(
        item.get("label")
        or item.get("name")
        or item.get("nominal")
        or item.get("code")
        or item.get("id")
        or ""
    ).strip()


def normalize_material_library(
    doc: Dict[str, Any],
    warnings: Optional[List[str]] = None,
    source_label: str = "",
) -> bool:
    if not isinstance(doc, dict):
        return False
    kind = str(doc.get("kind") or "")
    if kind != "material_library":
        return False

    changed = False
    conductors = list(doc.get("conductors") or [])
    if conductors:
        changed = _ensure_material_fields(conductors, "conductors", warnings, source_label) or changed
        doc["conductors"] = conductors

    cont = doc.get("containments") or {}
    for key in ("ducts", "epc", "bpc"):
        items = list(cont.get(key) or [])
        if items:
            changed = _ensure_material_fields(items, key, warnings, source_label) or changed
            cont[key] = items
    doc["containments"] = cont
    return changed


def _ensure_material_fields(
    items: List[Dict[str, Any]],
    scope: str,
    warnings: Optional[List[str]],
    source_label: str,
) -> bool:
    changed = False
    used_codes: set[str] = set()

    for item in items:
        if not isinstance(item, dict):
            continue

        uid = str(item.get("uid") or "").strip()
        if not uid:
            item["uid"] = str(uuid.uuid4())
            changed = True

        code = str(item.get("code") or "").strip()
        if not code:
            if scope == "ducts":
                code = _build_duct_code(item)
            else:
                legacy = str(item.get("id") or "").strip()
                if legacy:
                    code = legacy
                else:
                    name = str(item.get("name") or item.get("label") or item.get("nominal") or "").strip()
                    code = name
            if not code:
                code = str(item.get("uid") or "").split("-", 1)[0]
            item["code"] = code
            changed = True

        label = str(item.get("name") or item.get("label") or "").strip()
        if not label:
            fallback = str(item.get("nominal") or item.get("code") or item.get("id") or "").strip()
            if fallback:
                item["name"] = fallback
                changed = True

        code_norm = code.strip().lower()
        if code_norm:
            if code_norm in used_codes and warnings is not None:
                src = f"{source_label} " if source_label else ""
                warnings.append(f"[{scope}] {src}code duplicado '{code}' dentro de la libreria")
            used_codes.add(code_norm)

    return changed


def _build_duct_code(item: Dict[str, Any]) -> str:
    base = str(item.get("id") or item.get("name") or item.get("nominal") or "").strip()
    standard = str(item.get("standard") or "").strip()
    if standard:
        base = f"{base}_{standard}" if base else standard
    return _slug(base) if base else ""


def _slug(text: str) -> str:
    if not text:
        return ""
    out = []
    for ch in str(text):
        if ch.isalnum():
            out.append(ch.upper())
        elif ch in (" ", "-", "_", "."):
            out.append("_")
    slug = "".join(out).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug
