# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class MaterialsLibrary:
    schema_version: int = 1
    name: str = "Nueva Libreria"
    items: Dict[str, List[Dict[str, Any]]] = field(
        default_factory=lambda: {"cables": [], "ducts": [], "epc": [], "bpc": []}
    )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MaterialsLibrary":
        items = data.get("items") or {}
        return cls(
            schema_version=int(data.get("schema_version", 1) or 1),
            name=str(data.get("name", "Nueva Libreria")),
            items={
                "cables": list(items.get("cables") or []),
                "ducts": list(items.get("ducts") or []),
                "epc": list(items.get("epc") or []),
                "bpc": list(items.get("bpc") or []),
            },
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "name": str(self.name),
            "items": {
                "cables": list(self.items.get("cables") or []),
                "ducts": list(self.items.get("ducts") or []),
                "epc": list(self.items.get("epc") or []),
                "bpc": list(self.items.get("bpc") or []),
            },
        }
