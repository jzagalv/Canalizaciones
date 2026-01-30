# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List


class FillRulesStoreError(Exception):
    pass


DEFAULT_PRESETS_DOC = {
    "schema_version": 1,
    "presets": [
        {
            "id": "CL_RIC",
            "name": "Chile (RIC)",
            "rules": {
                "duct": {
                    "fill_by_conductors": [
                        {"min": 1, "max": 1, "fill_max_pct": 50},
                        {"min": 2, "max": 999, "fill_max_pct": 33},
                    ]
                },
                "bpc": {"fill_max_pct": 40, "layers_enabled": False, "max_layers": 1},
                "epc": {"fill_max_pct": 40, "layers_enabled": True, "max_layers": 2},
            },
        }
    ],
    "active_default_preset_id": "CL_RIC",
}


def _presets_path(app_dir: Path) -> Path:
    return Path(app_dir) / "config" / "fill_rules_presets.json"


def read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise FillRulesStoreError(f"JSON invalido en {path}: {exc}")


def write_json_atomic(path: Path, doc: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(str(tmp), str(path))
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


def ensure_default_presets(app_dir: Path) -> Dict[str, Any]:
    path = _presets_path(Path(app_dir))
    if not path.exists():
        write_json_atomic(path, dict(DEFAULT_PRESETS_DOC))
        return dict(DEFAULT_PRESETS_DOC)
    data = read_json(path)
    if data.get("schema_version") != 1:
        raise FillRulesStoreError("schema_version esperado 1")
    if "presets" not in data:
        data["presets"] = []
    if not data.get("active_default_preset_id") and data.get("presets"):
        data["active_default_preset_id"] = str(data["presets"][0].get("id") or "")
    return data


def load_presets(app_dir: Path) -> Dict[str, Any]:
    return ensure_default_presets(app_dir)


def save_presets(app_dir: Path, data: Dict[str, Any]) -> None:
    path = _presets_path(Path(app_dir))
    if data.get("schema_version") != 1:
        raise FillRulesStoreError("schema_version esperado 1")
    write_json_atomic(path, data)


def _find_preset_index(presets: List[Dict[str, Any]], preset_id: str) -> int:
    for idx, p in enumerate(presets or []):
        if str(p.get("id") or "") == str(preset_id):
            return idx
    return -1


def add_preset(data: Dict[str, Any], preset: Dict[str, Any]) -> Dict[str, Any]:
    presets = list(data.get("presets") or [])
    preset_id = str(preset.get("id") or "")
    if not preset_id:
        raise FillRulesStoreError("preset.id es obligatorio")
    if _find_preset_index(presets, preset_id) >= 0:
        raise FillRulesStoreError("Ya existe un preset con ese id")
    presets.append(dict(preset))
    data["presets"] = presets
    if not data.get("active_default_preset_id"):
        data["active_default_preset_id"] = preset_id
    return data


def update_preset(data: Dict[str, Any], preset: Dict[str, Any]) -> Dict[str, Any]:
    presets = list(data.get("presets") or [])
    preset_id = str(preset.get("id") or "")
    if not preset_id:
        raise FillRulesStoreError("preset.id es obligatorio")
    idx = _find_preset_index(presets, preset_id)
    if idx < 0:
        raise FillRulesStoreError("Preset no encontrado")
    presets[idx] = dict(preset)
    data["presets"] = presets
    return data


def delete_preset(data: Dict[str, Any], preset_id: str) -> Dict[str, Any]:
    presets = list(data.get("presets") or [])
    if len(presets) <= 1:
        raise FillRulesStoreError("No se puede borrar el ultimo preset")
    idx = _find_preset_index(presets, preset_id)
    if idx < 0:
        raise FillRulesStoreError("Preset no encontrado")
    presets.pop(idx)
    data["presets"] = presets
    active_id = str(data.get("active_default_preset_id") or "")
    if active_id == str(preset_id):
        data["active_default_preset_id"] = str(presets[0].get("id") or "")
    return data
