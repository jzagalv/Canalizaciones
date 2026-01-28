# -*- coding: utf-8 -*-
from __future__ import annotations

import json

from PyQt5.QtCore import Qt, pyqtSignal, QRect
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import QGraphicsView, QMenu

from ui.canvas.canvas_items import EdgeItem, NodeItem


class CanvasView(QGraphicsView):
    """QGraphicsView wrapper with zoom and drag&drop support."""

    view_state_changed = pyqtSignal(dict)
    troncal_create_requested = pyqtSignal()
    troncal_add_requested = pyqtSignal()
    troncal_remove_requested = pyqtSignal()
    edit_edge_tag_requested = pyqtSignal(str)
    edit_node_tag_requested = pyqtSignal(str)

    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setRubberBandSelectionMode(Qt.ContainsItemShape)
        self.setAcceptDrops(True)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setFocusPolicy(Qt.StrongFocus)
        self._panning = False
        self._pan_start = None
        self._default_drag_mode = self.dragMode()

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        current_zoom = self.transform().m11()
        next_zoom = current_zoom * factor
        min_zoom = 0.05
        max_zoom = 20.0
        if next_zoom < min_zoom:
            factor = min_zoom / current_zoom
        elif next_zoom > max_zoom:
            factor = max_zoom / current_zoom
        self.scale(factor, factor)
        self._emit_view_state()
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            self.setDragMode(QGraphicsView.NoDrag)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning and self._pan_start is not None:
            dx = event.pos().x() - self._pan_start.x()
            dy = event.pos().y() - self._pan_start.y()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - dx)
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - dy)
            self._pan_start = event.pos()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton and self._panning:
            self._panning = False
            self._pan_start = None
            self.setCursor(Qt.ArrowCursor)
            self.setDragMode(self._default_drag_mode)
            self._emit_view_state()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event):
        md = event.mimeData()
        if md.hasFormat("application/x-canalizaciones-item") or md.hasFormat("application/x-canalizaciones-equipment"):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        md = event.mimeData()
        if md.hasFormat("application/x-canalizaciones-item") or md.hasFormat("application/x-canalizaciones-equipment"):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event):
        md = event.mimeData()
        if md.hasFormat("application/x-canalizaciones-item"):
            try:
                payload = json.loads(bytes(md.data("application/x-canalizaciones-item")).decode("utf-8"))
                scene_pos = self.mapToScene(event.pos())
                sc = self.scene()
                if hasattr(sc, "handle_drop"):
                    if sc.handle_drop(scene_pos, payload):
                        event.acceptProposedAction()
                        return
            except Exception:
                pass
        if md.hasFormat("application/x-canalizaciones-equipment"):
            try:
                payload = json.loads(bytes(md.data("application/x-canalizaciones-equipment")).decode("utf-8"))
                scene_pos = self.mapToScene(event.pos())
                sc = self.scene()
                if hasattr(sc, "handle_drop"):
                    if sc.handle_drop(scene_pos, payload):
                        event.acceptProposedAction()
                        return
            except Exception:
                # Fallback: let base class handle
                pass
        super().dropEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            sc = self.scene()
            if hasattr(sc, "delete_selected"):
                sc.delete_selected()
                event.accept()
                return
        super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._emit_view_state()

    def contextMenuEvent(self, event):
        item = self.itemAt(event.pos())
        if item and item.parentItem():
            parent = item.parentItem()
            if isinstance(parent, EdgeItem):
                item = parent
            elif isinstance(parent, NodeItem):
                item = parent
        if isinstance(item, EdgeItem):
            scene = self.scene()
            if scene:
                scene.clearSelection()
            item.setSelected(True)
            menu = QMenu(self)
            act_assign = menu.addAction("Crear/Asignar troncal conectada")
            act_add = menu.addAction("Agregar conectados a troncal")
            act_remove = menu.addAction("Quitar de troncal")
            menu.addSeparator()
            act_tag = menu.addAction("Editar TAG tramo")
            action = menu.exec_(event.globalPos())
            if action == act_assign:
                self.troncal_create_requested.emit()
            elif action == act_add:
                self.troncal_add_requested.emit()
            elif action == act_remove:
                self.troncal_remove_requested.emit()
            elif action == act_tag:
                self.edit_edge_tag_requested.emit(str(item.edge_id))
            event.accept()
            return

        if isinstance(item, NodeItem):
            scene = self.scene()
            if scene:
                scene.clearSelection()
            item.setSelected(True)
            menu = QMenu(self)
            act_edit = menu.addAction("Editar TAG equipo")
            action = menu.exec_(event.globalPos())
            if action == act_edit:
                self.edit_node_tag_requested.emit(str(item.node_id))
            event.accept()
            return

        super().contextMenuEvent(event)

    def set_view_state(self, state: dict) -> None:
        scale = float(state.get("scale", 1.0) or 1.0)
        center = state.get("center") or None
        if scale <= 0:
            scale = 1.0
        self.resetTransform()
        self.scale(scale, scale)
        if isinstance(center, (list, tuple)) and len(center) >= 2:
            self.centerOn(float(center[0]), float(center[1]))
        else:
            self.centerOn(self.sceneRect().center())
        self._emit_view_state()

    def refresh_view_state(self) -> None:
        self._emit_view_state()

    def _emit_view_state(self) -> None:
        rect = self.viewport().rect() if isinstance(self.viewport().rect(), QRect) else None
        if rect is None or rect.isNull():
            return
        center = self.mapToScene(rect.center())
        payload = {
            "scale": float(self.transform().m11()),
            "center": [float(center.x()), float(center.y())],
        }
        self.view_state_changed.emit(payload)
