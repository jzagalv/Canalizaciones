# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Optional

from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.widgets.sidebar_nav import SidebarNav
from ui.widgets.header_bar import HeaderBar
from ui.widgets.inspector_panel import InspectorPanel


class DashboardShell(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.header = HeaderBar(self)
        root.addWidget(self.header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        root.addLayout(body, 1)

        self.sidebar = SidebarNav(self)
        body.addWidget(self.sidebar)

        center = QVBoxLayout()
        center.setContentsMargins(0, 0, 0, 0)
        center.setSpacing(0)
        body.addLayout(center, 1)

        self.action_bar = QFrame(self)
        self.action_bar.setObjectName("ActionBar")
        self._action_layout = QHBoxLayout(self.action_bar)
        self._action_layout.setContentsMargins(12, 8, 12, 8)
        self._action_layout.setSpacing(8)
        center.addWidget(self.action_bar)

        self.stack = QStackedWidget(self)
        self.stack.setObjectName("ContentStack")
        center.addWidget(self.stack, 1)

        self.inspector = InspectorPanel(self)
        body.addWidget(self.inspector)

    def set_action_widget(self, widget: Optional[QWidget]) -> None:
        while self._action_layout.count():
            item = self._action_layout.takeAt(0)
            if item and item.widget():
                item.widget().setParent(None)
        if widget is not None:
            widget.setParent(self.action_bar)
            self._action_layout.addWidget(widget)
            self._action_layout.addStretch(1)
        else:
            self._action_layout.addStretch(1)
