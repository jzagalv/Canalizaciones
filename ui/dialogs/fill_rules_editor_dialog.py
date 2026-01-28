# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)


class FillRulesEditorDialog(QDialog):
    def __init__(self, preset: Dict[str, Any], parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Editar reglas de llenado")
        self._preset = dict(preset or {})
        self._rules = dict(self._preset.get("rules") or {})

        root = QVBoxLayout(self)

        self.tbl_ranges = QTableWidget(0, 3)
        self.tbl_ranges.setHorizontalHeaderLabels(["Min", "Max", "% Max"])
        self.tbl_ranges.horizontalHeader().setStretchLastSection(True)
        root.addWidget(QLabel("Ductos: rangos por # conductores"))
        root.addWidget(self.tbl_ranges)

        row_btns = QHBoxLayout()
        self.btn_add_range = QPushButton("Agregar rango")
        self.btn_remove_range = QPushButton("Eliminar rango")
        self.btn_add_range.clicked.connect(self._add_range_row)
        self.btn_remove_range.clicked.connect(self._remove_range_row)
        row_btns.addWidget(self.btn_add_range)
        row_btns.addWidget(self.btn_remove_range)
        row_btns.addStretch(1)
        root.addLayout(row_btns)

        self._bpc = self._build_block_editor("BPC")
        self._epc = self._build_block_editor("EPC")
        root.addWidget(self._bpc["group"])
        root.addWidget(self._epc["group"])

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._load_rules()

    def _build_block_editor(self, label: str) -> Dict[str, Any]:
        group = QWidget()
        form = QFormLayout(group)
        form.addRow(QLabel(label))
        fill = QLineEdit()
        layers_enabled = QCheckBox("Capas habilitadas")
        max_layers = QSpinBox()
        max_layers.setRange(1, 99)
        form.addRow("% max:", fill)
        form.addRow(layers_enabled)
        form.addRow("Max capas:", max_layers)
        layers_enabled.toggled.connect(max_layers.setEnabled)
        return {"group": group, "fill": fill, "layers_enabled": layers_enabled, "max_layers": max_layers}

    def _load_rules(self) -> None:
        duct = self._rules.get("duct") or {}
        ranges = list(duct.get("fill_by_conductors") or [])
        for r in ranges:
            self._add_range_row(r.get("min"), r.get("max"), r.get("fill_max_pct"))
        if self.tbl_ranges.rowCount() == 0:
            self._add_range_row(1, 1, 50)
            self._add_range_row(2, 999, 33)

        for key, block in (("bpc", self._bpc), ("epc", self._epc)):
            data = self._rules.get(key) or {}
            block["fill"].setText(str(data.get("fill_max_pct", "")))
            block["layers_enabled"].setChecked(bool(data.get("layers_enabled")))
            block["max_layers"].setValue(int(data.get("max_layers") or 1))
            block["max_layers"].setEnabled(bool(data.get("layers_enabled")))

    def _add_range_row(self, min_v=None, max_v=None, pct=None) -> None:
        row = self.tbl_ranges.rowCount()
        self.tbl_ranges.insertRow(row)
        self.tbl_ranges.setItem(row, 0, QTableWidgetItem(str(min_v or "")))
        self.tbl_ranges.setItem(row, 1, QTableWidgetItem(str(max_v or "")))
        self.tbl_ranges.setItem(row, 2, QTableWidgetItem(str(pct or "")))

    def _remove_range_row(self) -> None:
        row = self.tbl_ranges.currentRow()
        if row >= 0:
            self.tbl_ranges.removeRow(row)

    def _read_ranges(self) -> List[Dict[str, int]]:
        ranges: List[Dict[str, int]] = []
        for r in range(self.tbl_ranges.rowCount()):
            try:
                min_v = int(self.tbl_ranges.item(r, 0).text())
                max_v = int(self.tbl_ranges.item(r, 1).text())
                pct = float(self.tbl_ranges.item(r, 2).text())
            except Exception:
                raise ValueError("Rangos de ductos inv�lidos")
            if min_v < 1 or max_v < min_v or pct <= 0 or pct > 100:
                raise ValueError("Rangos de ductos inv�lidos")
            ranges.append({"min": min_v, "max": max_v, "fill_max_pct": pct})
        return ranges

    def _read_block(self, block: Dict[str, Any]) -> Dict[str, Any]:
        fill_txt = (block["fill"].text() or "").strip()
        try:
            fill = float(fill_txt) if fill_txt else 0.0
        except Exception:
            raise ValueError("% max inv�lido")
        if fill <= 0 or fill > 100:
            raise ValueError("% max inv�lido")
        layers_enabled = bool(block["layers_enabled"].isChecked())
        max_layers = int(block["max_layers"].value() or 1)
        return {
            "fill_max_pct": fill,
            "layers_enabled": layers_enabled,
            "max_layers": max_layers,
        }

    def _on_accept(self) -> None:
        try:
            ranges = self._read_ranges()
            bpc = self._read_block(self._bpc)
            epc = self._read_block(self._epc)
        except ValueError as exc:
            QMessageBox.warning(self, "Validaci�n", str(exc))
            return
        self._preset["rules"] = {
            "duct": {"fill_by_conductors": ranges},
            "bpc": bpc,
            "epc": epc,
        }
        self.accept()

    def get_preset(self) -> Dict[str, Any]:
        return dict(self._preset)
