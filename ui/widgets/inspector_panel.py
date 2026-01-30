# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, List, Optional

from PyQt5.QtWidgets import (
    QFormLayout,
    QLabel,
    QScrollArea,
    QToolBox,
    QVBoxLayout,
    QWidget,
)

from domain.calculations.formatting import fmt_percent


class InspectorPanel(QScrollArea):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("InspectorPanel")
        self.setProperty("role", "inspector")
        self.setWidgetResizable(True)
        container = QWidget()
        self.setWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.toolbox = QToolBox()
        layout.addWidget(self.toolbox)
        layout.addStretch(1)

        self._geo = self._section_form()
        self._canal = self._section_form()
        self._occup = self._section_form()
        self._circuits = self._section_list()
        self._obs = self._section_list()

        self.toolbox.addItem(self._geo["widget"], "Geometría")
        self.toolbox.addItem(self._canal["widget"], "Canalización")
        self.toolbox.addItem(self._occup["widget"], "Ocupación")
        self.toolbox.addItem(self._circuits["widget"], "Circuitos del tramo")
        self.toolbox.addItem(self._obs["widget"], "Observaciones")

        self.clear()

    def _section_form(self) -> Dict[str, object]:
        widget = QWidget()
        form = QFormLayout(widget)
        form.setContentsMargins(8, 8, 8, 8)
        form.setSpacing(6)
        return {"widget": widget, "form": form, "labels": {}}

    def _section_list(self) -> Dict[str, object]:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        return {"widget": widget, "layout": layout, "labels": []}

    def clear(self) -> None:
        self._clear_form(self._geo)
        self._clear_form(self._canal)
        self._clear_form(self._occup)
        self._clear_list(self._circuits, ["(sin selección)"])
        self._clear_list(self._obs, ["(sin selección)"])

    def _clear_form(self, section: Dict[str, object]) -> None:
        form = section["form"]
        while form.rowCount():
            form.removeRow(0)

    def _clear_list(self, section: Dict[str, object], items: List[str]) -> None:
        layout = section["layout"]
        while layout.count():
            item = layout.takeAt(0)
            if item and item.widget():
                item.widget().setParent(None)
        for text in items:
            layout.addWidget(QLabel(text))

    def set_selection(self, project: Optional[object], selection: Dict[str, object]) -> None:
        if not selection or not project:
            self.clear()
            return
        kind = selection.get("kind")
        if kind == "edge":
            self._fill_edge(project, selection)
        elif kind == "node":
            self._fill_node(project, selection)
        else:
            self.clear()

    def _fill_node(self, project: object, selection: Dict[str, object]) -> None:
        self._clear_form(self._geo)
        self._clear_form(self._canal)
        self._clear_form(self._occup)
        self._clear_list(self._circuits, ["(no aplica)"])
        self._clear_list(self._obs, ["(sin observaciones)"])
        form = self._geo["form"]
        node_id = str(selection.get("id") or "")
        name = str(selection.get("name") or "")
        node_type = str(selection.get("type") or selection.get("kind") or "")
        form.addRow("Nodo:", QLabel(node_id))
        form.addRow("Nombre:", QLabel(name))
        form.addRow("Tipo:", QLabel(node_type))

    def _fill_edge(self, project: object, selection: Dict[str, object]) -> None:
        calc = getattr(project, "calc_state", None)
        if not isinstance(calc, dict):
            calc = getattr(project, "_calc", None)
        edge_id = str(selection.get("id") or "")
        props = selection.get("props") if isinstance(selection.get("props"), dict) else {}
        tag = str(props.get("tag") or "")
        self._clear_form(self._geo)
        form = self._geo["form"]
        form.addRow("Tramo:", QLabel(edge_id))
        form.addRow("TAG:", QLabel(tag or "SIN TAG"))

        self._clear_form(self._canal)
        cform = self._canal["form"]
        cform.addRow("Tipo:", QLabel(str(props.get("conduit_type") or "")))
        cform.addRow("Tamaño:", QLabel(str(props.get("size") or "")))
        cform.addRow("Cantidad:", QLabel(str(props.get("quantity") or "")))

        self._clear_form(self._occup)
        oform = self._occup["form"]
        fill_text = "(Recalcular)"
        max_text = ""
        if isinstance(calc, dict):
            fill_results = calc.get("fill_results") or {}
            entry = fill_results.get(edge_id) if isinstance(fill_results, dict) else None
            if entry:
                fill_text = fmt_percent(entry.get("fill_percent"))
                max_text = fmt_percent(entry.get("fill_max_percent"))
        oform.addRow("Utilizado:", QLabel(fill_text))
        oform.addRow("Máximo:", QLabel(max_text))

        circuits = []
        if isinstance(calc, dict):
            edge_to_circuits = calc.get("edge_to_circuits") or {}
            circuits = list(edge_to_circuits.get(edge_id, []) or [])
        if circuits:
            items = []
            circuits_data = list((getattr(project, "circuits", {}) or {}).get("items") or [])
            by_id = {str(c.get("id") or ""): c for c in circuits_data if c.get("id")}
            for cid in circuits:
                cid = str(cid)
                c = by_id.get(cid) or {}
                label = str(c.get("tag") or c.get("name") or cid)
                items.append(label)
            self._clear_list(self._circuits, items)
        else:
            self._clear_list(self._circuits, ["(sin circuitos)"])
        self._clear_list(self._obs, ["(sin observaciones)"])
