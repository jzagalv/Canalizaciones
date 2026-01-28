# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from pathlib import Path

from PyQt5.QtWidgets import QApplication

from infra.persistence.app_config import AppConfig
from ui.main_window import MainWindow
from ui.theme_manager import apply_theme


def main() -> int:
    app = QApplication(sys.argv)

    app_dir = Path(__file__).resolve().parent.parent
    app_config = AppConfig.load(app_dir)
    theme = app_config.theme
    apply_theme(app, app_dir, theme)

    w = MainWindow(app_dir, app_config)
    w.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
