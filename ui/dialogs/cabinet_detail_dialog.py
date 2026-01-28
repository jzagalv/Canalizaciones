# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from typing import Dict, List, Optional, Set, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush, QPen, QPainter, QFont
from PyQt5.QtWidgets import (
    QDialog,
    QGraphicsEllipseItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from domain.calculations.formatting import fmt2, fmt_percent
from domain.materials.material_service import MaterialService
from domain.services.cable_layout import expand_cable_items, layout_cables_in_circle, layout_cables_in_rect


class CabinetDetailDialog(QDialog):
    def __init__(
        self,
        parent: Optional[object] = None,
        project: Optional[object] = None,
        node_id: Optional[str] = None,
        material_service: Optional[MaterialService] = None,
        equipment_items_by_id: Optional[Dict[str, Dict[str, object]]] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ventana Armario/Tablero")
        self.setModal(False)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)
        self.setSizeGripEnabled(True)
        self.setMinimumSize(900, 620)
        self.resize(1200, 760)

        self._project = project
        self._node_id = str(node_id or "")
        self._material_service = material_service
        self._equipment_items_by_id = dict(equipment_items_by_id or {})

        self._build_ui()
        self._load_data()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        splitter.addWidget(left)
        left.setMinimumWidth(340)
        left.setMaximumWidth(460)

        left_layout.addWidget(QLabel("Tramos conectados"))
        self.tbl_edges = QTableWidget(0, 4)
        self.tbl_edges.setHorizontalHeaderLabels(
            ["Tramo (TAG)", "Servicio", "% Utilizado", "% Disponible"]
        )
        self.tbl_edges.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tbl_edges.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tbl_edges.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tbl_edges.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.tbl_edges.verticalHeader().setVisible(False)
        self.tbl_edges.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_edges.setSelectionMode(QTableWidget.NoSelection)
        left_layout.addWidget(self.tbl_edges, 1)

        left_layout.addWidget(QLabel("Cables"))
        self.tbl_cables = QTableWidget(0, 6)
        self.tbl_cables.setHorizontalHeaderLabels(
            ["TAG", "Cable", "Servicio", "Sección (mm²)", "Tramo", "Canalización"]
        )
        self.tbl_cables.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tbl_cables.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl_cables.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tbl_cables.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.tbl_cables.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.tbl_cables.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.tbl_cables.verticalHeader().setVisible(False)
        self.tbl_cables.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_cables.setSelectionMode(QTableWidget.NoSelection)
        left_layout.addWidget(self.tbl_cables, 1)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        splitter.addWidget(right)

        self._view_height = 0

        top_row = QHBoxLayout()
        right_layout.addLayout(top_row)

        self.front_scene = QGraphicsScene(self)
        self.front_view = QGraphicsView(self.front_scene)
        self.front_view.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        self._front_container = self._wrap_view(self.front_view, "Vista frontal")
        top_row.addWidget(self._front_container)

        self.side_scene = QGraphicsScene(self)
        self.side_view = QGraphicsView(self.side_scene)
        self.side_view.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        self._side_container = self._wrap_view(self.side_view, "Vista lateral")
        top_row.addWidget(self._side_container)

        self.bottom_scene = QGraphicsScene(self)
        self.bottom_view = QGraphicsView(self.bottom_scene)
        self.bottom_view.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        self._bottom_container = self._wrap_view(self.bottom_view, "Vista inferior")
        right_layout.addWidget(self._bottom_container, 1)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

    def _wrap_view(self, view: QGraphicsView, title: str) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(QLabel(title))
        layout.addWidget(view, 1)
        return container

    def _load_data(self) -> None:
        if not self._project or not self._node_id:
            return
        node = self._find_node(self._node_id)
        if not node:
            return
        edges = self._connected_edges(self._node_id)
        self._populate_edges_table(edges)
        conduits = self._collect_conduits(edges)
        self._populate_cables_table(conduits)
        dims = self._equipment_dimensions_mm(node)
        self._render_front_view(node, dims)
        self._render_side_view(node, dims)
        self._render_bottom_view(node, conduits, dims)

    def _find_node(self, node_id: str) -> Optional[Dict[str, object]]:
        nodes = list((getattr(self._project, "canvas", {}) or {}).get("nodes") or [])
        for node in nodes:
            if str(node.get("id") or "") == str(node_id):
                return node
        return None

    def _connected_edges(self, node_id: str) -> List[Dict[str, object]]:
        edges = list((getattr(self._project, "canvas", {}) or {}).get("edges") or [])
        connected = []
        for edge in edges:
            from_id = str(edge.get("from_node") or edge.get("from") or "")
            to_id = str(edge.get("to_node") or edge.get("to") or "")
            if str(node_id) in (from_id, to_id):
                connected.append(edge)
        return connected

    def _calc_context(self) -> Optional[Dict[str, object]]:
        calc = getattr(self._project, "_calc", None) if self._project else None
        return calc if isinstance(calc, dict) else None

    def _equipment_dimensions_mm(self, node: Dict[str, object]) -> Tuple[float, float, float]:
        width = 600.0
        height = 800.0
        depth = 400.0
        library_id = str(node.get("library_item_id") or "")
        if library_id:
            meta = self._equipment_items_by_id.get(library_id) or {}
            dims = meta.get("dimensions_mm") if isinstance(meta.get("dimensions_mm"), dict) else {}
            width = float(dims.get("width") or width)
            height = float(dims.get("height") or height)
            depth = float(dims.get("depth") or depth)
        return max(10.0, width), max(10.0, height), max(10.0, depth)

    def _equipment_cable_access(self, node: Dict[str, object]) -> str:
        library_id = str(node.get("library_item_id") or "")
        if library_id:
            meta = self._equipment_items_by_id.get(library_id) or {}
            access = str(meta.get("cable_access") or "").strip().lower()
            if access in ("top", "superior"):
                return "top"
        return "bottom"

    def _edge_tag(self, edge: Dict[str, object]) -> str:
        props = edge.get("props") if isinstance(edge.get("props"), dict) else {}
        tag = str(props.get("tag") or "").strip()
        return tag or "SIN TAG"

    def _populate_edges_table(self, edges: List[Dict[str, object]]) -> None:
        self.tbl_edges.setRowCount(0)
        if not edges:
            self._set_edges_placeholder("No hay tramos conectados")
            return
        self.tbl_edges.setEnabled(True)

        calc = self._calc_context()
        edge_to_circuits = calc.get("edge_to_circuits") if calc else None
        fill_results = calc.get("fill_results") if calc else None
        circuits_by_id = self._circuits_by_id()

        for edge in edges:
            edge_id = str(edge.get("id") or "")
            tag = self._edge_tag(edge)
            service = self._edge_service(edge_id, edge_to_circuits, circuits_by_id)
            util_text = ""
            avail_text = ""
            if isinstance(fill_results, dict):
                entry = fill_results.get(edge_id) or {}
                fill_percent = entry.get("fill_percent")
                fill_max = entry.get("fill_max_percent")
                if fill_percent is not None:
                    util_text = fmt_percent(fill_percent)
                    avail_text = fmt_percent(self._available_percent(fill_percent, fill_max))
                else:
                    util_text = "(Recalcular)"
            elif calc is None:
                util_text = "(Recalcular)"

            row = self.tbl_edges.rowCount()
            self.tbl_edges.insertRow(row)
            self.tbl_edges.setItem(row, 0, QTableWidgetItem(tag))
            self.tbl_edges.setItem(row, 1, QTableWidgetItem(service))
            self.tbl_edges.setItem(row, 2, QTableWidgetItem(util_text))
            self.tbl_edges.setItem(row, 3, QTableWidgetItem(avail_text))

    def _set_edges_placeholder(self, text: str) -> None:
        self.tbl_edges.setRowCount(0)
        self.tbl_edges.insertRow(0)
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        self.tbl_edges.setItem(0, 0, item)
        self.tbl_edges.setItem(0, 1, QTableWidgetItem(""))
        self.tbl_edges.setItem(0, 2, QTableWidgetItem(""))
        self.tbl_edges.setItem(0, 3, QTableWidgetItem(""))
        self.tbl_edges.setEnabled(False)

    def _populate_cables_table(self, conduits: List[Dict[str, object]]) -> None:
        self.tbl_cables.setRowCount(0)
        calc = self._calc_context()
        edge_to_circuits = calc.get("edge_to_circuits") if calc else None
        if not isinstance(edge_to_circuits, dict):
            self._set_cables_placeholder("Ejecuta Recalcular para ver cables")
            return

        circuits_by_id = self._circuits_by_id()
        rows = 0
        self.tbl_cables.setEnabled(True)
        for conduit in conduits:
            edge_tag = str(conduit.get("edge_tag") or "")
            conduit_tag = str(conduit.get("conduit_tag") or "")
            for entry in list(conduit.get("cables") or []):
                cid = str(entry.get("circuit_id") or "")
                circuit = circuits_by_id.get(cid)
                if not circuit:
                    continue
                tag_c, cable_label, service, area_mm2, _ = self._circuit_display_info(circuit)
                row = self.tbl_cables.rowCount()
                self.tbl_cables.insertRow(row)
                self.tbl_cables.setItem(row, 0, QTableWidgetItem(tag_c))
                self.tbl_cables.setItem(row, 1, QTableWidgetItem(cable_label))
                self.tbl_cables.setItem(row, 2, QTableWidgetItem(service))
                self.tbl_cables.setItem(row, 3, QTableWidgetItem(fmt2(area_mm2)))
                self.tbl_cables.setItem(row, 4, QTableWidgetItem(edge_tag))
                self.tbl_cables.setItem(row, 5, QTableWidgetItem(conduit_tag))
                rows += 1

        if rows == 0:
            self._set_cables_placeholder("No hay cables asignados a estos tramos")
        else:
            self.tbl_cables.setEnabled(True)

    def _set_cables_placeholder(self, text: str) -> None:
        self.tbl_cables.setRowCount(0)
        self.tbl_cables.insertRow(0)
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        self.tbl_cables.setItem(0, 0, item)
        self.tbl_cables.setItem(0, 1, QTableWidgetItem(""))
        self.tbl_cables.setItem(0, 2, QTableWidgetItem(""))
        self.tbl_cables.setItem(0, 3, QTableWidgetItem(""))
        self.tbl_cables.setItem(0, 4, QTableWidgetItem(""))
        self.tbl_cables.setItem(0, 5, QTableWidgetItem(""))
        self.tbl_cables.setEnabled(False)

    def _circuits_by_id(self) -> Dict[str, Dict[str, object]]:
        circuits = list((getattr(self._project, "circuits", {}) or {}).get("items") or [])
        return {str(c.get("id") or ""): c for c in circuits if c.get("id")}

    def _circuit_display_info(
        self,
        circuit: Dict[str, object],
    ) -> Tuple[str, str, str, float, float]:
        tag = str(circuit.get("tag") or circuit.get("name") or circuit.get("id") or "")
        cable_label = str(circuit.get("cable_label") or "")
        service = str(circuit.get("service") or "").strip()
        area_mm2 = float(circuit.get("area_mm2") or 0.0)
        qty = int(circuit.get("qty", 1) or 1)
        cable_ref = str(circuit.get("cable_ref") or "")
        snap = circuit.get("cable_snapshot") if isinstance(circuit.get("cable_snapshot"), dict) else None
        diameter = 0.0

        if snap:
            if not cable_label:
                cable_label = str(snap.get("name") or snap.get("code") or "")
            if not service:
                service = str(snap.get("service") or "")
            try:
                diameter = float(snap.get("outer_diameter_mm") or 0.0)
            except Exception:
                diameter = 0.0

        if self._material_service and cable_ref:
            if not cable_label:
                item = self._material_service.get_conductor_by_uid(cable_ref)
                if not item:
                    item = self._material_service.get_conductor_by_code(cable_ref)
                if item:
                    cable_label = str(item.get("name") or item.get("code") or "")
                    if not service:
                        service = str(item.get("service") or "")
                    diameter = max(diameter, float(item.get("outer_diameter_mm") or 0.0))
            if diameter <= 0:
                diameter = float(self._material_service.get_cable_outer_diameter(cable_ref) or 0.0)

        if not cable_label:
            cable_label = cable_ref or tag

        if area_mm2 <= 0 and diameter > 0:
            area_mm2 = math.pi * (diameter / 2.0) ** 2 * max(1, qty)

        return tag, cable_label, service, area_mm2, diameter

    def _edge_service(
        self,
        edge_id: str,
        edge_to_circuits: Optional[Dict[str, List[str]]],
        circuits_by_id: Dict[str, Dict[str, object]],
    ) -> str:
        if not isinstance(edge_to_circuits, dict):
            return ""
        services: Set[str] = set()
        for cid in edge_to_circuits.get(str(edge_id), []) or []:
            circuit = circuits_by_id.get(str(cid) or "")
            if not circuit:
                continue
            _, _, service, _, _ = self._circuit_display_info(circuit)
            service = str(service or "").strip()
            if service:
                services.add(service)
        if not services:
            return ""
        if len(services) == 1:
            return next(iter(services))
        return "Mixto"

    def _available_percent(self, fill_percent: object, fill_max: object) -> float:
        try:
            fill = float(fill_percent or 0.0)
        except Exception:
            fill = 0.0
        try:
            max_fill = float(fill_max or 0.0)
        except Exception:
            max_fill = 0.0
        if max_fill > 0:
            return max(0.0, max_fill - fill)
        return max(0.0, 100.0 - fill)

    def _render_front_view(self, node: Dict[str, object], dims_mm: Tuple[float, float, float]) -> None:
        self.front_scene.clear()
        width_mm, height_mm, _ = dims_mm
        rect = self._draw_equipment_rect(self.front_scene, width_mm, height_mm, self.front_view)
        rect.setPen(QPen(QColor("#6b7280"), 2))
        rect.setBrush(QBrush(QColor("#e5e7eb")))
        self._draw_dimension_h(self.front_scene, rect, f"{width_mm:.0f} mm")
        self._draw_dimension_v(self.front_scene, rect, f"{height_mm:.0f} mm")
        self._draw_centered_label(self.front_scene, rect, str(node.get("name") or "Tablero"))
        self._fit_view(self.front_scene, self.front_view)

    def _render_side_view(self, node: Dict[str, object], dims_mm: Tuple[float, float, float]) -> None:
        self.side_scene.clear()
        _, height_mm, depth_mm = dims_mm
        rect = self._draw_equipment_rect(self.side_scene, depth_mm, height_mm, self.side_view)
        rect.setPen(QPen(QColor("#6b7280"), 2))
        rect.setBrush(QBrush(QColor("#f3f4f6")))
        self._draw_dimension_h(self.side_scene, rect, f"{depth_mm:.0f} mm")
        self._draw_dimension_v(self.side_scene, rect, f"{height_mm:.0f} mm")
        self._draw_centered_label(self.side_scene, rect, str(node.get("name") or "Tablero"))
        self._fit_view(self.side_scene, self.side_view)

    def _render_bottom_view(
        self,
        node: Dict[str, object],
        conduits: List[Dict[str, object]],
        dims_mm: Tuple[float, float, float],
    ) -> None:
        self.bottom_scene.clear()
        calc = self._calc_context()
        edge_to_circuits = calc.get("edge_to_circuits") if calc else None
        if not isinstance(edge_to_circuits, dict):
            self._draw_placeholder(self.bottom_scene, "Ejecuta Recalcular para ver cables")
            return
        if not conduits:
            self._draw_placeholder(self.bottom_scene, "No hay tramos conectados")
            return

        width_mm, _, depth_mm = dims_mm
        cab_rect = self._draw_equipment_rect(self.bottom_scene, width_mm, depth_mm, self.bottom_view)
        cab_rect.setPen(QPen(QColor("#111827"), 2))
        cab_rect.setBrush(QBrush(QColor("#dbeafe")))
        self._draw_dimension_h(self.bottom_scene, cab_rect, f"{width_mm:.0f} mm")
        self._draw_dimension_v(self.bottom_scene, cab_rect, f"{depth_mm:.0f} mm")
        self._draw_centered_label(self.bottom_scene, cab_rect, str(node.get("name") or "Tablero"))

        rect = cab_rect.rect()
        rect_w = rect.width()
        rect_h = rect.height()
        pad_px = max(12.0, min(rect_w, rect_h) * 0.08)
        access = self._equipment_cable_access(node)
        gap_px = 10.0
        usable_w = max(10.0, rect_w - pad_px * 2.0)
        usable_h = max(10.0, rect_h - pad_px * 2.0)
        count = len(conduits)

        circuits_by_id = self._circuits_by_id()
        palette = [
            QColor("#bae6fd"),
            QColor("#bbf7d0"),
            QColor("#fde68a"),
            QColor("#fecdd3"),
            QColor("#ddd6fe"),
            QColor("#fed7aa"),
        ]

        scale = self._mm_scale(self.bottom_view, width_mm, depth_mm)
        max_w_px, max_h_px = self._max_conduit_pixel_size(conduits, scale)
        cell_w = max_w_px
        cell_h = max_h_px
        cols = max(1, int((usable_w + gap_px) / (cell_w + gap_px)))
        rows = max(1, int(math.ceil(count / cols)))
        needed_h = rows * cell_h + (rows - 1) * gap_px
        if needed_h > usable_h:
            shrink = max(0.4, usable_h / max(1.0, needed_h))
            cell_w *= shrink
            cell_h *= shrink
            max_w_px *= shrink
            max_h_px *= shrink
        for idx, conduit in enumerate(conduits):
            row = idx // cols
            col = idx % cols
            if access == "top":
                cy = rect.top() + pad_px + cell_h / 2.0 + row * (cell_h + gap_px)
            else:
                cy = rect.bottom() - pad_px - cell_h / 2.0 - row * (cell_h + gap_px)
            cx = rect.left() + pad_px + cell_w / 2.0 + col * (cell_w + gap_px)
            cx = min(rect.right() - pad_px - cell_w / 2.0, max(rect.left() + pad_px + cell_w / 2.0, cx))

            shape = str(conduit.get("shape") or "circle")
            if shape == "rect":
                outer = QGraphicsRectItem(
                    cx - max_w_px / 2.0,
                    cy - max_h_px / 2.0,
                    max_w_px,
                    max_h_px,
                )
            else:
                d = min(max_w_px, max_h_px)
                outer = QGraphicsEllipseItem(cx - d / 2.0, cy - d / 2.0, d, d)
            outer.setPen(QPen(QColor("#6b7280"), 2))
            outer.setBrush(QBrush(QColor("#f8fafc")))
            self.bottom_scene.addItem(outer)

            tag = str(conduit.get("conduit_tag") or "")
            tag_item = QGraphicsSimpleTextItem(tag)
            tag_item.setBrush(QBrush(QColor("#374151")))
            tag_item.setFont(QFont("", 8))
            tag_item.setPos(cx - max_w_px / 2.0, cy + max_h_px / 2.0 + 2)
            self.bottom_scene.addItem(tag_item)

            cable_items = self._build_conduit_cables(conduit)
            if cable_items:
                if shape == "rect":
                    positions = layout_cables_in_rect(
                        {"x0": 0.0, "y0": 0.0, "width_mm": conduit.get("inner_w_mm", 0.0), "height_mm": conduit.get("inner_h_mm", 0.0)},
                        cable_items,
                        spacing_mm=1.0,
                    )
                    for pos in positions:
                        px = cx - max_w_px / 2.0 + float(pos.get("x_mm") or 0.0) * scale
                        py = cy - max_h_px / 2.0 + float(pos.get("y_mm") or 0.0) * scale
                        d_px = float(pos.get("d_mm") or 0.0) * scale
                        r = max(2.0, d_px / 2.0)
                        circle = QGraphicsEllipseItem(px - r, py - r, r * 2.0, r * 2.0)
                        color = palette[hash(str(pos.get("circuit_tag") or "")) % len(palette)]
                        circle.setBrush(QBrush(color))
                        circle.setPen(QPen(QColor("#d1d5db"), 0.8))
                        self.bottom_scene.addItem(circle)
                else:
                    positions = layout_cables_in_circle(
                        {"cx": 0.0, "cy": 0.0, "inner_diameter_mm": conduit.get("inner_d_mm", 0.0)},
                        cable_items,
                        spacing_mm=1.0,
                    )
                    for pos in positions:
                        px = cx + float(pos.get("x_mm") or 0.0) * scale
                        py = cy + float(pos.get("y_mm") or 0.0) * scale
                        d_px = float(pos.get("d_mm") or 0.0) * scale
                        r = max(2.0, d_px / 2.0)
                        circle = QGraphicsEllipseItem(px - r, py - r, r * 2.0, r * 2.0)
                        color = palette[hash(str(pos.get("circuit_tag") or "")) % len(palette)]
                        circle.setBrush(QBrush(color))
                        circle.setPen(QPen(QColor("#d1d5db"), 0.8))
                        self.bottom_scene.addItem(circle)

        self._fit_view(self.bottom_scene, self.bottom_view)

    def _draw_placeholder(self, scene: QGraphicsScene, text: str) -> None:
        label = QGraphicsSimpleTextItem(text)
        label.setBrush(QBrush(QColor("#9ca3af")))
        label.setPos(0, 0)
        scene.addItem(label)
        scene.setSceneRect(scene.itemsBoundingRect().adjusted(-40, -40, 40, 40))

    def _mm_scale(self, view: QGraphicsView, width_mm: float, height_mm: float) -> float:
        viewport = view.viewport().size()
        w_px = max(1, viewport.width())
        h_px = max(1, viewport.height())
        padding = 24.0
        scale_x = (w_px - padding * 2.0) / max(1.0, width_mm)
        scale_y = (h_px - padding * 2.0) / max(1.0, height_mm)
        return max(0.1, min(scale_x, scale_y))

    def _draw_equipment_rect(
        self,
        scene: QGraphicsScene,
        width_mm: float,
        height_mm: float,
        view: QGraphicsView,
    ) -> QGraphicsRectItem:
        scale = self._mm_scale(view, width_mm, height_mm)
        w_px = width_mm * scale
        h_px = height_mm * scale
        rect = QGraphicsRectItem(-w_px / 2.0, -h_px / 2.0, w_px, h_px)
        scene.addItem(rect)
        return rect

    def _draw_centered_label(self, scene: QGraphicsScene, rect: QGraphicsRectItem, text: str) -> None:
        if not text:
            return
        label = QGraphicsSimpleTextItem(text)
        bounds = label.boundingRect()
        r = rect.rect()
        if bounds.width() <= r.width() - 10 and bounds.height() <= r.height() - 10:
            label.setPos(r.center().x() - bounds.width() / 2.0, r.center().y() - bounds.height() / 2.0)
        else:
            label.setPos(r.left() + 6, r.top() + 6)
        label.setBrush(QBrush(QColor("#374151")))
        scene.addItem(label)

    def _fit_view(self, scene: QGraphicsScene, view: QGraphicsView) -> None:
        bounds = scene.itemsBoundingRect().adjusted(-20, -20, 20, 20)
        scene.setSceneRect(bounds)
        view.fitInView(bounds, Qt.KeepAspectRatio)

    def _dimension_pen(self) -> QPen:
        pen = QPen(QColor("#9ca3af"), 1)
        pen.setCosmetic(True)
        return pen

    def _dimension_text_item(self, text: str, font_size: int = 8) -> QGraphicsSimpleTextItem:
        item = QGraphicsSimpleTextItem(text)
        font = QFont()
        font.setPointSize(max(7, font_size))
        item.setFont(font)
        item.setBrush(QBrush(QColor("#9ca3af")))
        return item

    def _draw_dimension_h(self, scene: QGraphicsScene, rect: QGraphicsRectItem, text: str) -> None:
        r = rect.rect()
        offset = 12.0
        tick = 6.0
        y_line = r.bottom() + offset
        x1 = r.left()
        x2 = r.right()
        pen = self._dimension_pen()
        scene.addLine(x1, r.bottom(), x1, y_line, pen)
        scene.addLine(x2, r.bottom(), x2, y_line, pen)
        scene.addLine(x1, y_line, x2, y_line, pen)
        scene.addLine(x1, y_line - tick / 2.0, x1, y_line + tick / 2.0, pen)
        scene.addLine(x2, y_line - tick / 2.0, x2, y_line + tick / 2.0, pen)
        text_item = self._dimension_text_item(text, 8)
        bounds = text_item.boundingRect()
        text_item.setPos((x1 + x2) / 2.0 - bounds.width() / 2.0, y_line + 4.0)
        scene.addItem(text_item)

    def _draw_dimension_v(self, scene: QGraphicsScene, rect: QGraphicsRectItem, text: str) -> None:
        r = rect.rect()
        offset = 12.0
        tick = 6.0
        x_line = r.left() - offset
        y1 = r.top()
        y2 = r.bottom()
        pen = self._dimension_pen()
        scene.addLine(r.left(), y1, x_line, y1, pen)
        scene.addLine(r.left(), y2, x_line, y2, pen)
        scene.addLine(x_line, y1, x_line, y2, pen)
        scene.addLine(x_line - tick / 2.0, y1, x_line + tick / 2.0, y1, pen)
        scene.addLine(x_line - tick / 2.0, y2, x_line + tick / 2.0, y2, pen)
        text_item = self._dimension_text_item(text, 8)
        bounds = text_item.boundingRect()
        text_item.setRotation(-90)
        text_item.setPos(x_line - bounds.height() - 4.0, (y1 + y2) / 2.0 + bounds.width() / 2.0)
        scene.addItem(text_item)

    def _index_to_letters(self, idx: int) -> str:
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        n = idx + 1
        out = ""
        while n > 0:
            n, rem = divmod(n - 1, 26)
            out = letters[rem] + out
        return out or "A"

    def _conduit_labels(self, base: str, qty: int) -> List[str]:
        base = str(base or "").strip()
        labels = []
        for idx in range(max(1, qty)):
            suffix = self._index_to_letters(idx)
            if base:
                labels.append(f"{base}-{suffix}")
            else:
                labels.append(f"Canalización {suffix}")
        return labels

    def _collect_conduits(self, edges: List[Dict[str, object]]) -> List[Dict[str, object]]:
        calc = self._calc_context() or {}
        edge_to_circuits = calc.get("edge_to_circuits") if isinstance(calc.get("edge_to_circuits"), dict) else {}
        canalizacion_assignments = calc.get("canalizacion_assignments") if isinstance(calc.get("canalizacion_assignments"), dict) else {}
        conduits: List[Dict[str, object]] = []
        for edge in edges:
            edge_id = str(edge.get("id") or "")
            props = edge.get("props") if isinstance(edge.get("props"), dict) else {}
            qty = int(props.get("quantity") or 1)
            qty = max(1, qty)
            cols = int(props.get("columns") or 1)
            cols = max(1, cols)
            total = max(1, qty * cols)
            edge_tag = self._edge_tag(edge)
            conduit_type = str(props.get("conduit_type") or "Ducto")
            size_label = str(props.get("size") or "")
            duct_uid = str(props.get("duct_uid") or "")
            labels = self._conduit_labels(edge_tag, total)
            buckets = list(canalizacion_assignments.get(edge_id, []))
            if not buckets:
                circuit_ids = list(edge_to_circuits.get(edge_id, []) or [])
                buckets = [{"index": i, "cables": []} for i in range(total)]
                for idx, cid in enumerate(circuit_ids):
                    buckets[idx % total]["cables"].append({"circuit_id": str(cid), "qty": 1})
            for idx in range(total):
                bucket = buckets[idx] if idx < len(buckets) else {"cables": []}
                conduit_tag = labels[idx] if idx < len(labels) else f"{edge_tag}-{self._index_to_letters(idx)}"
                if "conduit_tag" not in bucket and "tag" not in bucket:
                    bucket = dict(bucket)
                    bucket["conduit_tag"] = conduit_tag
                shape, inner_d, inner_w, inner_h, outer_w, outer_h = self._conduit_geometry(
                    conduit_type, size_label, duct_uid
                )
                conduits.append(
                    {
                        "edge_id": edge_id,
                        "edge_tag": edge_tag,
                        "conduit_tag": conduit_tag,
                        "conduit_type": conduit_type,
                        "shape": shape,
                        "inner_d_mm": inner_d,
                        "inner_w_mm": inner_w,
                        "inner_h_mm": inner_h,
                        "outer_w_mm": outer_w,
                        "outer_h_mm": outer_h,
                        "cables": list(bucket.get("cables") or []),
                    }
                )
        return conduits

    def _conduit_geometry(
        self,
        conduit_type: str,
        size_label: str,
        duct_uid: str,
    ) -> Tuple[str, float, float, float, float, float]:
        conduit_type = str(conduit_type or "Ducto")
        if conduit_type == "Ducto":
            inner_mm = 40.0
            outer_mm = 50.0
            if self._material_service:
                if duct_uid:
                    dims = self._material_service.get_duct_dimensions_by_uid(duct_uid)
                else:
                    dims = self._material_service.get_duct_dimensions(size_label)
                inner_mm = float(dims.get("inner_diameter_mm") or inner_mm)
                outer_mm = float(dims.get("outer_diameter_mm") or outer_mm)
            return "circle", inner_mm, 0.0, 0.0, outer_mm, outer_mm
        w_mm = 120.0
        h_mm = 60.0
        if self._material_service:
            dims = self._material_service.get_rect_dimensions(conduit_type.lower(), size_label)
            w_mm = float(dims.get("inner_width_mm") or w_mm)
            h_mm = float(dims.get("inner_height_mm") or h_mm)
        return "rect", 0.0, w_mm, h_mm, w_mm, h_mm

    def _max_conduit_pixel_size(self, conduits: List[Dict[str, object]], scale: float) -> Tuple[float, float]:
        max_w = 40.0
        max_h = 40.0
        for conduit in conduits:
            if conduit.get("shape") == "rect":
                w = float(conduit.get("outer_w_mm") or 0.0) * scale
                h = float(conduit.get("outer_h_mm") or 0.0) * scale
            else:
                d = float(conduit.get("outer_w_mm") or conduit.get("inner_d_mm") or 0.0) * scale
                w = d
                h = d
            if w <= 0:
                w = 40.0
            if h <= 0:
                h = 40.0
            max_w = max(max_w, w)
            max_h = max(max_h, h)
        return max(40.0, max_w), max(40.0, max_h)

    def _build_conduit_cables(self, conduit: Dict[str, object]) -> List[Dict[str, object]]:
        circuits_by_id = self._circuits_by_id()
        items: List[Dict[str, object]] = []
        for entry in list(conduit.get("cables") or []):
            cid = str(entry.get("circuit_id") or "")
            circuit = circuits_by_id.get(cid)
            if not circuit:
                continue
            tag_c, _, _, _, diameter = self._circuit_display_info(circuit)
            qty = int(entry.get("qty") or circuit.get("qty", 1) or 1)
            if diameter <= 0:
                diameter = 12.0
            items += expand_cable_items(tag_c, diameter, qty)
        return items

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._view_height <= 0:
            current = self._front_container.height()
            if current <= 0:
                current = max(160, int(self.height() / 4))
            self._view_height = max(120, int(current / 2))
            self._front_container.setFixedHeight(self._view_height)
            self._side_container.setFixedHeight(self._view_height)
            self._bottom_container.setFixedHeight(self._view_height)
            node = self._find_node(self._node_id) or {}
            dims = self._equipment_dimensions_mm(node)
            self._render_front_view(node, dims)
            self._render_side_view(node, dims)
            edges = self._connected_edges(self._node_id)
            conduits = self._collect_conduits(edges)
            self._render_bottom_view(node, conduits, dims)
