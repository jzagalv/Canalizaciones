# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, Optional, List

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QSlider,
    QToolButton,
    QMessageBox,
)

from domain.entities.models import Project
from ui.canvas.canvas_scene import CanvasScene
from ui.canvas.canvas_view import CanvasView
from ui.widgets.library_panel import LibraryPanel


class CanvasTab(QWidget):
    project_changed = pyqtSignal()
    selection_changed = pyqtSignal(dict)  # snapshot

    def __init__(self):
        super().__init__()
        self._project: Optional[Project] = None
        self.scene = CanvasScene()
        self.scene.signals.project_changed.connect(self.project_changed)
        self.scene.signals.selection_changed.connect(self.selection_changed)

        self._selected_edge_id: Optional[str] = None
        self._material: Dict = {}
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
        splitter.addWidget(self.library_panel)

        self.view = CanvasView(self.scene)
        self.view.view_state_changed.connect(self._on_view_state_changed)
        splitter.addWidget(self.view)

        # ---------------- Properties panel ----------------
        panel = QWidget()
        panel_l = QVBoxLayout(panel)

        gb = QGroupBox("Propiedades de tramo")
        form = QFormLayout(gb)
        self.lbl_sel_edge = QLabel("—")

        self.cmb_kind = QComboBox()
        self.cmb_kind.addItems(["duct", "epc", "bpc"])
        self.cmb_kind.currentTextChanged.connect(self._on_edge_kind_changed)

        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems(["auto", "manual"])
        self.cmb_mode.currentTextChanged.connect(self._on_edge_mode_changed)

        self.cmb_run_catalog = QComboBox()
        self.cmb_run_catalog.currentTextChanged.connect(self._on_edge_run_changed)

        self.spin_run_qty = QSpinBox()
        self.spin_run_qty.setRange(1, 99)
        self.spin_run_qty.valueChanged.connect(self._on_edge_run_changed)

        form.addRow("Selección:", self.lbl_sel_edge)
        form.addRow("Tipo:", self.cmb_kind)
        form.addRow("Modo:", self.cmb_mode)
        form.addRow("Catálogo:", self.cmb_run_catalog)
        form.addRow("Cantidad:", self.spin_run_qty)

        panel_l.addWidget(gb)
        panel_l.addStretch(1)
        splitter.addWidget(panel)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)

        self.scene.selectionChanged.connect(self._on_scene_selection_changed)

    # ---------------- Integration ----------------
    def set_material_catalog(self, material: Dict):
        self._material = material or {}
        self._refresh_catalog_options()

    def set_equipment_items(self, items_by_id: Dict[str, Dict]):
        try:
            self.scene.set_equipment_items(items_by_id)
            self.library_panel.set_equipment_items(items_by_id)
        except Exception:
            pass

    def set_project(self, project: Project) -> None:
        self._project = project
        self.scene.set_project_canvas(project.canvas)
        self._project.canvas = self.scene.get_project_canvas()
        self._sync_bg_controls_from_model()
        self._apply_view_state_from_model()

    def set_edge_statuses(self, solutions: Dict[str, Dict]) -> None:
        # solutions: edge_id -> {status, badge}
        for edge_id, sol in (solutions or {}).items():
            status = sol.get("status", "none")
            badge = sol.get("badge", "")
            self.scene.set_edge_status(edge_id, status, badge)

    # ---------------- Actions: nodes/edges ----------------
    def _on_connect_toggled(self, on: bool):
        self.scene.set_connect_mode(on)

    # ---------------- Selection + edge properties ----------------
    def _on_scene_selection_changed(self):
        sel = self.scene.selectedItems()
        edge = next((it for it in sel if hasattr(it, "edge_id")), None)
        if not edge:
            self._selected_edge_id = None
            self.lbl_sel_edge.setText("—")
            return

        self._selected_edge_id = edge.edge_id
        self.lbl_sel_edge.setText(edge.edge_id)

        self.cmb_kind.blockSignals(True)
        self.cmb_kind.setCurrentText(getattr(edge, "containment_kind", "duct"))
        self.cmb_kind.blockSignals(False)

        self.cmb_mode.blockSignals(True)
        self.cmb_mode.setCurrentText(getattr(edge, "mode", "auto"))
        self.cmb_mode.blockSignals(False)

        # runs
        self._refresh_catalog_options()
        runs = getattr(edge, "runs", []) or []
        if runs:
            r0 = runs[0]
            cid = str(r0.get("catalog_id", ""))
            qty = int(r0.get("qty", 1) or 1)
            self.cmb_run_catalog.blockSignals(True)
            if cid:
                idx = self.cmb_run_catalog.findText(cid)
                if idx >= 0:
                    self.cmb_run_catalog.setCurrentIndex(idx)
            self.cmb_run_catalog.blockSignals(False)
            self.spin_run_qty.blockSignals(True)
            self.spin_run_qty.setValue(qty)
            self.spin_run_qty.blockSignals(False)

    def _on_edge_kind_changed(self, kind: str):
        if not self._selected_edge_id:
            return
        self.scene.set_edge_kind(self._selected_edge_id, kind)
        self._refresh_catalog_options()

    def _on_edge_mode_changed(self, mode: str):
        if not self._selected_edge_id:
            return
        self.scene.set_edge_mode(self._selected_edge_id, mode)

    def _on_edge_run_changed(self, *_):
        if not self._selected_edge_id:
            return
        cid = self.cmb_run_catalog.currentText().strip()
        qty = int(self.spin_run_qty.value() or 1)
        if not cid:
            self.scene.set_edge_runs(self._selected_edge_id, [])
            return
        self.scene.set_edge_runs(self._selected_edge_id, [{"catalog_id": cid, "qty": qty}])

    def _refresh_catalog_options(self):
        """Populate run catalog combo filtered by current edge kind."""
        kind = self.cmb_kind.currentText().strip() or "duct"

        # Heuristic: catalog ids are keys in material dict, grouped by kind substring
        # material schema might vary; this keeps UI functional even with partial libs.
        ids: List[str] = []
        if isinstance(self._material, dict):
            ids = [str(k) for k in self._material.keys()]

        if kind == "duct":
            ids = [i for i in ids if "duct" in i.lower() or "ducto" in i.lower()] or ids
        elif kind == "epc":
            ids = [i for i in ids if "epc" in i.lower()] or ids
        elif kind == "bpc":
            ids = [i for i in ids if "bpc" in i.lower()] or ids

        ids = sorted(set(ids))

        self.cmb_run_catalog.blockSignals(True)
        self.cmb_run_catalog.clear()
        self.cmb_run_catalog.addItem("")
        for i in ids:
            self.cmb_run_catalog.addItem(i)
        self.cmb_run_catalog.blockSignals(False)

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
