# -*- coding: utf-8 -*-
from __future__ import annotations

import json

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import QGraphicsView


class CanvasView(QGraphicsView):
    """QGraphicsView wrapper with zoom and drag&drop support."""

    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setAcceptDrops(True)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
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
                    sc.handle_drop(scene_pos, payload)
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
                    sc.handle_drop(scene_pos, payload)
                event.acceptProposedAction()
                return
            except Exception:
                # Fallback: let base class handle
                pass
        super().dropEvent(event)
