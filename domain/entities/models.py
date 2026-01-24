# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class LibraryRef:
    path: str
    enabled: bool = True
    priority: int = 10


@dataclass
class Project:
    project_version: str = '1.0'
    name: str = 'Nuevo proyecto'
    active_profile: str = 'ss_conventional'
    libraries: List[LibraryRef] = field(default_factory=list)
    canvas: Dict = field(default_factory=lambda: {'nodes': [], 'edges': []})
    circuits: Dict = field(default_factory=lambda: {'source': 'none', 'items': []})
    primary_equipment: List[Dict] = field(default_factory=list)



@dataclass(frozen=True)
class LibDoc:
    schema_version: str
    kind: str
    meta: Dict
    payload: Dict
