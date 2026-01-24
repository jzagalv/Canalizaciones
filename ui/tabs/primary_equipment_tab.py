# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Optional, List, Dict

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QMessageBox
)

from domain.entities.models import Project


class PrimaryEquipmentTab(QWidget):
    project_changed = pyqtSignal()

    COLS = ["Tag", "Tipo", "Nivel kV", "Ubicación", "Notas"]

    def __init__(self):
        super().__init__()
        self._project: Optional[Project] = None

        root = QVBoxLayout(self)
        root.addWidget(QLabel("Equipos Primarios del Proyecto"))

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("Agregar")
        self.btn_del = QPushButton("Eliminar")
        self.btn_add.clicked.connect(self._add_row)
        self.btn_del.clicked.connect(self._del_selected)
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_del)
        btn_row.addStretch(1)
        root.addLayout(btn_row)

        self.tbl = QTableWidget(0, len(self.COLS))
        self.tbl.setHorizontalHeaderLabels(self.COLS)
        self.tbl.itemChanged.connect(self._on_item_changed)
        root.addWidget(self.tbl, 1)

    def set_project(self, project: Project) -> None:
        self._project = project
        self._reload()

    def _reload(self) -> None:
        self.tbl.blockSignals(True)
        self.tbl.setRowCount(0)
        items: List[Dict] = (self._project.primary_equipment if self._project else []) or []
        for it in items:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            self.tbl.setItem(r, 0, QTableWidgetItem(str(it.get("tag",""))))
            self.tbl.setItem(r, 1, QTableWidgetItem(str(it.get("type",""))))
            self.tbl.setItem(r, 2, QTableWidgetItem(str(it.get("kv",""))))
            self.tbl.setItem(r, 3, QTableWidgetItem(str(it.get("location",""))))
            self.tbl.setItem(r, 4, QTableWidgetItem(str(it.get("notes",""))))
        self.tbl.blockSignals(False)

    def _add_row(self):
        if not self._project:
            return
        self._project.primary_equipment.append({"tag":"", "type":"", "kv":"", "location":"", "notes":""})
        self._reload()
        self.project_changed.emit()

    def _del_selected(self):
        if not self._project:
            return
        rows = sorted({i.row() for i in self.tbl.selectedIndexes()}, reverse=True)
        if not rows:
            return
        if QMessageBox.question(self, "Eliminar", f"¿Eliminar {len(rows)} fila(s)?") != QMessageBox.Yes:
            return
        for r in rows:
            try:
                self._project.primary_equipment.pop(r)
            except Exception:
                pass
        self._reload()
        self.project_changed.emit()

    def _on_item_changed(self, _item):
        if not self._project:
            return
        # write-back full table to project to keep things simple
        out: List[Dict] = []
        for r in range(self.tbl.rowCount()):
            out.append({
                "tag": self._get(r,0),
                "type": self._get(r,1),
                "kv": self._get(r,2),
                "location": self._get(r,3),
                "notes": self._get(r,4),
            })
        self._project.primary_equipment = out
        self.project_changed.emit()

    def _get(self, r, c) -> str:
        it = self.tbl.item(r,c)
        return it.text().strip() if it else ""
