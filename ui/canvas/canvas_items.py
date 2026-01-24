# -*- coding: utf-8 -*-
"""Canvas graphics items.

This module intentionally keeps *only* QGraphicsItem concerns.
Project persistence and business rules belong to the scene/controller.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from PyQt5.QtCore import QPointF, Qt, pyqtSignal, QObject, QLineF
from PyQt5.QtGui import QBrush, QPen, QColor
from PyQt5.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsSimpleTextItem,
    QGraphicsTextItem,
)


@dataclass
class NodeData:
    id: str
    kind: str  # 'equipment' | 'chamber' | 'junction'
    name: str
    x: float
    y: float
    library_item_id: Optional[str] = None


class NodeItemSignals(QObject):
    moved = pyqtSignal(str, float, float)  # id, x, y


class NodeItem(QGraphicsEllipseItem):
    """Draggable node representing an equipment/chamber/junction."""

    def __init__(self, data: NodeData, radius: float = 18.0):
        super().__init__(-radius, -radius, 2 * radius, 2 * radius)
        self.data = data
        self.radius = radius
        self.signals = NodeItemSignals()

        self.setFlag(self.ItemIsMovable, True)
        self.setFlag(self.ItemIsSelectable, True)
        self.setFlag(self.ItemSendsGeometryChanges, True)
        self.setZValue(10)

        # Style
        if data.kind == "equipment":
            self.setBrush(QBrush(Qt.white))
            self.setPen(QPen(Qt.black, 2))
        elif data.kind == "chamber":
            self.setBrush(QBrush(Qt.lightGray))
            self.setPen(QPen(Qt.black, 2))
        else:  # junction or other
            self.setBrush(QBrush(QColor("#e5e7eb")))
            self.setPen(QPen(Qt.black, 2))

        self.label = QGraphicsSimpleTextItem(data.name, self)
        self.label.setFlag(self.label.ItemIgnoresTransformations, True)
        self.label.setPos(radius + 4, -radius)

        self.setPos(QPointF(float(data.x), float(data.y)))

    @property
    def node_id(self) -> str:
        return self.data.id

    @property
    def node_type(self) -> str:
        return self.data.kind

    @property
    def name(self) -> str:
        return self.data.name

    def itemChange(self, change, value):
        if change == self.ItemPositionHasChanged:
            p: QPointF = value
            self.data.x, self.data.y = float(p.x()), float(p.y())
            self.signals.moved.emit(self.data.id, self.data.x, self.data.y)
        return super().itemChange(change, value)


class EdgeItem(QGraphicsLineItem):
    """Straight edge between two NodeItems."""

    def __init__(
        self,
        edge_id: str,
        from_node: NodeItem,
        to_node: NodeItem,
        containment_kind: str = "duct",
        mode: str = "auto",
        runs: Optional[list] = None,
    ):
        super().__init__()
        self.edge_id = str(edge_id)
        self.from_node = from_node
        self.to_node = to_node
        self.containment_kind = str(containment_kind)
        self.mode = str(mode)
        self.runs = runs or []
        self.status = "ok"

        self.setZValue(-1)
        self.setFlag(self.ItemIsSelectable, True)

        self.badge = QGraphicsTextItem("", self)
        self.badge.setZValue(10)
        self.badge.setDefaultTextColor(QColor("#111827"))

        self.update_geometry()
        self.set_status("ok")

    def update_geometry(self) -> None:
        p1 = self.from_node.scenePos()
        p2 = self.to_node.scenePos()
        self.setLine(QLineF(p1, p2))
        mid = (p1 + p2) / 2
        self.badge.setPos(mid.x() + 6, mid.y() + 6)

    def _runs_label(self) -> str:
        if not self.runs:
            return ""
        parts = []
        for r in self.runs:
            cid = str(r.get("catalog_id", ""))
            qty = int(r.get("qty", 1) or 1)
            if not cid:
                continue

            if "duct" in (self.containment_kind or "") and "duct" in cid:
                m = re.search(r"(\d+)", cid)
                dim = f"Ø{m.group(1)}" if m else cid
            else:
                dim = cid.replace("_", " ")
            parts.append(f"{qty}x{dim}" if qty != 1 else f"{dim}")
        return " + ".join(parts)

    def set_status(self, status: str, badge_text: str = "") -> None:
        self.status = str(status or "ok")
        if badge_text:
            self.badge.setPlainText(str(badge_text))
        else:
            summary = self._runs_label()
            k = (self.containment_kind or "").upper()
            self.badge.setPlainText(f"{k} {summary}".strip())
        self._apply_style()

    def update_meta(
        self,
        containment_kind: Optional[str] = None,
        mode: Optional[str] = None,
        runs: Optional[list] = None,
    ) -> None:
        if containment_kind is not None:
            self.containment_kind = str(containment_kind)
        if mode is not None:
            self.mode = str(mode)
        if runs is not None:
            self.runs = runs
        self.set_status(self.status)

    def _apply_style(self) -> None:
        pen = QPen(QColor("#6b7280"), 2)
        if self.isSelected():
            pen = QPen(QColor("#3b82f6"), 3)
        if self.status == "warn":
            pen = QPen(QColor("#f59e0b"), 3)
        elif self.status == "error":
            pen = QPen(QColor("#ef4444"), 3)
        self.setPen(pen)
