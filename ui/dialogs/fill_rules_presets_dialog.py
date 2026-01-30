# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any, Dict, List

from PyQt5.QtWidgets import (
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QInputDialog,
)

from data.repositories.fill_rules_presets_store import (
    add_preset,
    delete_preset,
    ensure_default_presets,
    save_presets,
    update_preset,
)
from ui.dialogs.fill_rules_editor_dialog import FillRulesEditorDialog
from ui.dialogs.base_dialog import BaseDialog


class FillRulesPresetsDialog(BaseDialog):
    def __init__(self, app_dir, project, parent=None):
        super().__init__(parent, title="Presets de reglas de llenado")
        self.setWindowTitle("Presets de reglas de llenado")
        self._app_dir = app_dir
        self._project = project
        self._doc = ensure_default_presets(app_dir)

        root = self.body_layout
        root.addWidget(QLabel("Presets disponibles"))
        self.list = QListWidget()
        root.addWidget(self.list, 1)

        btns = QHBoxLayout()
        self.btn_new = QPushButton("Nuevo")
        self.btn_dup = QPushButton("Duplicar")
        self.btn_edit = QPushButton("Editar")
        self.btn_del = QPushButton("Borrar")
        self.btn_use = QPushButton("Usar en este proyecto")
        btns.addWidget(self.btn_new)
        btns.addWidget(self.btn_dup)
        btns.addWidget(self.btn_edit)
        btns.addWidget(self.btn_del)
        btns.addWidget(self.btn_use)
        root.addLayout(btns)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        close_btn = buttons.button(QDialogButtonBox.Close)
        if close_btn is not None:
            close_btn.setProperty("secondary", True)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        self.footer_layout.addWidget(buttons)

        self.btn_new.clicked.connect(self._on_new)
        self.btn_dup.clicked.connect(self._on_duplicate)
        self.btn_edit.clicked.connect(self._on_edit)
        self.btn_del.clicked.connect(self._on_delete)
        self.btn_use.clicked.connect(self._on_use)

        self._reload()

    def _reload(self) -> None:
        self.list.clear()
        presets = list(self._doc.get("presets") or [])
        active = str(self._project.active_fill_rules_preset_id or "")
        for p in presets:
            pid = str(p.get("id") or "")
            name = str(p.get("name") or pid)
            label = f"{name} ({pid})"
            if pid and pid == active:
                label = f"{label} [activo]"
            item = QListWidgetItem(label)
            item.setData(1, p)
            self.list.addItem(item)

    def _selected_preset(self) -> Dict[str, Any] | None:
        item = self.list.currentItem()
        if not item:
            return None
        return item.data(1)

    def _make_id(self, name: str) -> str:
        base = "".join(ch if ch.isalnum() else "_" for ch in name.strip().upper())
        base = "_".join([b for b in base.split("_") if b])
        return base or "PRESET"

    def _on_new(self) -> None:
        name, ok = QInputDialog.getText(self, "Nuevo preset", "Nombre:")
        if not ok or not name.strip():
            return
        pid = self._make_id(name)
        preset = {
            "id": pid,
            "name": name.strip(),
            "rules": {
                "duct": {"fill_by_conductors": [{"min": 1, "max": 1, "fill_max_pct": 50}, {"min": 2, "max": 999, "fill_max_pct": 33}]},
                "bpc": {"fill_max_pct": 40, "layers_enabled": False, "max_layers": 1},
                "epc": {"fill_max_pct": 40, "layers_enabled": True, "max_layers": 2},
            },
        }
        dlg = FillRulesEditorDialog(preset, self)
        if dlg.exec_() != QDialog.Accepted:
            return
        preset = dlg.get_preset()
        try:
            self._doc = add_preset(self._doc, preset)
            save_presets(self._app_dir, self._doc)
            self._reload()
        except Exception as exc:
            QMessageBox.warning(self, "Presets", str(exc))

    def _on_duplicate(self) -> None:
        preset = self._selected_preset()
        if not preset:
            return
        name, ok = QInputDialog.getText(self, "Duplicar preset", "Nombre:", text=str(preset.get("name") or ""))
        if not ok or not name.strip():
            return
        pid = self._make_id(name)
        new_preset = dict(preset)
        new_preset["id"] = pid
        new_preset["name"] = name.strip()
        try:
            self._doc = add_preset(self._doc, new_preset)
            save_presets(self._app_dir, self._doc)
            self._reload()
        except Exception as exc:
            QMessageBox.warning(self, "Presets", str(exc))

    def _on_edit(self) -> None:
        preset = self._selected_preset()
        if not preset:
            return
        dlg = FillRulesEditorDialog(preset, self)
        if dlg.exec_() != QDialog.Accepted:
            return
        new_preset = dlg.get_preset()
        try:
            self._doc = update_preset(self._doc, new_preset)
            save_presets(self._app_dir, self._doc)
            self._reload()
        except Exception as exc:
            QMessageBox.warning(self, "Presets", str(exc))

    def _on_delete(self) -> None:
        preset = self._selected_preset()
        if not preset:
            return
        pid = str(preset.get("id") or "")
        resp = QMessageBox.question(self, "Presets", f"�Borrar preset {pid}?")
        if resp != QMessageBox.Yes:
            return
        try:
            self._doc = delete_preset(self._doc, pid)
            save_presets(self._app_dir, self._doc)
            self._reload()
        except Exception as exc:
            QMessageBox.warning(self, "Presets", str(exc))

    def _on_use(self) -> None:
        preset = self._selected_preset()
        if not preset:
            return
        pid = str(preset.get("id") or "")
        self._project.active_fill_rules_preset_id = pid
        self.accept()

    def get_presets_doc(self) -> Dict[str, Any]:
        return dict(self._doc)
