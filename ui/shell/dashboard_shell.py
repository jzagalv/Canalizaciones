# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Optional

from PyQt5.QtWidgets import (
    QHBoxLayout,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.widgets.sidebar_nav import SidebarNav
from ui.widgets.header_bar import HeaderBar
from ui.widgets.inspector_panel import InspectorPanel
from ui.widgets.action_bar import ActionBar


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

        self.action_bar = ActionBar(self)
        center.addWidget(self.action_bar)

        self.stack = QStackedWidget(self)
        self.stack.setObjectName("ContentStack")
        center.addWidget(self.stack, 1)

        self.inspector = InspectorPanel(self)
        body.addWidget(self.inspector)

    def set_action_widget(self, widget: Optional[QWidget]) -> None:
        self.action_bar.set_action_widget(widget)
