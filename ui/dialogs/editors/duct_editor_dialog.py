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

        self.cmb_shape = QComboBox()
        self.cmb_shape.setEditable(True)
        self.cmb_shape.addItems(["circular", "rectangular"])

        self.ed_nominal = QLineEdit()
        self.ed_inner_d = QLineEdit()
        self.ed_inner_d.setValidator(QDoubleValidator(0.0, 100000.0, 3, self))
        self.ed_max_fill = QLineEdit()
        self.ed_max_fill.setValidator(QDoubleValidator(0.0, 100.0, 2, self))

        self.ed_material = QLineEdit()
        self.ed_standard = QLineEdit()
        self.ed_manufacturer = QLineEdit()
        self.ed_tags = QLineEdit()

        form.addRow("Código:", self.ed_id)
        form.addRow("Nombre:", self.ed_name)
        form.addRow("Forma:", self.cmb_shape)
        form.addRow("Nominal:", self.ed_nominal)
        form.addRow("Diámetro interno (mm):", self.ed_inner_d)
        form.addRow("% Ocupación:", self.ed_max_fill)
        form.addRow("Material:", self.ed_material)
        form.addRow("Norma:", self.ed_standard)
        form.addRow("Fabricante:", self.ed_manufacturer)
        form.addRow("Tags (coma):", self.ed_tags)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        if data:
            self._load_data(data)

    def _load_data(self, data: Dict[str, Any]) -> None:
        self.ed_id.setText(str(data.get("code") or data.get("id") or ""))
        self.ed_name.setText(str(data.get("name", "")))
        self.cmb_shape.setCurrentText(str(data.get("shape", "")))
        self.ed_nominal.setText(str(data.get("nominal", "")))
        self.ed_inner_d.setText(str(data.get("inner_diameter_mm", "")))
        self.ed_max_fill.setText(str(data.get("max_fill_percent", "")))
        self.ed_material.setText(str(data.get("material", "") or ""))
        self.ed_standard.setText(str(data.get("standard", "") or ""))
        self.ed_manufacturer.setText(str(data.get("manufacturer", "") or ""))
        tags = data.get("tags") or []
        if isinstance(tags, list):
            self.ed_tags.setText(", ".join([str(t) for t in tags]))

    def _read_float(self, widget: QLineEdit, label: str) -> Optional[float]:
        text = widget.text().strip()
        if not text:
            QMessageBox.warning(self, "Validación", f"{label} es obligatorio.")
            return None
        try:
            val = float(text)
        except Exception:
            QMessageBox.warning(self, "Validación", f"{label} debe ser numérico.")
            return None
        if val <= 0:
            QMessageBox.warning(self, "Validación", f"{label} debe ser > 0.")
            return None
        return val

    def _read_fill(self, widget: QLineEdit) -> Optional[float]:
        val = self._read_float(widget, "% Ocupación")
        if val is None:
            return None
        if val <= 0 or val > 100:
            QMessageBox.warning(self, "Validación", "% Ocupación debe ser > 0 y <= 100.")
            return None
        return val

    def _on_accept(self) -> None:
        code = self.ed_id.text().strip()
        name = self.ed_name.text().strip()
        if not code or not name:
            QMessageBox.warning(self, "Validación", "Código y nombre son obligatorios.")
            return
        if code in self._existing_ids:
            QMessageBox.warning(self, "Validación", "El código ya existe en ductos.")
            return

        inner_d = self._read_float(self.ed_inner_d, "Diámetro interno (mm)")
        if inner_d is None:
            return
        max_fill = self._read_fill(self.ed_max_fill)
        if max_fill is None:
            return

        tags = [t.strip() for t in self.ed_tags.text().split(",") if t.strip()]
        manufacturer = self.ed_manufacturer.text().strip()
        material = self.ed_material.text().strip()
        standard = self.ed_standard.text().strip()

        self._result = {
            "code": code,
            "id": code,
            "name": name,
            "shape": self.cmb_shape.currentText().strip(),
            "nominal": self.ed_nominal.text().strip(),
            "inner_diameter_mm": inner_d,
            "max_fill_percent": max_fill,
            "material": material if material else None,
            "standard": standard if standard else None,
            "manufacturer": manufacturer if manufacturer else None,
            "tags": tags,
        }
        self.accept()

    def get_data(self) -> Dict[str, Any]:
        return dict(self._result or {})
