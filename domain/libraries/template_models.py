# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class BaseTemplate:
    schema_version: str = "1.0"
    installation_type: str = ""
    name: str = ""
    defaults: Dict[str, Any] = field(default_factory=dict)
    meta: Optional[Dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseTemplate":
        return cls(
            schema_version=data.get("schema_version", "1.0"),
            installation_type=data.get("installation_type", "") or "",
            name=data.get("name", "") or "",
            defaults=dict(data.get("defaults") or {}),
            meta=dict(data.get("meta") or {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "installation_type": self.installation_type,
            "name": self.name,
            "defaults": dict(self.defaults or {}),
            "meta": dict(self.meta or {}),
        }
