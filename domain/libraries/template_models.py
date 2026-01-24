# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class BaseTemplate:
    schema_version: int = 1
    installation_type: str = ""
    defaults: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseTemplate":
        return cls(
            schema_version=int(data.get("schema_version", 1) or 1),
            installation_type=str(data.get("installation_type", "") or ""),
            defaults=dict(data.get("defaults") or {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "installation_type": str(self.installation_type or ""),
            "defaults": dict(self.defaults or {}),
        }
