# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Optional

from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget


class HeaderBar(QFrame):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("HeaderBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)

        self.lbl_project = QLabel("Proyecto: (sin guardar)")
        self.lbl_project.setObjectName("HeaderProject")
        layout.addWidget(self.lbl_project, 2)

        self.lbl_libs = QLabel("Bibliotecas: (no cargadas)")
        self.lbl_libs.setObjectName("HeaderLibraries")
        layout.addWidget(self.lbl_libs, 2)

        self.lbl_status = QLabel("")
        self.lbl_status.setObjectName("HeaderStatus")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status, 1)

        layout.addStretch(1)

        self.btn_validate = QPushButton("Validar bibliotecas")
        self.btn_validate.setProperty("secondary", True)
        layout.addWidget(self.btn_validate)

        self.btn_recalc = QPushButton("Recalcular")
        self.btn_recalc.setProperty("primary", True)
        layout.addWidget(self.btn_recalc)

    def set_project_text(self, text: str) -> None:
        self.lbl_project.setText(text)

    def set_libraries_text(self, text: str) -> None:
        self.lbl_libs.setText(text)

    def set_status_text(self, text: str) -> None:
        self.lbl_status.setText(text)
