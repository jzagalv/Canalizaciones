# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Optional

from PyQt5.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class BaseDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None, title: str = "", subtitle: str = "") -> None:
        super().__init__(parent)
        self.setObjectName("BaseDialog")
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        self.header = QFrame(self)
        self.header.setObjectName("DialogHeader")
        self.header.setProperty("card", True)
        header_layout = QVBoxLayout(self.header)
        header_layout.setContentsMargins(12, 10, 12, 10)
        header_layout.setSpacing(4)
        self.lbl_title = QLabel(title)
        self.lbl_title.setObjectName("DialogTitle")
        self.lbl_subtitle = QLabel(subtitle)
        self.lbl_subtitle.setObjectName("DialogSubtitle")
        self.lbl_subtitle.setVisible(bool(subtitle))
        header_layout.addWidget(self.lbl_title)
        header_layout.addWidget(self.lbl_subtitle)
        root.addWidget(self.header)

        self.body = QFrame(self)
        self.body.setProperty("card", True)
        self.body.setObjectName("DialogBody")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(12, 12, 12, 12)
        self.body_layout.setSpacing(8)
        root.addWidget(self.body, 1)

        self.footer = QFrame(self)
        self.footer.setObjectName("DialogFooter")
        self.footer_layout = QHBoxLayout(self.footer)
        self.footer_layout.setContentsMargins(0, 0, 0, 0)
        self.footer_layout.setSpacing(8)
        self.footer_layout.addStretch(1)
        root.addWidget(self.footer)

    def set_title(self, text: str) -> None:
        self.lbl_title.setText(text)

    def set_subtitle(self, text: str) -> None:
        self.lbl_subtitle.setText(text)
        self.lbl_subtitle.setVisible(bool(text))
