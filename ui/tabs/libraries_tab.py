# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from data.repositories.lib_loader import load_lib
from domain.entities.models import Project


class LibrariesTab(QWidget):
    project_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._project: Optional[Project] = None

        root = QVBoxLayout(self)
        root.addWidget(QLabel('Bibliotecas cargadas (.lib) — editable: Enabled/Priority/Path'))

        self.tbl = QTableWidget(0, 4)
        self.tbl.setHorizontalHeaderLabels(['Enabled', 'Priority', 'Path', 'Kind'])
        self.tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.SelectedClicked)
        self.tbl.itemChanged.connect(self._on_item_changed)
        root.addWidget(self.tbl, 1)

    def set_project(self, project: Project) -> None:
        self._project = project
        self._refresh()

    def _refresh(self):
        if not self._project:
            return
        self.tbl.blockSignals(True)
        self.tbl.setRowCount(0)
        for lr in self._project.libraries:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            self.tbl.setItem(r, 0, QTableWidgetItem('true' if lr.enabled else 'false'))
            self.tbl.setItem(r, 1, QTableWidgetItem(str(lr.priority)))
            self.tbl.setItem(r, 2, QTableWidgetItem(lr.path))
            kind = ''
            try:
                res = load_lib(lr.path)
                kind = res.doc.get('kind', '')
            except Exception:
                kind = '??'
            self.tbl.setItem(r, 3, QTableWidgetItem(kind))
        self.tbl.blockSignals(False)

    def _on_item_changed(self, item: QTableWidgetItem):
        if not self._project:
            return
        row = item.row()
        if row < 0 or row >= len(self._project.libraries):
            return
        lr = self._project.libraries[row]
        col = item.column()
        if col == 0:
            lr.enabled = item.text().strip().lower() in ('1', 'true', 'yes', 'si', 'sí', 'on')
        elif col == 1:
            try:
                lr.priority = int(item.text())
            except Exception:
                pass
        elif col == 2:
            lr.path = item.text().strip()
        self.project_changed.emit()
