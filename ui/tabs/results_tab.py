# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, List, Optional

from PyQt5.QtWidgets import (
    QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from domain.entities.models import Project
from domain.calculations.formatting import fmt_percent


class ResultsTab(QWidget):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)

        root.addWidget(QLabel('Resultados por tramo (edge)'))

        self.tbl = QTableWidget(0, 6)
        self.tbl.setHorizontalHeaderLabels(['EdgeId', 'Kind', 'Propuesta', 'Fill', 'Status', 'Notas'])
        self.tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tbl.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.tbl.verticalHeader().setVisible(False)
        root.addWidget(self.tbl, 1)

        self.lbl_warn = QLabel('')
        self.lbl_warn.setWordWrap(True)
        root.addWidget(self.lbl_warn)

    def set_results(self, project: Project, fill_results: Dict[str, Dict], warnings: List[str]) -> None:
        self.tbl.setRowCount(0)
        edges = list((project.canvas or {}).get('edges') or [])
        by_id = {e.get('id'): e for e in edges}

        for edge_id, sol in (fill_results or {}).items():
            e = by_id.get(edge_id) or {}
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            self.tbl.setItem(r, 0, QTableWidgetItem(str(edge_id)))
            self.tbl.setItem(r, 1, QTableWidgetItem(str(e.get('containment_kind', ''))))
            self.tbl.setItem(r, 2, QTableWidgetItem(""))
            fill_val = sol.get("fill_percent")
            fill_max = sol.get("fill_max_percent")
            if fill_max is not None and float(fill_max or 0.0) > 0:
                fill_text = f"{fmt_percent(fill_val)} (max {fmt_percent(fill_max)})"
            else:
                fill_text = f"{fmt_percent(fill_val)}"
            self.tbl.setItem(r, 3, QTableWidgetItem(fill_text))
            status = str(sol.get("status") or "")
            self.tbl.setItem(r, 4, QTableWidgetItem(status))
            self.tbl.setItem(r, 5, QTableWidgetItem(""))

        if warnings:
            self.lbl_warn.setText('Warnings:\n' + '\n'.join(f'- {w}' for w in warnings[:25]))
        else:
            self.lbl_warn.setText('')
