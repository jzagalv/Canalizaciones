# -*- coding: utf-8 -*-
"""Canvas graphics items.

This module intentionally keeps *only* QGraphicsItem concerns.
Project persistence and business rules belong to the scene/controller.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from PyQt5.QtCore import QPointF, Qt, pyqtSignal, QObject, QLineF, QRectF
from PyQt5.QtGui import QBrush, QPen, QColor, QPainter, QFont, QFontMetricsF
from PyQt5.QtWidgets import (
    QGraphicsItem,
    QGraphicsLineItem,
)

from domain.calculations.formatting import fmt_percent, util_color


class BadgeLabelItem(QGraphicsItem):
    def __init__(
        self,
        text: str = "",
        padding: float = 4.0,
        radius: float = 4.0,
        parent: Optional[QGraphicsItem] = None,
    ):
        super().__init__(parent)
        self._text = str(text or "")
        self._padding = float(padding)
        self._radius = float(radius)
        self._font = QFont()
        self._text_color = QColor("#111827")
        self._bg_color = QColor("#ffffff")
        self._border_color = QColor("#e5e7eb")
        self._lines: List[Tuple[str, QColor]] = []
        self._bounds = QRectF()
        self.set_text(text)

    def set_text(self, text: str) -> None:
        self._text = str(text or "")
        self._lines = []
        if self._text:
            self._lines.append((self._text, QColor(self._text_color)))
        self._recalc_bounds()
        self.update()

    def text(self) -> str:
        return self._text

    def set_font(self, font: QFont) -> None:
        self._font = QFont(font)
        self._recalc_bounds()
        self.update()

    def set_text_color(self, color: QColor) -> None:
        self._text_color = QColor(color)
        if len(self._lines) <= 1:
            self._lines = [(self._text, QColor(self._text_color))] if self._text else []
        self.update()

    def set_background_color(self, color: QColor) -> None:
        self._bg_color = QColor(color)
        self.update()

    def set_border_color(self, color: QColor) -> None:
        self._border_color = QColor(color)
        self.update()

    def set_lines(self, lines: List[Tuple[str, QColor]]) -> None:
        clean: List[Tuple[str, QColor]] = []
        for text, color in lines or []:
            clean.append((str(text or ""), QColor(color)))
        self._lines = clean
        self._text = "\n".join(line for line, _ in clean).strip()
        self._recalc_bounds()
        self.update()

    def _recalc_bounds(self) -> None:
        metrics = QFontMetricsF(self._font)
        if not self._lines:
            self._bounds = QRectF(0, 0, 0, 0)
            return
        widths = [metrics.boundingRect(line).width() for line, _ in self._lines]
        line_height = metrics.height()
        w = (max(widths) if widths else 0.0) + self._padding * 2
        h = line_height * len(self._lines) + self._padding * 2
        self._bounds = QRectF(0, 0, w, h)

    def boundingRect(self) -> QRectF:
        return QRectF(self._bounds)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        if self._bounds.isNull():
            return
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setBrush(QBrush(self._bg_color))
        painter.setPen(QPen(self._border_color, 1))
        painter.drawRoundedRect(self._bounds, self._radius, self._radius)
        painter.setFont(self._font)
        metrics = QFontMetricsF(self._font)
        x = self._padding
        y = self._padding + metrics.ascent()
        line_height = metrics.height()
        for line, color in self._lines:
            painter.setPen(QPen(color))
            painter.drawText(QPointF(x, y), line)
            y += line_height


@dataclass
class NodeData:
    id: str
    kind: str  # 'equipment' | 'cabinet' | 'chamber' | 'junction'
    name: str
    x: float
    y: float
    library_item_id: Optional[str] = None


class NodeItemSignals(QObject):
    moved = pyqtSignal(str, float, float)  # id, x, y


class NodeItem(QGraphicsItem):
    """Draggable node representing an equipment/chamber/junction."""

    def __init__(self, data: NodeData, radius: float = 18.0):
        super().__init__()
        self.data = data
        self.radius = radius
        self.signals = NodeItemSignals()

        self.setFlag(self.ItemIsMovable, True)
        self.setFlag(self.ItemIsSelectable, True)
        self.setFlag(self.ItemSendsGeometryChanges, True)
        self.setZValue(10)

        self.label = BadgeLabelItem(data.name, parent=self)
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

    def boundingRect(self) -> QRectF:
        r = float(self.radius)
        return QRectF(-r, -r, 2 * r, 2 * r)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        rect = self.boundingRect()
        selected = self.isSelected()
        pen = QPen(QColor("#3b82f6"), 3) if selected else QPen(Qt.black, 2)

        if self.data.kind == "equipment":
            base_color = QColor(Qt.white)
        elif self.data.kind == "cabinet":
            base_color = QColor(173, 216, 230)
        elif self.data.kind == "chamber":
            base_color = QColor(Qt.lightGray)
        else:  # junction or other
            base_color = QColor("#e5e7eb")
        if selected:
            base_color = base_color.lighter(115)
        brush = QBrush(base_color)

        painter.setPen(pen)
        painter.setBrush(brush)

        if self.data.kind == "cabinet":
            painter.drawRect(rect)
        else:
            painter.drawEllipse(rect)

    def itemChange(self, change, value):
        if change == self.ItemPositionHasChanged:
            p: QPointF = value
            self.data.x, self.data.y = float(p.x()), float(p.y())
            self.signals.moved.emit(self.data.id, self.data.x, self.data.y)
        elif change == self.ItemSelectedHasChanged:
            self.update()
        return super().itemChange(change, value)


class EdgeItemSignals(QObject):
    double_clicked = pyqtSignal(object)


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
        self.props = {}
        self._fill_info: Dict[str, object] = {}
        self.signals = EdgeItemSignals()

        self.setZValue(-1)
        self.setFlag(self.ItemIsSelectable, True)

        self.badge = BadgeLabelItem("", parent=self)
        self.badge.setZValue(10)
        self.badge.setFlag(self.badge.ItemIgnoresTransformations, True)

        self.update_geometry()
        self.set_status("ok")

    def mouseDoubleClickEvent(self, event):
        self.setSelected(True)
        self._apply_style()
        try:
            self.signals.double_clicked.emit(self)
        except Exception:
            pass
        event.accept()

    def update_geometry(self) -> None:
        p1 = self.from_node.scenePos()
        p2 = self.to_node.scenePos()
        self.setLine(QLineF(p1, p2))
        mid = (p1 + p2) / 2
        self.badge.setPos(mid.x() + 6, mid.y() + 6)

    def _label_text(self) -> List[Tuple[str, QColor]]:
        props = self.props or {}
        tag = str(props.get("tag") or "").strip()
        has_tag = bool(tag)
        tag_text = tag if has_tag else "SIN TAG"
        kind_map = {"duct": "Ducto", "epc": "EPC", "bpc": "BPC"}
        kind = str(props.get("conduit_type") or "").strip()
        if not kind:
            kind = kind_map.get(str(self.containment_kind or "").strip().lower(), "Ducto")
        size = str(props.get("size") or "").strip()
        qty = int(props.get("quantity") or 1)
        if not size and self.runs:
            size = str(self.runs[0].get("catalog_id") or "").strip()
        size_text = size or "?"
        fill_percent = self._fill_info.get("fill_percent", props.get("fill_percent"))
        max_allowed = self._fill_info.get("fill_max_percent", props.get("fill_max_percent"))
        if fill_percent is None:
            fill_line = "Utilizacion: (Recalcular)"
            fill_color = QColor("#9ca3af")
        else:
            fill_state = self._fill_info.get("fill_state", props.get("fill_state")) or util_color(fill_percent, max_allowed)
            fill_line = f"Utilizacion: {fmt_percent(fill_percent)}"
            fill_color = {
                "ok": QColor("#16a34a"),
                "warn": QColor("#f59e0b"),
                "over": QColor("#dc2626"),
            }.get(str(fill_state), QColor("#111827"))
        return [
            (tag_text, QColor("#111827")),
            (f"{kind} | {qty} x {size_text}", QColor("#111827")),
            (fill_line, fill_color),
        ]

    def set_status(self, status: str, badge_text: str = "") -> None:
        self.status = str(status or "ok")
        lines = self._label_text()
        self.badge.set_lines(lines)
        self._apply_style()

    def set_fill_info(self, fill_info: Dict[str, object]) -> None:
        self._fill_info = dict(fill_info or {})
        self.set_status(self.status)

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
        fill_over = bool(self._fill_info.get("fill_over", (self.props or {}).get("fill_over")))
        if self.status == "error":
            pen = QPen(QColor("#ef4444"), 3)
        elif self.status == "warn" or fill_over:
            pen = QPen(QColor("#f59e0b"), 3)
        if self.isSelected():
            pen = QPen(QColor("#3b82f6"), max(4, pen.width() + 1))
        self.setPen(pen)
