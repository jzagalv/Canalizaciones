# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, Optional

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ui.widgets.library_editor_widget import LibraryEditorWidget
from ui.dialogs.base_dialog import BaseDialog


class LibrariesTemplatesDialog(BaseDialog):
    request_load_materiales = pyqtSignal()
    request_save_materiales = pyqtSignal()
    request_save_materiales_as = pyqtSignal()
    request_load_template = pyqtSignal()
    request_save_template = pyqtSignal()
    request_apply_template = pyqtSignal()

    materiales_changed = pyqtSignal(dict)
    installation_type_changed = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent, title="Administrador de materiales_bd.lib y Plantillas")
        self.setWindowTitle("Administrador de materiales_bd.lib y Plantillas")
        self.setWindowModality(Qt.NonModal)
        self.setMinimumSize(980, 600)

        self._materiales_doc: Dict = {}
        self._materiales_path: str = ""
        self._template_path: str = ""

        root = self.body_layout
        header = QHBoxLayout()
        header.addWidget(QLabel("Administrador de materiales_bd.lib y Plantillas"), 1)
        root.addLayout(header)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        self._build_materiales_tab()
        self._build_templates_tab()

    # ---------------- materiales_bd.lib tab ----------------
    def _build_materiales_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        top = QHBoxLayout()
        self.btn_mat_load = QPushButton("Cargar materiales_bd.lib...")
        self.btn_mat_load.clicked.connect(self.request_load_materiales)
        top.addWidget(self.btn_mat_load)

        self.btn_mat_save = QPushButton("Guardar")
        self.btn_mat_save.clicked.connect(self.request_save_materiales)
        top.addWidget(self.btn_mat_save)

        self.btn_mat_save_as = QPushButton("Guardar como...")
        self.btn_mat_save_as.clicked.connect(self.request_save_materiales_as)
        top.addWidget(self.btn_mat_save_as)

        self.lbl_materiales_status = QLabel("materiales_bd.lib activo: (no cargado)")
        top.addWidget(self.lbl_materiales_status, 1)
        layout.addLayout(top)

        self.editor = LibraryEditorWidget()
        self.editor.materials_changed.connect(self._on_materiales_changed)
        layout.addWidget(self.editor, 1)

        self.tabs.addTab(tab, "materiales_bd.lib")

    # ---------------- Plantillas tab ----------------
    def _build_templates_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        top = QHBoxLayout()
        top.addWidget(QLabel("Tipo de instalación:"))
        self.cmb_installation = QComboBox()
        self.cmb_installation.setEditable(True)
        self.cmb_installation.addItems(["Subestación", "Línea", "Industria", "Edificio"])
        self.cmb_installation.currentTextChanged.connect(self.installation_type_changed)
        top.addWidget(self.cmb_installation, 1)
        layout.addLayout(top)

        buttons = QHBoxLayout()
        self.btn_tpl_load = QPushButton("Cargar plantilla")
        self.btn_tpl_load.clicked.connect(self.request_load_template)
        buttons.addWidget(self.btn_tpl_load)

        self.btn_tpl_save = QPushButton("Guardar plantilla")
        self.btn_tpl_save.clicked.connect(self.request_save_template)
        buttons.addWidget(self.btn_tpl_save)

        self.btn_tpl_apply = QPushButton("Aplicar al proyecto")
        self.btn_tpl_apply.clicked.connect(self.request_apply_template)
        buttons.addWidget(self.btn_tpl_apply)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.lbl_template_status = QLabel("Plantilla activa: (no cargada)")
        layout.addWidget(self.lbl_template_status)

        self.tabs.addTab(tab, "Plantillas base")

    # ---------------- Public API ----------------
    def set_materiales_doc(self, doc: Dict, path: str = "") -> None:
        self._materiales_doc = doc or {}
        self._materiales_path = path or ""
        self.editor.set_document(self._materiales_doc)
        self._update_materiales_status()

    def get_materiales_doc(self) -> Dict:
        return self.editor.document()

    def set_materiales_path(self, path: str) -> None:
        self._materiales_path = path or ""
        self._update_materiales_status()

    def set_installation_type(self, value: str) -> None:
        self.cmb_installation.setCurrentText(value or "")

    def set_template_status(self, path: str) -> None:
        self._template_path = path or ""
        label = self._template_path or "(no cargada)"
        self.lbl_template_status.setText(f"Plantilla activa: {label}")

    def _update_materiales_status(self) -> None:
        meta = self._materiales_doc.get("meta") or {}
        name = str(meta.get("name", "") or "")
        path = self._materiales_path or "(no cargado)"
        suffix = f" | {name}" if name else ""
        self.lbl_materiales_status.setText(f"materiales_bd.lib activo: {path}{suffix}")

    def _on_materiales_changed(self, doc: Dict) -> None:
        self._materiales_doc = doc
        self._update_materiales_status()
        self.materiales_changed.emit(self._materiales_doc)
