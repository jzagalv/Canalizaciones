# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)

from domain.libraries.materials_models import MaterialsLibrary
from ui.dialogs.editors.cable_editor_dialog import CableEditorDialog
from ui.dialogs.editors.duct_editor_dialog import DuctEditorDialog
from ui.dialogs.editors.epc_editor_dialog import EPCEditorDialog
from ui.dialogs.editors.bpc_editor_dialog import BPCEditorDialog


class LibraryEditorWidget(QWidget):
    library_changed = pyqtSignal(object)  # MaterialsLibrary

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._library = MaterialsLibrary()
        self._categories: List[Tuple[str, str]] = [
            ("cables", "Cables"),
            ("ducts", "Ductos"),
            ("epc", "EPC"),
            ("bpc", "BPC"),
        ]

        root = QHBoxLayout(self)

        # Categories
        left = QVBoxLayout()
        left.addWidget(QLabel("Categorías"))
        self.lst_categories = QListWidget()
        for key, label in self._categories:
            it = QListWidgetItem(label)
            it.setData(Qt.UserRole, key)
            self.lst_categories.addItem(it)
        self.lst_categories.currentRowChanged.connect(self._on_category_changed)
        left.addWidget(self.lst_categories, 1)
        root.addLayout(left, 1)

        # Table
        mid = QVBoxLayout()
        mid.addWidget(QLabel("Elementos"))
        self.tbl = QTableWidget(0, 1)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        mid.addWidget(self.tbl, 1)
        root.addLayout(mid, 3)

        # Actions
        right = QVBoxLayout()
        right.addWidget(QLabel("Acciones"))
        self.btn_add = QPushButton("Agregar")
        self.btn_add.clicked.connect(self._add_item)
        right.addWidget(self.btn_add)

        self.btn_edit = QPushButton("Editar")
        self.btn_edit.clicked.connect(self._edit_item)
        right.addWidget(self.btn_edit)

        self.btn_del = QPushButton("Eliminar")
        self.btn_del.clicked.connect(self._delete_item)
        right.addWidget(self.btn_del)

        self.btn_dup = QPushButton("Duplicar")
        self.btn_dup.clicked.connect(self._duplicate_item)
        right.addWidget(self.btn_dup)

        right.addStretch(1)
        root.addLayout(right, 1)

        if self.lst_categories.count() > 0:
            self.lst_categories.setCurrentRow(0)

    def set_library(self, library: MaterialsLibrary) -> None:
        self._library = library or MaterialsLibrary()
        self._refresh_table()

    def library(self) -> MaterialsLibrary:
        return self._library

    def _current_category(self) -> str:
        it = self.lst_categories.currentItem()
        if not it:
            return "cables"
        return str(it.data(Qt.UserRole) or "cables")

    def _columns_for(self, category: str) -> List[Tuple[str, str]]:
        if category == "ducts":
            return [
                ("id", "Código"),
                ("name", "Nombre"),
                ("material", "Material"),
                ("inner_diameter_mm", "Ø int (mm)"),
                ("outer_diameter_mm", "Ø ext (mm)"),
                ("duct_type", "Tipo"),
                ("notes", "Notas"),
            ]
        if category in ("epc", "bpc"):
            return [
                ("id", "Código"),
                ("name", "Nombre"),
                ("type", "Tipo"),
                ("inner_width_mm", "Ancho útil (mm)"),
                ("inner_height_mm", "Alto (mm)"),
                ("material", "Material"),
                ("max_fill_percent", "% Ocupación"),
                ("notes", "Notas"),
            ]
        return [
            ("id", "Código"),
            ("name", "Nombre"),
            ("type", "Tipo"),
            ("kv", "Tensión (kV)"),
            ("section_mm2", "Sección (mm²)"),
            ("outer_diameter_mm", "Ø ext (mm)"),
            ("weight_kg_m", "Peso (kg/m)"),
            ("notes", "Notas"),
        ]

    def _get_items(self, category: str) -> List[Dict[str, Any]]:
        return list(self._library.items.get(category) or [])

    def _set_items(self, category: str, items: List[Dict[str, Any]]) -> None:
        self._library.items[category] = list(items)
        self._refresh_table()
        self.library_changed.emit(self._library)

    def _refresh_table(self) -> None:
        category = self._current_category()
        cols = self._columns_for(category)
        items = self._get_items(category)

        self.tbl.setColumnCount(len(cols))
        self.tbl.setHorizontalHeaderLabels([c[1] for c in cols])
        self.tbl.setRowCount(0)

        for it in items:
            row = self.tbl.rowCount()
            self.tbl.insertRow(row)
            for c_idx, (key, _) in enumerate(cols):
                val = it.get(key, "")
                self.tbl.setItem(row, c_idx, QTableWidgetItem(str(val)))

    def _existing_ids(self, category: str, exclude_id: Optional[str] = None) -> List[str]:
        ids = []
        for it in self._get_items(category):
            cid = str(it.get("id") or "").strip()
            if not cid:
                continue
            if exclude_id and cid == exclude_id:
                continue
            ids.append(cid)
        return ids

    def _selected_row(self) -> int:
        sel = self.tbl.selectionModel().selectedRows()
        return sel[0].row() if sel else -1

    def _edit_dialog_for(self, category: str, data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        existing_ids = self._existing_ids(category, exclude_id=(data or {}).get("id"))
        dlg = None
        if category == "ducts":
            dlg = DuctEditorDialog(data=data, existing_ids=existing_ids, parent=self)
        elif category == "epc":
            dlg = EPCEditorDialog(data=data, existing_ids=existing_ids, parent=self)
        elif category == "bpc":
            dlg = BPCEditorDialog(data=data, existing_ids=existing_ids, parent=self)
        else:
            dlg = CableEditorDialog(data=data, existing_ids=existing_ids, parent=self)
        if dlg.exec_() != dlg.Accepted:
            return None
        return dlg.get_data()

    def _add_item(self) -> None:
        category = self._current_category()
        data = self._edit_dialog_for(category)
        if not data:
            return
        items = self._get_items(category)
        items.append(data)
        self._set_items(category, items)

    def _edit_item(self) -> None:
        category = self._current_category()
        row = self._selected_row()
        if row < 0:
            QMessageBox.information(self, "Editar", "Selecciona un elemento para editar.")
            return
        items = self._get_items(category)
        if row >= len(items):
            return
        updated = self._edit_dialog_for(category, data=dict(items[row]))
        if not updated:
            return
        items[row] = updated
        self._set_items(category, items)

    def _delete_item(self) -> None:
        category = self._current_category()
        row = self._selected_row()
        if row < 0:
            return
        items = self._get_items(category)
        if row >= len(items):
            return
        items.pop(row)
        self._set_items(category, items)

    def _duplicate_item(self) -> None:
        category = self._current_category()
        row = self._selected_row()
        if row < 0:
            return
        items = self._get_items(category)
        if row >= len(items):
            return
        src = dict(items[row])
        src_id = str(src.get("id", "") or "")
        if src_id:
            src["id"] = f"{src_id}_copia"
        updated = self._edit_dialog_for(category, data=src)
        if not updated:
            return
        items.append(updated)
        self._set_items(category, items)

    def _on_category_changed(self, *_):
        self._refresh_table()
