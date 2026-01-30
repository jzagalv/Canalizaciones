# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set, Tuple

from domain.entities.models import Project


def ensure_troncales(project: Project) -> List[Dict[str, object]]:
    troncales = getattr(project, "troncales", None)
    if not isinstance(troncales, list):
        project.troncales = []
    return project.troncales


def next_troncal_id(project: Project) -> str:
    troncales = ensure_troncales(project)
    existing = {str(t.get("id") or "") for t in troncales}
    idx = 1
    while True:
        candidate = f"TR-{idx:03d}"
        if candidate not in existing:
            return candidate
        idx += 1


def get_edge_by_id(project: Project, edge_id: str) -> Optional[Dict[str, object]]:
    edges = list((project.canvas or {}).get("edges") or [])
    for e in edges:
        if str(e.get("id") or "") == str(edge_id):
            return e
    return None


def get_connected_edge_ids(project: Project, start_edge_id: str) -> List[str]:
    edges = list((project.canvas or {}).get("edges") or [])
    nodes = list((project.canvas or {}).get("nodes") or [])
    node_by_id = {str(n.get("id") or ""): n for n in nodes if n.get("id")}
    edge_by_id = {str(e.get("id") or ""): e for e in edges if e.get("id")}
    start_id = str(start_edge_id or "")
    if start_id not in edge_by_id:
        return []

    node_to_edges: Dict[str, List[str]] = {}
    for e in edges:
        eid = str(e.get("id") or "")
        a = str(e.get("from_node") or e.get("from") or "")
        b = str(e.get("to_node") or e.get("to") or "")
        if a:
            node_to_edges.setdefault(a, []).append(eid)
        if b:
            node_to_edges.setdefault(b, []).append(eid)

    def is_cut_node(node: Dict[str, object]) -> bool:
        if not node:
            return False
        node_type = str(node.get("type") or "")
        if node_type == "equipment":
            return True
        if node_type == "chamber":
            return True
        if node_type == "junction":
            name = str(node.get("name") or "").strip().upper()
            if name == "GAP":
                return True
        props = node.get("props") if isinstance(node.get("props"), dict) else {}
        return bool(props.get("is_cut_node"))

    base = edge_by_id.get(start_id) or {}
    a = str(base.get("from_node") or base.get("from") or "")
    b = str(base.get("to_node") or base.get("to") or "")
    visited_edges: Set[str] = {start_id}
    visited_nodes: Set[str] = set()
    frontier: List[str] = []
    if a and a in node_by_id and not is_cut_node(node_by_id[a]):
        frontier.append(a)
    if b and b in node_by_id and not is_cut_node(node_by_id[b]):
        frontier.append(b)

    while frontier:
        n = frontier.pop(0)
        if n in visited_nodes:
            continue
        visited_nodes.add(n)
        for eid in node_to_edges.get(n, []):
            if eid in visited_edges:
                continue
            visited_edges.add(eid)
            edge = edge_by_id.get(eid) or {}
            na = str(edge.get("from_node") or edge.get("from") or "")
            nb = str(edge.get("to_node") or edge.get("to") or "")
            other = nb if na == n else na
            if other and other in node_by_id and not is_cut_node(node_by_id[other]):
                frontier.append(other)

    return list(visited_edges)


def assign_troncal_to_edges(project: Project, edge_ids: Iterable[str], troncal_id: str) -> None:
    for eid in edge_ids:
        edge = get_edge_by_id(project, str(eid) or "")
        if not edge:
            continue
        props = edge.get("props") if isinstance(edge.get("props"), dict) else {}
        props["troncal_id"] = str(troncal_id or "")
        edge["props"] = props


def add_connected_to_troncal(
    project: Project,
    start_edge_id: str,
    troncal_id: str,
) -> Tuple[List[str], List[str]]:
    connected = get_connected_edge_ids(project, start_edge_id)
    target = str(troncal_id or "")
    assignable: List[str] = []
    conflicts: List[str] = []
    for eid in connected:
        edge = get_edge_by_id(project, eid)
        if not edge:
            continue
        props = edge.get("props") if isinstance(edge.get("props"), dict) else {}
        cur = str(props.get("troncal_id") or "")
        if not cur:
            assignable.append(eid)
        elif cur != target:
            conflicts.append(eid)
    return assignable, conflicts


def remove_troncal_from_edges(project: Project, edge_ids: Iterable[str]) -> None:
    for eid in edge_ids:
        edge = get_edge_by_id(project, str(eid) or "")
        if not edge:
            continue
        props = edge.get("props") if isinstance(edge.get("props"), dict) else {}
        props["troncal_id"] = None
        edge["props"] = props
