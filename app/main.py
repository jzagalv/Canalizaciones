# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path (classic layout)
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import os
import sys
from pathlib import Path

from PyQt5.QtWidgets import QApplication

from ui.main_window import MainWindow


def _load_qss(app: QApplication, qss_path: Path) -> None:
    try:
        app.setStyleSheet(qss_path.read_text(encoding='utf-8'))
    except Exception:
        pass


def main() -> int:
    app = QApplication(sys.argv)

    app_dir = Path(os.path.dirname(os.path.abspath(__file__))).parent
    qss = app_dir / 'ui' / 'styles' / 'theme.qss'
    _load_qss(app, qss)

    w = MainWindow(str(app_dir))
    w.show()
    return app.exec_()


if __name__ == '__main__':
    raise SystemExit(main())