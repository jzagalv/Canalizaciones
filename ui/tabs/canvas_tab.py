# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, Optional

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QSlider,
    QToolButton,
    QMessageBox,
)

from domain.calculations.formatting import fmt_percent, util_color
from domain.entities.models import Project
from ui.canvas.canvas_scene import CanvasScene
from ui.canvas.canvas_items import EdgeItem
from ui.canvas.canvas_view import CanvasView
from ui.widgets.library_panel import LibraryPanel


class CanvasTab(QWidget):
    project_changed = pyqtSignal()
    selection_changed = pyqtSignal(dict)  # snapshot
    segment_double_clicked = pyqtSignal(object)
    segment_removed = pyqtSignal(str)
    equipment_add_requested = pyqtSignal(str, str)
    troncal_create_requested = pyqtSignal()
    troncal_add_requested = pyqtSignal()
    troncal_remove_requested = pyqtSignal()
    edit_edge_tag_requested = pyqtSignal(str)
    edit_node_tag_requested = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._project: Optional[Project] = None
        self._selection_snapshot: Dict = {}
        self.scene = CanvasScene()
        self.scene.signals.project_changed.connect(self.project_changed)
        self.scene.signals.selection_changed.connect(self.selection_changed)
        self.scene.signals.selection_changed.connect(self._on_selection_changed)
        self.scene.signals.library_item_used.connect(self._on_library_item_used)
        self.scene.signals.library_item_released.connect(self._on_library_item_released)
        self.scene.signals.segment_double_clicked.connect(self.segment_double_clicked)
        self.scene.signals.segment_removed.connect(self.segment_removed)

        self._suspend_view_updates = False

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)

        # ---------------- Top toolbar ----------------
        top = QHBoxLayout()
        root.addLayout(top)

        self.btn_connect = QPushButton("Conectar tramo")
        self.btn_connect.setCheckable(True)
        self.btn_connect.toggled.connect(self._on_connect_toggled)
        top.addWidget(self.btn_connect)

        self.btn_delete = QPushButton("Eliminar seleccionado")
        self.btn_delete.clicked.connect(self.scene.delete_selected)
        top.addWidget(self.btn_delete)

        top.addSpacing(12)

        self.btn_load_plan = QPushButton("Cargar plano…")
        self.btn_load_plan.clicked.connect(self._load_background)
        top.addWidget(self.btn_load_plan)

        self.btn_fit = QPushButton("Ajustar a vista")
        self.btn_fit.clicked.connect(self._fit_background)
        top.addWidget(self.btn_fit)

        self.btn_lock_bg = QToolButton()
        self.btn_lock_bg.setText("Fondo bloqueado")
        self.btn_lock_bg.setCheckable(True)
        self.btn_lock_bg.setChecked(True)
        self.btn_lock_bg.toggled.connect(self._toggle_bg_lock)
        top.addWidget(self.btn_lock_bg)

        self.slider_bg_opacity = QSlider(Qt.Horizontal)
        self.slider_bg_opacity.setRange(10, 100)
        self.slider_bg_opacity.setValue(100)
        self.slider_bg_opacity.setFixedWidth(160)
        self.slider_bg_opacity.valueChanged.connect(self._on_bg_opacity_changed)
        top.addWidget(QLabel("Opacidad"))
        top.addWidget(self.slider_bg_opacity)

        self.btn_export_png = QPushButton("Exportar PNG")
        self.btn_export_png.clicked.connect(self._export_png)
        top.addWidget(self.btn_export_png)

        self.btn_export_pdf = QPushButton("Exportar PDF")
        self.btn_export_pdf.clicked.connect(self._export_pdf)
        top.addWidget(self.btn_export_pdf)

        top.addStretch(1)

        # ---------------- Main splitter ----------------
        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        self.library_panel = LibraryPanel()
        self.library_panel.equipmentRequestedAdd.connect(self.equipment_add_requested)
        splitter.addWidget(self.library_panel)

        self.view = CanvasView(self.scene)
        self.view.view_state_changed.connect(self._on_view_state_changed)
        self.view.troncal_create_requested.connect(self.troncal_create_requested)
        self.view.troncal_add_requested.connect(self.troncal_add_requested)
        self.view.troncal_remove_requested.connect(self.troncal_remove_requested)
        self.view.edit_edge_tag_requested.connect(self.edit_edge_tag_requested)
        self.view.edit_node_tag_requested.connect(self.edit_node_tag_requested)
        splitter.addWidget(self.view)

        self.detail_panel = QWidget()
        detail_layout = QVBoxLayout(self.detail_panel)
        detail_layout.addWidget(QLabel("Detalle del tramo"))
        self.lbl_detail_fill = QLabel("(sin seleccion)")
        self.lbl_detail_fill.setWordWrap(True)
        detail_layout.addWidget(self.lbl_detail_fill)
        detail_layout.addStretch(1)
        self.detail_panel.setMinimumWidth(220)
        splitter.addWidget(self.detail_panel)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)

    # ---------------- Integration ----------------
    def set_equipment_items(self, items_by_id: Dict[str, Dict]):
        try:
            self.scene.set_equipment_items(items_by_id)
            self.library_panel.set_equipment_items(items_by_id)
            self._sync_library_usage_from_canvas()
        except Exception:
            pass

    def refresh_library_used_markers(self) -> None:
        self._sync_library_usage_from_canvas()

    def set_project(self, project: Project) -> None:
        self._project = project
        self.scene.set_project_canvas(project.canvas)
        self._project.canvas = self.scene.get_project_canvas()
        self._sync_bg_controls_from_model()
        self._apply_view_state_from_model()
        self._sync_library_usage_from_canvas()
        self._refresh_detail_panel()

    def set_edge_statuses(self, fill_results: Dict[str, Dict]) -> None:
        # fill_results: edge_id -> {status}
        for edge_id, sol in (fill_results or {}).items():
            status = str(sol.get("status") or "OK")
            status_norm = "error" if status.strip().lower() == "no cumple" else "ok"
            self.scene.set_edge_status(edge_id, status_norm, "")
        self._refresh_detail_panel()

    # ---------------- Actions: nodes/edges ----------------
    def _on_connect_toggled(self, on: bool):
        self.scene.set_connect_mode(on)

    def _sync_library_usage_from_canvas(self) -> None:
        if not self._project:
            return
        used_ids = self.get_used_equipment_ids()
        self.library_panel.update_library_tree_used_markers(used_ids)

    def get_used_equipment_ids(self) -> set[str]:
        if not self._project:
            return set()
        return {
            str(n.get("library_item_id"))
            for n in (self._project.canvas.get("nodes") or [])
            if n.get("library_item_id")
        }

    def get_selected_edge_ids(self) -> list[str]:
        return [
            it.edge_id
            for it in (self.scene.selectedItems() or [])
            if isinstance(it, EdgeItem)
        ]

    def _on_library_item_used(self, library_id: str) -> None:
        self.library_panel.set_library_item_state_by_id(library_id, "used")

    def _on_library_item_released(self, library_id: str) -> None:
        self.library_panel.set_library_item_state_by_id(library_id, "available")

    def _on_selection_changed(self, payload: Dict) -> None:
        self._selection_snapshot = dict(payload or {})
        self._refresh_detail_panel()

    def get_selection_snapshot(self) -> Dict:
        return dict(self._selection_snapshot or {})

    def _refresh_detail_panel(self) -> None:
        payload = self._selection_snapshot or {}
        if not self._project or payload.get("kind") != "edge":
            self.lbl_detail_fill.setText("(sin seleccion)")
            self.lbl_detail_fill.setStyleSheet("")
            return
        edge_id = str(payload.get("id") or "")
        props = self._edge_props(edge_id)
        fill_info = self.scene.get_edge_fill_results(edge_id) or {}
        fill_percent = fill_info.get("fill_percent", props.get("fill_percent"))
        max_fill = fill_info.get("fill_max_percent", props.get("fill_max_percent"))
        if fill_percent is None:
            self.lbl_detail_fill.setText("Ocupacion: (Recalcular)")
            self.lbl_detail_fill.setStyleSheet("color: #9ca3af;")
            return
        fill_state = fill_info.get("fill_state", props.get("fill_state")) or util_color(fill_percent, max_fill)
        if max_fill and float(max_fill) > 0:
            text = f"Ocupacion: {fmt_percent(fill_percent)} (max {fmt_percent(max_fill)})"
        else:
            text = f"Ocupacion: {fmt_percent(fill_percent)}"
        color = {
            "ok": "#16a34a",
            "warn": "#f59e0b",
            "over": "#dc2626",
        }.get(str(fill_state), "")
        self.lbl_detail_fill.setText(text)
        self.lbl_detail_fill.setStyleSheet(f"color: {color};" if color else "")

    def _edge_props(self, edge_id: str) -> Dict[str, object]:
        edges = list((self._project.canvas or {}).get("edges") or []) if self._project else []
        for edge in edges:
            if str(edge.get("id")) == str(edge_id):
                return dict(edge.get("props") or {})
        return {}

    def _on_view_state_changed(self, state: Dict) -> None:
        if self._suspend_view_updates or not self._project:
            return
        self._project.canvas.setdefault("view", {})
        self._project.canvas["view"] = {
            "scale": float(state.get("scale", 1.0) or 1.0),
            "center": list(state.get("center") or [0.0, 0.0]),
        }
        self.project_changed.emit()

    def _apply_view_state_from_model(self) -> None:
        if not self._project:
            return
        view_state = (self._project.canvas or {}).get("view") or {}
        if not view_state:
            return
        self._suspend_view_updates = True
        try:
            self.view.set_view_state(view_state)
        finally:
            self._suspend_view_updates = False

    # ---------------- Background plan ----------------
    def _sync_bg_controls_from_model(self):
        bg = (self._project.canvas.get("background") or {}) if self._project else {}
        op = float(bg.get("opacity", 1.0) or 1.0)
        locked = bool(bg.get("locked", True))
        self.slider_bg_opacity.blockSignals(True)
        self.slider_bg_opacity.setValue(int(round(max(0.1, min(1.0, op)) * 100)))
        self.slider_bg_opacity.blockSignals(False)
        self.btn_lock_bg.blockSignals(True)
        self.btn_lock_bg.setChecked(locked)
        self.btn_lock_bg.setText("Fondo bloqueado" if locked else "Fondo desbloqueado")
        self.btn_lock_bg.blockSignals(False)

    def _load_background(self):
        if not self._project:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar plano (imagen)",
            "",
            "Imágenes (*.png *.jpg *.jpeg *.bmp *.webp);;Todos (*.*)",
        )
        if not path:
            return
        try:
            self.scene.set_background_image(path)
            self._sync_bg_controls_from_model()
            self._fit_background()
        except Exception as e:
            QMessageBox.warning(self, "Plano", f"No se pudo cargar el plano:\n{e}")

    def _fit_background(self):
        bg_rect = self.scene.background_bounding_rect()
        if bg_rect is None:
            return
        self.view.fitInView(bg_rect, Qt.KeepAspectRatio)
        self.view.refresh_view_state()

    def _toggle_bg_lock(self, locked: bool):
        self.btn_lock_bg.setText("Fondo bloqueado" if locked else "Fondo desbloqueado")
        self.scene.set_background_locked(locked)

    def _on_bg_opacity_changed(self, value: int):
        self.scene.set_background_opacity(float(value) / 100.0)

    # ---------------- Export ----------------
    def _export_png(self):
        if not self._project:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar canvas a PNG", "canvas.png", "PNG (*.png)")
        if not path:
            return
        try:
            self.scene.export_to_png(path)
        except Exception as e:
            QMessageBox.warning(self, "Exportar PNG", f"No se pudo exportar:\n{e}")

    def _export_pdf(self):
        if not self._project:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar canvas a PDF", "canvas.pdf", "PDF (*.pdf)")
        if not path:
            return
        try:
            self.scene.export_to_pdf(path)
        except Exception as e:
            QMessageBox.warning(self, "Exportar PDF", f"No se pudo exportar:\n{e}")



