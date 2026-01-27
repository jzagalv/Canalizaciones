# -*- coding: utf-8 -*-
from __future__ import annotations

import math
import re
from typing import Dict, List, Optional, Tuple

from PyQt5.QtCore import Qt, QRectF, pyqtSignal
from PyQt5.QtGui import QPen, QBrush, QColor, QFont, QPainter, QPainterPath, QFontMetrics
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGraphicsEllipseItem,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QDoubleSpinBox,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from domain.calculations.occupancy import (
    DEFAULT_DUCT_MAX_FILL_PERCENT,
    DEFAULT_TRAY_MAX_FILL_PERCENT,
    calc_duct_fill,
    calc_tray_fill,
    get_material_max_fill_percent,
)
from domain.calculations.formatting import fmt_percent, round2, util_color
from domain.materials.material_service import MaterialService


class SectionGraphicsView(QGraphicsView):
    zoomRequested = pyqtSignal(float)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        if delta == 0:
            event.ignore()
            return
        factor = 1.15 if delta > 0 else (1.0 / 1.15)
        self.zoomRequested.emit(factor)
        event.accept()


class ConduitSegmentDialog(QDialog):
    def __init__(self, parent=None, material_service: Optional[MaterialService] = None):
        super().__init__(parent)
        self.setWindowTitle("Características del tramo")
        self.setModal(False)
        self.resize(900, 520)

        self._segment = None
        self._zoom = 1.0
        self._min_zoom = 0.2
        self._max_zoom = 5.0
        self._user_zoomed = False
        self._section_bounds = QRectF()
        self._material_service: Optional[MaterialService] = material_service
        self._spacing_custom = False
        self._setting_spacing = False
        self._loading_segment = False
        self._preview_dirty = False
        self._project = None

        self._size_options = {
            "Ducto": ['1"', '2"', '3"', '4"'],
            "EPC": ["100x50", "200x50", "300x50"],
            "BPC": ["100x50", "200x50", "300x50"],
        }

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        splitter.addWidget(left)

        self.lbl_status = QLabel("")
        left_layout.addWidget(self.lbl_status)

        gb = QGroupBox("Características de la canalización")
        form = QFormLayout(gb)
        self.edt_tag = QLineEdit()
        self.edt_tag.textChanged.connect(self._on_form_changed)
        self.cmb_type = QComboBox()
        self.cmb_type.addItems(["Ducto", "EPC", "BPC"])
        self.cmb_type.currentTextChanged.connect(self._on_type_changed)

        self.cmb_duct_standard = QComboBox()
        self.cmb_duct_standard.currentTextChanged.connect(self._on_duct_standard_changed)

        self.cmb_duct = QComboBox()
        self.cmb_duct.currentIndexChanged.connect(self._on_duct_changed)

        self.cmb_size = QComboBox()
        self.cmb_size.currentTextChanged.connect(self._on_size_changed)

        self.spin_qty = QSpinBox()
        self.spin_qty.setRange(1, 99)
        self.spin_qty.valueChanged.connect(self._on_qty_changed)

        self.spin_cols = QSpinBox()
        self.spin_cols.setRange(1, 12)
        self.spin_cols.setValue(3)
        self.spin_cols.valueChanged.connect(self._redraw_section)
        self.spin_cols.valueChanged.connect(self._on_form_changed)

        self.spin_spacing = QDoubleSpinBox()
        self.spin_spacing.setDecimals(1)
        self.spin_spacing.setRange(0.0, 200.0)
        self.spin_spacing.setSingleStep(1.0)
        self.spin_spacing.valueChanged.connect(self._on_spacing_changed)

        form.addRow("Tag del tramo:", self.edt_tag)
        form.addRow("Tipo de canalización:", self.cmb_type)
        self.lbl_duct_standard = QLabel("Norma:")
        form.addRow(self.lbl_duct_standard, self.cmb_duct_standard)
        self.lbl_duct = QLabel("Ducto:")
        form.addRow(self.lbl_duct, self.cmb_duct)
        self.lbl_size = QLabel("Tamaño general:")
        form.addRow(self.lbl_size, self.cmb_size)
        form.addRow("Cantidad:", self.spin_qty)
        form.addRow("Columnas:", self.spin_cols)
        self.lbl_spacing = QLabel("Separacion entre ductos (mm):")
        form.addRow(self.lbl_spacing, self.spin_spacing)

        left_layout.addWidget(gb)
        self._props_group = gb

        circuits_group = QGroupBox("Circuitos que pasan por este tramo")
        circuits_layout = QVBoxLayout(circuits_group)
        circuits_header = QHBoxLayout()
        circuits_header.addStretch(1)
        self.btn_refresh_circuits = QPushButton("Actualizar")
        self.btn_refresh_circuits.clicked.connect(self._refresh_circuits_list)
        circuits_header.addWidget(self.btn_refresh_circuits)
        circuits_layout.addLayout(circuits_header)
        self.lst_circuits = QListWidget()
        self.lst_circuits.setFixedHeight(140)
        circuits_layout.addWidget(self.lst_circuits)
        left_layout.addWidget(circuits_group)
        self._circuits_group = circuits_group

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.btn_apply = QPushButton("Aplicar")
        self.btn_close = QPushButton("Cerrar")
        self.btn_apply.clicked.connect(self._apply_to_segment)
        self.btn_close.clicked.connect(self.close)
        btn_row.addWidget(self.btn_apply)
        btn_row.addWidget(self.btn_close)
        left_layout.addLayout(btn_row)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        splitter.addWidget(right)

        right_layout.addWidget(QLabel("Sección / Corte"))
        self.section_scene = QGraphicsScene(self)
        self.view = SectionGraphicsView(self.section_scene)
        self.view.setRenderHints(
            QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform
        )
        self.view.setMinimumSize(360, 300)
        right_layout.addWidget(self.view, 1)

        zoom_bar = QHBoxLayout()
        self.btn_zoom_out = QPushButton("-")
        self.lbl_zoom = QLabel("100%")
        self.btn_zoom_in = QPushButton("+")
        self.btn_fit = QPushButton("Ajustar")
        self.btn_reset = QPushButton("Reset")
        zoom_bar.addWidget(self.btn_zoom_out)
        zoom_bar.addWidget(self.lbl_zoom)
        zoom_bar.addWidget(self.btn_zoom_in)
        zoom_bar.addSpacing(8)
        zoom_bar.addWidget(self.btn_fit)
        zoom_bar.addWidget(self.btn_reset)
        zoom_bar.addStretch(1)
        right_layout.addLayout(zoom_bar)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        self.view.zoomRequested.connect(self._apply_zoom_from_user)
        self.btn_zoom_in.clicked.connect(lambda: self._apply_zoom(1.15, user_action=True))
        self.btn_zoom_out.clicked.connect(lambda: self._apply_zoom(1.0 / 1.15, user_action=True))
        self.btn_fit.clicked.connect(lambda: self._fit_section_view(user_action=True))
        self.btn_reset.clicked.connect(lambda: self._set_zoom(1.0, user_action=True))

        self._on_type_changed(self.cmb_type.currentText())
        self._render_section()

    def set_material_service(self, material_service: Optional[MaterialService]) -> None:
        self._material_service = material_service
        self._reload_sizes_for_type(self.cmb_type.currentText().strip())
        self._update_type_controls_visibility(self.cmb_type.currentText().strip())

    def set_project(self, project) -> None:
        self._project = project
        self._refresh_circuits_list()

    def set_segment(self, segment_item) -> None:
        self._loading_segment = True
        self._segment = segment_item if self._is_segment_alive(segment_item) else None
        if self._segment is None:
            self._set_form_enabled(False)
            self.lbl_status.setText("(sin selección)")
            self.lbl_status.setStyleSheet("")
            self.edt_tag.setText("")
            self.cmb_type.setCurrentIndex(0)
            self.spin_qty.setValue(1)
            self.spin_cols.setValue(3)
            self._update_spacing_visibility()
            self._user_zoomed = False
            self._preview_dirty = False
            self._set_zoom(1.0, user_action=False)
            self._render_section()
            self._refresh_circuits_list()
            self._loading_segment = False
            return

        props = self._segment_props(self._segment)
        self._set_form_enabled(True)
        self.lbl_status.setText("")

        self.edt_tag.setText(props.get("tag", ""))
        conduit_type = props.get("conduit_type", "Ducto")
        idx = self.cmb_type.findText(conduit_type)
        self.cmb_type.setCurrentIndex(idx if idx >= 0 else 0)

        size = props.get("size", '1"')
        self._reload_sizes_for_type(
            conduit_type,
            desired=size,
            duct_standard=props.get("duct_standard"),
            duct_uid=props.get("duct_uid"),
        )
        qty = int(props.get("quantity", 1) or 1)
        self.spin_qty.setValue(qty)
        cols = int(props.get("columns", 3) or 3)
        self.spin_cols.blockSignals(True)
        self.spin_cols.setValue(cols)
        self.spin_cols.blockSignals(False)
        self._load_spacing_from_props(props, self._current_size_for_type(conduit_type, size))
        self._update_spacing_visibility()

        try:
            self._segment.setSelected(True)
            self._segment._apply_style()
        except Exception:
            pass

        self._user_zoomed = False
        self._preview_dirty = False
        self._set_zoom(1.0, user_action=False)
        self._render_section()
        self._refresh_circuits_list()
        self._loading_segment = False

    def _set_form_enabled(self, enabled: bool) -> None:
        self._props_group.setEnabled(enabled)
        self.btn_apply.setEnabled(enabled)

    def _refresh_circuits_list(self) -> None:
        if not hasattr(self, "lst_circuits"):
            return
        self.lst_circuits.clear()
        if not self._is_segment_alive(self._segment):
            return
        calc = getattr(self._project, "_calc", None) if self._project is not None else None
        edge_to_circuits = calc.get("edge_to_circuits") if isinstance(calc, dict) else None
        if not isinstance(edge_to_circuits, dict):
            self._set_circuits_placeholder("Ejecuta Recalcular para ver los circuitos que pasan por este tramo")
            return
        circuit_ids = list(edge_to_circuits.get(self._segment.edge_id, []) or [])
        if not circuit_ids:
            self._set_circuits_placeholder("Ningun circuito pasa por este tramo")
            return
        circuits = list((getattr(self._project, "circuits", {}) or {}).get("items") or [])
        by_id = {str(c.get("id") or ""): c for c in circuits if c.get("id")}
        for cid in circuit_ids:
            circuit = by_id.get(str(cid) or "")
            name = str((circuit or {}).get("name") or cid or "")
            if name:
                self.lst_circuits.addItem(name)
        self.lst_circuits.setEnabled(True)

    def _set_circuits_placeholder(self, text: str) -> None:
        self.lst_circuits.clear()
        self.lst_circuits.addItem(text)
        self.lst_circuits.setEnabled(False)

    def _segment_props(self, segment_item) -> Dict[str, str]:
        if segment_item is None:
            return {}
        props = getattr(segment_item, "props", None) or {}
        if not props:
            props = {
                "tag": "",
                "conduit_type": "Ducto",
                "size": '1"',
                "duct_standard": "",
                "duct_uid": "",
                "duct_snapshot": {},
                "quantity": 1,
                "columns": 3,
                "cables": [],
                "duct_spacing_mm": None,
                "duct_spacing_custom": False,
            }
            try:
                segment_item.props = dict(props)
            except Exception:
                pass
        if "cables" not in props:
            props["cables"] = []
            try:
                segment_item.props = dict(props)
            except Exception:
                pass
        if "duct_standard" not in props:
            props["duct_standard"] = ""
            try:
                segment_item.props = dict(props)
            except Exception:
                pass
        if "duct_uid" not in props:
            props["duct_uid"] = ""
            try:
                segment_item.props = dict(props)
            except Exception:
                pass
        if "duct_snapshot" not in props:
            props["duct_snapshot"] = {}
            try:
                segment_item.props = dict(props)
            except Exception:
                pass
        if not props.get("duct_uid"):
            snap = props.get("duct_snapshot") if isinstance(props.get("duct_snapshot"), dict) else {}
            snap_uid = str(snap.get("uid") or "").strip()
            if snap_uid:
                props["duct_uid"] = snap_uid
                try:
                    segment_item.props = dict(props)
                except Exception:
                    pass
        if "duct_id" in props and not props.get("duct_uid"):
            legacy_id = str(props.get("duct_id") or "").strip()
            resolved_uid = ""
            if legacy_id and self._material_service:
                resolved_uid = self._material_service.resolve_duct_uid(legacy_id, props.get("size"))
            if resolved_uid:
                props["duct_uid"] = resolved_uid
                props.pop("duct_id", None)
                try:
                    segment_item.props = dict(props)
                except Exception:
                    pass
        return dict(props)

    def _on_type_changed(self, text: str) -> None:
        if not self._loading_segment:
            self._preview_dirty = True
        self._reload_sizes_for_type(text)
        self._update_type_controls_visibility(text)
        if text.strip() == "Ducto" and not self._spacing_custom:
            self._apply_default_spacing_for_size(self._current_duct_label(), self._current_duct_uid())
        self._update_spacing_visibility()
        self._render_section()
        self._sync_preview_props()

    def _on_size_changed(self, text: str) -> None:
        if not self._loading_segment:
            self._preview_dirty = True
        if self.cmb_type.currentText().strip() == "Ducto" and not self._spacing_custom:
            self._apply_default_spacing_for_size(self._current_duct_label(), self._current_duct_uid())
        self._render_section()
        self._sync_preview_props()

    def _on_duct_standard_changed(self, text: str) -> None:
        if not self._loading_segment:
            self._preview_dirty = True
        desired_id = self._current_duct_uid()
        desired_label = self.cmb_duct.currentText().strip()
        self._reload_ducts_for_standard(text, desired_id=desired_id, desired_label=desired_label)
        if self.cmb_type.currentText().strip() == "Ducto" and not self._spacing_custom:
            self._apply_default_spacing_for_size(self._current_duct_label(), self._current_duct_uid())
        self._render_section()
        self._sync_preview_props()

    def _on_duct_changed(self, index: int) -> None:
        if not self._loading_segment:
            self._preview_dirty = True
        if self.cmb_type.currentText().strip() == "Ducto" and not self._spacing_custom:
            self._apply_default_spacing_for_size(self._current_duct_label(), self._current_duct_uid())
        self._render_section()
        self._sync_preview_props()

    def _on_qty_changed(self, value: int) -> None:
        if not self._loading_segment:
            self._preview_dirty = True
        if self._spacing_is_applicable() and not self._spacing_custom:
            self._apply_default_spacing_for_size(self._current_duct_label(), self._current_duct_uid())
        self._update_spacing_visibility()
        self._render_section()
        self._sync_preview_props()

    def _on_spacing_changed(self, value: float) -> None:
        if self._setting_spacing:
            return
        if not self._loading_segment:
            self._preview_dirty = True
        self._spacing_custom = True
        self._render_section()
        self._sync_preview_props()

    def _redraw_section(self, *args) -> None:
        self._render_section()

    def _on_form_changed(self, *args) -> None:
        if self._loading_segment:
            return
        self._preview_dirty = True
        self._sync_preview_props()

    def _apply_to_segment(self) -> None:
        if not self._is_segment_alive(self._segment):
            self.set_segment(None)
            return
        props, _, _ = self._build_props_from_inputs()
        self._persist_props(props)
        self._preview_dirty = False
        try:
            self._segment.update()
            self._segment._apply_style()
        except Exception:
            pass
        self._render_section()

    def _build_props_from_inputs(self) -> Tuple[Dict[str, object], float, float]:
        existing = self._segment_props(self._segment) if self._is_segment_alive(self._segment) else {}
        conduit_type = self.cmb_type.currentText().strip()
        size = self._ensure_valid_size_selection(conduit_type, fallback=str(existing.get("size") or ""))
        duct_standard = ""
        duct_uid = ""
        if conduit_type == "Ducto":
            duct_standard = self._current_duct_standard()
            duct_uid = self._current_duct_uid()
            size = self._current_duct_label() or size
        duct_snapshot = {}
        if conduit_type == "Ducto" and duct_uid:
            duct_snapshot = self._build_duct_snapshot(duct_uid)
        fill_percent_raw, max_fill_raw = self._compute_fill_percent()
        fill_over = bool(max_fill_raw > 0 and fill_percent_raw > max_fill_raw + 1e-6)
        fill_percent = round2(fill_percent_raw)
        max_fill = round2(max_fill_raw)
        fill_state = util_color(fill_percent_raw, max_fill_raw)
        props = dict(existing)
        props.update({
            "tag": self.edt_tag.text().strip(),
            "conduit_type": conduit_type,
            "size": size,
            "duct_standard": duct_standard,
            "duct_uid": duct_uid,
            "duct_snapshot": duct_snapshot,
            "quantity": int(self.spin_qty.value() or 1),
            "columns": int(self.spin_cols.value() or 1),
            "fill_percent": fill_percent,
            "fill_max_percent": max_fill,
            "fill_over": fill_over,
            "fill_state": fill_state,
            "duct_spacing_mm": float(self.spin_spacing.value() or 0.0),
            "duct_spacing_custom": bool(self._spacing_custom),
        })
        props.setdefault("cables", list(existing.get("cables") or []))
        return props, fill_percent_raw, max_fill_raw

    def _persist_props(self, props: Dict[str, object], emit: bool = True) -> None:
        if not self._is_segment_alive(self._segment):
            return
        self._segment.props = dict(props)
        scene = self._segment.scene()
        conduit_type = str(props.get("conduit_type") or "Ducto")
        kind_map = {"Ducto": "duct", "EPC": "epc", "BPC": "bpc"}
        kind = kind_map.get(conduit_type, "duct")
        if scene is not None and hasattr(scene, "set_edge_props"):
            scene.set_edge_props(self._segment.edge_id, props, emit=emit)
        if scene is not None and hasattr(scene, "set_edge_kind"):
            scene.set_edge_kind(self._segment.edge_id, kind, emit=emit)
        else:
            self._segment.update_meta(containment_kind=kind)
        runs = []
        duct_uid = str(props.get("duct_uid") or "")
        if conduit_type == "Ducto" and duct_uid:
            duct_code = ""
            if self._material_service:
                duct_item = self._material_service.get_duct_material_by_uid(duct_uid)
                duct_code = str(duct_item.get("code") or "")
            runs = [{"catalog_id": duct_code or duct_uid, "qty": int(props.get("quantity") or 1)}]
        if scene is not None and hasattr(scene, "set_edge_runs"):
            scene.set_edge_runs(self._segment.edge_id, runs, emit=emit)
        else:
            self._segment.update_meta(runs=runs)

    def _sync_preview_props(self) -> None:
        if self._loading_segment or not self._is_segment_alive(self._segment):
            return
        _, fill_percent, max_fill = self._build_props_from_inputs()
        self._update_fill_label(fill_percent, max_fill)

    def _render_section(self) -> None:
        self.section_scene.clear()
        conduit_type = self.cmb_type.currentText().strip()
        size = self.cmb_size.currentText().strip()
        size = self._ensure_valid_size_selection(conduit_type, fallback=size)
        tag = self.edt_tag.text().strip()

        pen = QPen(QColor("#111827"), 2)
        brush = QBrush(Qt.NoBrush)
        font = QFont()
        font.setPointSize(10)
        metrics = QFontMetrics(font)
        label_gap = 4.0
        label_h = float(metrics.height())

        items = []
        n, cols = self._sync_columns()
        rows = (n + cols - 1) // cols
        gap_px = 0.0
        cable_groups = self._split_cables(n, self._expand_cables(self._segment_cables()))

        if conduit_type == "Ducto":
            duct_id = self._current_duct_uid()
            size_label = self._current_duct_label() or size
            inner_mm, outer_mm = self._duct_dimensions_mm(size_label, duct_id)
            px_per_mm = self._duct_pixels_per_mm(outer_mm)
            outer_px = outer_mm * px_per_mm if outer_mm > 0 else 70.0
            inner_px = inner_mm * px_per_mm if inner_mm > 0 else outer_px - 12.0
            outer_px = max(20.0, outer_px)
            inner_px = min(inner_px, outer_px - 6.0)
            inner_px = max(1.0, inner_px)
            inner_margin = max(2.0, (outer_px - inner_px) / 2.0)
            spacing_mm = self._current_spacing_mm(size_label, duct_id)
            gap_px = max(0.0, spacing_mm * px_per_mm)
            item_w = outer_px
            item_h = outer_px + label_gap + label_h
            for i in range(n):
                r = i // cols
                c = i % cols
                x = c * (item_w + gap_px)
                y = r * (item_h + gap_px)
                outer = QGraphicsEllipseItem(x, y, outer_px, outer_px)
                outer.setPen(pen)
                outer.setBrush(brush)
                inner = QGraphicsEllipseItem(
                    x + inner_margin,
                    y + inner_margin,
                    max(1.0, outer_px - 2 * inner_margin),
                    max(1.0, outer_px - 2 * inner_margin),
                )
                inner.setPen(pen)
                inner.setBrush(brush)
                self.section_scene.addItem(outer)
                self.section_scene.addItem(inner)
                items.extend([outer, inner])

                cable_items, overfull = self._draw_cables_in_circle(
                    x + inner_margin,
                    y + inner_margin,
                    inner_px,
                    inner_mm,
                    cable_groups[i],
                )
                items.extend(cable_items)
                if overfull:
                    marker = QGraphicsEllipseItem(
                        x + inner_margin + 1.0,
                        y + inner_margin + 1.0,
                        max(1.0, inner_px - 2.0),
                        max(1.0, inner_px - 2.0),
                    )
                    marker.setPen(self._overfill_pen())
                    marker.setBrush(QBrush(Qt.NoBrush))
                    self.section_scene.addItem(marker)
                    items.append(marker)

                label = QGraphicsSimpleTextItem(size_label or '1"')
                label.setFont(font)
                label_rect = label.boundingRect()
                label.setPos(x + outer_px / 2 - label_rect.width() / 2, y + outer_px + label_gap)
                self.section_scene.addItem(label)
                items.append(label)
        else:
            w_mm, h_mm = self._rect_dimensions_mm(conduit_type, size)
            w, h = self._normalize_rect_size((w_mm, h_mm))
            lip = min(12.0, w * 0.15)
            item_w = w
            item_h = h + label_gap + label_h
            gap = 18.0
            for i in range(n):
                r = i // cols
                c = i % cols
                x = c * (item_w + gap)
                y = r * (item_h + gap)
                profile = self._add_u_profile(x, y, w, h, lip, pen)
                items.append(profile)

                cable_items, overfull = self._draw_cables_in_rect(
                    x,
                    y,
                    w,
                    h,
                    w_mm,
                    h_mm,
                    cable_groups[i],
                )
                items.extend(cable_items)
                if overfull:
                    marker = QGraphicsPathItem()
                    marker.setPath(self._rect_marker_path(x, y, w, h))
                    marker.setPen(self._overfill_pen())
                    marker.setBrush(QBrush(Qt.NoBrush))
                    self.section_scene.addItem(marker)
                    items.append(marker)

                label = QGraphicsSimpleTextItem(size or "100x50")
                label.setFont(font)
                label_rect = label.boundingRect()
                label.setPos(x + w / 2 - label_rect.width() / 2, y + h + label_gap)
                self.section_scene.addItem(label)
                items.append(label)

        if tag:
            tag_item = QGraphicsSimpleTextItem(tag)
            tag_item.setFont(font)
            tag_rect = tag_item.boundingRect()
            if conduit_type == "Ducto":
                grid_w = cols * (item_w + gap_px) - gap_px
                grid_h = rows * (item_h + gap_px) - gap_px
            else:
                grid_w = cols * (item_w + gap) - gap
                grid_h = rows * (item_h + gap) - gap
            tag_item.setPos(grid_w / 2 - tag_rect.width() / 2, grid_h + label_gap)
            self.section_scene.addItem(tag_item)
            items.append(tag_item)

        bounds = self._items_bounds(items)
        if bounds.isNull():
            bounds = QRectF(-60, -60, 120, 120)
        margin = 12.0
        bounds = bounds.adjusted(-margin, -margin, margin, margin)
        self._section_bounds = bounds
        self.section_scene.setSceneRect(bounds)
        if not self._user_zoomed:
            self._fit_section_view(user_action=False)
        if self._is_segment_alive(self._segment):
            fill_percent, max_fill = self._compute_fill_percent()
            self._update_fill_label(fill_percent, max_fill)

    def _apply_zoom_from_user(self, factor: float) -> None:
        self._apply_zoom(factor, user_action=True)

    def _apply_zoom(self, factor: float, user_action: bool = False) -> None:
        if factor <= 0:
            return
        target = self._zoom * factor
        target = max(self._min_zoom, min(self._max_zoom, target))
        if target == self._zoom:
            return
        applied = target / self._zoom
        self.view.scale(applied, applied)
        self._zoom = target
        if user_action:
            self._user_zoomed = True
        self._update_zoom_label()

    def _set_zoom(self, scale_value: float, user_action: bool = False) -> None:
        target = max(self._min_zoom, min(self._max_zoom, scale_value))
        self.view.resetTransform()
        self.view.scale(target, target)
        self._zoom = target
        if user_action:
            self._user_zoomed = True
        self._update_zoom_label()
        if not self._section_bounds.isNull():
            self.view.centerOn(self._section_bounds.center())

    def _update_zoom_label(self) -> None:
        self.lbl_zoom.setText(f"{int(self._zoom * 100)}%")

    def _fit_section_view(self, user_action: bool = False) -> None:
        if self._section_bounds.isNull():
            return
        self.view.fitInView(self._section_bounds, Qt.KeepAspectRatio)
        new_zoom = self.view.transform().m11() or 1.0
        self._zoom = max(self._min_zoom, min(self._max_zoom, new_zoom))
        if user_action:
            self._user_zoomed = True
        self._update_zoom_label()

    def _sync_columns(self) -> tuple:
        n = int(self.spin_qty.value() or 1)
        cols = int(self.spin_cols.value() or 1)
        cols = max(1, min(cols, n))
        if cols != self.spin_cols.value():
            self.spin_cols.blockSignals(True)
            self.spin_cols.setValue(cols)
            self.spin_cols.blockSignals(False)
        return n, cols

    def _add_u_profile(self, x: float, y: float, w: float, h: float, lip: float, pen: QPen):
        path = QPainterPath()
        path.moveTo(x + lip, y)
        path.lineTo(x, y)
        path.lineTo(x, y + h)
        path.lineTo(x + w, y + h)
        path.lineTo(x + w, y)
        path.lineTo(x + w - lip, y)
        item = QGraphicsPathItem(path)
        item.setPen(pen)
        item.setBrush(QBrush(Qt.NoBrush))
        self.section_scene.addItem(item)
        return item

    def _parse_rect_size(self, text: str) -> tuple:
        nums = [int(n) for n in re.findall(r"\d+", text or "")]
        if len(nums) >= 2:
            return float(nums[0]), float(nums[1])
        return 160.0, 80.0

    def _normalize_rect_size(self, size: tuple, max_dim: float = 160.0) -> tuple:
        w, h = size
        if w <= 0 or h <= 0:
            return 160.0, 80.0
        scale = min(1.0, max_dim / max(w, h))
        w = w * scale
        h = h * scale
        w = max(90.0, min(180.0, w))
        h = max(40.0, min(120.0, h))
        return w, h

    def _reload_sizes_for_type(
        self,
        conduit_type: Optional[str] = None,
        desired: Optional[str] = None,
        duct_standard: Optional[str] = None,
        duct_uid: Optional[str] = None,
    ) -> None:
        conduit_type = conduit_type or self.cmb_type.currentText().strip()
        if conduit_type == "Ducto":
            self._reload_duct_standards(desired_standard=duct_standard)
            self._reload_ducts_for_standard(
                self._current_duct_standard(),
                desired_id=duct_uid,
                desired_label=desired,
            )
            return
        current = desired if desired is not None else self.cmb_size.currentText().strip()
        options = self._available_sizes(conduit_type)
        self.cmb_size.blockSignals(True)
        self.cmb_size.clear()
        if options:
            for size in options:
                self.cmb_size.addItem(size)
            if current and current in options:
                self.cmb_size.setCurrentIndex(options.index(current))
            else:
                self.cmb_size.setCurrentIndex(0)
            self.cmb_size.setEnabled(True)
        else:
            self.cmb_size.addItem("Sin tamaños en BD")
            self.cmb_size.setEnabled(False)
        self.cmb_size.blockSignals(False)

    def _available_sizes(self, conduit_type: str) -> list:
        if self._material_service:
            if conduit_type == "Ducto":
                return self._material_service.list_duct_sizes()
            elif conduit_type == "EPC":
                return self._material_service.list_epc_sizes()
            elif conduit_type == "BPC":
                return self._material_service.list_bpc_sizes()
        return list(self._size_options.get(conduit_type, []))

    def _reload_duct_standards(self, desired_standard: Optional[str] = None) -> None:
        standards = self._material_service.list_duct_standards() if self._material_service else []
        current = str(desired_standard or "").strip()
        self.cmb_duct_standard.blockSignals(True)
        self.cmb_duct_standard.clear()
        self.cmb_duct_standard.addItem("(sin selección)", "")
        for std in standards:
            self.cmb_duct_standard.addItem(std, std)
        if current:
            idx = self.cmb_duct_standard.findData(current)
            if idx >= 0:
                self.cmb_duct_standard.setCurrentIndex(idx)
        self.cmb_duct_standard.blockSignals(False)
        if standards:
            self.cmb_duct_standard.setToolTip("")
        else:
            self.cmb_duct_standard.setToolTip("Sin normas en BD")

    def _reload_ducts_for_standard(
        self,
        standard: Optional[str],
        desired_id: Optional[str] = None,
        desired_label: Optional[str] = None,
    ) -> None:
        ducts = self._material_service.list_ducts_by_standard(standard) if self._material_service else []
        self.cmb_duct.blockSignals(True)
        self.cmb_duct.clear()
        if ducts:
            for duct in ducts:
                label = str(duct.get("name") or duct.get("nominal") or duct.get("code") or "")
                self.cmb_duct.addItem(label, str(duct.get("uid") or ""))
            selected = self._resolve_duct_uid(ducts, desired_id, desired_label)
            if selected:
                idx = self.cmb_duct.findData(selected)
                if idx >= 0:
                    self.cmb_duct.setCurrentIndex(idx)
            self.cmb_duct.setEnabled(True)
            self.cmb_duct.setToolTip("")
        else:
            self.cmb_duct.addItem("Sin ductos en BD", "")
            self.cmb_duct.setEnabled(False)
            std_label = str(standard or "").strip() or "(sin selección)"
            self.cmb_duct.setToolTip(f"Sin ductos para norma: {std_label}")
        self.cmb_duct.blockSignals(False)

    def _resolve_duct_uid(
        self,
        ducts: List[Dict[str, object]],
        desired_id: Optional[str],
        desired_label: Optional[str],
    ) -> Optional[str]:
        if desired_id:
            desired_norm = str(desired_id).strip().lower()
            for duct in ducts:
                if str(duct.get("uid") or "").strip().lower() == desired_norm:
                    return str(duct.get("uid") or "")
                if str(duct.get("code") or "").strip().lower() == desired_norm:
                    return str(duct.get("uid") or "")
        if desired_label:
            desired_norm = str(desired_label).strip().lower()
            for duct in ducts:
                name = str(duct.get("name") or "").strip().lower()
                nominal = str(duct.get("nominal") or "").strip().lower()
                if desired_norm and desired_norm in (name, nominal):
                    return str(duct.get("uid") or "")
        return None

    def _current_duct_standard(self) -> str:
        if not self.cmb_duct_standard.isEnabled():
            return ""
        return str(self.cmb_duct_standard.currentData() or "").strip()

    def _current_duct_uid(self) -> str:
        if not self.cmb_duct.isEnabled():
            return ""
        return str(self.cmb_duct.currentData() or "").strip()

    def _current_duct_item(self) -> Dict[str, object]:
        duct_uid = self._current_duct_uid()
        if not duct_uid or not self._material_service:
            return {}
        ducts = self._material_service.list_ducts_by_standard(self._current_duct_standard())
        for duct in ducts:
            if str(duct.get("uid") or "") == duct_uid:
                return duct
        return {}

    def _current_duct_label(self) -> str:
        item = self._current_duct_item()
        if item:
            return str(item.get("name") or item.get("nominal") or item.get("code") or "")
        return self.cmb_duct.currentText().strip()

    def _build_duct_snapshot(self, duct_uid: str) -> Dict[str, object]:
        if not self._material_service:
            return {}
        item = self._material_service.get_duct_material_by_uid(duct_uid)
        if not item:
            return {}
        return {
            "uid": str(item.get("uid") or ""),
            "code": str(item.get("code") or ""),
            "name": str(item.get("name") or item.get("nominal") or ""),
            "shape": str(item.get("shape") or ""),
            "inner_diameter_mm": item.get("inner_diameter_mm"),
            "max_fill_percent": item.get("max_fill_percent"),
            "standard": item.get("standard"),
            "material": item.get("material"),
        }

    def _current_size_for_type(self, conduit_type: str, fallback: str) -> str:
        if conduit_type == "Ducto":
            return self._current_duct_label() or fallback
        if not self.cmb_size.isEnabled():
            return fallback
        current = self.cmb_size.currentText().strip()
        return current or fallback

    def _ensure_valid_size_selection(self, conduit_type: str, fallback: str = "") -> str:
        if conduit_type == "Ducto":
            return self._current_duct_label() or fallback
        if not self.cmb_size.isEnabled():
            return fallback
        sizes = self._available_sizes(conduit_type)
        if not sizes:
            return fallback
        current = self.cmb_size.currentText().strip()
        if current in sizes:
            return current
        self.cmb_size.blockSignals(True)
        self.cmb_size.setCurrentIndex(0)
        self.cmb_size.blockSignals(False)
        return self.cmb_size.currentText().strip()

    def _duct_dimensions_mm(self, size: str, duct_id: Optional[str] = None) -> Tuple[float, float]:
        if self._material_service:
            if duct_id:
                dims = self._material_service.get_duct_dimensions_by_uid(duct_id)
            else:
                dims = self._material_service.get_duct_dimensions(size)
            return float(dims.get("inner_diameter_mm", 0.0)), float(dims.get("outer_diameter_mm", 0.0))
        inner = self._fallback_duct_inner_mm(size)
        outer = inner + max(4.0, inner * 0.1)
        return inner, outer

    def _rect_dimensions_mm(self, conduit_type: str, size: str) -> Tuple[float, float]:
        if self._material_service:
            dims = self._material_service.get_rect_dimensions(conduit_type.lower(), size)
            return float(dims.get("inner_width_mm", 0.0)), float(dims.get("inner_height_mm", 0.0))
        return self._parse_rect_size(size)

    def _fallback_duct_inner_mm(self, size: str) -> float:
        nums = [int(n) for n in re.findall(r"\d+", size or "")]
        if "mm" in (size or "").lower() and nums:
            return float(nums[0])
        if nums:
            return float(nums[0]) * 25.4
        return 50.0

    def _normalize_circle_pixels(self, outer_mm: float, inner_mm: float) -> Tuple[float, float]:
        if outer_mm <= 0:
            return 70.0, 54.0
        max_px = 90.0
        min_px = 60.0
        scale = min(1.0, max_px / outer_mm)
        outer_px = outer_mm * scale
        if outer_px < min_px:
            scale = min_px / outer_mm
            outer_px = min_px
        inner_px = inner_mm * scale if inner_mm > 0 else outer_px - 12.0
        inner_px = min(inner_px, outer_px - 6.0)
        if inner_px <= 0:
            inner_px = outer_px - 12.0
        return outer_px, inner_px

    def _spacing_is_applicable(self) -> bool:
        return self.cmb_type.currentText().strip() == "Ducto" and int(self.spin_qty.value() or 1) > 1

    def _update_spacing_visibility(self) -> None:
        visible = self._spacing_is_applicable()
        self.spin_spacing.setVisible(visible)
        self.lbl_spacing.setVisible(visible)

    def _update_type_controls_visibility(self, conduit_type: Optional[str] = None) -> None:
        conduit_type = conduit_type or self.cmb_type.currentText().strip()
        is_duct = conduit_type == "Ducto"
        self.lbl_duct_standard.setVisible(is_duct)
        self.cmb_duct_standard.setVisible(is_duct)
        self.lbl_duct.setVisible(is_duct)
        self.cmb_duct.setVisible(is_duct)
        self.lbl_size.setVisible(not is_duct)
        self.cmb_size.setVisible(not is_duct)

    def _apply_default_spacing_for_size(self, size: str, duct_id: Optional[str] = None) -> None:
        self._set_spacing_value(self._default_duct_spacing_mm(size, duct_id))

    def _set_spacing_value(self, value: float) -> None:
        self._setting_spacing = True
        self.spin_spacing.setValue(float(value))
        self._setting_spacing = False

    def _default_duct_spacing_mm(self, size: str, duct_id: Optional[str] = None) -> float:
        _, outer_mm = self._duct_dimensions_mm(size, duct_id)
        if outer_mm <= 0:
            return 25.0
        return max(25.0, 0.25 * outer_mm)

    def _current_spacing_mm(self, size: str, duct_id: Optional[str] = None) -> float:
        if not self._spacing_is_applicable():
            return 0.0
        spacing = float(self.spin_spacing.value() or 0.0)
        if spacing <= 0 and not self._spacing_custom:
            spacing = self._default_duct_spacing_mm(size, duct_id)
        return max(0.0, spacing)

    def _duct_pixels_per_mm(self, outer_mm: float) -> float:
        if outer_mm <= 0:
            return 1.2
        target_px = 80.0
        scale = target_px / outer_mm
        return max(0.4, min(2.0, scale))

    def _load_spacing_from_props(self, props: Dict[str, object], size: str) -> None:
        spacing = props.get("duct_spacing_mm")
        custom = bool(props.get("duct_spacing_custom"))
        if spacing is None or (not custom and float(spacing or 0.0) <= 0.0):
            spacing = self._default_duct_spacing_mm(size, self._current_duct_uid())
            custom = False
        self._spacing_custom = custom
        self._set_spacing_value(float(spacing or 0.0))

    def _items_bounds(self, items) -> QRectF:
        rect = QRectF()
        for it in items:
            try:
                rect = rect.united(it.mapToScene(it.boundingRect()).boundingRect())
            except Exception:
                continue
        return rect

    def _is_segment_alive(self, segment_item: Optional[object]) -> bool:
        if segment_item is None:
            return False
        try:
            return segment_item.scene() is not None
        except RuntimeError:
            return False

    def _segment_cables(self) -> List[Dict[str, object]]:
        if not self._is_segment_alive(self._segment):
            return []
        props = self._segment_props(self._segment)
        return list(props.get("cables") or [])

    def _calc_context(self) -> Optional[Dict[str, object]]:
        calc = getattr(self._project, "_calc", None) if self._project is not None else None
        return calc if isinstance(calc, dict) else None

    def _edge_cables_from_calc(self) -> List[Dict[str, object]]:
        if not self._is_segment_alive(self._segment):
            return []
        calc = self._calc_context()
        if not calc:
            return []
        edge_to_circuits = calc.get("edge_to_circuits")
        if not isinstance(edge_to_circuits, dict):
            return []
        circuit_ids = list(edge_to_circuits.get(self._segment.edge_id, []) or [])
        if not circuit_ids:
            return []
        circuits = list((getattr(self._project, "circuits", {}) or {}).get("items") or [])
        by_id = {str(c.get("id") or ""): c for c in circuits if c.get("id")}
        cables: List[Dict[str, object]] = []
        for cid in circuit_ids:
            circuit = by_id.get(str(cid) or "")
            if not circuit:
                continue
            cable_ref = str(circuit.get("cable_ref") or "")
            if not cable_ref:
                continue
            qty = int(circuit.get("qty", 1) or 1)
            diameter = 0.0
            if self._material_service:
                diameter = float(self._material_service.get_cable_outer_diameter(cable_ref) or 0.0)
            if diameter <= 0:
                continue
            cables.append({"outer_diameter_mm": diameter, "qty": qty})
        return cables

    def _compute_fill_percent(self) -> Tuple[float, float]:
        if self._is_segment_alive(self._segment):
            props = self._segment_props(self._segment)
            if not self._preview_dirty:
                calc = self._calc_context()
                fill_results = calc.get("fill_results") if calc else None
                if isinstance(fill_results, dict):
                    entry = fill_results.get(self._segment.edge_id)
                    if entry:
                        try:
                            return float(entry.get("fill_percent") or 0.0), float(entry.get("fill_max_percent") or 0.0)
                        except Exception:
                            pass
                try:
                    fill_percent = float(props.get("fill_percent") or 0.0)
                    fill_max = float(props.get("fill_max_percent") or 0.0)
                    return fill_percent, fill_max
                except Exception:
                    pass

        conduit_type = self.cmb_type.currentText().strip()
        size = self.cmb_size.currentText().strip()
        n, _ = self._sync_columns()
        cables = self._edge_cables_from_calc() or self._segment_cables()
        expanded = self._expand_cables(cables)
        cable_groups = self._split_cables(n, expanded)

        if conduit_type == "Ducto":
            duct_id = self._current_duct_uid()
            size_label = self._current_duct_label() or size
            material = self._duct_material(size_label, duct_id)
            max_fill = get_material_max_fill_percent(material, DEFAULT_DUCT_MAX_FILL_PERCENT)
            fills = [calc_duct_fill(material, cables) for cables in cable_groups]
        else:
            material = self._rect_material(conduit_type, size)
            max_fill = get_material_max_fill_percent(material, DEFAULT_TRAY_MAX_FILL_PERCENT)
            fills = [calc_tray_fill(material, cables, has_separator=False) for cables in cable_groups]

        fill_percent = max(fills) if fills else 0.0
        return float(fill_percent), float(max_fill)

    def _usable_area_mm2(self, conduit_type: str, size: str, duct_id: Optional[str]) -> float:
        if conduit_type == "Ducto":
            material = self._duct_material(size, duct_id)
            usable_area = float(material.get("usable_area_mm2") or 0.0)
            if usable_area > 0:
                return usable_area
            inner_mm = float(material.get("inner_diameter_mm") or 0.0)
            if inner_mm > 0:
                r = inner_mm / 2.0
                return math.pi * r * r
            return 0.0
        material = self._rect_material(conduit_type, size)
        usable_area = float(material.get("usable_area_mm2") or 0.0)
        if usable_area > 0:
            return usable_area
        w_mm = float(material.get("inner_width_mm") or 0.0)
        h_mm = float(material.get("inner_height_mm") or 0.0)
        return max(0.0, w_mm * h_mm)

    def _update_fill_label(self, fill_percent: float, max_fill: float) -> None:
        fill_percent_disp = round2(fill_percent)
        max_fill_disp = round2(max_fill)
        if max_fill_disp > 0:
            text = f"Ocupacion: {fmt_percent(fill_percent_disp)} (max {fmt_percent(max_fill_disp)})"
        else:
            text = f"Ocupacion: {fmt_percent(fill_percent_disp)}"
        self.lbl_status.setText(text)
        fill_state = util_color(fill_percent, max_fill)
        color = {
            "ok": "#16a34a",
            "warn": "#f59e0b",
            "over": "#dc2626",
        }.get(str(fill_state), "")
        self.lbl_status.setStyleSheet(f"color: {color};" if color else "")

    def _duct_material(self, size: str, duct_id: Optional[str] = None) -> Dict[str, object]:
        if self._material_service:
            if duct_id:
                material = self._material_service.get_duct_material_by_uid(duct_id)
            else:
                material = self._material_service.get_duct_material(size)
        else:
            material = {}
        if not material:
            inner_mm, _ = self._duct_dimensions_mm(size, duct_id)
            material = {"inner_diameter_mm": inner_mm}
        return material

    def _rect_material(self, conduit_type: str, size: str) -> Dict[str, object]:
        if self._material_service:
            material = self._material_service.get_rect_material(conduit_type.lower(), size)
        else:
            material = {}
        if not material:
            w_mm, h_mm = self._rect_dimensions_mm(conduit_type, size)
            material = {"inner_width_mm": w_mm, "inner_height_mm": h_mm}
        return material

    def _expand_cables(self, cables: List[Dict[str, object]]) -> List[Dict[str, object]]:
        expanded: List[Dict[str, object]] = []
        palette = [
            QColor("#bae6fd"),
            QColor("#bbf7d0"),
            QColor("#fde68a"),
            QColor("#fecdd3"),
            QColor("#ddd6fe"),
            QColor("#fed7aa"),
        ]
        idx = 0
        for c in cables or []:
            code = str(c.get("code") or "")
            qty = int(c.get("qty", 1) or 1)
            diameter = 0.0
            if self._material_service and code:
                diameter = float(self._material_service.get_cable_outer_diameter(code) or 0.0)
            if diameter <= 0:
                diameter = float(c.get("outer_diameter_mm") or 0.0)
            if diameter <= 0:
                diameter = 12.0
            for _ in range(max(1, qty)):
                expanded.append(
                    {
                        "code": code,
                        "outer_diameter_mm": diameter,
                        "color": palette[idx % len(palette)],
                    }
                )
                idx += 1
        return expanded

    def _split_cables(self, n: int, cables: List[Dict[str, object]]) -> List[List[Dict[str, object]]]:
        groups: List[List[Dict[str, object]]] = [[] for _ in range(max(1, n))]
        if not cables:
            return groups
        for idx, cable in enumerate(cables):
            groups[idx % len(groups)].append(cable)
        return groups

    def _overfill_pen(self) -> QPen:
        pen = QPen(QColor("#ef4444"), 2)
        pen.setStyle(Qt.DashLine)
        return pen

    def _cable_pen(self) -> QPen:
        return QPen(QColor("#d1d5db"), 0.8)

    def _draw_cables_in_circle(
        self,
        x: float,
        y: float,
        inner_px: float,
        inner_mm: float,
        cables: List[Dict[str, object]],
    ) -> Tuple[List[QGraphicsEllipseItem], bool]:
        items: List[QGraphicsEllipseItem] = []
        if not cables or inner_px <= 0:
            return items, False
        count = len(cables)
        cols = max(1, int(math.ceil(math.sqrt(count))))
        rows = max(1, int(math.ceil(count / cols)))
        cell = inner_px / max(cols, rows)
        scale = inner_px / inner_mm if inner_mm > 0 else 1.0
        overfull = False
        cx = x + inner_px / 2.0
        cy = y + inner_px / 2.0
        pen = self._cable_pen()
        for i, cable in enumerate(cables):
            r = i // cols
            c = i % cols
            center_x = x + cell * (c + 0.5)
            center_y = y + cell * (r + 0.5)
            diameter = float(cable.get("outer_diameter_mm") or 0.0)
            radius = max(2.0, (diameter * scale) / 2.0)
            if radius * 2.0 > cell:
                overfull = True
            dist = math.hypot(center_x - cx, center_y - cy)
            if dist + radius > inner_px / 2.0:
                overfull = True
            item = QGraphicsEllipseItem(center_x - radius, center_y - radius, radius * 2.0, radius * 2.0)
            item.setPen(pen)
            item.setBrush(QBrush(cable.get("color") or QColor("#e5e7eb")))
            self.section_scene.addItem(item)
            items.append(item)
        return items, overfull

    def _draw_cables_in_rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        w_mm: float,
        h_mm: float,
        cables: List[Dict[str, object]],
    ) -> Tuple[List[QGraphicsEllipseItem], bool]:
        items: List[QGraphicsEllipseItem] = []
        if not cables or w <= 0 or h <= 0:
            return items, False
        scale = min(w / w_mm if w_mm > 0 else 1.0, h / h_mm if h_mm > 0 else 1.0)
        diameters = [max(0.0, float(c.get("outer_diameter_mm") or 0.0)) * scale for c in cables]
        max_d = max(diameters) if diameters else 0.0
        if max_d <= 0:
            max_d = min(w, h) * 0.2
        gap = 2.0
        cell = max_d + gap
        cols = max(1, int((w + gap) / cell))
        rows = max(1, int(math.ceil(len(cables) / cols)))
        used_w = cols * cell - gap
        used_h = rows * cell - gap
        start_x = x + (w - used_w) / 2.0 + max_d / 2.0
        start_y = y + (h - used_h) / 2.0 + max_d / 2.0
        overfull = used_w > w + 0.1 or used_h > h + 0.1 or max_d > min(w, h)
        pen = self._cable_pen()
        for i, cable in enumerate(cables):
            r = i // cols
            c = i % cols
            center_x = start_x + c * cell
            center_y = start_y + r * cell
            diameter = max_d
            if i < len(diameters) and diameters[i] > 0:
                diameter = max(2.0, diameters[i])
            radius = diameter / 2.0
            if radius * 2.0 > cell:
                overfull = True
            item = QGraphicsEllipseItem(center_x - radius, center_y - radius, radius * 2.0, radius * 2.0)
            item.setPen(pen)
            item.setBrush(QBrush(cable.get("color") or QColor("#e5e7eb")))
            self.section_scene.addItem(item)
            items.append(item)
        return items, overfull

    def _rect_marker_path(self, x: float, y: float, w: float, h: float) -> QPainterPath:
        path = QPainterPath()
        path.addRect(QRectF(x + 1.0, y + 1.0, max(1.0, w - 2.0), max(1.0, h - 2.0)))
        return path

    def closeEvent(self, event) -> None:
        event.accept()


