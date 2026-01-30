# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class BaseTemplate:
    installation_type: str = ""
    defaults: Dict[str, Any] = field(default_factory=dict)
