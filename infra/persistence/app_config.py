# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


class AppConfig:
    DEFAULTS: Dict[str, Any] = {
        "theme": "light",
        "materiales_bd_path": "",
        "last_project_path": "",
        "ui": {
            "window_size": [1200, 750],
            "window_pos": [80, 80],
        },
    }

    def __init__(self, path: Path, data: Dict[str, Any]) -> None:
        self._path = path
        self._data = self._normalize(data)

    @classmethod
    def load(cls, app_dir: Path) -> "AppConfig":
        path = app_dir / "config" / "app.config"
        if not path.exists():
            cfg = cls(path, {})
            cfg.save()
            return cfg

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        cfg = cls(path, data)
        if cfg._data != data:
            cfg.save()
        return cfg

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")

    @property
    def theme(self) -> str:
        return str(self._data.get("theme") or "light")

    @theme.setter
    def theme(self, value: str) -> None:
        self._data["theme"] = str(value or "light")

    @property
    def materiales_bd_path(self) -> str:
        return str(self._data.get("materiales_bd_path") or "")

    @materiales_bd_path.setter
    def materiales_bd_path(self, value: str) -> None:
        self._data["materiales_bd_path"] = str(value or "")

    @property
    def last_project_path(self) -> str:
        return str(self._data.get("last_project_path") or "")

    @last_project_path.setter
    def last_project_path(self, value: str) -> None:
        self._data["last_project_path"] = str(value or "")

    @property
    def window_size(self) -> List[int]:
        ui = self._data.get("ui") or {}
        size = ui.get("window_size") or [1200, 750]
        return [int(size[0]), int(size[1])] if len(size) >= 2 else [1200, 750]

    @window_size.setter
    def window_size(self, size: List[int]) -> None:
        ui = self._data.setdefault("ui", {})
        ui["window_size"] = [int(size[0]), int(size[1])]

    @property
    def window_pos(self) -> List[int]:
        ui = self._data.get("ui") or {}
        pos = ui.get("window_pos") or [80, 80]
        return [int(pos[0]), int(pos[1])] if len(pos) >= 2 else [80, 80]

    @window_pos.setter
    def window_pos(self, pos: List[int]) -> None:
        ui = self._data.setdefault("ui", {})
        ui["window_pos"] = [int(pos[0]), int(pos[1])]

    def _normalize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        base = json.loads(json.dumps(self.DEFAULTS))
        if isinstance(data, dict):
            theme = str(data.get("theme") or base["theme"]).lower()
            base["theme"] = theme if theme in ("light", "dark") else base["theme"]
            base["materiales_bd_path"] = str(data.get("materiales_bd_path") or "")
            base["last_project_path"] = str(data.get("last_project_path") or "")
            ui = data.get("ui") or {}
            if isinstance(ui, dict):
                size = ui.get("window_size") or base["ui"]["window_size"]
                pos = ui.get("window_pos") or base["ui"]["window_pos"]
                if isinstance(size, (list, tuple)) and len(size) >= 2:
                    base["ui"]["window_size"] = [int(size[0]), int(size[1])]
                if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                    base["ui"]["window_pos"] = [int(pos[0]), int(pos[1])]
        return base
