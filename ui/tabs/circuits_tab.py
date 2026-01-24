# -*- coding: utf-8 -*-
from __future__ import annotations

import uuid
from typing import Dict, List, Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from data.repositories.lib_merge import EffectiveCatalog
from domain.entities.models import Project


class CircuitsTab(QWidget):
    project_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._project: Optional[Project] = None
        self._active_node_id: Optional[str] = None
        self._eff: Optional[EffectiveCatalog] = None

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

        self.tbl = QTableWidget(0, 7)
        self.tbl.setHorizontalHeaderLabels([
            'Name', 'Service', 'CableRef', 'Qty', 'FromNode', 'ToNode', 'CircuitId'
        ])
        self.tbl.itemChanged.connect(self._on_item_changed)
        root.addWidget(self.tbl, 1)

        hint = QLabel('Tip: Para calcular rutas compartidas, define FromNode/ToNode como IDs de nodos del canvas.')
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

    # -------------------- internal --------------------
    def _refresh(self):
        if not self._project:
            return
        active_id = self._active_node_id if isinstance(self._active_node_id, str) else None
        self.lbl_active.setText(active_id or '-')
        self.tbl.blockSignals(True)
        self.tbl.setRowCount(0)
        for c in (self._project.circuits.get('items') or []):
            if active_id and c.get('equipment_node_id') != active_id:
                continue
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            self.tbl.setItem(r, 0, QTableWidgetItem(str(c.get('name', ''))))
            self.tbl.setItem(r, 1, QTableWidgetItem(str(c.get('service', 'power'))))
            self.tbl.setItem(r, 2, QTableWidgetItem(str(c.get('cable_ref', ''))))
            self.tbl.setItem(r, 3, QTableWidgetItem(str(c.get('qty', 1))))
            self.tbl.setItem(r, 4, QTableWidgetItem(str(c.get('from_node', ''))))
            self.tbl.setItem(r, 5, QTableWidgetItem(str(c.get('to_node', ''))))
            self.tbl.setItem(r, 6, QTableWidgetItem(str(c.get('id', ''))))
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
        cid = self.tbl.item(row, 6).text().strip() if self.tbl.item(row, 6) else ''
        if not cid:
            return
        self._project.circuits['items'] = [c for c in (self._project.circuits.get('items') or []) if c.get('id') != cid]
        self.project_changed.emit()
        self._refresh()

    def _on_item_changed(self, item: QTableWidgetItem):
        if not self._project:
            return
        row = item.row()
        cid = self.tbl.item(row, 6).text().strip() if self.tbl.item(row, 6) else ''
        if not cid:
            return
        c = next((x for x in (self._project.circuits.get('items') or []) if x.get('id') == cid), None)
        if not c:
            return
        c['name'] = self.tbl.item(row, 0).text() if self.tbl.item(row, 0) else c.get('name')
        c['service'] = self.tbl.item(row, 1).text() if self.tbl.item(row, 1) else c.get('service')
        c['cable_ref'] = self.tbl.item(row, 2).text() if self.tbl.item(row, 2) else c.get('cable_ref')
        try:
            c['qty'] = int(self.tbl.item(row, 3).text())
        except Exception:
            pass
        c['from_node'] = self.tbl.item(row, 4).text().strip() if self.tbl.item(row, 4) else c.get('from_node')
        c['to_node'] = self.tbl.item(row, 5).text().strip() if self.tbl.item(row, 5) else c.get('to_node')
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
