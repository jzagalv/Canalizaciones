# -*- coding: utf-8 -*-
from __future__ import annotations

import uuid
from functools import partial
from typing import Dict, List, Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from data.repositories.lib_merge import EffectiveCatalog
from domain.entities.models import Project
from domain.services.canvas_nodes import NodeOption, list_canvas_nodes_for_circuits


class CircuitsTab(QWidget):
    project_changed = pyqtSignal()

    COL_NAME = 0
    COL_SERVICE = 1
    COL_CABLE = 2
    COL_QTY = 3
    COL_FROM = 4
    COL_TO = 5
    COL_STATUS = 6
    COL_ID = 7

    def __init__(self):
        super().__init__()
        self._project: Optional[Project] = None
        self._active_node_id: Optional[str] = None
        self._eff: Optional[EffectiveCatalog] = None
        self._node_options: List[NodeOption] = []
        self._node_options_by_id: Dict[str, NodeOption] = {}

        root = QVBoxLayout(self)

        top = QHBoxLayout()
        root.addLayout(top)
        top.addWidget(QLabel('Equipo activo:'))
        self.lbl_active = QLabel('-')
        self.lbl_active.setTextInteractionFlags(
            self.lbl_active.textInteractionFlags() | Qt.TextSelectableByMouse
        )
        top.addWidget(self.lbl_active, 1)

        self.btn_add = QPushButton('Agregar circuito')
        self.btn_add.clicked.connect(self._add_circuit)
        top.addWidget(self.btn_add)

        self.btn_del = QPushButton('Eliminar circuito')
        self.btn_del.clicked.connect(self._del_circuit)
        top.addWidget(self.btn_del)

        self.btn_template = QPushButton('Generar desde plantilla (perfil)')
        self.btn_template.clicked.connect(self._generate_from_template)
        top.addWidget(self.btn_template)

        self.tbl = QTableWidget(0, 8)
        self.tbl.setHorizontalHeaderLabels([
            'Name', 'Service', 'CableRef', 'Qty', 'Origen', 'Destino', 'Estado', 'CircuitId'
        ])
        self.tbl.itemChanged.connect(self._on_item_changed)
        root.addWidget(self.tbl, 1)

        hint = QLabel('Tip: Para calcular rutas compartidas, selecciona Origen/Destino desde los nodos del canvas.')
        hint.setWordWrap(True)
        root.addWidget(hint)

    def set_project(self, project: Project) -> None:
        self._project = project
        self._refresh()

    def set_effective_catalog(self, eff: Optional[EffectiveCatalog]) -> None:
        self._eff = eff

    def set_active_node(self, node) -> None:
        node_id = None
        if isinstance(node, dict):
            node_id = node.get('id') or node.get('node_id')
        else:
            node_id = node
        if node_id is not None:
            node_id = str(node_id).strip()
            if not node_id:
                node_id = None
        self._active_node_id = node_id or None
        self._refresh()

    def reload_node_lists(self) -> None:
        if not self._project:
            return
        self._refresh()

    # -------------------- internal --------------------
    def _refresh(self):
        if not self._project:
            return
        self._node_options = list_canvas_nodes_for_circuits(self._project)
        self._node_options_by_id = {opt.node_id: opt for opt in self._node_options}
        active_id = self._active_node_id if isinstance(self._active_node_id, str) else None
        self.lbl_active.setText(active_id or '-')
        self.tbl.blockSignals(True)
        self.tbl.setRowCount(0)
        for c in (self._project.circuits.get('items') or []):
            if active_id and c.get('equipment_node_id') != active_id:
                continue
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            self.tbl.setItem(r, self.COL_NAME, QTableWidgetItem(str(c.get('name', ''))))
            self.tbl.setItem(r, self.COL_SERVICE, QTableWidgetItem(str(c.get('service', 'power'))))
            self.tbl.setItem(r, self.COL_CABLE, QTableWidgetItem(str(c.get('cable_ref', ''))))
            self.tbl.setItem(r, self.COL_QTY, QTableWidgetItem(str(c.get('qty', 1))))

            from_id = str(c.get('from_node') or '')
            to_id = str(c.get('to_node') or '')

            cmb_from, missing_from = self._build_node_combo(self._node_options, from_id)
            cmb_to, missing_to = self._build_node_combo(self._node_options, to_id)

            cmb_from.currentIndexChanged.connect(partial(self._on_node_combo_changed, r, "from_node"))
            cmb_to.currentIndexChanged.connect(partial(self._on_node_combo_changed, r, "to_node"))

            self.tbl.setCellWidget(r, self.COL_FROM, cmb_from)
            self.tbl.setCellWidget(r, self.COL_TO, cmb_to)

            status = "Incompleto" if missing_from or missing_to or not from_id or not to_id else "OK"
            status_item = QTableWidgetItem(status)
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
            self.tbl.setItem(r, self.COL_STATUS, status_item)

            item_id = QTableWidgetItem(str(c.get('id', '')))
            item_id.setFlags(item_id.flags() & ~Qt.ItemIsEditable)
            self.tbl.setItem(r, self.COL_ID, item_id)
        self.tbl.blockSignals(False)

    def _add_circuit(self):
        if not self._project:
            return
        if not self._active_node_id:
            QMessageBox.information(self, 'Selecciona un equipo', 'Selecciona un equipo en el Canvas para asociar circuitos.')
            return
        cid = f"C{uuid.uuid4().hex[:8]}"
        self._project.circuits.setdefault('items', []).append({
            'id': cid,
            'equipment_node_id': self._active_node_id,
            'name': 'Nuevo circuito',
            'service': 'power',
            'cable_ref': '',
            'qty': 1,
            'from_node': self._active_node_id,
            'to_node': '',
        })
        self.project_changed.emit()
        self._refresh()

    def _del_circuit(self):
        if not self._project:
            return
        row = self.tbl.currentRow()
        if row < 0:
            return
        cid = self.tbl.item(row, self.COL_ID).text().strip() if self.tbl.item(row, self.COL_ID) else ''
        if not cid:
            return
        self._project.circuits['items'] = [c for c in (self._project.circuits.get('items') or []) if c.get('id') != cid]
        self.project_changed.emit()
        self._refresh()

    def _on_item_changed(self, item: QTableWidgetItem):
        if not self._project:
            return
        if item.column() in (self.COL_STATUS, self.COL_ID):
            return
        row = item.row()
        cid = self.tbl.item(row, self.COL_ID).text().strip() if self.tbl.item(row, self.COL_ID) else ''
        if not cid:
            return
        c = next((x for x in (self._project.circuits.get('items') or []) if x.get('id') == cid), None)
        if not c:
            return
        c['name'] = self.tbl.item(row, self.COL_NAME).text() if self.tbl.item(row, self.COL_NAME) else c.get('name')
        c['service'] = self.tbl.item(row, self.COL_SERVICE).text() if self.tbl.item(row, self.COL_SERVICE) else c.get('service')
        c['cable_ref'] = self.tbl.item(row, self.COL_CABLE).text() if self.tbl.item(row, self.COL_CABLE) else c.get('cable_ref')
        try:
            c['qty'] = int(self.tbl.item(row, self.COL_QTY).text())
        except Exception:
            pass
        self.project_changed.emit()

    def _generate_from_template(self):
        if not self._project:
            return
        if not self._active_node_id:
            QMessageBox.information(self, 'Selecciona un equipo', 'Selecciona un equipo en el Canvas primero.')
            return
        if not self._eff:
            QMessageBox.information(self, 'Bibliotecas', 'Primero valida/combina bibliotecas (boton en barra superior).')
            return

        # pick first applicable template (best effort) â€” later we can choose via dialog
        templates = list(self._eff.templates.get('equipment_templates_by_id', {}).values())
        profile = self._project.active_profile
        tpl = next((t for t in templates if profile in (t.get('applies_to_profiles') or [])), None)
        if not tpl:
            QMessageBox.information(self, 'Plantillas', 'No se encontro una plantilla aplicable al perfil actual.')
            return

        created = 0
        for cir in (tpl.get('circuits') or []):
            qty = int(cir.get('qty', 1) or 1)
            cid = f"C{uuid.uuid4().hex[:8]}"
            self._project.circuits.setdefault('items', []).append({
                'id': cid,
                'equipment_node_id': self._active_node_id,
                'name': str(cir.get('name', cir.get('id', 'Circuito'))),
                'service': str(cir.get('service', 'power')),
                'cable_ref': str(cir.get('cable_ref', '')),
                'qty': qty,
                'from_node': self._active_node_id,
                'to_node': '',
                'template_id': tpl.get('id'),
            })
            created += 1

        self._project.circuits['source'] = 'generated_from_templates'
        self.project_changed.emit()
        self._refresh()
        QMessageBox.information(self, 'Plantillas', f'Se generaron {created} circuitos desde plantilla.')

    def _build_node_combo(self, node_options: List[NodeOption], selected_id: str):
        combo = QComboBox()
        combo.addItem("", "")
        for opt in node_options:
            combo.addItem(opt.display_text, opt.node_id)

        missing = False
        selected_id = str(selected_id or "")
        if selected_id:
            idx = combo.findData(selected_id)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                combo.insertItem(0, "(no encontrado)", selected_id)
                combo.setCurrentIndex(0)
                missing = True
        return combo, missing

    def _on_node_combo_changed(self, row: int, field: str):
        if not self._project:
            return
        item_id = self.tbl.item(row, self.COL_ID)
        if not item_id:
            return
        cid = item_id.text().strip()
        if not cid:
            return
        c = next((x for x in (self._project.circuits.get('items') or []) if x.get('id') == cid), None)
        if not c:
            return
        combo = self.tbl.cellWidget(row, self.COL_FROM if field == "from_node" else self.COL_TO)
        if not isinstance(combo, QComboBox):
            return
        node_id = combo.currentData()
        c[field] = str(node_id or "")
        self._update_row_status(row)
        self.project_changed.emit()

    def _update_row_status(self, row: int) -> None:
        item_id = self.tbl.item(row, self.COL_ID)
        if not item_id or not self._project:
            return
        cid = item_id.text().strip()
        if not cid:
            return
        c = next((x for x in (self._project.circuits.get('items') or []) if x.get('id') == cid), None)
        if not c:
            return
        from_id = str(c.get("from_node") or "")
        to_id = str(c.get("to_node") or "")
        missing = False
        if not from_id or from_id not in self._node_options_by_id:
            missing = True
        if not to_id or to_id not in self._node_options_by_id:
            missing = True
        status = "Incompleto" if missing else "OK"
        self.tbl.blockSignals(True)
        status_item = self.tbl.item(row, self.COL_STATUS)
        if status_item is None:
            status_item = QTableWidgetItem(status)
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
            self.tbl.setItem(row, self.COL_STATUS, status_item)
        else:
            status_item.setText(status)
        self.tbl.blockSignals(False)
