# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from domain.libraries.materials_models import MaterialsLibrary


class MaterialsLibraryError(Exception):
    pass


def load_materials_library(path: str) -> MaterialsLibrary:
    p = Path(path)
    if not p.exists():
        raise MaterialsLibraryError(f"No existe la libreria: {path}")
    try:
        data: Dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise MaterialsLibraryError(f"JSON invalido en {path}: {e}")
    return MaterialsLibrary.from_dict(data)


def save_materials_library(library: MaterialsLibrary, path: str) -> None:
    p = Path(path)
    data = library.to_dict()
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
