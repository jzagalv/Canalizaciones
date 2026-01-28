# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QAction, QActionGroup, QApplication, QFileDialog, QHBoxLayout, QLabel,
    QMainWindow, QMessageBox, QPushButton, QSplitter, QTabWidget, QVBoxLayout,
    QWidget, QInputDialog, QDialog
)

from data.repositories.project_store import load_project, save_project
from data.repositories.lib_loader import LibError, load_lib
from data.repositories.lib_merge import EffectiveCatalog, merge_libs
from data.repositories.template_repo import (
    TemplateRepoError,
    load_base_template,
    save_base_template,
)
from data.repositories.lib_writer import (
    LibWriteError,
    delete_equipment_item,
    normalize_equipment_id,
    upsert_equipment_item,
)
from infra.persistence.app_config import AppConfig
from infra.persistence.materiales_bd_repo import (
    MaterialesBdError,
    load_materiales_bd,
    save_materiales_bd,
)
from infra.persistence.materiales_repo import MaterialesRepo
from domain.entities.models import LibraryRef, Project
from domain.libraries.template_models import BaseTemplate
from domain.materials.material_service import MaterialService
from domain.services.engine import compute_project_solutions
from domain.services.troncal_service import (
    add_connected_to_troncal,
    assign_troncal_to_edges,
    ensure_troncales,
    get_connected_edge_ids,
    get_edge_by_id,
    next_troncal_id,
    remove_troncal_from_edges,
)
from ui.tabs.canvas_tab import CanvasTab
from ui.tabs.circuits_tab import CircuitsTab
from ui.tabs.primary_equipment_tab import PrimaryEquipmentTab
from ui.tabs.equipment_library_tab import EquipmentLibraryTab
from ui.tabs.results_tab import ResultsTab
from ui.dialogs.libraries_templates_dialog import LibrariesTemplatesDialog
from ui.dialogs.conduit_segment_dialog import ConduitSegmentDialog
from ui.dialogs.fill_rules_presets_dialog import FillRulesPresetsDialog
from ui.dialogs.equipment_bulk_edit_dialog import EquipmentBulkEditDialog
from ui.dialogs.cabinet_detail_dialog import CabinetDetailDialog
from ui.theme_manager import apply_theme


