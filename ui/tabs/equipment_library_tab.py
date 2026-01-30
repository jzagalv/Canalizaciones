# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from PyQt5.QtCore import Qt, QMimeData, pyqtSignal
from PyQt5.QtGui import QDrag
from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QLabel

from domain.entities.models import Project


class EquipmentLibraryTab(QWidget):
    """Biblioteca de equipos (global, via .lib kind equipment_library).
    - Muestra items agrupados por categoría
    - Permite drag&drop al Canvas
    """

    project_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._project: Optional[Project] = None
        self._items_by_id: Dict[str, Dict[str, Any]] = {}

        root = QVBoxLayout(self)
        root.addWidget(QLabel("Biblioteca de Equipos (arrastrar al Canvas)"))

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Categoría / Equipo"])
        self.tree.setDragEnabled(True)
        self.tree.setSelectionMode(self.tree.SingleSelection)
        self.tree.viewport().setAcceptDrops(False)
        self.tree.setDropIndicatorShown(False)
        self.tree.setDefaultDropAction(Qt.CopyAction)

        # custom start drag
        self.tree.startDrag = self._start_drag  # type: ignore

        root.addWidget(self.tree, 1)

    def set_project(self, project: Project) -> None:
        self._project = project

    def set_equipment_items(self, items_by_id: Dict[str, Dict[str, Any]]) -> None:
        self._items_by_id = items_by_id or {}
        self._reload()

    def _reload(self):
        self.tree.clear()
        # group by category
        cats: Dict[str, QTreeWidgetItem] = {}
        for _id, it in sorted(self._items_by_id.items(), key=lambda kv: (str(kv[1].get("category","")), str(kv[1].get("name","")))):
            cat = str(it.get("category","(Sin categoría)"))
            if cat not in cats:
                parent = QTreeWidgetItem([cat])
                parent.setFlags(parent.flags() & ~Qt.ItemIsDragEnabled)
                self.tree.addTopLevelItem(parent)
                cats[cat] = parent
            child = QTreeWidgetItem([str(it.get("name", _id))])
            child.setData(0, Qt.UserRole, _id)
            child.setFlags(child.flags() | Qt.ItemIsDragEnabled)
            cats[cat].addChild(child)
        self.tree.expandAll()

    def _start_drag(self, supportedActions):
        item = self.tree.currentItem()
        if not item:
            return
        equip_id = item.data(0, Qt.UserRole)
        if not equip_id:
            return
        payload = {"kind": "equipment_item", "id": str(equip_id)}
        md = QMimeData()
        md.setData("application/x-canalizaciones-equipment", json.dumps(payload).encode("utf-8"))
        drag = QDrag(self.tree)
        drag.setMimeData(md)
        drag.exec_(Qt.CopyAction)
