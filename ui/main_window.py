# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QAction, QActionGroup, QApplication, QFileDialog, QHBoxLayout, QLabel,
    QMainWindow, QMessageBox, QPushButton, QSplitter, QTabWidget, QVBoxLayout,
    QWidget
)

from data.repositories.project_store import load_project, save_project
from data.repositories.lib_loader import LibError, load_lib
from data.repositories.lib_merge import EffectiveCatalog, merge_libs
from data.repositories.template_repo import (
    TemplateRepoError,
    load_base_template,
    save_base_template,
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
from domain.calculations.formatting import round2, util_color
from domain.services.engine import build_circuits_by_edge_index, compute_project_solutions
from ui.tabs.canvas_tab import CanvasTab
from ui.tabs.circuits_tab import CircuitsTab
from ui.tabs.primary_equipment_tab import PrimaryEquipmentTab
from ui.tabs.equipment_library_tab import EquipmentLibraryTab
from ui.tabs.results_tab import ResultsTab
from ui.dialogs.libraries_templates_dialog import LibrariesTemplatesDialog
from ui.dialogs.conduit_segment_dialog import ConduitSegmentDialog
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

        # cached effective catalog
        self._eff: Optional[EffectiveCatalog] = None
        self._materiales_doc: Optional[Dict] = None
        self._materiales_path: str = ""
        self._base_template: Optional[BaseTemplate] = None
        self._lib_tpl_dialog: Optional[LibrariesTemplatesDialog] = None
        self._segment_dialog: Optional[ConduitSegmentDialog] = None

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

    def open_segment_dialog(self, segment_item) -> None:
        try:
            if segment_item is None:
                return
            if self._segment_dialog is None:
                self._segment_dialog = ConduitSegmentDialog(self)
                self._segment_dialog.set_material_service(self._material_service)
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
            self._app_config.last_project_path = path
            self._app_config.save()
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

        solutions, warnings = compute_project_solutions(self.project, self._eff)
        self.tab_canvas.scene.set_circuits_by_edge(build_circuits_by_edge_index(self.project))
        self._sync_edge_fill_props(solutions)
        self.tab_results.set_results(self.project, solutions, warnings)
        self.tab_canvas.set_edge_statuses(solutions)
        self._refresh_status(extra_warnings=warnings)

    def _sync_edge_fill_props(self, solutions: Dict[str, Dict]) -> None:
        if not solutions:
            return
        emit = False
        for edge_id, sol in solutions.items():
            props = self._edge_props(edge_id)
            fill_percent_raw = sol.get("fill_percent")
            fill_max_raw = sol.get("fill_max_percent")
            fill_percent = round2(fill_percent_raw)
            fill_max = round2(fill_max_raw)
            props["fill_percent"] = fill_percent
            props["fill_max_percent"] = fill_max
            props["fill_over"] = bool(sol.get("fill_over"))
            props["fill_state"] = sol.get("fill_state") or util_color(fill_percent_raw, fill_max_raw)
            props["group_area_sums"] = list(sol.get("group_area_sums") or [])
            props["group_max_fills"] = list(sol.get("group_max_fills") or [])
            self.tab_canvas.scene.set_edge_props(edge_id, props, emit=False)
            emit = True
        if emit:
            self.tab_canvas.scene.signals.project_changed.emit(self.project.canvas)

    def _edge_props(self, edge_id: str) -> Dict[str, object]:
        edges = list((self.project.canvas or {}).get("edges") or [])
        for edge in edges:
            if str(edge.get("id")) == str(edge_id):
                return dict(edge.get("props") or {})
        return {}

    # -------------------- Refresh --------------------
    def _on_project_mutated(self) -> None:
        # mark dirty (lightweight)
        self._eff = None  # libraries/canvas/circuits may have changed
        self.tab_canvas.scene.set_circuits_by_edge(None)
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
                self._segment_dialog.set_segment(None)
            except Exception:
                pass
        self._refresh_equipment_library_items()
        self._load_active_materiales()
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
        self.lbl_project.setText(f"{name} — {p}")

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
