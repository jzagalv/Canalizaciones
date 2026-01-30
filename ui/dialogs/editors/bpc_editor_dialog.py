# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List, Optional

from PyQt5.QtGui import QDoubleValidator, QIntValidator
from PyQt5.QtWidgets import (
    QComboBox,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)
from ui.dialogs.base_dialog import BaseDialog


class BPCEditorDialog(BaseDialog):
    def __init__(self, parent=None, data: Optional[Dict[str, Any]] = None, existing_ids: Optional[List[str]] = None) -> None:
        super().__init__(parent, title="Editar BPC")
        self.setWindowTitle("Editar BPC")
        self._existing_ids = set(existing_ids or [])
        self._result: Optional[Dict[str, Any]] = None

        root = self.body_layout
        form = QFormLayout()
        root.addLayout(form)

        self.ed_id = QLineEdit()
        self.ed_name = QLineEdit()

        self.cmb_shape = QComboBox()
        self.cmb_shape.setEditable(True)
        self.cmb_shape.addItems(["rectangular"])

        self.ed_width = QLineEdit()
        self.ed_width.setValidator(QDoubleValidator(0.0, 100000.0, 3, self))
        self.ed_height = QLineEdit()
        self.ed_height.setValidator(QDoubleValidator(0.0, 100000.0, 3, self))
        self.ed_max_fill = QLineEdit()
        self.ed_max_fill.setValidator(QDoubleValidator(0.0, 100.0, 2, self))
        self.ed_max_layers = QLineEdit()
        self.ed_max_layers.setValidator(QIntValidator(1, 999, self))
        self.ed_material = QLineEdit()
        self.ed_tags = QLineEdit()

        form.addRow("Código:", self.ed_id)
        form.addRow("Nombre:", self.ed_name)
        form.addRow("Forma:", self.cmb_shape)
        form.addRow("Ancho interno (mm):", self.ed_width)
        form.addRow("Alto interno (mm):", self.ed_height)
        form.addRow("% Ocupación:", self.ed_max_fill)
        form.addRow("Máx. capas:", self.ed_max_layers)
        form.addRow("Material:", self.ed_material)
        form.addRow("Tags (coma):", self.ed_tags)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        self.footer_layout.addWidget(buttons)

        if data:
            self._load_data(data)

    def _load_data(self, data: Dict[str, Any]) -> None:
        self.ed_id.setText(str(data.get("code") or data.get("id") or ""))
        self.ed_name.setText(str(data.get("name", "")))
        self.cmb_shape.setCurrentText(str(data.get("shape", "")))
        self.ed_width.setText(str(data.get("inner_width_mm", "")))
        self.ed_height.setText(str(data.get("inner_height_mm", "")))
        self.ed_max_fill.setText(str(data.get("max_fill_percent", "")))
        self.ed_max_layers.setText(str(data.get("max_layers", "")))
        self.ed_material.setText(str(data.get("material", "") or ""))
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
        text = widget.text().strip()
        if not text:
            return None
        try:
            val = float(text)
        except Exception:
            QMessageBox.warning(self, "Validación", "% Ocupación debe ser numérico.")
            return None
        if val <= 0 or val > 100:
            QMessageBox.warning(self, "Validación", "% Ocupación debe ser > 0 y <= 100.")
            return None
        return val

    def _read_layers(self, widget: QLineEdit) -> Optional[int]:
        text = widget.text().strip()
        if not text:
            return None
        try:
            val = int(text)
        except Exception:
            QMessageBox.warning(self, "Validación", "Máx. capas debe ser numérico.")
            return None
        if val < 1:
            QMessageBox.warning(self, "Validación", "Máx. capas debe ser >= 1.")
            return None
        return val

    def _on_accept(self) -> None:
        code = self.ed_id.text().strip()
        name = self.ed_name.text().strip()
        if not code or not name:
            QMessageBox.warning(self, "Validación", "Código y nombre son obligatorios.")
            return
        if code in self._existing_ids:
            QMessageBox.warning(self, "Validación", "El código ya existe en BPC.")
            return

        width = self._read_float(self.ed_width, "Ancho interno (mm)")
        if width is None:
            return
        height = self._read_float(self.ed_height, "Alto interno (mm)")
        if height is None:
            return
        max_fill = self._read_fill(self.ed_max_fill)
        max_layers = self._read_layers(self.ed_max_layers)

        tags = [t.strip() for t in self.ed_tags.text().split(",") if t.strip()]
        material = self.ed_material.text().strip()

        self._result = {
            "code": code,
            "id": code,
            "name": name,
            "shape": self.cmb_shape.currentText().strip(),
            "inner_width_mm": width,
            "inner_height_mm": height,
            "max_fill_percent": max_fill,
            "max_layers": max_layers,
            "material": material if material else None,
            "tags": tags,
        }
        self.accept()

    def get_data(self) -> Dict[str, Any]:
        return dict(self._result or {})
