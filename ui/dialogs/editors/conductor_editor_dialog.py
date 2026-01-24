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


class ConductorEditorDialog(QDialog):
    def __init__(self, parent=None, data: Optional[Dict[str, Any]] = None, existing_ids: Optional[List[str]] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar conductor")
        self._existing_ids = set(existing_ids or [])
        self._result: Optional[Dict[str, Any]] = None

        root = QVBoxLayout(self)
        form = QFormLayout()
        root.addLayout(form)

        self.ed_id = QLineEdit()
        self.ed_name = QLineEdit()
        self.cmb_service = QComboBox()
        self.cmb_service.setEditable(True)
        self.cmb_service.addItems(["power", "control", "communications", "comms"])

        self.ed_outer_d = QLineEdit()
        self.ed_outer_d.setValidator(QDoubleValidator(0.0, 100000.0, 3, self))
        self.ed_manufacturer = QLineEdit()
        self.ed_model = QLineEdit()
        self.ed_tags = QLineEdit()

        form.addRow("ID:", self.ed_id)
        form.addRow("Nombre:", self.ed_name)
        form.addRow("Servicio:", self.cmb_service)
        form.addRow("Diámetro exterior (mm):", self.ed_outer_d)
        form.addRow("Fabricante:", self.ed_manufacturer)
        form.addRow("Modelo:", self.ed_model)
        form.addRow("Tags (coma):", self.ed_tags)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        if data:
            self._load_data(data)

    def _load_data(self, data: Dict[str, Any]) -> None:
        self.ed_id.setText(str(data.get("id", "")))
        self.ed_name.setText(str(data.get("name", "")))
        self.cmb_service.setCurrentText(str(data.get("service", "")))
        self.ed_outer_d.setText(str(data.get("outer_diameter_mm", "")))
        self.ed_manufacturer.setText("" if data.get("manufacturer") is None else str(data.get("manufacturer", "")))
        self.ed_model.setText("" if data.get("model") is None else str(data.get("model", "")))
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

    def _on_accept(self) -> None:
        code = self.ed_id.text().strip()
        name = self.ed_name.text().strip()
        if not code or not name:
            QMessageBox.warning(self, "Validación", "ID y nombre son obligatorios.")
            return
        if code in self._existing_ids:
            QMessageBox.warning(self, "Validación", "El ID ya existe en conductores.")
            return
        outer_d = self._read_float(self.ed_outer_d, "Diámetro exterior (mm)")
        if outer_d is None:
            return

        tags = [t.strip() for t in self.ed_tags.text().split(",") if t.strip()]

        manufacturer = self.ed_manufacturer.text().strip()
        model = self.ed_model.text().strip()
        self._result = {
            "id": code,
            "name": name,
            "service": self.cmb_service.currentText().strip(),
            "outer_diameter_mm": outer_d,
            "manufacturer": manufacturer if manufacturer else None,
            "model": model if model else None,
            "tags": tags,
        }
        self.accept()

    def get_data(self) -> Dict[str, Any]:
        return dict(self._result or {})
