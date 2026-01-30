# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from domain.libraries.template_models import BaseTemplate


class TemplateRepoError(Exception):
    pass


def _base_doc() -> Dict[str, Any]:
    return {
        "schema_version": "1.0",
        "kind": "base_template",
        "meta": {"name": "Base Template", "created": "", "source": ""},
        "installation_type": "",
        "defaults": {},
    }


def load_base_template(path: str) -> BaseTemplate:
    p = Path(path)
    if not p.exists():
        raise TemplateRepoError(f"Template file not found: {path}")
    try:
        data: Dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise TemplateRepoError(f"Invalid JSON in {path}: {e}")

    if str(data.get("schema_version", "")) != "1.0":
        raise TemplateRepoError("schema_version expected 1.0")
    if str(data.get("kind", "")) != "base_template":
        raise TemplateRepoError("kind expected base_template")

    installation_type = str(data.get("installation_type") or "")
    defaults = data.get("defaults") or {}
    if not isinstance(defaults, dict):
        defaults = {}

    return BaseTemplate(installation_type=installation_type, defaults=defaults)


def save_base_template(template: BaseTemplate, path: str) -> None:
    p = Path(path)
    doc = _base_doc()
    doc["installation_type"] = template.installation_type or ""
    defaults = template.defaults or {}
    if not isinstance(defaults, dict):
        defaults = {}
    doc["defaults"] = defaults

    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
