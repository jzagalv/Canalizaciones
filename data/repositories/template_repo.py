# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from domain.libraries.template_models import BaseTemplate


class TemplateRepoError(Exception):
    pass


def load_base_template(path: str) -> BaseTemplate:
    p = Path(path)
    if not p.exists():
        raise TemplateRepoError(f"No existe la plantilla: {path}")
    try:
        data: Dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise TemplateRepoError(f"JSON invalido en {path}: {e}")
    return BaseTemplate.from_dict(data)


def save_base_template(template: BaseTemplate, path: str) -> None:
    p = Path(path)
    data = template.to_dict()
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
