# -*- coding: utf-8 -*-
from __future__ import annotations

"""CanvasScene

- Holds graphics items (nodes/edges) and a background plan image.
- Maintains a lightweight, JSON-serializable canvas dict stored in Project.canvas.

Design goals:
- Scene is UI-layer only, but owns the *projection* of the model to QGraphicsItems.
- Project.canvas remains the single source of truth for persistence.
"""

import base64
import math
from pathlib import Path
from typing import Dict, List, Optional

from PyQt5.QtCore import QObject, pyqtSignal, Qt, QRectF
from PyQt5.QtGui import QPixmap, QImage, QPainter
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsPixmapItem

from PyQt5.QtPrintSupport import QPrinter

from ui.canvas.canvas_items import NodeItem, EdgeItem, NodeData


class CanvasSceneSignals(QObject):
    project_changed = pyqtSignal(dict)
    selection_changed = pyqtSignal(dict)
    library_item_used = pyqtSignal(str)
    library_item_released = pyqtSignal(str)
    segment_double_clicked = pyqtSignal(object)
    segment_removed = pyqtSignal(str)


class CanvasScene(QGraphicsScene):
    """Canvas scene holding nodes (equipment/chamber/junction) and edges."""

    SNAP_THRESHOLD_PX = 24.0

    def __init__(self):
        super().__init__()
        self.signals = CanvasSceneSignals()

        self._project_canvas: Dict = {
            "nodes": [],
            "edges": [],
            "background": {
                "path": "",
                "opacity": 1.0,
                "locked": True,
                "pos": [0.0, 0.0],
                "scale": 1.0,
                "image_data": "",
                "image_format": "",
            },
        }
        self._nodes_by_id: Dict[str, NodeItem] = {}
        self._edges_by_id: Dict[str, EdgeItem] = {}

        self._equipment_items_by_id: Dict[str, Dict] = {}

        self._connect_mode: bool = False
        self._pending_from_node_id: Optional[str] = None

        self._background_item: Optional[QGraphicsPixmapItem] = None
        self._circuits_by_edge: Optional[Dict[str, List[str]]] = None
        self._fill_results: Dict[str, Dict[str, object]] = {}

        self.selectionChanged.connect(self._emit_selection_snapshot)

    # -------------------- External data --------------------
    def set_equipment_items(self, items_by_id: Dict[str, Dict]) -> None:
        self._equipment_items_by_id = items_by_id or {}

    def set_circuits_by_edge(self, circuits_by_edge: Optional[Dict[str, List[str]]]) -> None:
        self._circuits_by_edge = circuits_by_edge

    def get_circuit_ids_for_edge(self, edge_id: str) -> Optional[List[str]]:
        if self._circuits_by_edge is None:
            return None
        return list(self._circuits_by_edge.get(str(edge_id), []))

    def set_edge_fill_results(self, edge_id: str, fill_result: Dict[str, object]) -> None:
        self._fill_results[str(edge_id)] = dict(fill_result or {})
        edge = self._edges_by_id.get(str(edge_id))
        if edge:
            edge.set_fill_info(self._fill_results.get(str(edge_id), {}))

    def get_edge_fill_results(self, edge_id: str) -> Optional[Dict[str, object]]:
        return self._fill_results.get(str(edge_id))

    # -------------------- Project canvas --------------------
    def set_project_canvas(self, canvas: Dict) -> None:
        """Load a canvas dict (as stored in Project.canvas) into the scene."""
        self.clear()
        self._nodes_by_id.clear()
        self._edges_by_id.clear()
        self._background_item = None
        self._circuits_by_edge = None
        self._fill_results = {}

        base = {
            "nodes": [],
            "edges": [],
            "background": {
                "path": "",
                "opacity": 1.0,
                "locked": True,
                "pos": [0.0, 0.0],
                "scale": 1.0,
                "image_data": "",
                "image_format": "",
            },
        }
        self._project_canvas = {**base, **(canvas or {})}
        # Ensure background dict exists
        bg = self._project_canvas.get("background") or {}
        self._project_canvas["background"] = {
            "path": str(bg.get("path", "") or ""),
            "opacity": float(bg.get("opacity", 1.0) or 1.0),
            "locked": bool(bg.get("locked", True)),
            "pos": list(bg.get("pos") or [0.0, 0.0]),
            "scale": float(bg.get("scale", 1.0) or 1.0),
            "image_data": str(bg.get("image_data", "") or ""),
            "image_format": str(bg.get("image_format", "") or ""),
        }

        # Background first (sets sceneRect to image size)
        bg_path = self._project_canvas["background"]["path"]
        bg_data = self._project_canvas["background"]["image_data"]
        if bg_data:
            try:
                raw = base64.b64decode(bg_data.encode("ascii"))
                pix = QPixmap()
                fmt = self._project_canvas["background"]["image_format"] or None
                if fmt:
                    pix.loadFromData(raw, fmt.upper())
                else:
                    pix.loadFromData(raw)
                if pix.isNull():
                    raise ValueError("Imagen embebida inválida")
                self._apply_background_pixmap(pix, emit=False)
            except Exception:
                self._project_canvas["background"]["image_data"] = ""
        elif bg_path:
            try:
                self.set_background_image(bg_path, emit=False)
            except Exception:
                # keep running even if the file is missing
                self._project_canvas["background"]["path"] = ""

        if self._background_item is not None:
            pos = self._project_canvas["background"]["pos"]
            if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                self._background_item.setPos(float(pos[0]), float(pos[1]))
            scale = float(self._project_canvas["background"]["scale"] or 1.0)
            if scale > 0:
                self._background_item.setScale(scale)
            self.set_background_opacity(self._project_canvas["background"]["opacity"], emit=False)
            self.set_background_locked(self._project_canvas["background"]["locked"], emit=False)

        # rebuild nodes
        for n in self._project_canvas.get("nodes", []) or []:
            nid = str(n.get("id", ""))
            if not nid:
                continue
            data = NodeData(
                id=nid,
                kind=str(n.get("type", n.get("kind", "equipment")) or "equipment"),
                name=str(n.get("name", nid) or nid),
                x=float(n.get("x", 0.0) or 0.0),
                y=float(n.get("y", 0.0) or 0.0),
                library_item_id=(str(n.get("library_item_id")) if n.get("library_item_id") else None),
            )
            node = NodeItem(data)
            node.signals.moved.connect(self._on_node_moved)
            self.addItem(node)
            self._nodes_by_id[nid] = node

        # rebuild edges
        for e in self._project_canvas.get("edges", []) or []:
            from_id = str(e.get("from_node") or e.get("from") or "")
            to_id = str(e.get("to_node") or e.get("to") or "")
            if from_id not in self._nodes_by_id or to_id not in self._nodes_by_id:
                continue
            e["from"] = from_id
            e["to"] = to_id
            e["from_node"] = from_id
            e["to_node"] = to_id
            e["props"] = dict(e.get("props") or {})
            edge = EdgeItem(
                edge_id=str(e.get("id", "")),
                from_node=self._nodes_by_id[from_id],
                to_node=self._nodes_by_id[to_id],
                containment_kind=str(e.get("kind", "duct")),
                mode=str(e.get("mode", "auto")),
                runs=list(e.get("runs", []) or []),
            )
            edge.props = dict(e.get("props") or {})
            edge.signals.double_clicked.connect(self._on_edge_double_clicked)
            self.addItem(edge)
            self._edges_by_id[edge.edge_id] = edge

        self._refresh_edges()
        self.signals.project_changed.emit(self._project_canvas)

    def get_project_canvas(self) -> Dict:
        return self._project_canvas

    # -------------------- Background image --------------------
    def _apply_background_pixmap(self, pix: QPixmap, emit: bool = True) -> None:
        if self._background_item is None:
            self._background_item = QGraphicsPixmapItem()
            self._background_item.setZValue(-1000)
            self._background_item.setFlag(QGraphicsPixmapItem.ItemIsSelectable, False)
            self._background_item.setTransformationMode(Qt.SmoothTransformation)
            self.addItem(self._background_item)

        self._background_item.setPixmap(pix)
        self.setSceneRect(QRectF(pix.rect()))

        if emit:
            self.signals.project_changed.emit(self._project_canvas)

    def set_background_image(self, image_path: str, emit: bool = True) -> None:
        try:
            raw = Path(image_path).read_bytes()
        except Exception:
            raw = b""
        fmt = Path(image_path).suffix.lstrip(".").lower()
        pix = QPixmap()
        if raw:
            pix.loadFromData(raw, fmt.upper() if fmt else None)
        if pix.isNull():
            pix = QPixmap(image_path)
        if pix.isNull():
            raise ValueError(f"No se pudo cargar la imagen: {image_path}")
        self._apply_background_pixmap(pix, emit=False)

        self._project_canvas.setdefault("background", {})
        self._project_canvas["background"]["path"] = str(image_path)
        self._project_canvas["background"]["image_data"] = base64.b64encode(raw).decode("ascii") if raw else ""
        self._project_canvas["background"]["image_format"] = fmt or ""
        self._project_canvas["background"].setdefault("opacity", 1.0)
        self._project_canvas["background"].setdefault("locked", True)
        self._project_canvas["background"].setdefault("pos", [0.0, 0.0])
        self._project_canvas["background"].setdefault("scale", 1.0)
        if self._background_item is not None:
            pos = self._project_canvas["background"]["pos"]
            self._background_item.setPos(float(pos[0]), float(pos[1]))
            self._background_item.setScale(float(self._project_canvas["background"]["scale"]))

        if emit:
            self.signals.project_changed.emit(self._project_canvas)

    def clear_background(self, emit: bool = True) -> None:
        if self._background_item is not None:
            self.removeItem(self._background_item)
            self._background_item = None
        self._project_canvas["background"] = {
            "path": "",
            "opacity": 1.0,
            "locked": True,
            "pos": [0.0, 0.0],
            "scale": 1.0,
            "image_data": "",
            "image_format": "",
        }
        if emit:
            self.signals.project_changed.emit(self._project_canvas)

    def background_bounding_rect(self) -> Optional[QRectF]:
        """Return background bounding rect if present, else None."""
        if self._background_item is None:
            return None
        try:
            return self._background_item.boundingRect().translated(self._background_item.pos())
        except Exception:
            return None

    def set_background_opacity(self, opacity: float, emit: bool = True) -> None:
        op = max(0.0, min(1.0, float(opacity)))
        if self._background_item is not None:
            self._background_item.setOpacity(op)
        self._project_canvas.setdefault("background", {})
        self._project_canvas["background"]["opacity"] = op
        if emit:
            self.signals.project_changed.emit(self._project_canvas)

    def set_background_locked(self, locked: bool, emit: bool = True) -> None:
        locked = bool(locked)
        if self._background_item is not None:
            if locked:
                self._background_item.setAcceptedMouseButtons(Qt.NoButton)
                self._background_item.setFlag(QGraphicsPixmapItem.ItemIsMovable, False)
            else:
                self._background_item.setAcceptedMouseButtons(Qt.LeftButton)
                self._background_item.setFlag(QGraphicsPixmapItem.ItemIsMovable, True)
            self._background_item.setFlag(QGraphicsPixmapItem.ItemSendsGeometryChanges, True)
        self._project_canvas.setdefault("background", {})
        self._project_canvas["background"]["locked"] = locked
        if emit:
            self.signals.project_changed.emit(self._project_canvas)

    # -------------------- Public commands --------------------
    def set_connect_mode(self, enabled: bool) -> None:
        self._connect_mode = bool(enabled)
        self._pending_from_node_id = None

    def add_node(self, node_type: str, name: str, x: float, y: float, library_item_id: Optional[str] = None) -> str:
        node_id = self._next_node_id()
        data = NodeData(id=node_id, kind=str(node_type), name=str(name), x=float(x), y=float(y), library_item_id=library_item_id)
        node = NodeItem(data)
        node.signals.moved.connect(self._on_node_moved)
        self.addItem(node)
        self._nodes_by_id[node_id] = node

        self._project_canvas.setdefault("nodes", []).append(
            {"id": node_id, "type": str(node_type), "name": str(name), "x": float(x), "y": float(y), "library_item_id": library_item_id}
        )
        self.signals.project_changed.emit(self._project_canvas)
        return node_id

    def add_edge(self, from_node_id: str, to_node_id: str, kind: str = "duct") -> Optional[str]:
        if from_node_id not in self._nodes_by_id or to_node_id not in self._nodes_by_id:
            return None
        edge_id = self._next_edge_id()
        edge = EdgeItem(edge_id=edge_id, from_node=self._nodes_by_id[from_node_id], to_node=self._nodes_by_id[to_node_id], containment_kind=str(kind), mode="manual", runs=[])
        edge.signals.double_clicked.connect(self._on_edge_double_clicked)
        self.addItem(edge)
        self._edges_by_id[edge_id] = edge

        self._project_canvas.setdefault("edges", []).append(
            {
                "id": edge_id,
                "from": from_node_id,
                "to": to_node_id,
                "from_node": from_node_id,
                "to_node": to_node_id,
                "kind": str(kind),
                "mode": "manual",
                "runs": [],
                "props": {},
            }
        )
        self._refresh_edges()
        self.signals.project_changed.emit(self._project_canvas)
        return edge_id

    def set_edge_kind(self, edge_id: str, kind: str, emit: bool = True) -> None:
        edge = self._edges_by_id.get(edge_id)
        if not edge:
            return
        edge.update_meta(containment_kind=str(kind))
        for e in self._project_canvas.get("edges", []) or []:
            if str(e.get("id")) == str(edge_id):
                e["kind"] = str(kind)
                break
        if emit:
            self.signals.project_changed.emit(self._project_canvas)

    def set_edge_props(self, edge_id: str, props: dict, emit: bool = True) -> None:
        edge = self._edges_by_id.get(edge_id)
        if not edge:
            return
        edge.props = dict(props or {})
        edge.set_status(edge.status)
        for e in self._project_canvas.get("edges", []) or []:
            if str(e.get("id")) == str(edge_id):
                e["props"] = dict(props or {})
                break
        if emit:
            self.signals.project_changed.emit(self._project_canvas)

    def set_edge_mode(self, edge_id: str, mode: str, emit: bool = True) -> None:
        edge = self._edges_by_id.get(edge_id)
        if not edge:
            return
        edge.update_meta(mode=str(mode))
        for e in self._project_canvas.get("edges", []) or []:
            if str(e.get("id")) == str(edge_id):
                e["mode"] = str(mode)
                break
        if emit:
            self.signals.project_changed.emit(self._project_canvas)

    def set_edge_runs(self, edge_id: str, runs: list, emit: bool = True) -> None:
        edge = self._edges_by_id.get(edge_id)
        if not edge:
            return
        edge.update_meta(runs=list(runs or []))
        for e in self._project_canvas.get("edges", []) or []:
            if str(e.get("id")) == str(edge_id):
                e["runs"] = list(runs or [])
                break
        if emit:
            self.signals.project_changed.emit(self._project_canvas)

    def set_edge_status(self, edge_id: str, status: str, badge_text: str = "") -> None:
        edge = self._edges_by_id.get(edge_id)
        if not edge:
            return
        edge.set_status(status, badge_text)

    def delete_selected(self) -> None:
        for item in list(self.selectedItems()):
            if isinstance(item, NodeItem):
                nid = item.node_id
                # remove connected edges
                to_remove = [str(e.get("id")) for e in (self._project_canvas.get("edges", []) or []) if e.get("from") == nid or e.get("to") == nid]
                for eid in to_remove:
                    self._remove_edge(eid)
                self._remove_node(nid, release_library_item=True)
            elif isinstance(item, EdgeItem):
                self._remove_edge(item.edge_id)

        self._refresh_edges()
        self.signals.project_changed.emit(self._project_canvas)

    # -------------------- DnD support --------------------
    def handle_drop(self, scene_pos, payload: Dict) -> bool:
        kind = str(payload.get("kind", ""))
        if kind == "equipment_item":
            equip_id = str(payload.get("id", ""))
            if not equip_id:
                return False
            meta = self._equipment_items_by_id.get(equip_id, {})
            name = str(meta.get("name", equip_id))
            self.add_node("equipment", name, float(scene_pos.x()), float(scene_pos.y()), library_item_id=equip_id)
            return True

        if kind == "equipment":
            equip_type = str(payload.get("type", "") or payload.get("id", ""))
            normalized = equip_type.strip().lower()
            is_cabinet = normalized in ("cabinet", "armario", "tablero")
            meta = {} if is_cabinet else self._equipment_items_by_id.get(equip_type, {})
            name = str(payload.get("label") or meta.get("name") or equip_type or "Equipo")
            library_id = str(payload.get("library_id") or "") or None
            self.add_node(
                "cabinet" if is_cabinet else "equipment",
                name,
                float(scene_pos.x()),
                float(scene_pos.y()),
                library_item_id=(library_id or (None if is_cabinet else (equip_type or None))),
            )
            if library_id:
                self.signals.library_item_used.emit(library_id)
            return True

        if kind == "camera":
            name = str(payload.get("label") or "C?mara")
            self.add_node("chamber", name, float(scene_pos.x()), float(scene_pos.y()))
            return True

        if kind == "gap":
            name = str(payload.get("label") or "GAP")
            self.add_node("junction", name, float(scene_pos.x()), float(scene_pos.y()))
            return True
        return False

    # -------------------- Events --------------------
    def mousePressEvent(self, event):
        pos = event.scenePos()
        if self._connect_mode:
            view = self.views()[0] if self.views() else None
            item = self.itemAt(pos, view.transform()) if view else None
            if isinstance(item, NodeItem):
                if self._pending_from_node_id is None:
                    self._pending_from_node_id = item.node_id
                else:
                    self.add_edge(self._pending_from_node_id, item.node_id, kind="duct")
                    self._pending_from_node_id = None
            else:
                self._pending_from_node_id = None
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self._auto_snap_selected_edges():
            self._refresh_edges()
            self.signals.project_changed.emit(self._project_canvas)
        if self._background_item is None:
            return
        if self._project_canvas.get("background", {}).get("locked", True):
            return
        pos = self._background_item.pos()
        self._project_canvas.setdefault("background", {})
        self._project_canvas["background"]["pos"] = [float(pos.x()), float(pos.y())]
        self._project_canvas["background"]["scale"] = float(self._background_item.scale() or 1.0)
        self.signals.project_changed.emit(self._project_canvas)

    # -------------------- Internals --------------------
    def _next_node_id(self) -> str:
        existing = set(self._nodes_by_id.keys())
        i = 1
        while True:
            nid = f"N{i}"
            if nid not in existing:
                return nid
            i += 1

    def _next_edge_id(self) -> str:
        existing = set(self._edges_by_id.keys())
        i = 1
        while True:
            eid = f"E{i}"
            if eid not in existing:
                return eid
            i += 1

    def _on_node_moved(self, node_id: str, x: float, y: float) -> None:
        # Update persisted dict and edge geometry
        for n in self._project_canvas.get("nodes", []) or []:
            if str(n.get("id")) == str(node_id):
                n["x"] = float(x)
                n["y"] = float(y)
                break
        self._refresh_edges()
        self.signals.project_changed.emit(self._project_canvas)

    def _remove_node(self, node_id: str, release_library_item: bool = False) -> None:
        node = self._nodes_by_id.pop(node_id, None)
        if node:
            library_item_id = node.data.library_item_id
            self.removeItem(node)
        self._project_canvas["nodes"] = [n for n in (self._project_canvas.get("nodes", []) or []) if str(n.get("id")) != str(node_id)]
        if release_library_item and node and library_item_id:
            remaining = any(str(n.get("library_item_id")) == str(library_item_id) for n in (self._project_canvas.get("nodes", []) or []))
            if not remaining:
                self.signals.library_item_released.emit(str(library_item_id))

    def _remove_edge(self, edge_id: str) -> None:
        edge = self._edges_by_id.pop(edge_id, None)
        if edge:
            self.removeItem(edge)
        self._project_canvas["edges"] = [e for e in (self._project_canvas.get("edges", []) or []) if str(e.get("id")) != str(edge_id)]
        self.signals.segment_removed.emit(str(edge_id))

    def _refresh_edges(self) -> None:
        for edge in self._edges_by_id.values():
            edge.update_geometry()
            self._sync_edge_model_endpoints(edge)

    def _sync_edge_model_endpoints(self, edge: EdgeItem) -> None:
        for e in self._project_canvas.get("edges", []) or []:
            if str(e.get("id")) == str(edge.edge_id):
                from_id = str(edge.from_node.node_id)
                to_id = str(edge.to_node.node_id)
                e["from"] = from_id
                e["to"] = to_id
                e["from_node"] = from_id
                e["to_node"] = to_id
                break

    def _auto_snap_selected_edges(self) -> bool:
        changed = False
        selected = [it for it in self.selectedItems() if isinstance(it, EdgeItem)]
        if not selected:
            return False
        nodes = list(self._nodes_by_id.values())
        for edge in selected:
            if self._snap_edge_endpoint(edge, nodes, is_start=True):
                changed = True
            if self._snap_edge_endpoint(edge, nodes, is_start=False):
                changed = True
        return changed

    def _snap_edge_endpoint(self, edge: EdgeItem, nodes: list, is_start: bool) -> bool:
        line = edge.line()
        point = line.p1() if is_start else line.p2()
        closest = self._nearest_node(point.x(), point.y(), nodes, self.SNAP_THRESHOLD_PX)
        if closest is None:
            return False
        if is_start and closest.node_id != edge.from_node.node_id:
            edge.from_node = closest
        elif (not is_start) and closest.node_id != edge.to_node.node_id:
            edge.to_node = closest
        else:
            return False
        self._sync_edge_model_endpoints(edge)
        edge.update_geometry()
        return True

    def _nearest_node(self, x: float, y: float, nodes: list, max_dist: float) -> Optional[NodeItem]:
        best = None
        best_dist = float(max_dist)
        for node in nodes:
            pos = node.scenePos()
            dist = math.hypot(float(pos.x()) - x, float(pos.y()) - y)
            if dist <= best_dist:
                best = node
                best_dist = dist
        return best

    def _emit_selection_snapshot(self) -> None:
        # Update edge style on selection changes
        for e in self._edges_by_id.values():
            try:
                e._apply_style()
            except Exception:
                pass

        sel = self.selectedItems()
        payload: Dict = {"kind": None}
        if len(sel) == 1:
            it = sel[0]
            if isinstance(it, NodeItem):
                payload = {"kind": "node", "id": it.node_id, "type": it.node_type, "name": it.name}
            elif isinstance(it, EdgeItem):
                payload = {
                    "kind": "edge",
                    "id": it.edge_id,
                    "from": it.from_node.node_id,
                    "to": it.to_node.node_id,
                    "type": it.containment_kind,
                    "mode": it.mode,
                    "runs": it.runs,
                }
        self.signals.selection_changed.emit(payload)

    def _on_edge_double_clicked(self, edge_item) -> None:
        self.signals.segment_double_clicked.emit(edge_item)

    # -------------------- Export --------------------
    def export_to_png(self, path: str, with_background: bool = True) -> None:
        """Render the current scene to a PNG image.

        Notes:
        - Uses sceneRect() as export bounds.
        - If with_background is False, the background pixmap is temporarily hidden.
        """
        rect = self.sceneRect().toAlignedRect()
        if rect.width() <= 0 or rect.height() <= 0:
            rect = self.itemsBoundingRect().toAlignedRect()
        if rect.width() <= 0 or rect.height() <= 0:
            raise ValueError("La escena está vacía")

        img = QImage(rect.size(), QImage.Format_ARGB32)
        img.fill(0x00000000)

        bg = self._background_item
        prev_vis = None
        if bg is not None and not with_background:
            prev_vis = bg.isVisible()
            bg.setVisible(False)
        try:
            p = QPainter(img)
            p.setRenderHint(QPainter.Antialiasing, True)
            p.setRenderHint(QPainter.TextAntialiasing, True)
            self.render(p, target=QRectF(img.rect()), source=QRectF(rect))
            p.end()
        finally:
            if bg is not None and prev_vis is not None:
                bg.setVisible(prev_vis)

        if not img.save(path, "PNG"):
            raise IOError(f"No se pudo guardar PNG en: {path}")

    def export_to_pdf(self, path: str, with_background: bool = True) -> None:
        """Render the current scene into a single-page PDF."""
        rect = self.sceneRect()
        if rect.width() <= 0 or rect.height() <= 0:
            rect = self.itemsBoundingRect()
        if rect.width() <= 0 or rect.height() <= 0:
            raise ValueError("La escena está vacía")

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(path)
        printer.setFullPage(True)

        # Page size (points) proportional to scene size
        # We keep it simple: scale-to-fit by mapping scene rect to page rect.
        p = QPainter(printer)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)

        bg = self._background_item
        prev_vis = None
        if bg is not None and not with_background:
            prev_vis = bg.isVisible()
            bg.setVisible(False)
        try:
            page = printer.pageRect()  # QRect
            self.render(p, target=QRectF(page), source=rect)
        finally:
            if bg is not None and prev_vis is not None:
                bg.setVisible(prev_vis)
            p.end()

        # Keep edge selection style in sync (EdgeItem styles are pen-based)
        for e in self._edges_by_id.values():
            try:
                e._apply_style()  # noqa: SLF001 - internal helper for immediate UI feedback
            except Exception:
                pass
