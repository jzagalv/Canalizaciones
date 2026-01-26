# -*- coding: utf-8 -*-
from __future__ import annotations

import uuid
from functools import partial
from typing import Any, Dict, List, Optional, Tuple

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from data.repositories.lib_merge import EffectiveCatalog
from domain.entities.models import Project
from domain.materials.material_service import MaterialService
from domain.services.canvas_nodes import NodeOption, list_canvas_nodes_for_circuits


class CircuitsTab(QWidget):
    project_changed = pyqtSignal()

    COL_NAME = 0
    COL_SERVICE = 1
    COL_CABLE = 2
    COL_QTY = 3
    COL_FROM = 4
    COL_TO = 5
    COL_ROUTE = 6
    COL_STATUS = 7
    COL_ID = 8

    def __init__(self):
        super().__init__()
        self._project: Optional[Project] = None
        self._active_node_id: Optional[str] = None
        self._eff: Optional[EffectiveCatalog] = None
        self._material_service: Optional[MaterialService] = None
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

        self.tbl = QTableWidget(0, 9)
        self.tbl.setHorizontalHeaderLabels([
            'Name', 'Service', 'Cable', 'Qty', 'Origen', 'Destino', 'Recorrido', 'Estado', 'CircuitId'
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
        self._refresh()

    def set_material_service(self, material_service: Optional[MaterialService]) -> None:
        self._material_service = material_service
        self._refresh()

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
        route_ctx = self._build_route_context()
        self.tbl.blockSignals(True)
        self.tbl.setRowCount(0)
        for c in (self._project.circuits.get('items') or []):
            if active_id and c.get('equipment_node_id') != active_id:
                continue
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            self.tbl.setItem(r, self.COL_NAME, QTableWidgetItem(str(c.get('name', ''))))
            self.tbl.setItem(r, self.COL_SERVICE, QTableWidgetItem(str(c.get('service', 'power'))))
            cable_combo, missing_cable = self._build_cable_combo(
                str(c.get('service', 'power')),
                str(c.get('cable_ref', '')),
            )
            cable_combo.currentIndexChanged.connect(partial(self._on_cable_combo_changed, r))
            self.tbl.setCellWidget(r, self.COL_CABLE, cable_combo)
            self.tbl.setItem(r, self.COL_QTY, QTableWidgetItem(str(c.get('qty', 1))))

            from_id = str(c.get('from_node') or '')
            to_id = str(c.get('to_node') or '')

            cmb_from, missing_from = self._build_node_combo(self._node_options, from_id)
            cmb_to, missing_to = self._build_node_combo(self._node_options, to_id)

            cmb_from.currentIndexChanged.connect(partial(self._on_node_combo_changed, r, "from_node"))
            cmb_to.currentIndexChanged.connect(partial(self._on_node_combo_changed, r, "to_node"))

            self.tbl.setCellWidget(r, self.COL_FROM, cmb_from)
            self.tbl.setCellWidget(r, self.COL_TO, cmb_to)

            route_item = QTableWidgetItem(self._route_text_for_circuit(c, route_ctx))
            route_item.setFlags(route_item.flags() & ~Qt.ItemIsEditable)
            self.tbl.setItem(r, self.COL_ROUTE, route_item)

            status = self._row_status(missing_from, missing_to, missing_cable, from_id, to_id)
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
        if item.column() in (self.COL_STATUS, self.COL_ID, self.COL_CABLE, self.COL_ROUTE):
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
        try:
            c['qty'] = int(self.tbl.item(row, self.COL_QTY).text())
        except Exception:
            pass
        if item.column() == self.COL_SERVICE:
            self._refresh_cable_combo(row)
        self._update_row_status(row)
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

    def _build_cable_combo(self, service: str, selected_id: str):
        combo = QComboBox()
        combo.blockSignals(True)
        combo.setProperty("valid_cable_ids", [])
        combo.setProperty("no_matches", False)
        combo.setProperty("missing_cable", False)
        service_norm = str(service or "").strip().lower() or "power"
        cables = self._list_cables_for_service(service_norm)
        valid_ids = [str(c.get("id") or "") for c in cables if c.get("id")]
        if cables:
            combo.addItem("(sin selecciÃ³n)", "")
            for cable in cables:
                cid = str(cable.get("id") or "")
                name = str(cable.get("name") or cable.get("Nombre") or cid)
                combo.addItem(name, cid)
        else:
            combo.addItem("(sin cables compatibles)", "")
            combo.setProperty("no_matches", True)
        combo.setProperty("valid_cable_ids", valid_ids)

        selected_id = str(selected_id or "").strip()
        missing = False
        if selected_id:
            idx = combo.findData(selected_id)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                label = self._label_for_missing_cable(selected_id, service_norm)
                combo.insertItem(0, label, selected_id)
                combo.setCurrentIndex(0)
                missing = True

        if not cables:
            combo.setToolTip(f"Sin cables para servicio: {service_norm}")
            missing = True

        combo.setProperty("missing_cable", missing)
        combo.blockSignals(False)
        return combo, missing

    def _label_for_missing_cable(self, cable_id: str, service_norm: str) -> str:
        cable = self._find_cable_by_id(cable_id)
        if not cable:
            return f"(no encontrado) {cable_id}"
        name = str(cable.get("name") or cable_id)
        found_service = str(cable.get("service") or "").strip().lower()
        if found_service and found_service != service_norm:
            return f"(no coincide) {name}"
        return f"(no encontrado) {name}"

    def _find_cable_by_id(self, cable_id: str) -> Optional[Dict[str, object]]:
        cable_id_norm = str(cable_id or "").strip().lower()
        if self._eff:
            for cable in (self._eff.material.get("conductors_by_id") or {}).values():
                if str(cable.get("id") or "").strip().lower() == cable_id_norm:
                    return cable
        if self._material_service:
            for cable in self._material_service.list_conductors(None):
                if str(cable.get("id") or "").strip().lower() == cable_id_norm:
                    return cable
        return None

    def _list_cables_for_service(self, service: str) -> List[Dict[str, object]]:
        if not self._eff:
            return []
        service_norm = str(service or "").strip().lower()
        cables = list((self._eff.material.get("conductors_by_id") or {}).values())
        if service_norm:
            cables = [c for c in cables if str(c.get("service") or "").strip().lower() == service_norm]
        cables.sort(key=lambda c: str(c.get("name") or c.get("id") or ""))
        return cables

    def _on_cable_combo_changed(self, row: int) -> None:
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
        combo = self.tbl.cellWidget(row, self.COL_CABLE)
        if not isinstance(combo, QComboBox):
            return
        cable_id = str(combo.currentData() or "")
        c["cable_ref"] = cable_id
        self._sync_cable_combo_warning(combo)
        self._update_row_status(row)
        self.project_changed.emit()

    def _sync_cable_combo_warning(self, combo: QComboBox) -> None:
        no_matches = bool(combo.property("no_matches"))
        valid_ids = combo.property("valid_cable_ids") or []
        current = combo.currentData()
        if no_matches:
            combo.setProperty("missing_cable", True)
            return
        if current and str(current) not in [str(v) for v in valid_ids]:
            combo.setProperty("missing_cable", True)
            return
        combo.setProperty("missing_cable", False)

    def _refresh_cable_combo(self, row: int) -> None:
        if not self._project:
            return
        service_item = self.tbl.item(row, self.COL_SERVICE)
        service = service_item.text() if service_item else "power"
        item_id = self.tbl.item(row, self.COL_ID)
        if not item_id:
            return
        cid = item_id.text().strip()
        if not cid:
            return
        c = next((x for x in (self._project.circuits.get('items') or []) if x.get('id') == cid), None)
        if not c:
            return
        selected = str(c.get("cable_ref") or "")
        combo, missing = self._build_cable_combo(service, selected)
        combo.currentIndexChanged.connect(partial(self._on_cable_combo_changed, row))
        self.tbl.setCellWidget(row, self.COL_CABLE, combo)
        self._update_row_status(row, cable_missing=missing)

    def _row_status(
        self,
        missing_from: bool,
        missing_to: bool,
        missing_cable: bool,
        from_id: str,
        to_id: str,
    ) -> str:
        if missing_from or missing_to or not from_id or not to_id:
            return "Incompleto"
        if missing_cable:
            return "Advertencia"
        return "OK"

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

    def _update_row_status(self, row: int, cable_missing: Optional[bool] = None) -> None:
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
        missing_from = not from_id or from_id not in self._node_options_by_id
        missing_to = not to_id or to_id not in self._node_options_by_id
        if cable_missing is None:
            cable_missing = self._row_has_cable_warning(row)
        status = self._row_status(missing_from, missing_to, bool(cable_missing), from_id, to_id)
        self.tbl.blockSignals(True)
        status_item = self.tbl.item(row, self.COL_STATUS)
        if status_item is None:
            status_item = QTableWidgetItem(status)
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
            self.tbl.setItem(row, self.COL_STATUS, status_item)
        else:
            status_item.setText(status)
        self.tbl.blockSignals(False)

    def _row_has_cable_warning(self, row: int) -> bool:
        combo = self.tbl.cellWidget(row, self.COL_CABLE)
        if not isinstance(combo, QComboBox):
            return False
        return bool(combo.property("missing_cable"))

    def _build_route_context(self) -> Dict[str, Any]:
        canvas = self._project.canvas if self._project else {}
        nodes = list((canvas or {}).get("nodes") or [])
        edges = list((canvas or {}).get("edges") or [])
        nodes_by_id = {str(n.get("id") or ""): n for n in nodes if n.get("id")}
        edge_by_id = {str(e.get("id") or ""): e for e in edges if e.get("id")}
        adj: Dict[str, List[Tuple[str, str, float]]] = {}

        for e in edges:
            from_id, to_id = self._edge_endpoints(e)
            if not from_id or not to_id:
                continue
            eid = str(e.get("id") or "")
            if not eid:
                continue
            w = self._edge_weight(e, nodes_by_id)
            adj.setdefault(from_id, []).append((to_id, eid, w))
            adj.setdefault(to_id, []).append((from_id, eid, w))

        return {"adj": adj, "edge_by_id": edge_by_id, "nodes_by_id": nodes_by_id}

    def _edge_endpoints(self, edge: Dict[str, Any]) -> Tuple[str, str]:
        from_id = str(edge.get("from_node") or edge.get("from") or "")
        to_id = str(edge.get("to_node") or edge.get("to") or "")
        return from_id, to_id

    def _edge_weight(self, edge: Dict[str, Any], nodes_by_id: Dict[str, Dict[str, Any]]) -> float:
        if edge.get("length_m") is not None:
            try:
                return float(edge.get("length_m"))
            except Exception:
                pass
        a = nodes_by_id.get(str(edge.get("from_node") or edge.get("from") or ""))
        b = nodes_by_id.get(str(edge.get("to_node") or edge.get("to") or ""))
        if not (a and b):
            return 1.0
        try:
            dx = float(a.get("x", 0)) - float(b.get("x", 0))
            dy = float(a.get("y", 0)) - float(b.get("y", 0))
        except Exception:
            return 1.0
        return (dx * dx + dy * dy) ** 0.5 * 0.05

    def _shortest_path_edges(self, start: str, goal: str, adj: Dict[str, List[Tuple[str, str, float]]]) -> Optional[List[str]]:
        if start == goal:
            return []
        if start not in adj or goal not in adj:
            return None
        import heapq

        pq: List[Tuple[float, str]] = [(0.0, start)]
        dist: Dict[str, float] = {start: 0.0}
        prev: Dict[str, Tuple[str, str]] = {}
        visited = set()

        while pq:
            d, u = heapq.heappop(pq)
            if u in visited:
                continue
            visited.add(u)
            if u == goal:
                break
            for v, eid, w in adj.get(u, []):
                nd = d + w
                if nd < dist.get(v, 1e18):
                    dist[v] = nd
                    prev[v] = (u, eid)
                    heapq.heappush(pq, (nd, v))

        if goal not in prev and goal != start:
            return None

        path_edges: List[str] = []
        cur = goal
        while cur != start:
            u, eid = prev[cur]
            path_edges.append(eid)
            cur = u
        path_edges.reverse()
        return path_edges

    def _route_text_for_circuit(self, circuit: Dict[str, Any], route_ctx: Dict[str, Any]) -> str:
        from_id = str(circuit.get("from_node") or "")
        to_id = str(circuit.get("to_node") or "")
        if not from_id or not to_id:
            return "(sin ruta)"
        path = self._shortest_path_edges(from_id, to_id, route_ctx.get("adj") or {})
        if not path:
            return "(sin ruta)"
        edge_by_id = route_ctx.get("edge_by_id") or {}
        labels: List[str] = []
        for eid in path:
            edge = edge_by_id.get(eid) or {}
            labels.append(self._edge_label(edge))
        return " -> ".join(labels) if labels else "(sin ruta)"

    def _edge_label(self, edge: Dict[str, Any]) -> str:
        props = edge.get("props") if isinstance(edge.get("props"), dict) else {}
        label = props.get("tag") or props.get("label") or props.get("name")
        if not label:
            label = edge.get("tag") or edge.get("label") or edge.get("name")
        if label:
            return str(label)
        edge_id = str(edge.get("id") or "")
        return edge_id[:6] if edge_id else "(sin id)"
