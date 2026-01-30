# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

from domain.materials.material_ids import normalize_material_library

class LibError(Exception):
    pass


@dataclass
class LibLoadResult:
    doc: Dict[str, Any]
    warnings: List[str]
    changed: bool = False


def load_lib(path: str) -> LibLoadResult:
    p = Path(path)
    if not p.exists():
        raise LibError(f"No existe la libreria: {path}")

    try:
        data = json.loads(p.read_text(encoding='utf-8'))
    except Exception as e:
        raise LibError(f"JSON invalido en {path}: {e}")

    warnings: List[str] = []
    schema = data.get('schema_version')
    kind = data.get('kind')
    if schema != '1.0':
        warnings.append(f"schema_version esperado 1.0, recibido: {schema}")
    if kind not in ('material_library', 'template_library', 'equipment_library'):
        raise LibError(f"kind no soportado: {kind}")

    changed = False
    if kind == "material_library":
        changed = normalize_material_library(data, warnings=warnings, source_label=p.name)

    return LibLoadResult(doc=data, warnings=warnings, changed=changed)
