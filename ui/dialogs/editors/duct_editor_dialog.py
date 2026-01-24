# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List, Optional

from PyQt5.QtGui import QDoubleValidator
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)


class DuctEditorDialog(QDialog):
    def __init__(self, parent=None, data: Optional[Dict[str, Any]] = None, existing_ids: Optional[List[str]] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar ducto")
        self._existing_ids = set(existing_ids or [])
        self._result: Optional[Dict[str, Any]] = None

        root = QVBoxLayout(self)
        form = QFormLayout()
        root.addLayout(form)

        self.ed_id = QLineEdit()
        self.ed_name = QLineEdit()

        self.cmb_material = QComboBox()
        self.cmb_material.setEditable(True)
        self.cmb_material.addItems(["PVC", "HDPE", "Acero"])

        self.ed_inner_d = QLineEdit()
        self.ed_inner_d.setValidator(QDoubleValidator(0.0, 100000.0, 3, self))
        self.ed_outer_d = QLineEdit()
        self.ed_outer_d.setValidator(QDoubleValidator(0.0, 100000.0, 3, self))

        self.cmb_type = QComboBox()
        self.cmb_type.setEditable(True)
        self.cmb_type.addItems(["liso", "corrugado"])

        self.ed_notes = QLineEdit()

        form.addRow("Código/ID:", self.ed_id)
        form.addRow("Nombre:", self.ed_name)
        form.addRow("Material:", self.cmb_material)
        form.addRow("Diámetro interno (mm):", self.ed_inner_d)
        form.addRow("Diámetro externo (mm):", self.ed_outer_d)
        form.addRow("Tipo:", self.cmb_type)
        form.addRow("Notas:", self.ed_notes)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        if data:
            self._load_data(data)

    def _load_data(self, data: Dict[str, Any]) -> None:
        self.ed_id.setText(str(data.get("id", "")))
        self.ed_name.setText(str(data.get("name", "")))
        self.cmb_material.setCurrentText(str(data.get("material", "")))
        self.ed_inner_d.setText(str(data.get("inner_diameter_mm", "")))
        self.ed_outer_d.setText(str(data.get("outer_diameter_mm", "")))
        self.cmb_type.setCurrentText(str(data.get("duct_type", "")))
        self.ed_notes.setText(str(data.get("notes", "")))

    def _read_float(self, widget: QLineEdit, label: str) -> Optional[float]:
        text = widget.text().strip()
        if not text:
            QMessageBox.warning(self, "Validación", f"{label} es obligatorio.")
            return None
        try:
            return float(text)
        except Exception:
            QMessageBox.warning(self, "Validación", f"{label} debe ser numérico.")
            return None

    def _on_accept(self) -> None:
        code = self.ed_id.text().strip()
        name = self.ed_name.text().strip()
        if not code or not name:
            QMessageBox.warning(self, "Validación", "Código y nombre son obligatorios.")
            return
        if code in self._existing_ids:
            QMessageBox.warning(self, "Validación", "El código ya existe en esta categoría.")
            return

        inner_d = self._read_float(self.ed_inner_d, "Diámetro interno (mm)")
        if inner_d is None:
            return
        outer_d = self._read_float(self.ed_outer_d, "Diámetro externo (mm)")
        if outer_d is None:
            return

        self._result = {
            "id": code,
            "name": name,
            "material": self.cmb_material.currentText().strip(),
            "inner_diameter_mm": inner_d,
            "outer_diameter_mm": outer_d,
            "duct_type": self.cmb_type.currentText().strip(),
            "notes": self.ed_notes.text().strip(),
        }
        self.accept()

    def get_data(self) -> Dict[str, Any]:
        return dict(self._result or {})
