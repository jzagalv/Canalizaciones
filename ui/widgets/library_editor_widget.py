# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from PyQt5.QtCore import pyqtSignal, Qt, QPoint
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)

from ui.dialogs.editors.conductor_editor_dialog import ConductorEditorDialog
from ui.dialogs.editors.duct_editor_dialog import DuctEditorDialog
from ui.dialogs.editors.epc_editor_dialog import EPCEditorDialog
from ui.dialogs.editors.bpc_editor_dialog import BPCEditorDialog
from domain.materials.material_ids import normalize_material_library


class LibraryEditorWidget(QWidget):
    materials_changed = pyqtSignal(dict)  # materiales_bd dict

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._doc: Dict[str, Any] = {}
        self._categories: List[Tuple[str, str]] = [
            ("conductors", "Conductores"),
            ("ducts", "Ductos"),
            ("epc", "EPC"),
            ("bpc", "BPC"),
        ]

        root = QHBoxLayout(self)

        # Categories
        left = QVBoxLayout()
        left.addWidget(QLabel("Categorías"))
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        for key, label in self._categories:
            it = QTreeWidgetItem([label])
            it.setData(0, Qt.UserRole, key)
            self.tree.addTopLevelItem(it)
        self.tree.currentItemChanged.connect(self._on_category_changed)
        left.addWidget(self.tree, 1)
        root.addLayout(left, 1)

        # Table
        mid = QVBoxLayout()
        mid.addWidget(QLabel("Elementos"))
        self.tbl = QTableWidget(0, 1)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tbl.customContextMenuRequested.connect(self._show_context_menu)
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

        if self.tree.topLevelItemCount() > 0:
            self.tree.setCurrentItem(self.tree.topLevelItem(0))

    def set_document(self, doc: Dict[str, Any]) -> None:
        self._doc = doc or {}
        normalize_material_library(self._doc)
        self._refresh_table()

    def document(self) -> Dict[str, Any]:
        return self._doc

    def _current_category(self) -> str:
        it = self.tree.currentItem()
        if not it:
            return "conductors"
        return str(it.data(0, Qt.UserRole) or "conductors")

    def _columns_for(self, category: str) -> List[Tuple[str, str]]:
        if category == "conductors":
            return [
                ("code", "Código"),
                ("name", "Nombre"),
                ("service", "Servicio"),
                ("outer_diameter_mm", "Ø ext (mm)"),
                ("manufacturer", "Fabricante"),
                ("model", "Modelo"),
                ("tags", "Tags"),
            ]
        if category == "ducts":
            return [
                ("code", "Código"),
                ("name", "Nombre"),
                ("shape", "Forma"),
                ("nominal", "Nominal"),
                ("inner_diameter_mm", "Ø int (mm)"),
                ("max_fill_percent", "% Ocupación"),
                ("material", "Material"),
                ("standard", "Norma"),
                ("manufacturer", "Fabricante"),
                ("tags", "Tags"),
            ]
        return [
            ("code", "Código"),
            ("name", "Nombre"),
            ("shape", "Forma"),
            ("inner_width_mm", "Ancho (mm)"),
            ("inner_height_mm", "Alto (mm)"),
            ("max_fill_percent", "% Ocupación"),
            ("max_layers", "Capas"),
            ("material", "Material"),
            ("tags", "Tags"),
        ]

    def _category_items(self, category: str) -> List[Dict[str, Any]]:
        if category == "conductors":
            return list(self._doc.get("conductors") or [])
        cont = self._doc.get("containments") or {}
        return list(cont.get(category) or [])

    def _set_category_items(self, category: str, items: List[Dict[str, Any]]) -> None:
        if category == "conductors":
            self._doc["conductors"] = list(items)
        else:
            cont = self._doc.get("containments") or {}
            cont[category] = list(items)
            self._doc["containments"] = cont
        normalize_material_library(self._doc)
        self._refresh_table()
        self.materials_changed.emit(self._doc)

    def _refresh_table(self) -> None:
        category = self._current_category()
        cols = self._columns_for(category)
        items = self._category_items(category)

        self.tbl.setColumnCount(len(cols))
        self.tbl.setHorizontalHeaderLabels([c[1] for c in cols])
        self.tbl.setRowCount(0)

        for it in items:
            row = self.tbl.rowCount()
            self.tbl.insertRow(row)
            for c_idx, (key, _) in enumerate(cols):
                val = it.get(key, "")
                if isinstance(val, list):
                    val = ", ".join([str(v) for v in val])
                self.tbl.setItem(row, c_idx, QTableWidgetItem(str(val)))

    def _existing_ids(self, category: str, exclude_id: Optional[str] = None) -> List[str]:
        ids = []
        for it in self._category_items(category):
            cid = str(it.get("code") or it.get("id") or "").strip()
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
        existing_ids = self._existing_ids(category, exclude_id=(data or {}).get("code") or (data or {}).get("id"))
        if category == "ducts":
            dlg = DuctEditorDialog(data=data, existing_ids=existing_ids, parent=self)
        elif category == "epc":
            dlg = EPCEditorDialog(data=data, existing_ids=existing_ids, parent=self)
        elif category == "bpc":
            dlg = BPCEditorDialog(data=data, existing_ids=existing_ids, parent=self)
        else:
            dlg = ConductorEditorDialog(data=data, existing_ids=existing_ids, parent=self)
        if dlg.exec_() != dlg.Accepted:
            return None
        return dlg.get_data()

    def _add_item(self) -> None:
        category = self._current_category()
        data = self._edit_dialog_for(category)
        if not data:
            return
        items = self._category_items(category)
        items.append(data)
        self._set_category_items(category, items)

    def _edit_item(self) -> None:
        category = self._current_category()
        row = self._selected_row()
        if row < 0:
            QMessageBox.information(self, "Editar", "Selecciona un elemento para editar.")
            return
        items = self._category_items(category)
        if row >= len(items):
            return
        updated = self._edit_dialog_for(category, data=dict(items[row]))
        if not updated:
            return
        items[row] = updated
        self._set_category_items(category, items)

    def _delete_item(self) -> None:
        category = self._current_category()
        row = self._selected_row()
        if row < 0:
            return
        items = self._category_items(category)
        if row >= len(items):
            return
        items.pop(row)
        self._set_category_items(category, items)

    def _duplicate_item(self) -> None:
        category = self._current_category()
        row = self._selected_row()
        if row < 0:
            return
        items = self._category_items(category)
        if row >= len(items):
            return
        src = dict(items[row])
        src_id = str(src.get("code", "") or src.get("id") or "")
        if src_id:
            src["code"] = f"{src_id}_copia"
            src["id"] = src["code"]
        updated = self._edit_dialog_for(category, data=src)
        if not updated:
            return
        items.append(updated)
        self._set_category_items(category, items)

    def _on_category_changed(self, *_):
        self._refresh_table()

    def _show_context_menu(self, pos: QPoint) -> None:
        if self.tbl.rowCount() == 0:
            return
        row = self.tbl.indexAt(pos).row()
        if row >= 0:
            self.tbl.selectRow(row)
        menu = QMenu(self)
        act_edit = menu.addAction("Editar")
        act_del = menu.addAction("Eliminar")
        act_dup = menu.addAction("Duplicar")
        action = menu.exec_(self.tbl.viewport().mapToGlobal(pos))
        if action == act_edit:
            self._edit_item()
        elif action == act_del:
            self._delete_item()
        elif action == act_dup:
            self._duplicate_item()
