# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import Set

from PyQt5.QtWidgets import QApplication


THEMES: Set[str] = {"light", "dark"}


def apply_theme(app: QApplication, app_dir: Path, theme: str) -> None:
    qss_path = qss_path_for_theme(app_dir, theme)
    try:
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))
    except Exception:
        app.setStyleSheet("")


def qss_path_for_theme(app_dir: Path, theme: str) -> Path:
    theme = theme if theme in THEMES else "light"
    filename = "theme_dark.qss" if theme == "dark" else "theme_light.qss"
    return app_dir / "ui" / "styles" / filename
