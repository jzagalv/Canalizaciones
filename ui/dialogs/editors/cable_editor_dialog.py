# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List, Optional

from PyQt5.QtCore import Qt
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


class CableEditorDialog(QDialog):
    def __init__(self, parent=None, data: Optional[Dict[str, Any]] = None, existing_ids: Optional[List[str]] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar cable")
        self._existing_ids = set(existing_ids or [])
        self._result: Optional[Dict[str, Any]] = None

        root = QVBoxLayout(self)
        form = QFormLayout()
        root.addLayout(form)

        self.ed_id = QLineEdit()
        self.ed_name = QLineEdit()
        self.cmb_type = QComboBox()
        self.cmb_type.setEditable(True)
        self.cmb_type.addItems(["Cu", "Al", "XLPE", "PVC"])

        self.ed_kv = QLineEdit()
        self.ed_kv.setValidator(QDoubleValidator(0.0, 1000.0, 3, self))
        self.ed_section = QLineEdit()
        self.ed_section.setValidator(QDoubleValidator(0.0, 100000.0, 3, self))
        self.ed_outer_d = QLineEdit()
        self.ed_outer_d.setValidator(QDoubleValidator(0.0, 100000.0, 3, self))
        self.ed_weight = QLineEdit()
        self.ed_weight.setValidator(QDoubleValidator(0.0, 100000.0, 3, self))
        self.ed_notes = QLineEdit()

        form.addRow("Código/ID:", self.ed_id)
        form.addRow("Nombre:", self.ed_name)
        form.addRow("Tipo:", self.cmb_type)
        form.addRow("Tensión (kV):", self.ed_kv)
        form.addRow("Sección (mm²):", self.ed_section)
        form.addRow("Diámetro exterior (mm):", self.ed_outer_d)
        form.addRow("Peso (kg/m):", self.ed_weight)
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
        self.cmb_type.setCurrentText(str(data.get("type", "")))
        self.ed_kv.setText(str(data.get("kv", "")))
        self.ed_section.setText(str(data.get("section_mm2", "")))
        self.ed_outer_d.setText(str(data.get("outer_diameter_mm", "")))
        self.ed_weight.setText(str(data.get("weight_kg_m", "")))
        self.ed_notes.setText(str(data.get("notes", "")))

    def _read_float(self, widget: QLineEdit, label: str, required: bool) -> Optional[float]:
        text = widget.text().strip()
        if not text:
            if required:
                QMessageBox.warning(self, "Validación", f"{label} es obligatorio.")
                return None
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

        kv = self._read_float(self.ed_kv, "Tensión (kV)", True)
        if kv is None:
            return
        section = self._read_float(self.ed_section, "Sección (mm²)", True)
        if section is None:
            return
        outer_d = self._read_float(self.ed_outer_d, "Diámetro exterior (mm)", True)
        if outer_d is None:
            return
        weight = self._read_float(self.ed_weight, "Peso (kg/m)", False)

        self._result = {
            "id": code,
            "name": name,
            "type": self.cmb_type.currentText().strip(),
            "kv": kv,
            "section_mm2": section,
            "outer_diameter_mm": outer_d,
            "weight_kg_m": weight if weight is not None else "",
            "notes": self.ed_notes.text().strip(),
        }
        self.accept()

    def get_data(self) -> Dict[str, Any]:
        return dict(self._result or {})
