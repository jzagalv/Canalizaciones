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


class EPCEditorDialog(QDialog):
    def __init__(self, parent=None, data: Optional[Dict[str, Any]] = None, existing_ids: Optional[List[str]] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar EPC")
        self._existing_ids = set(existing_ids or [])
        self._result: Optional[Dict[str, Any]] = None

        root = QVBoxLayout(self)
        form = QFormLayout()
        root.addLayout(form)

        self.ed_id = QLineEdit()
        self.ed_name = QLineEdit()
        self.ed_type = QLineEdit("EPC")
        self.ed_type.setReadOnly(True)

        self.ed_width = QLineEdit()
        self.ed_width.setValidator(QDoubleValidator(0.0, 100000.0, 3, self))
        self.ed_height = QLineEdit()
        self.ed_height.setValidator(QDoubleValidator(0.0, 100000.0, 3, self))

        self.cmb_material = QComboBox()
        self.cmb_material.setEditable(True)
        self.cmb_material.addItems(["Galvanizado", "Aluminio", "Acero"])

        self.ed_max_fill = QLineEdit()
        self.ed_max_fill.setValidator(QDoubleValidator(0.0, 100.0, 2, self))

        self.ed_notes = QLineEdit()

        form.addRow("Código/ID:", self.ed_id)
        form.addRow("Nombre:", self.ed_name)
        form.addRow("Tipo:", self.ed_type)
        form.addRow("Ancho útil (mm):", self.ed_width)
        form.addRow("Alto (mm):", self.ed_height)
        form.addRow("Material/acabado:", self.cmb_material)
        form.addRow("% Ocupación permitido:", self.ed_max_fill)
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
        self.ed_width.setText(str(data.get("inner_width_mm", "")))
        self.ed_height.setText(str(data.get("inner_height_mm", "")))
        self.cmb_material.setCurrentText(str(data.get("material", "")))
        self.ed_max_fill.setText(str(data.get("max_fill_percent", "")))
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

    def _read_float_optional(self, widget: QLineEdit, label: str) -> Optional[float]:
        text = widget.text().strip()
        if not text:
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

        width = self._read_float(self.ed_width, "Ancho útil (mm)")
        if width is None:
            return
        height = self._read_float(self.ed_height, "Alto (mm)")
        if height is None:
            return
        max_fill = self._read_float_optional(self.ed_max_fill, "% Ocupación permitido")
        if max_fill is None and self.ed_max_fill.text().strip():
            return

        self._result = {
            "id": code,
            "name": name,
            "type": "EPC",
            "inner_width_mm": width,
            "inner_height_mm": height,
            "material": self.cmb_material.currentText().strip(),
            "max_fill_percent": max_fill if max_fill is not None else "",
            "notes": self.ed_notes.text().strip(),
        }
        self.accept()

    def get_data(self) -> Dict[str, Any]:
        return dict(self._result or {})
