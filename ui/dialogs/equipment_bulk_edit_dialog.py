# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from data.repositories.lib_writer import LibWriteError, upsert_equipment_item
from ui.dialogs.base_dialog import BaseDialog


class EquipmentBulkEditDialog(BaseDialog):
    def __init__(
        self,
        parent: Optional[object] = None,
        items_by_id: Optional[Dict[str, Dict[str, Any]]] = None,
        item_sources: Optional[Dict[str, str]] = None,
        ensure_writable_lib_cb: Optional[Callable[[], str]] = None,
    ) -> None:
        super().__init__(parent, title="Editar equipos/armarios")
        self.setWindowTitle("Editar equipos/armarios")
        self._items_by_id = dict(items_by_id or {})
        self._item_sources = dict(item_sources or {})
        self._ensure_writable_lib_cb = ensure_writable_lib_cb

        self.table = QTableWidget(0, 6, self)
        self.table.setHorizontalHeaderLabels(
            ["Tag", "Tipo", "Acceso cables", "Ancho (mm)", "Alto (mm)", "Profundidad (mm)"]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.body_layout.addWidget(self.table)

        self._load_items()

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        save_btn = buttons.button(QDialogButtonBox.Save)
        if save_btn is not None:
            save_btn.setText("Guardar")
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        self.footer_layout.addWidget(buttons)

    def _load_items(self) -> None:
        rows: List[Tuple[str, Dict[str, Any]]] = sorted(
            self._items_by_id.items(),
            key=lambda kv: str(kv[1].get("name") or kv[0]).lower(),
        )
        self.table.setRowCount(len(rows))
        for row_idx, (item_id, item) in enumerate(rows):
            name = str(item.get("name") or item_id)
            tag_item = QTableWidgetItem(name)
            tag_item.setData(Qt.UserRole, str(item_id))
            self.table.setItem(row_idx, 0, tag_item)

            type_combo = QComboBox(self.table)
            type_combo.addItems(["Tablero", "Armario"])
            equip_type = str(item.get("equipment_type") or "").strip()
            if not equip_type or equip_type == "Equipo":
                equip_type = "Tablero"
            if equip_type not in ("Tablero", "Armario"):
                equip_type = "Tablero"
            type_combo.setCurrentText(equip_type)
            self.table.setCellWidget(row_idx, 1, type_combo)

            cable_combo = QComboBox(self.table)
            cable_combo.addItems(["Inferior", "Superior"])
            cable_value = str(item.get("cable_access") or "").strip().lower()
            if cable_value in ("top", "superior"):
                cable_combo.setCurrentText("Superior")
            else:
                cable_combo.setCurrentText("Inferior")
            self.table.setCellWidget(row_idx, 2, cable_combo)

            dims = item.get("dimensions_mm") if isinstance(item.get("dimensions_mm"), dict) else {}
            self._set_dim_item(row_idx, 3, dims.get("width"))
            self._set_dim_item(row_idx, 4, dims.get("height"))
            self._set_dim_item(row_idx, 5, dims.get("depth"))

        if rows:
            self.table.resizeRowsToContents()

    def _set_dim_item(self, row: int, col: int, value: Any) -> None:
        text = ""
        if value is not None and value != "":
            try:
                text = str(int(value))
            except Exception:
                text = str(value)
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.setItem(row, col, item)

    def _parse_dim(self, row: int, col: int, label: str) -> int:
        item = self.table.item(row, col)
        raw = (item.text() if item is not None else "").strip()
        if not raw:
            return 0
        try:
            value = int(raw)
        except ValueError:
            raise ValueError(f"{label} debe ser un entero (fila {row + 1}).")
        if value < 0:
            raise ValueError(f"{label} debe ser >= 0 (fila {row + 1}).")
        return value

    def _on_save(self) -> None:
        updates: List[Dict[str, Any]] = []
        for row in range(self.table.rowCount()):
            tag_item = self.table.item(row, 0)
            name = str(tag_item.text() if tag_item is not None else "").strip()
            item_id = str(tag_item.data(Qt.UserRole) if tag_item is not None else "").strip()
            if not item_id:
                continue
            if not name:
                QMessageBox.warning(self, "Equipos", f"Tag obligatorio en fila {row + 1}.")
                self.table.setCurrentCell(row, 0)
                return

            type_widget = self.table.cellWidget(row, 1)
            equip_type = ""
            if isinstance(type_widget, QComboBox):
                equip_type = type_widget.currentText().strip()
            if not equip_type or equip_type == "Equipo":
                equip_type = "Tablero"
            if equip_type not in ("Tablero", "Armario"):
                QMessageBox.warning(self, "Equipos", f"Tipo inválido en fila {row + 1}.")
                return

            cable_widget = self.table.cellWidget(row, 2)
            cable_text = ""
            if isinstance(cable_widget, QComboBox):
                cable_text = cable_widget.currentText().strip()
            cable_access = "top" if cable_text == "Superior" else "bottom"

            try:
                width = self._parse_dim(row, 3, "Ancho")
                height = self._parse_dim(row, 4, "Alto")
                depth = self._parse_dim(row, 5, "Profundidad")
            except ValueError as exc:
                QMessageBox.warning(self, "Equipos", str(exc))
                return

            existing = self._items_by_id.get(item_id) or {}
            payload = {
                "id": item_id,
                "name": name,
                "category": existing.get("category") or "Usuario",
                "equipment_type": equip_type,
                "template_ref": existing.get("template_ref"),
                "cable_access": cable_access,
                "dimensions_mm": {"width": width, "height": height, "depth": depth},
            }
            updates.append(payload)

        fallback_lib: Optional[str] = None
        for payload in updates:
            item_id = str(payload.get("id") or "")
            lib_path = self._item_sources.get(item_id)
            if not lib_path:
                if fallback_lib is None:
                    if not self._ensure_writable_lib_cb:
                        QMessageBox.warning(self, "Equipos", "No hay librería editable disponible.")
                        return
                    fallback_lib = self._ensure_writable_lib_cb()
                lib_path = fallback_lib
            try:
                upsert_equipment_item(lib_path, payload)
            except LibWriteError as exc:
                QMessageBox.warning(self, "Equipos", f"No se pudo guardar '{payload.get('name')}':\n{exc}")
                return

        self.accept()
