# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, Optional

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QFrame, QToolButton, QVBoxLayout


class SidebarNav(QFrame):
    navRequested = pyqtSignal(str)

    def __init__(self, parent: Optional[QFrame] = None) -> None:
        super().__init__(parent)
        self.setObjectName("SidebarNav")
        self.setProperty("role", "sidebar")
        self._buttons: Dict[str, QToolButton] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addStretch(1)

    def add_item(self, key: str, text: str) -> QToolButton:
        btn = QToolButton(self)
        btn.setText(text)
        btn.setCheckable(True)
        btn.clicked.connect(lambda: self.navRequested.emit(key))
        self.layout().insertWidget(self.layout().count() - 1, btn)
        self._buttons[key] = btn
        return btn

    def set_active(self, key: str) -> None:
        for k, btn in self._buttons.items():
            btn.setChecked(k == key)
