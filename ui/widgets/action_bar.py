# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Optional

from PyQt5.QtWidgets import QFrame, QHBoxLayout, QWidget


class ActionBar(QFrame):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ActionBar")
        self.setProperty("role", "actionbar")
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(12, 8, 12, 8)
        self._layout.setSpacing(8)
        self._layout.addStretch(1)

    def set_action_widget(self, widget: Optional[QWidget]) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item and item.widget():
                item.widget().setParent(None)
        if widget is not None:
            widget.setParent(self)
            self._layout.addWidget(widget)
            self._layout.addStretch(1)
        else:
            self._layout.addStretch(1)
