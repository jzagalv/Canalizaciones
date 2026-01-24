# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from PyQt5.QtCore import Qt, QMimeData, QPoint
from PyQt5.QtGui import QDrag, QFontMetrics, QPainter, QPixmap, QColor, QPen, QBrush
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class LibraryTree(QTreeWidget):
    """Draggable tree for Biblioteca items."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setDragEnabled(True)
        self.setSelectionMode(self.SingleSelection)
        self.viewport().setAcceptDrops(False)
        self.setDropIndicatorShown(False)
        self.setDefaultDropAction(Qt.CopyAction)

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if not item:
            return
        payload = item.data(0, Qt.UserRole)
        if not payload:
            return

        md = QMimeData()
        md.setData("application/x-canalizaciones-item", json.dumps(payload).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(md)

        pixmap = self._build_drag_pixmap(item.text(0))
        if pixmap is not None:
            drag.setPixmap(pixmap)
            drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))

        drag.exec_(Qt.CopyAction)

    def _build_drag_pixmap(self, text: str) -> Optional[QPixmap]:
        if not text:
            return None
        fm = QFontMetrics(self.font())
        padding_x = 10
        padding_y = 6
        w = fm.horizontalAdvance(text) + padding_x * 2
        h = fm.height() + padding_y * 2
        if w <= 0 or h <= 0:
            return None

        pix = QPixmap(w, h)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        try:
            rect = pix.rect()
            p.setRenderHint(QPainter.Antialiasing, True)
            p.setBrush(QBrush(QColor("#f3f4f6")))
            p.setPen(QPen(QColor("#9ca3af")))
            p.drawRoundedRect(rect.adjusted(0, 0, -1, -1), 6, 6)
            p.setPen(QPen(QColor("#111827")))
            p.drawText(rect.adjusted(padding_x, padding_y, -padding_x, -padding_y), Qt.AlignLeft | Qt.AlignVCenter, text)
        finally:
            p.end()
        return pix


class LibraryPanel(QWidget):
    """Left Biblioteca panel with search + draggable items."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._equipment_items_by_id: Dict[str, Dict[str, Any]] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        root.addWidget(QLabel("Biblioteca"))

        self.btn_add_equipment = QPushButton("Agregar Equipo/Armario")
        self.btn_add_equipment.clicked.connect(self._open_add_equipment_dialog)
        root.addWidget(self.btn_add_equipment)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar...")
        self.search.textChanged.connect(self._apply_filter)
        root.addWidget(self.search)

        self.tree = LibraryTree()
        root.addWidget(self.tree, 1)

        self._reload()

    def set_equipment_items(self, items_by_id: Dict[str, Dict[str, Any]]) -> None:
        self._equipment_items_by_id = items_by_id or {}
        self._reload()

    def _reload(self) -> None:
        self.tree.clear()
        self.tree.setUpdatesEnabled(False)
        try:
            self._add_section("Equipos", self._equipment_payloads())
            self._add_section("GAP", [self._simple_payload("gap", "gap", "GAP")])
            self._add_section("Cámaras", [self._simple_payload("camera", "camera", "Cámara")])
            self.tree.expandAll()
        finally:
            self.tree.setUpdatesEnabled(True)
        self._apply_filter(self.search.text())

    def _equipment_payloads(self) -> List[Dict[str, Any]]:
        items = []
        for equip_id, meta in sorted(self._equipment_items_by_id.items(), key=lambda kv: str(kv[1].get("name", kv[0]))):
            name = str(meta.get("name", equip_id))
            payload = {
                "kind": "equipment",
                "type": str(equip_id),
                "label": name,
            }
            items.append(payload)
        return items

    def _simple_payload(self, kind: str, type_id: str, label: str) -> Dict[str, Any]:
        return {
            "kind": kind,
            "type": type_id,
            "label": label,
        }

    def _add_section(self, title: str, payloads: List[Dict[str, Any]]) -> None:
        parent = QTreeWidgetItem([title])
        parent.setFlags(parent.flags() & ~Qt.ItemIsDragEnabled)
        self.tree.addTopLevelItem(parent)

        for payload in payloads:
            label = str(payload.get("label", "") or payload.get("type", ""))
            child = QTreeWidgetItem([label])
            child.setData(0, Qt.UserRole, payload)
            child.setData(0, Qt.UserRole + 1, f"{label} {payload.get('type', '')} {payload.get('kind', '')}")
            child.setFlags(child.flags() | Qt.ItemIsDragEnabled)
            parent.addChild(child)

    def _apply_filter(self, text: str) -> None:
        needle = (text or "").strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            any_visible = False
            for j in range(top.childCount()):
                child = top.child(j)
                hay = str(child.data(0, Qt.UserRole + 1) or child.text(0)).lower()
                visible = not needle or needle in hay
                child.setHidden(not visible)
                any_visible = any_visible or visible
            top.setHidden(bool(needle) and not any_visible)

    def _find_section_item(self, title: str) -> Optional[QTreeWidgetItem]:
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            if top.text(0) == title:
                return top
        return None

    def _open_add_equipment_dialog(self) -> None:
        dlg = AddEquipmentDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return

        name, kind = dlg.get_values()
        if not name:
            return

        parent = self._find_section_item("Equipos")
        if parent is None:
            parent = QTreeWidgetItem(["Equipos"])
            parent.setFlags(parent.flags() & ~Qt.ItemIsDragEnabled)
            self.tree.addTopLevelItem(parent)

        needle = name.strip().lower()
        for i in range(parent.childCount()):
            if parent.child(i).text(0).strip().lower() == needle:
                QMessageBox.warning(self, "Equipos", f"Ya existe un equipo llamado '{name}'.")
                return

        payload: Dict[str, Any] = {"kind": "equipment", "type": kind, "label": name}

        child = QTreeWidgetItem([name])
        child.setData(0, Qt.UserRole, payload)
        child.setData(0, Qt.UserRole + 1, f"{name} {kind} equipment")
        child.setFlags(child.flags() | Qt.ItemIsDragEnabled)
        parent.addChild(child)
        parent.setExpanded(True)

        self._apply_filter(self.search.text())
        self.tree.setCurrentItem(child)
        self.tree.scrollToItem(child)


class AddEquipmentDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Agregar Equipo/Armario")

        root = QVBoxLayout(self)
        form = QFormLayout()
        root.addLayout(form)

        self.edt_name = QLineEdit()
        form.addRow("Nombre:", self.edt_name)

        self.cmb_type = QComboBox()
        self.cmb_type.addItems(["Equipo", "Armario"])
        form.addRow("Tipo:", self.cmb_type)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _on_accept(self) -> None:
        if not self.edt_name.text().strip():
            QMessageBox.warning(self, "Equipos", "El nombre es obligatorio.")
            return
        self.accept()

    def get_values(self) -> tuple[str, str]:
        name = self.edt_name.text().strip()
        type_label = self.cmb_type.currentText().strip()
        kind = "equipment" if type_label == "Equipo" else "cabinet"
        return name, kind