class MainWindow(QMainWindow):
    materialsDbChanged = pyqtSignal(str, dict)
    """Main window.

    Goals:
    - GUI only orchestrates actions.
    - Domain/services perform routing + proposal + checks.
    - Project (.proj.json) persists canvas + circuits + library selection.
    """

    def __init__(self, app_dir: Path, app_config: AppConfig):
        super().__init__()
        self._logger = logging.getLogger(__name__)
        self.setWindowTitle("Canalizaciones BT - Rediseño")
        self._app_dir = Path(app_dir)
        self._app_config = app_config
        self._current_theme = app_config.theme
        self._project_path: Optional[str] = None
        self.project = Project()
        self._project_dirty = False

        # cached effective catalog
        self._eff: Optional[EffectiveCatalog] = None
        self._materiales_doc: Optional[Dict] = None
        self._materiales_path: str = ""
        self._base_template: Optional[BaseTemplate] = None
        self._lib_tpl_dialog: Optional[LibrariesTemplatesDialog] = None
        self._segment_dialog: Optional[ConduitSegmentDialog] = None
        self._cabinet_dialog: Optional[CabinetDetailDialog] = None
        self._calc_dirty = True
        self._libs_pending_normalize: Dict[str, Dict] = {}
        self._equipment_items_by_id: Dict[str, Dict] = {}
        self._equipment_item_sources: Dict[str, str] = {}

        if self._app_config.materiales_bd_path and Path(self._app_config.materiales_bd_path).exists():
            self.project.active_materiales_bd_path = self._app_config.materiales_bd_path

        self._materiales_repo = MaterialesRepo(self.project.active_materiales_bd_path or "")
        self._material_service = MaterialService(self._materiales_repo)

        self._apply_window_state_from_config()
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

        m_calc = self.menuBar().addMenu("Calculo")
        act_recalc = QAction("Recalcular", self)
        act_recalc.triggered.connect(self._recalculate)
        m_calc.addAction(act_recalc)

        m_libs = self.menuBar().addMenu("Librerías")

        act_open_mat = QAction("Abrir materiales_bd.lib...", self)
        act_open_mat.triggered.connect(self._open_materiales_bd)
        m_libs.addAction(act_open_mat)

        act_edit_mat = QAction("Editar materiales_bd.lib...", self)
        act_edit_mat.triggered.connect(self._open_materiales_editor)
        m_libs.addAction(act_edit_mat)

        act_admin = QAction("Administrador de Librerías y Plantillas...", self)
        act_admin.triggered.connect(self._open_libraries_templates_dialog)
        m_libs.addAction(act_admin)

        m_view = self.menuBar().addMenu("Ver")
        m_theme = m_view.addMenu("Tema")

        self._theme_group = QActionGroup(self)
        self._theme_group.setExclusive(True)

        self.act_theme_light = QAction("I-SEP Claro", self)
        self.act_theme_light.setCheckable(True)
        self.act_theme_light.toggled.connect(lambda checked: self._on_theme_toggled("light", checked))
        self._theme_group.addAction(self.act_theme_light)
        m_theme.addAction(self.act_theme_light)

        self.act_theme_dark = QAction("I-SEP Oscuro", self)
        self.act_theme_dark.setCheckable(True)
        self.act_theme_dark.toggled.connect(lambda checked: self._on_theme_toggled("dark", checked))
        self._theme_group.addAction(self.act_theme_dark)
        m_theme.addAction(self.act_theme_dark)

        if self._current_theme == "dark":
            self.act_theme_dark.setChecked(True)
        else:
            self.act_theme_light.setChecked(True)

        m_cfg = self.menuBar().addMenu("Configuración")
        act_fill_presets = QAction("Presets de reglas de llenado...", self)
        act_fill_presets.triggered.connect(self._open_fill_rules_presets_dialog)
        m_cfg.addAction(act_fill_presets)

        m_troncales = self.menuBar().addMenu("Troncales")
        act_troncal_assign = QAction("Crear/Asignar Troncal (conectada) desde tramo seleccionado", self)
        act_troncal_assign.triggered.connect(self._troncal_create_or_assign_from_selected)
        m_troncales.addAction(act_troncal_assign)

        act_troncal_add_connected = QAction("Agregar conectados a Troncal", self)
        act_troncal_add_connected.triggered.connect(self._troncal_add_connected_from_selected)
        m_troncales.addAction(act_troncal_add_connected)

        act_troncal_remove = QAction("Quitar tramo(s) de troncal", self)
        act_troncal_remove.triggered.connect(self._troncal_remove_from_selected)
        m_troncales.addAction(act_troncal_remove)

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

        self.lbl_materiales = QLabel("materiales_bd.lib activo: (no cargado)")
        self.lbl_materiales.setTextInteractionFlags(Qt.TextSelectableByMouse)
        top.addWidget(self.lbl_materiales, 1)

        self.btn_validate = QPushButton("Validar bibliotecas")
        self.btn_validate.setProperty("secondary", True)
        self.btn_validate.clicked.connect(self._validate_libs)
        top.addWidget(self.btn_validate)

        self.btn_recalc = QPushButton("Recalcular")
        self.btn_recalc.setProperty("primary", True)
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

        self.tabs.addTab(self.tab_canvas, "Canvas")
        self.tabs.addTab(self.tab_circuits, "Circuitos")
        self.tabs.addTab(self.tab_results, "Resultados")

        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setObjectName("statusLabel")
        splitter.addWidget(self.lbl_status)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)

        # wiring
        self.tab_canvas.project_changed.connect(self._on_project_mutated)
        self.tab_circuits.project_changed.connect(self._on_project_mutated)

        self.tab_circuits.set_material_service(self._material_service)

        self.tab_canvas.selection_changed.connect(self.tab_circuits.set_active_node)
        self.tab_canvas.project_changed.connect(self.tab_circuits.reload_node_lists)
        self.tab_canvas.segment_double_clicked.connect(self.open_segment_dialog)
        self.tab_canvas.segment_removed.connect(self._on_segment_removed)
        self.tab_canvas.equipment_add_requested.connect(self._on_equipment_add_requested)
        self.tab_canvas.troncal_create_requested.connect(self._troncal_create_or_assign_from_selected)
        self.tab_canvas.troncal_add_requested.connect(self._troncal_add_connected_from_selected)
        self.tab_canvas.troncal_remove_requested.connect(self._troncal_remove_from_selected)
        self.tab_canvas.edit_edge_tag_requested.connect(self._edit_edge_tag_from_menu)
        self.tab_canvas.edit_node_tag_requested.connect(self._edit_node_tag_from_menu)
        self.tab_canvas.open_cabinet_window_requested.connect(self._open_cabinet_detail_dialog)
        self.tab_canvas.library_panel.equipmentRequestedRename.connect(self._on_equipment_rename_requested)
        self.tab_canvas.library_panel.equipmentRequestedDelete.connect(self._on_equipment_delete_requested)
        self.tab_canvas.library_panel.equipmentRequestedBulkEdit.connect(self._open_equipment_bulk_edit_dialog)

    def open_segment_dialog(self, segment_item) -> None:
        try:
            if segment_item is None:
                return
            if self._segment_dialog is None:
                self._segment_dialog = ConduitSegmentDialog(self)
                self._segment_dialog.set_material_service(self._material_service)
                self._segment_dialog.set_project(self.project)
            else:
                self._segment_dialog.set_project(self.project)
            self._segment_dialog.set_segment(segment_item)
            self._segment_dialog.show()
            self._segment_dialog.raise_()
            self._segment_dialog.activateWindow()
        except Exception as exc:
            self._logger.exception("Failed to open segment dialog")
            QMessageBox.critical(self, "Error", f"No se pudo abrir el dialogo del tramo:\n{exc}")

    def _on_theme_toggled(self, theme: str, checked: bool) -> None:
        if not checked:
            return
        self._set_theme(theme)

    def _set_theme(self, theme: str) -> None:
        if theme == self._current_theme:
            return
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, self._app_dir, theme)
        self._app_config.theme = theme
        self._app_config.save()
        self._current_theme = theme

    # -------------------- Project I/O --------------------
    def _new_project(self) -> None:
        self.project = Project()
        self._project_path = None
        self._eff = None
        self._calc_dirty = True
        self._project_dirty = True
        self._refresh_all()

    def _open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir proyecto",
            self._project_dialog_dir(),
            "Project (*.proj.json)"
        )
        if not path:
            return
        try:
            self.project = load_project(path)
            self._project_path = path
            self._project_dirty = False
            self._app_config.last_project_path = path
            self._app_config.save()
            self._eff = None
            self._calc_dirty = True
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
            self._project_dirty = False
            self._refresh_title()
            self._app_config.last_project_path = self._project_path
            self._app_config.save()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _save_project_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar proyecto",
            self._project_dialog_dir(),
            "Project (*.proj.json)"
        )
        if not path:
            return
        if not path.endswith(".proj.json"):
            path += ".proj.json"
        self._project_path = path
        self._save_project()
        self._app_config.last_project_path = path
        self._app_config.save()

    # -------------------- Libraries --------------------
    def _validate_libs(self) -> None:
        try:
            self._eff = self._build_effective_catalog()
        except LibError as e:
            QMessageBox.critical(self, "Error en biblioteca", str(e))
            return
        if self._libs_pending_normalize:
            self._offer_normalize_libs()
        self.tab_circuits.set_effective_catalog(self._eff)
        self._refresh_status()

    def _build_effective_catalog(self) -> EffectiveCatalog:
        libs = sorted([lr for lr in self.project.libraries if lr.enabled], key=lambda x: x.priority)
        loaded: List[Tuple[str, Dict]] = []
        warnings: List[str] = []
        self._libs_pending_normalize = {}
        for lr in libs:
            res = load_lib(lr.path)
            source_label = str((res.doc.get("meta") or {}).get("name") or Path(lr.path).name)
            loaded.append((source_label, res.doc))
            warnings += [f"{Path(lr.path).name}: {w}" for w in res.warnings]
            if res.changed and res.doc.get("kind") == "material_library":
                self._libs_pending_normalize[str(lr.path)] = res.doc

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

        routes, edge_to_circuits, canalizacion_assignments, fill_results = compute_project_solutions(
            self.project,
            self._eff,
            self._app_dir,
        )
        self.project._calc = {
            "routes": routes,
            "edge_to_circuits": edge_to_circuits,
            "canalizacion_assignments": canalizacion_assignments,
            "fill_results": fill_results,
        }
        self._calc_dirty = False
        self._sync_edge_fill_props(fill_results)
        if self._segment_dialog is not None:
            try:
                self._segment_dialog.set_project(self.project)
            except Exception:
                pass
        self.tab_results.set_results(self.project, fill_results, [])
        self.tab_canvas.set_edge_statuses(fill_results)
        self._refresh_status(extra_warnings=[])

    def _sync_edge_fill_props(self, fill_results: Dict[str, Dict]) -> None:
        if not fill_results:
            return
        for edge_id, sol in fill_results.items():
            self.tab_canvas.scene.set_edge_fill_results(edge_id, sol)

    def _edge_props(self, edge_id: str) -> Dict[str, object]:
        edges = list((self.project.canvas or {}).get("edges") or [])
        for edge in edges:
            if str(edge.get("id")) == str(edge_id):
                return dict(edge.get("props") or {})
        return {}

    # -------------------- Refresh --------------------
    def _on_project_mutated(self) -> None:
        # mark dirty (lightweight)
        self._project_dirty = True
        self._eff = None  # libraries/canvas/circuits may have changed
        self._calc_dirty = True
        if self._segment_dialog is not None:
            try:
                self._segment_dialog.set_project(self.project)
            except Exception:
                pass
        self._refresh_title()

    def _refresh_all(self) -> None:
        self._refresh_title()
        self.tab_canvas.set_project(self.project)
        self.tab_circuits.set_project(self.project)
        self.tab_equipment_lib.set_project(self.project)
        self.tab_primary.set_project(self.project)
        self.tab_results.set_results(self.project, {}, [])
        if self._segment_dialog is not None:
            try:
                self._segment_dialog.set_project(self.project)
                self._segment_dialog.set_segment(None)
            except Exception:
                pass
        self._refresh_equipment_library_items()
        self._load_active_materiales()
        if self._migrate_project_material_refs():
            self._on_project_mutated()
            self.tab_canvas.set_project(self.project)
            self.tab_circuits.set_project(self.project)
        self._sync_libraries_templates_dialog()
        self._refresh_status()

    def _on_segment_removed(self, edge_id: str) -> None:
        if self._segment_dialog is None:
            return
        seg = getattr(self._segment_dialog, "_segment", None)
        seg_id = getattr(seg, "edge_id", None) if seg is not None else None
        if seg_id and str(seg_id) == str(edge_id):
            try:
                self._segment_dialog.set_segment(None)
            except Exception:
                pass

    def _refresh_title(self) -> None:
        name = self.project.name or "Proyecto"
        p = self._project_path or "(sin guardar)"
        dirty = " *" if self._project_dirty else ""
        self.lbl_project.setText(f"{name} — {p}{dirty}")

    def _refresh_materiales_label(self) -> None:
        path = self._materiales_path or "(no cargado)"
        self.lbl_materiales.setText(f"materiales_bd.lib activo: {path}")

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

    # ---------------- Libraries & Templates dialog ----------------
    def _open_libraries_templates_dialog(self) -> None:
        if self._lib_tpl_dialog is None:
            self._lib_tpl_dialog = LibrariesTemplatesDialog(self)
            self._lib_tpl_dialog.request_load_materiales.connect(self._open_materiales_bd)
            self._lib_tpl_dialog.request_save_materiales.connect(self._save_materiales_bd)
            self._lib_tpl_dialog.request_save_materiales_as.connect(self._save_materiales_bd_as)
            self._lib_tpl_dialog.request_load_template.connect(self._load_base_template_dialog)
            self._lib_tpl_dialog.request_save_template.connect(self._save_base_template_dialog)
            self._lib_tpl_dialog.request_apply_template.connect(self._apply_base_template_to_project)
            self._lib_tpl_dialog.materiales_changed.connect(self._on_materiales_changed)
            self._lib_tpl_dialog.installation_type_changed.connect(self._on_installation_type_changed)
        self._sync_libraries_templates_dialog()
        self._lib_tpl_dialog.show()
        self._lib_tpl_dialog.raise_()
        self._lib_tpl_dialog.activateWindow()

    def _open_fill_rules_presets_dialog(self) -> None:
        dlg = FillRulesPresetsDialog(self._app_dir, self.project, self)
        if dlg.exec_() == QDialog.Accepted:
            self._on_project_mutated()
            try:
                self._recalculate()
            except Exception:
                pass

    def _sync_libraries_templates_dialog(self) -> None:
        if not self._lib_tpl_dialog:
            return
        self._lib_tpl_dialog.set_materiales_doc(self._materiales_doc or {}, self._materiales_path)
        self._lib_tpl_dialog.set_template_status(self.project.active_template_path)
        self._lib_tpl_dialog.set_installation_type(self.project.active_installation_type)

    def _on_materiales_changed(self, doc: Dict) -> None:
        self._materiales_doc = doc
        self._refresh_materiales_label()

    def _on_installation_type_changed(self, value: str) -> None:
        self.project.active_installation_type = value or ""
        if self._base_template:
            self._base_template.installation_type = value or ""

    def _load_active_materiales(self) -> None:
        self._materiales_doc = None
        self._materiales_path = self.project.active_materiales_bd_path or ""
        self._refresh_materiales_label()
        if self._materiales_path:
            try:
                self._materiales_doc = load_materiales_bd(self._materiales_path)
            except MaterialesBdError:
                self._materiales_doc = None
            else:
                self._app_config.materiales_bd_path = self._materiales_path
                self._app_config.save()
        self._update_material_service()

        self._base_template = None
        if self.project.active_template_path:
            try:
                self._base_template = load_base_template(self.project.active_template_path)
                if self._base_template and self._base_template.installation_type:
                    self.project.active_installation_type = self._base_template.installation_type
            except TemplateRepoError:
                self._base_template = None

    def _materials_bd_default_dir(self) -> str:
        base = Path(self._app_dir) / "libs"
        base.mkdir(parents=True, exist_ok=True)
        return str(base)

    def _templates_default_dir(self) -> str:
        base = Path(self._app_dir) / "data" / "templates"
        base.mkdir(parents=True, exist_ok=True)
        return str(base)

    def _new_materiales_doc(self) -> Dict:
        return {
            "schema_version": "1.0",
            "kind": "material_library",
            "meta": {"name": "Materiales", "created": "", "source": ""},
            "conductors": [],
            "containments": {"ducts": [], "epc": [], "bpc": []},
            "rules": {},
        }

    def _open_materiales_bd(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir materiales_bd.lib",
            self._materials_bd_default_dir(),
            "materiales_bd.lib (materiales_bd.lib)",
        )
        if not path:
            return
        if Path(path).name != "materiales_bd.lib":
            QMessageBox.warning(self, "materiales_bd.lib", "Selecciona un archivo llamado exactamente materiales_bd.lib.")
            return
        try:
            self._materiales_doc = load_materiales_bd(path)
            self._materiales_path = path
            self.project.active_materiales_bd_path = path
            self._app_config.materiales_bd_path = path
            self._app_config.save()
            self._ensure_materiales_in_libraries(path)
            self._refresh_materiales_label()
            self._sync_libraries_templates_dialog()
            self.materialsDbChanged.emit(path, self._materiales_doc)
            self._update_material_service()
        except MaterialesBdError as e:
            QMessageBox.critical(self, "materiales_bd.lib", str(e))

    def _open_materiales_editor(self) -> None:
        self._open_libraries_templates_dialog()
        if self._lib_tpl_dialog:
            self._lib_tpl_dialog.tabs.setCurrentIndex(0)

    def _save_materiales_bd(self) -> None:
        if not self._materiales_path:
            self._save_materiales_bd_as()
            return
        if self._lib_tpl_dialog:
            self._materiales_doc = self._lib_tpl_dialog.get_materiales_doc()
        if not self._materiales_doc:
            self._materiales_doc = self._new_materiales_doc()
        try:
            save_materiales_bd(self._materiales_path, self._materiales_doc)
            self.materialsDbChanged.emit(self._materiales_path, self._materiales_doc)
            self._update_material_service()
        except MaterialesBdError as e:
            QMessageBox.critical(self, "materiales_bd.lib", str(e))

    def _save_materiales_bd_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar materiales_bd.lib",
            str(Path(self._materials_bd_default_dir()) / "materiales_bd.lib"),
            "materiales_bd.lib (materiales_bd.lib)",
        )
        if not path:
            return
        target = Path(path)
        if target.name != "materiales_bd.lib":
            target = target.parent / "materiales_bd.lib"
        if self._lib_tpl_dialog:
            self._materiales_doc = self._lib_tpl_dialog.get_materiales_doc()
        if not self._materiales_doc:
            self._materiales_doc = self._new_materiales_doc()
        try:
            save_materiales_bd(str(target), self._materiales_doc)
            self._materiales_path = str(target)
            self.project.active_materiales_bd_path = self._materiales_path
            self._app_config.materiales_bd_path = self._materiales_path
            self._app_config.save()
            self._ensure_materiales_in_libraries(self._materiales_path)
            self._refresh_materiales_label()
            self._sync_libraries_templates_dialog()
            self.materialsDbChanged.emit(self._materiales_path, self._materiales_doc)
            self._update_material_service()
        except MaterialesBdError as e:
            QMessageBox.critical(self, "materiales_bd.lib", str(e))

    def _ensure_materiales_in_libraries(self, path: str) -> None:
        if not path:
            return
        for lr in self.project.libraries:
            if str(lr.path) == str(path):
                return
        self.project.libraries.append(LibraryRef(path=path, enabled=True, priority=10))
        self._eff = None

    def _update_material_service(self) -> None:
        path = self._materiales_path or self.project.active_materiales_bd_path or ""
        self._materiales_repo.set_path(path)
        self.tab_circuits.set_material_service(self._material_service)
        if self._segment_dialog is not None:
            try:
                self._segment_dialog.set_material_service(self._material_service)
            except Exception:
                pass

    def _offer_normalize_libs(self) -> None:
        libs = list(self._libs_pending_normalize.keys())
        if not libs:
            return
        count = len(libs)
        msg = f"Se detectaron {count} librería(s) con uid/code faltantes. ¿Deseas normalizarlas y guardar?"
        res = QMessageBox.question(self, "Normalizar librerías", msg, QMessageBox.Yes | QMessageBox.No)
        if res != QMessageBox.Yes:
            return
        for path, doc in self._libs_pending_normalize.items():
            try:
                Path(path).write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception as exc:
                QMessageBox.warning(self, "Normalizar librerías", f"No se pudo guardar {path}:\n{exc}")
        self._libs_pending_normalize = {}

    def _migrate_project_material_refs(self) -> bool:
        if not self._material_service:
            return False
        changed = False
        canvas = self.project.canvas or {}
        edges = list(canvas.get("edges") or [])
        for edge in edges:
            props = edge.get("props") if isinstance(edge.get("props"), dict) else None
            if not props:
                continue
            duct_uid = str(props.get("duct_uid") or "").strip()
            snap = props.get("duct_snapshot") if isinstance(props.get("duct_snapshot"), dict) else {}
            snap_uid = str(snap.get("uid") or "").strip()
            if not duct_uid and snap_uid:
                props["duct_uid"] = snap_uid
                duct_uid = snap_uid
                changed = True
            legacy = str(props.get("duct_id") or "").strip()
            if not duct_uid and legacy:
                resolved = self._material_service.resolve_duct_uid(legacy, props.get("size"))
                if resolved:
                    props["duct_uid"] = resolved
                    props.pop("duct_id", None)
                    changed = True
            elif duct_uid and "duct_id" in props:
                props.pop("duct_id", None)
                changed = True
            if duct_uid and not props.get("duct_snapshot"):
                snapshot = self._material_service.build_duct_snapshot(duct_uid)
                if snapshot:
                    props["duct_snapshot"] = snapshot
                    changed = True

        circuits = list((self.project.circuits or {}).get("items") or [])
        for cir in circuits:
            cref = str(cir.get("cable_ref") or "").strip()
            if not cref:
                continue
            resolved = self._material_service.resolve_conductor_uid(cref)
            if resolved and resolved != cref:
                cir["cable_ref"] = resolved
                changed = True
            if resolved:
                if not cir.get("cable_snapshot"):
                    snap = self._material_service.build_conductor_snapshot(resolved)
                    if snap:
                        cir["cable_snapshot"] = snap
                        changed = True

        return changed

    def _load_base_template_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Cargar plantilla base",
            self._templates_default_dir(),
            "Base Template (*.json)",
        )
        if not path:
            return
        try:
            self._base_template = load_base_template(path)
            self.project.active_template_path = path
            self.project.active_installation_type = self._base_template.installation_type or ""
            self._sync_libraries_templates_dialog()
        except TemplateRepoError as e:
            QMessageBox.critical(self, "Plantilla base", str(e))

    def _save_base_template_dialog(self) -> None:
        if not self.project.active_template_path:
            self._save_base_template_as_dialog()
            return
        install_type = self.project.active_installation_type
        if self._lib_tpl_dialog:
            install_type = self._lib_tpl_dialog.cmb_installation.currentText().strip() or install_type
        self._base_template = BaseTemplate(installation_type=install_type, defaults={})
        try:
            save_base_template(self._base_template, self.project.active_template_path)
            self._sync_libraries_templates_dialog()
        except TemplateRepoError as e:
            QMessageBox.critical(self, "Plantilla base", str(e))

    def _save_base_template_as_dialog(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar plantilla base",
            self._templates_default_dir(),
            "Base Template (*.json)",
        )
        if not path:
            return
        if not path.endswith(".json"):
            path += ".json"
        install_type = self.project.active_installation_type
        if self._lib_tpl_dialog:
            install_type = self._lib_tpl_dialog.cmb_installation.currentText().strip() or install_type
        self._base_template = BaseTemplate(installation_type=install_type, defaults={})
        try:
            save_base_template(self._base_template, path)
            self.project.active_template_path = path
            self.project.active_installation_type = self._base_template.installation_type or ""
            self._sync_libraries_templates_dialog()
        except TemplateRepoError as e:
            QMessageBox.critical(self, "Plantilla base", str(e))

    def _apply_base_template_to_project(self) -> None:
        if self._lib_tpl_dialog:
            self.project.active_installation_type = self._lib_tpl_dialog.cmb_installation.currentText().strip()
        self._refresh_status()

    def _refresh_equipment_library_items(self) -> None:
        items_by_id: Dict[str, Dict] = {}
        item_sources: Dict[str, str] = {}
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
                equip_id = str(equip_id)
                equip_type = str(it.get("equipment_type") or "").strip()
                if not equip_type or equip_type == "Equipo":
                    equip_type = "Tablero"
                if equip_type not in ("Tablero", "Armario"):
                    equip_type = "Tablero"
                normalized = dict(it)
                normalized["equipment_type"] = equip_type
                items_by_id[equip_id] = normalized
                item_sources.setdefault(equip_id, str(lr.path))
        self._equipment_items_by_id = items_by_id
        self._equipment_item_sources = item_sources
        self.tab_canvas.set_equipment_items(items_by_id)
        self.tab_equipment_lib.set_equipment_items(items_by_id)
        self.tab_canvas.refresh_library_used_markers()

    def _troncal_create_or_assign_from_selected(self) -> None:
        edge_ids = list(self.tab_canvas.get_selected_edge_ids() or [])
        payload = self.tab_canvas.get_selection_snapshot()
        if not edge_ids and payload.get("kind") == "node":
            node_id = str(payload.get("id") or "")
            adj = self._get_adjacent_edge_ids(node_id)
            if not adj:
                QMessageBox.warning(self, "Troncales", "El nodo no tiene tramos adyacentes.")
                return
            if len(adj) == 1:
                edge_ids = [adj[0]]
            else:
                selection, ok = QInputDialog.getItem(
                    self,
                    "Troncales",
                    "Selecciona tramo adyacente:",
                    adj,
                    0,
                    False,
                )
                if not ok or not selection:
                    return
                edge_ids = [selection]

        if not edge_ids:
            QMessageBox.warning(self, "Troncales", "Selecciona tramo(s) completos o un nodo.")
            return

        mode = "connected"
        base_edge_id = str(edge_ids[0])
        connected: List[str] = []
        if len(edge_ids) > 1:
            opts = [
                f"Usar selecci\u00f3n ({len(edge_ids)} tramos) [recomendado]",
                "Usar conectados desde 1 tramo (elige 1)",
            ]
            choice, ok = QInputDialog.getItem(self, "Troncales", "Modo de asignaci\u00f3n:", opts, 0, False)
            if not ok or not choice:
                return
            if choice.startswith("Usar selecci"):
                mode = "selection"
                connected = edge_ids
                base_edge_id = str(edge_ids[0])
            else:
                selection, ok = QInputDialog.getItem(
                    self,
                    "Troncales",
                    "Selecciona tramo base:",
                    edge_ids,
                    0,
                    False,
                )
                if not ok or not selection:
                    return
                base_edge_id = str(selection)
        if not connected:
            connected = get_connected_edge_ids(self.project, base_edge_id)
        self._logger.info("Troncales: mode=%s base edge id=%s", mode, base_edge_id)
        self._logger.info("Troncales: connected edges=%s sample=%s", len(connected), connected[:15])
        base_edge = self._edge_by_id(base_edge_id) or {}
        a = str(base_edge.get("from_node") or base_edge.get("from") or "")
        b = str(base_edge.get("to_node") or base_edge.get("to") or "")
        node_by_id = {str(n.get("id") or ""): n for n in ((self.project.canvas or {}).get("nodes") or []) if n.get("id")}
        def _is_cut(node: Optional[Dict[str, object]]) -> bool:
            if not node:
                return False
            node_type = str(node.get("type") or "")
            if node_type in ("equipment", "chamber"):
                return True
            if node_type == "junction" and str(node.get("name") or "").strip().upper() == "GAP":
                return True
            props = node.get("props") if isinstance(node.get("props"), dict) else {}
            return bool(props.get("is_cut_node"))
        self._logger.info(
            "Troncales: base endpoints a=%s cut=%s b=%s cut=%s",
            a,
            _is_cut(node_by_id.get(a)),
            b,
            _is_cut(node_by_id.get(b)),
        )
        before_troncales = list(ensure_troncales(self.project))
        troncales = ensure_troncales(self.project)
        choices = [str(t.get("id") or "") for t in troncales if t.get("id")]
        choice_items = ["(Nueva troncal)"] + choices
        selection, ok = QInputDialog.getItem(
            self,
            "Troncales",
            "Crear nueva troncal o asignar a existente:",
            choice_items,
            0,
            False,
        )
        if not ok or not selection:
            return
        if selection == "(Nueva troncal)":
            troncal_id = next_troncal_id(self.project)
            troncales.append({"id": troncal_id, "name": troncal_id})
        else:
            troncal_id = selection
        self._logger.info("Troncales: troncal_id selected=%s", troncal_id)
        assign_troncal_to_edges(self.project, connected, troncal_id)
        updated = 0
        for eid in connected:
            edge = self._edge_by_id(eid)
            if edge:
                props = edge.get("props") if isinstance(edge.get("props"), dict) else {}
                if props.get("troncal_id") == troncal_id:
                    updated += 1
                self.tab_canvas.scene.set_edge_props(eid, props or {}, emit=False)
        after_troncales = list(self.project.troncales or [])
        self._logger.info("Troncales: updated edges=%s", updated)
        self._logger.info(
            "Troncales: troncales before=%s after=%s",
            [t.get("id") for t in (before_troncales or [])],
            [t.get("id") for t in (after_troncales or [])],
        )
        try:
            self.tab_canvas.scene.rebuild_troncal_overlays()
            self._logger.info("Troncales: rebuild_troncal_overlays called")
        except Exception as exc:
            self._logger.warning("Troncales: rebuild_troncal_overlays failed: %s", exc)
        self._on_project_mutated()
        self._logger.info("Troncales: _on_project_mutated called")

    def _troncal_add_connected_from_selected(self) -> None:
        edge_ids = list(self.tab_canvas.get_selected_edge_ids() or [])
        payload = self.tab_canvas.get_selection_snapshot()
        if not edge_ids and payload.get("kind") == "node":
            node_id = str(payload.get("id") or "")
            adj = self._get_adjacent_edge_ids(node_id)
            if not adj:
                QMessageBox.warning(self, "Troncales", "El nodo no tiene tramos adyacentes.")
                return
            if len(adj) == 1:
                edge_ids = [adj[0]]
            else:
                selection, ok = QInputDialog.getItem(
                    self,
                    "Troncales",
                    "Selecciona tramo adyacente:",
                    adj,
                    0,
                    False,
                )
                if not ok or not selection:
                    return
                edge_ids = [selection]

        if not edge_ids:
            QMessageBox.warning(self, "Troncales", "Selecciona tramo(s) completos o un nodo.")
            return

        mode = "connected"
        base_edge_id = str(edge_ids[0])
        if len(edge_ids) > 1:
            opts = [
                f"Usar selecci\u00f3n ({len(edge_ids)} tramos) [recomendado]",
                "Usar conectados desde 1 tramo (elige 1)",
            ]
            choice, ok = QInputDialog.getItem(self, "Troncales", "Modo de asignaci\u00f3n:", opts, 0, False)
            if not ok or not choice:
                return
            if choice.startswith("Usar selecci"):
                QMessageBox.warning(self, "Troncales", "Esta acción requiere un tramo base. Selecciona 1 tramo.")
                return
            selection, ok = QInputDialog.getItem(
                self,
                "Troncales",
                "Selecciona tramo base:",
                edge_ids,
                0,
                False,
            )
            if not ok or not selection:
                return
            base_edge_id = str(selection)
        self._logger.info("Troncales(add): mode=%s base edge id=%s", mode, base_edge_id)
        edge = self._edge_by_id(base_edge_id)
        props = edge.get("props") if edge else {}
        troncal_id = str((props or {}).get("troncal_id") or "")
        if not troncal_id:
            troncales = ensure_troncales(self.project)
            choices = [str(t.get("id") or "") for t in troncales if t.get("id")]
            if not choices:
                QMessageBox.warning(self, "Troncales", "No hay troncales disponibles para asignar.")
                return
            selection, ok = QInputDialog.getItem(
                self,
                "Troncales",
                "Selecciona troncal destino:",
                choices,
                0,
                False,
            )
            if not ok or not selection:
                return
            troncal_id = selection
        assignable, conflicts = add_connected_to_troncal(self.project, base_edge_id, troncal_id)
        self._logger.info(
            "Troncales(add): troncal_id=%s assignable=%s conflicts=%s",
            troncal_id,
            len(assignable),
            len(conflicts),
        )
        if conflicts:
            QMessageBox.warning(
                self,
                "Troncales",
                "Hay tramos conectados con otra troncal. Operación bloqueada.",
            )
            return
        assign_troncal_to_edges(self.project, assignable, troncal_id)
        for eid in assignable:
            edge = self._edge_by_id(eid)
            if edge:
                self.tab_canvas.scene.set_edge_props(eid, edge.get("props") or {}, emit=False)
        try:
            self.tab_canvas.scene.rebuild_troncal_overlays()
            self._logger.info("Troncales(add): rebuild_troncal_overlays called")
        except Exception as exc:
            self._logger.warning("Troncales(add): rebuild_troncal_overlays failed: %s", exc)
        self._on_project_mutated()
        self._logger.info("Troncales(add): _on_project_mutated called")

    def _troncal_remove_from_selected(self) -> None:
        edge_ids = self.tab_canvas.get_selected_edge_ids()
        payload = self.tab_canvas.get_selection_snapshot()
        if not edge_ids and payload.get("kind") == "node":
            node_id = str(payload.get("id") or "")
            adj = self._get_adjacent_edge_ids(node_id)
            if not adj:
                QMessageBox.warning(self, "Troncales", "El nodo no tiene tramos adyacentes.")
                return
            if len(adj) == 1:
                edge_ids = [adj[0]]
            else:
                selection, ok = QInputDialog.getItem(
                    self,
                    "Troncales",
                    "Selecciona tramo adyacente:",
                    adj,
                    0,
                    False,
                )
                if not ok or not selection:
                    return
                edge_ids = [selection]
        if not edge_ids:
            QMessageBox.warning(self, "Troncales", "Selecciona tramo(s) completos o un nodo.")
            return
        self._logger.info("Troncales(remove): edges=%s sample=%s", len(edge_ids), edge_ids[:10])
        remove_troncal_from_edges(self.project, edge_ids)
        for eid in edge_ids:
            edge = self._edge_by_id(eid)
            if edge:
                self.tab_canvas.scene.set_edge_props(eid, edge.get("props") or {}, emit=False)
        try:
            self.tab_canvas.scene.rebuild_troncal_overlays()
            self._logger.info("Troncales(remove): rebuild_troncal_overlays called")
        except Exception as exc:
            self._logger.warning("Troncales(remove): rebuild_troncal_overlays failed: %s", exc)
        self._on_project_mutated()
        self._logger.info("Troncales(remove): _on_project_mutated called")

    def _get_adjacent_edge_ids(self, node_id: str) -> List[str]:
        edges = list((self.project.canvas or {}).get("edges") or [])
        nid = str(node_id or "")
        result = []
        for e in edges:
            a = str(e.get("from_node") or e.get("from") or "")
            b = str(e.get("to_node") or e.get("to") or "")
            if nid and (a == nid or b == nid):
                eid = str(e.get("id") or "")
                if eid:
                    result.append(eid)
        return result

    def _edge_by_id(self, edge_id: str) -> Optional[Dict[str, object]]:
        edges = list((self.project.canvas or {}).get("edges") or [])
        for e in edges:
            if str(e.get("id") or "") == str(edge_id):
                return e
        return None

    def _edit_edge_tag_from_menu(self, edge_id: str) -> None:
        edge = self._edge_by_id(edge_id)
        if not edge:
            return
        props = edge.get("props") if isinstance(edge.get("props"), dict) else {}
        current = str(props.get("tag") or "")
        value, ok = QInputDialog.getText(self, "Editar TAG tramo", "TAG:", text=current)
        if not ok:
            return
        props["tag"] = str(value or "").strip()
        edge["props"] = props
        self.tab_canvas.scene.set_edge_props(edge_id, props, emit=False)
        self._on_project_mutated()

    def _edit_node_tag_from_menu(self, node_id: str) -> None:
        node = self.tab_canvas.scene.get_node_data(node_id)
        if not node:
            return
        current = str(node.get("name") or "")
        value, ok = QInputDialog.getText(self, "Editar TAG equipo", "TAG:", text=current)
        if not ok:
            return
        self.tab_canvas.scene.set_node_name(node_id, str(value or "").strip(), emit=False)
        self._on_project_mutated()

    def _open_cabinet_detail_dialog(self, node_id: str) -> None:
        node = self.tab_canvas.scene.get_node_data(node_id)
        if not node:
            return
        self._cabinet_dialog = CabinetDetailDialog(
            self,
            project=self.project,
            node_id=str(node_id),
            material_service=self._material_service,
            equipment_items_by_id=self._equipment_items_by_id,
        )
        self._cabinet_dialog.show()
        self._cabinet_dialog.raise_()
        self._cabinet_dialog.activateWindow()

    def _equipment_lib_path_for_id(self, item_id: str) -> Optional[str]:
        return self._equipment_item_sources.get(str(item_id))

    def _on_equipment_rename_requested(self, item_id: str, current_name: str) -> None:
        item_id = str(item_id or "")
        if not item_id:
            return
        item = self._equipment_items_by_id.get(item_id) or {}
        name, ok = QInputDialog.getText(
            self,
            "Renombrar equipo",
            "Nombre:",
            text=str(current_name or item.get("name") or item_id),
        )
        if not ok or not str(name or "").strip():
            return
        lib_path = self._equipment_lib_path_for_id(item_id) or self._ensure_equipment_library()
        payload = {
            "id": item_id,
            "name": str(name).strip(),
            "category": item.get("category") or "Usuario",
            "equipment_type": item.get("equipment_type"),
            "template_ref": item.get("template_ref"),
            "cable_access": item.get("cable_access", "bottom"),
            "dimensions_mm": item.get("dimensions_mm") or {"width": 0, "height": 0, "depth": 0},
        }
        try:
            upsert_equipment_item(lib_path, payload)
        except LibWriteError as exc:
            QMessageBox.warning(self, "Equipos", f"No se pudo renombrar:\n{exc}")
            return
        self._refresh_equipment_library_items()

    def _on_equipment_delete_requested(self, item_id: str, item_name: str) -> None:
        item_id = str(item_id or "")
        if not item_id:
            return
        used = self.tab_canvas.get_used_equipment_ids()
        if item_id in used:
            QMessageBox.warning(self, "Equipos", "No se puede eliminar: el equipo está en uso.")
            return
        lib_path = self._equipment_lib_path_for_id(item_id)
        if not lib_path:
            QMessageBox.warning(self, "Equipos", "No se encontró la librería del equipo.")
            return
        resp = QMessageBox.question(
            self,
            "Eliminar equipo",
            f"¿Eliminar '{item_name}' de la librería?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return
        try:
            delete_equipment_item(lib_path, item_id)
        except LibWriteError as exc:
            QMessageBox.warning(self, "Equipos", f"No se pudo eliminar:\n{exc}")
            return
        self._refresh_equipment_library_items()

    def _find_writable_equipment_library(self) -> Optional[str]:
        libs = sorted([lr for lr in self.project.libraries if lr.enabled], key=lambda x: x.priority)
        for lr in libs:
            try:
                res = load_lib(lr.path)
            except Exception:
                continue
            if res.doc.get("kind") != "equipment_library":
                continue
            if Path(lr.path).exists() and os.access(str(lr.path), os.W_OK):
                return str(lr.path)
        return None

    def _ensure_equipment_library(self) -> str:
        existing = self._find_writable_equipment_library()
        if existing:
            return existing
        base_dir = Path(self._project_path).parent if self._project_path else self._app_dir
        lib_dir = base_dir / "libs"
        lib_dir.mkdir(parents=True, exist_ok=True)
        lib_path = lib_dir / "equipment_user.lib"
        if not lib_path.exists():
            doc = {
                "schema_version": "1.0",
                "kind": "equipment_library",
                "meta": {"name": "Equipos Usuario"},
                "items": [],
            }
            from data.repositories.lib_writer import write_json_atomic
            write_json_atomic(str(lib_path), doc)
        self.project.libraries.append(LibraryRef(path=str(lib_path), enabled=True, priority=1))
        self._on_project_mutated()
        return str(lib_path)

    def _on_equipment_add_requested(self, name: str, equipment_type: str) -> None:
        equip_name = str(name or "").strip()
        if not equip_name:
            return
        equip_type = str(equipment_type or "").strip()
        if not equip_type or equip_type == "Equipo":
            equip_type = "Tablero"
        if equip_type not in ("Tablero", "Armario"):
            QMessageBox.warning(self, "Equipos", "Tipo inválido. Usa Tablero o Armario.")
            return
        equip_id = normalize_equipment_id(equip_name)
        item = {
            "id": equip_id,
            "name": equip_name,
            "category": "Usuario",
            "equipment_type": equip_type,
            "template_ref": None,
            "cable_access": "bottom",
            "dimensions_mm": {"width": 0, "height": 0, "depth": 0},
        }
        lib_path = self._ensure_equipment_library()
        try:
            upsert_equipment_item(lib_path, item)
        except LibWriteError as exc:
            QMessageBox.warning(self, "Equipos", f"No se pudo guardar el equipo:\n{exc}")
            return
        self._refresh_equipment_library_items()

    def _open_equipment_bulk_edit_dialog(self) -> None:
        dlg = EquipmentBulkEditDialog(
            self,
            items_by_id=self._equipment_items_by_id,
            item_sources=self._equipment_item_sources,
            ensure_writable_lib_cb=self._ensure_equipment_library,
        )
        if dlg.exec_() == QDialog.Accepted:
            self._refresh_equipment_library_items()

    def _project_dialog_dir(self) -> str:
        last_path = self._app_config.last_project_path
        if last_path:
            parent = Path(last_path).parent
            if parent.exists():
                return str(parent)
        return str(self._app_dir)

    def _apply_window_state_from_config(self) -> None:
        size = self._app_config.window_size
        pos = self._app_config.window_pos
        if size:
            self.resize(int(size[0]), int(size[1]))
        if pos:
            self.move(int(pos[0]), int(pos[1]))

    def closeEvent(self, event) -> None:
        self._app_config.window_size = [self.width(), self.height()]
        self._app_config.window_pos = [self.x(), self.y()]
        if self._project_path:
            self._app_config.last_project_path = self._project_path
        if self._materiales_path:
            self._app_config.materiales_bd_path = self._materiales_path
        self._app_config.save()
        super().closeEvent(event)
