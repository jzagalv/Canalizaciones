# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Optional

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)

from domain.libraries.materials_models import MaterialsLibrary
from domain.libraries.template_models import BaseTemplate
from ui.widgets.library_editor_widget import LibraryEditorWidget


class LibrariesTemplatesDialog(QDialog):
    request_load_library = pyqtSignal()
    request_save_library = pyqtSignal()
    request_save_library_as = pyqtSignal()
    request_load_template = pyqtSignal()
    request_save_template = pyqtSignal()
    request_save_template_as = pyqtSignal()

    library_changed = pyqtSignal(object)  # MaterialsLibrary
    template_changed = pyqtSignal(object)  # BaseTemplate
    installation_type_changed = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Gestión de Librerías y Plantillas")
        self.setWindowModality(Qt.NonModal)
        self.setMinimumSize(900, 600)

        self._library: MaterialsLibrary = MaterialsLibrary()
        self._template: BaseTemplate = BaseTemplate()
        self._library_path: str = ""
        self._template_path: str = ""

        root = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel("Gestión de Librerías y Plantillas"), 1)
        root.addLayout(header)

        install_row = QHBoxLayout()
        install_row.addWidget(QLabel("Tipo de instalación:"))
        self.cmb_installation = QComboBox()
        self.cmb_installation.setEditable(True)
        self.cmb_installation.addItems(["Subestación", "Línea", "Industria", "Edificio"])
        self.cmb_installation.currentTextChanged.connect(self._on_installation_changed)
        install_row.addWidget(self.cmb_installation, 1)
        root.addLayout(install_row)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        self._build_templates_tab()
        self._build_materials_tab()

    # ---------------- Templates tab ----------------
    def _build_templates_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        top = QHBoxLayout()
        self.lbl_template_path = QLabel("Plantilla activa: (sin archivo)")
        top.addWidget(self.lbl_template_path, 1)

        self.btn_tpl_load = QPushButton("Cargar...")
        self.btn_tpl_load.clicked.connect(self.request_load_template)
        top.addWidget(self.btn_tpl_load)

        self.btn_tpl_save = QPushButton("Guardar")
        self.btn_tpl_save.clicked.connect(self.request_save_template)
        top.addWidget(self.btn_tpl_save)

        self.btn_tpl_save_as = QPushButton("Guardar como...")
        self.btn_tpl_save_as.clicked.connect(self.request_save_template_as)
        top.addWidget(self.btn_tpl_save_as)

        layout.addLayout(top)

        layout.addWidget(QLabel("Defaults (JSON):"))
        self.txt_defaults = QTextEdit()
        self.txt_defaults.setPlaceholderText("{\n  \"key\": \"value\"\n}")
        layout.addWidget(self.txt_defaults, 1)

        apply_row = QHBoxLayout()
        apply_row.addStretch(1)
        self.btn_tpl_apply = QPushButton("Aplicar cambios")
        self.btn_tpl_apply.clicked.connect(self._apply_template_changes)
        apply_row.addWidget(self.btn_tpl_apply)
        layout.addLayout(apply_row)

        self.tabs.addTab(tab, "Plantillas")

    # ---------------- Materials tab ----------------
    def _build_materials_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        top = QHBoxLayout()
        self.lbl_library_path = QLabel("Librería activa: (sin archivo)")
        top.addWidget(self.lbl_library_path, 1)

        self.btn_lib_load = QPushButton("Cargar...")
        self.btn_lib_load.clicked.connect(self.request_load_library)
        top.addWidget(self.btn_lib_load)

        self.btn_lib_save = QPushButton("Guardar")
        self.btn_lib_save.clicked.connect(self.request_save_library)
        top.addWidget(self.btn_lib_save)

        self.btn_lib_save_as = QPushButton("Guardar como...")
        self.btn_lib_save_as.clicked.connect(self.request_save_library_as)
        top.addWidget(self.btn_lib_save_as)

        layout.addLayout(top)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Nombre librería:"))
        self.ed_library_name = QLineEdit()
        self.ed_library_name.textChanged.connect(self._on_library_name_changed)
        name_row.addWidget(self.ed_library_name, 1)
        layout.addLayout(name_row)

        self.editor = LibraryEditorWidget()
        self.editor.library_changed.connect(self._on_library_changed)
        layout.addWidget(self.editor, 1)

        self.tabs.addTab(tab, "Librerías de materiales")

    # ---------------- Public API ----------------
    def set_library(self, library: MaterialsLibrary, path: str = "") -> None:
        self._library = library or MaterialsLibrary()
        self._library_path = path or ""
        self.editor.set_library(self._library)
        self.ed_library_name.setText(self._library.name)
        self._update_library_path_label()

    def set_template(self, template: BaseTemplate, path: str = "") -> None:
        self._template = template or BaseTemplate()
        self._template_path = path or ""
        self.cmb_installation.setCurrentText(self._template.installation_type or "")
        self._update_template_path_label()
        self.txt_defaults.setPlainText(json.dumps(self._template.defaults or {}, ensure_ascii=False, indent=2))

    def set_installation_type(self, value: str) -> None:
        self.cmb_installation.setCurrentText(value or "")

    def set_library_path(self, path: str) -> None:
        self._library_path = path or ""
        self._update_library_path_label()

    def set_template_path(self, path: str) -> None:
        self._template_path = path or ""
        self._update_template_path_label()

    def get_template_from_ui(self) -> Optional[BaseTemplate]:
        try:
            defaults = json.loads(self.txt_defaults.toPlainText() or "{}")
        except Exception as e:
            QMessageBox.warning(self, "Plantilla", f"Defaults JSON invalido:\n{e}")
            return None
        tpl = BaseTemplate(
            schema_version=1,
            installation_type=self.cmb_installation.currentText().strip(),
            defaults=defaults,
        )
        return tpl

    def get_library_from_ui(self) -> MaterialsLibrary:
        return self.editor.library()

    # ---------------- Internals ----------------
    def _update_library_path_label(self) -> None:
        path = self._library_path or "(sin archivo)"
        self.lbl_library_path.setText(f"Librería activa: {path}")

    def _update_template_path_label(self) -> None:
        path = self._template_path or "(sin archivo)"
        self.lbl_template_path.setText(f"Plantilla activa: {path}")

    def _on_library_name_changed(self, text: str) -> None:
        self._library.name = text.strip()
        self.library_changed.emit(self._library)

    def _on_library_changed(self, library: MaterialsLibrary) -> None:
        self._library = library
        self.library_changed.emit(self._library)

    def _on_installation_changed(self, text: str) -> None:
        self.installation_type_changed.emit(text.strip())

    def _apply_template_changes(self) -> None:
        tpl = self.get_template_from_ui()
        if tpl is None:
            return
        self._template = tpl
        self.template_changed.emit(self._template)
