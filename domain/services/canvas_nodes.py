# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from domain.entities.models import Project


@dataclass(frozen=True)
class NodeOption:
    node_id: str
    display_text: str
    sort_key: str


def _short_id(node_id: str) -> str:
    node_id = str(node_id or "")
    return node_id[:6] if len(node_id) > 6 else node_id


def _display_text_for_node(node: dict) -> str:
    raw = node.get("tag") or node.get("name") or node.get("label") or node.get("text")
    if raw is not None:
        text = str(raw).strip()
        if text:
            return text
    node_type = str(node.get("type") or node.get("kind") or "node")
    return f"(sin tag) {node_type} {_short_id(node.get('id'))}".strip()


def list_canvas_nodes_for_circuits(project_model: Project) -> List[NodeOption]:
    canvas = project_model.canvas or {}
    nodes = list(canvas.get("nodes") or [])

    # TODO: filter out non-connectable or internal nodes by type once metadata exists.
    options: List[NodeOption] = []
    for node in nodes:
        node_id = str(node.get("id") or "").strip()
        if not node_id:
            continue
        display = _display_text_for_node(node)
        sort_key = display.lower()
        options.append(NodeOption(node_id=node_id, display_text=display, sort_key=sort_key))

    options.sort(key=lambda o: o.sort_key)
    return options
