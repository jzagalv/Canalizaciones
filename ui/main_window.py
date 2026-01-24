# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAction, QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QSplitter, QTabWidget, QVBoxLayout, QWidget
)

from data.repositories.project_store import load_project, save_project
from data.repositories.lib_loader import LibError, load_lib
from data.repositories.lib_merge import EffectiveCatalog, merge_libs
from domain.entities.models import LibraryRef, Project
from domain.services.engine import compute_project_solutions
from ui.tabs.canvas_tab import CanvasTab
from ui.tabs.circuits_tab import CircuitsTab
from ui.tabs.libraries_tab import LibrariesTab
from ui.tabs.primary_equipment_tab import PrimaryEquipmentTab
from ui.tabs.equipment_library_tab import EquipmentLibraryTab
from ui.tabs.results_tab import ResultsTab


class MainWindow(QMainWindow):
    """Main window.

    Goals:
    - GUI only orchestrates actions.
    - Domain/services perform routing + proposal + checks.
    - Project (.proj.json) persists canvas + circuits + library selection.
    """

    def __init__(self, app_dir: str):
        super().__init__()
        self.setWindowTitle("Canalizaciones BT - Rediseño")
        self.resize(1200, 750)

        self._app_dir = Path(app_dir)
        self._project_path: Optional[str] = None
        self.project = Project()

        # cached effective catalog
        self._eff: Optional[EffectiveCatalog] = None

        self._build_menu()
        self._build_ui()
        self._refresh_all()

    # -------------------- Menu --------------------
    def _build_menu(self) -> None:
        m_file = self.menuBar().addMenu("Archivo")

        act_new = QAction("Nuevo proyecto", self)
        act_new.triggered.connect(self._new_project)
        m_file.addAction(act_new)

        act_open = QAction("Abrir proyecto...", self)
        act_open.triggered.connect(self._open_project)
        m_file.addAction(act_open)

        act_save = QAction("Guardar", self)
        act_save.triggered.connect(self._save_project)
        m_file.addAction(act_save)

        act_save_as = QAction("Guardar como...", self)
        act_save_as.triggered.connect(self._save_project_as)
        m_file.addAction(act_save_as)

        m_lib = self.menuBar().addMenu("Bibliotecas")

        act_add_lib = QAction("Agregar .lib...", self)
        act_add_lib.triggered.connect(self._add_lib)
        m_lib.addAction(act_add_lib)

        act_validate = QAction("Validar/Combinar", self)
        act_validate.triggered.connect(self._validate_libs)
        m_lib.addAction(act_validate)

        m_calc = self.menuBar().addMenu("Calculo")
        act_recalc = QAction("Recalcular", self)
        act_recalc.triggered.connect(self._recalculate)
        m_calc.addAction(act_recalc)

    # -------------------- UI --------------------
    def _build_ui(self) -> None:
        cw = QWidget(self)
        self.setCentralWidget(cw)
        root = QVBoxLayout(cw)

        top = QHBoxLayout()
        root.addLayout(top)

        self.lbl_project = QLabel("Proyecto: (sin guardar)")
        self.lbl_project.setTextInteractionFlags(Qt.TextSelectableByMouse)
        top.addWidget(self.lbl_project, 1)

        self.btn_validate = QPushButton("Validar bibliotecas")
        self.btn_validate.clicked.connect(self._validate_libs)
        top.addWidget(self.btn_validate)

        self.btn_recalc = QPushButton("Recalcular")
        self.btn_recalc.clicked.connect(self._recalculate)
        top.addWidget(self.btn_recalc)

        splitter = QSplitter(Qt.Vertical)
        root.addWidget(splitter, 1)

        self.tabs = QTabWidget()
        splitter.addWidget(self.tabs)

        # Tabs
        self.tab_canvas = CanvasTab()
        self.tab_circuits = CircuitsTab()
        self.tab_equipment_lib = EquipmentLibraryTab()
        self.tab_primary = PrimaryEquipmentTab()
        self.tab_results = ResultsTab()
        self.tab_libs = LibrariesTab()

        self.tabs.addTab(self.tab_canvas, "Canvas")
        self.tabs.addTab(self.tab_circuits, "Circuitos")
        self.tabs.addTab(self.tab_results, "Resultados")
        self.tabs.addTab(self.tab_libs, "Bibliotecas")

        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        splitter.addWidget(self.lbl_status)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)

        # wiring
        self.tab_canvas.project_changed.connect(self._on_project_mutated)
        self.tab_circuits.project_changed.connect(self._on_project_mutated)
        self.tab_libs.project_changed.connect(self._on_libs_mutated)

        self.tab_canvas.selection_changed.connect(self.tab_circuits.set_active_node)

    # -------------------- Project I/O --------------------
    def _new_project(self) -> None:
        self.project = Project()
        self._project_path = None
        self._eff = None
        self._refresh_all()

    def _open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir proyecto",
            str(self._app_dir),
            "Project (*.proj.json)"
        )
        if not path:
            return
        try:
            self.project = load_project(path)
            self._project_path = path
            self._eff = None
            self._refresh_all()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _save_project(self) -> None:
        if not self._project_path:
            self._save_project_as()
            return
        try:
            save_project(self.project, self._project_path)
            self.statusBar().showMessage("Proyecto guardado", 2000)
            self._refresh_title()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _save_project_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar proyecto",
            str(self._app_dir),
            "Project (*.proj.json)"
        )
        if not path:
            return
        if not path.endswith(".proj.json"):
            path += ".proj.json"
        self._project_path = path
        self._save_project()

    # -------------------- Libraries --------------------
    def _add_lib(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Agregar biblioteca .lib",
            str(self._app_dir),
            "Library (*.lib *.json)"
        )
        if not path:
            return
        self.project.libraries.append(LibraryRef(path=path, enabled=True, priority=10))
        self._eff = None
        self._refresh_all()

    def _validate_libs(self) -> None:
        try:
            self._eff = self._build_effective_catalog()
        except LibError as e:
            QMessageBox.critical(self, "Error en biblioteca", str(e))
            return
        self.tab_circuits.set_effective_catalog(self._eff)
        self._refresh_status()

    def _build_effective_catalog(self) -> EffectiveCatalog:
        libs = sorted([lr for lr in self.project.libraries if lr.enabled], key=lambda x: x.priority)
        loaded: List[Dict] = []
        warnings: List[str] = []
        for lr in libs:
            res = load_lib(lr.path)
            loaded.append(res.doc)
            warnings += [f"{Path(lr.path).name}: {w}" for w in res.warnings]

        eff = merge_libs(loaded)
        eff.warnings = warnings + eff.warnings
        return eff

    # -------------------- Calculation --------------------
    def _recalculate(self) -> None:
        if not self._eff:
            try:
                self._eff = self._build_effective_catalog()
            except LibError as e:
                QMessageBox.critical(self, "Error", f"No se pudo cargar/combinar bibliotecas: {e}")
                return

        self.tab_circuits.set_effective_catalog(self._eff)

        self.tab_circuits.set_effective_catalog(self._eff)

        solutions, warnings = compute_project_solutions(self.project, self._eff)
        self.tab_results.set_results(self.project, solutions, warnings)
        self.tab_canvas.set_edge_statuses(solutions)
        self._refresh_status(extra_warnings=warnings)

    # -------------------- Refresh --------------------
    def _on_project_mutated(self) -> None:
        # mark dirty (lightweight)
        self._eff = None  # libraries/canvas/circuits may have changed
        self._refresh_title()

    def _on_libs_mutated(self) -> None:
        self._on_project_mutated()
        self._refresh_equipment_library_items()

    def _refresh_all(self) -> None:
        self._refresh_title()
        self.tab_canvas.set_project(self.project)
        self.tab_circuits.set_project(self.project)
        self.tab_equipment_lib.set_project(self.project)
        self.tab_primary.set_project(self.project)
        self.tab_libs.set_project(self.project)
        self.tab_results.set_results(self.project, {}, [])
        self._refresh_equipment_library_items()
        self._refresh_status()

    def _refresh_title(self) -> None:
        name = self.project.name or "Proyecto"
        p = self._project_path or "(sin guardar)"
        self.lbl_project.setText(f"{name} — {p}")

    def _refresh_status(self, extra_warnings: Optional[List[str]] = None) -> None:
        lines: List[str] = []
        lines.append(f"Perfil: {self.project.active_profile}")

        libs_enabled = len([lr for lr in self.project.libraries if lr.enabled])
        lines.append(f"Bibliotecas activas: {libs_enabled}/{len(self.project.libraries)}")

        nodes = len((self.project.canvas or {}).get("nodes") or [])
        edges = len((self.project.canvas or {}).get("edges") or [])
        circuits = len((self.project.circuits or {}).get("items") or [])
        lines.append(f"Canvas: {nodes} nodos, {edges} tramos | Circuitos: {circuits}")

        warnings: List[str] = []
        if self._eff:
            warnings += list(self._eff.warnings or [])
        if extra_warnings:
            warnings += list(extra_warnings)

        if warnings:
            lines.append("\nWarnings:")
            lines.extend([f"- {w}" for w in warnings[:25]])
            if len(warnings) > 25:
                lines.append(f"... ({len(warnings)-25} mas)")

        self.lbl_status.setText("\n".join(lines))

    def _refresh_equipment_library_items(self) -> None:
        items_by_id: Dict[str, Dict] = {}
        libs = sorted([lr for lr in self.project.libraries if lr.enabled], key=lambda x: x.priority)
        for lr in libs:
            try:
                res = load_lib(lr.path)
            except Exception:
                continue
            if res.doc.get("kind") != "equipment_library":
                continue
            for it in (res.doc.get("items") or []):
                equip_id = it.get("id")
                if not equip_id:
                    continue
                items_by_id[str(equip_id)] = it
        self.tab_canvas.set_equipment_items(items_by_id)
        self.tab_equipment_lib.set_equipment_items(items_by_id)
