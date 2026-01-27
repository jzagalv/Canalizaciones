# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from data.repositories.lib_merge import EffectiveCatalog
from domain.calculations.formatting import round2, util_color
from domain.calculations.occupancy import (
    DEFAULT_DUCT_MAX_FILL_PERCENT,
    DEFAULT_TRAY_MAX_FILL_PERCENT,
    calc_duct_fill,
    calc_tray_fill,
    get_material_max_fill_percent,
)
from domain.entities.models import Project


def _cable_area_mm2(outer_diameter_mm: float) -> float:
    r = float(outer_diameter_mm) / 2.0
    return math.pi * r * r


def resolve_node_id(ref: str, node_by_id: Dict[str, Dict[str, Any]]) -> Optional[str]:
    ref_raw = str(ref or "")
    if not ref_raw:
        return None
    if ref_raw in node_by_id:
        return ref_raw
    ref_norm = ref_raw.strip().casefold()
    exact_id = None
    for nid, node in node_by_id.items():
        name = str(node.get("name") or "")
        tag = str(node.get("tag") or "")
        label = str(node.get("label") or "")
        if ref_raw in (name, tag, label):
            return nid
        if exact_id is None:
            if ref_norm and ref_norm in (name.strip().casefold(), tag.strip().casefold(), label.strip().casefold()):
                exact_id = nid
    return exact_id


def compute_project_solutions(
    project: Project,
    eff: EffectiveCatalog,
) -> Tuple[
    Dict[str, List[str]],
    Dict[str, List[str]],
    Dict[str, List[Dict[str, Any]]],
    Dict[str, Dict[str, Any]],
]:
    """Compute manual-only routes and fill results.

    Returns:
        routes: circuito_id -> list[edge_id]
        edge_to_circuits: edge_id -> list[circuit_id]
        canalizacion_assignments: edge_id -> list of canalizacion entries with cables/areas
        fill_results: edge_id -> dict with fill_percent, fill_max_percent, fill_over, fill_state, status
    """
    canvas = project.canvas or {'nodes': [], 'edges': []}
    edges = list(canvas.get('edges') or [])
    nodes = list(canvas.get('nodes') or [])

    # Build graph adjacency: node_id -> list[(to_node, edge_id, weight_m)]
    adj: Dict[str, List[Tuple[str, str, float]]] = {}
    edge_by_id: Dict[str, Dict[str, Any]] = {str(e.get('id')): e for e in edges}
    node_by_id: Dict[str, Dict[str, Any]] = {str(n.get('id')): n for n in nodes}

    def edge_endpoints(edge: Dict[str, Any]) -> Tuple[str, str]:
        from_id = str(edge.get('from_node') or edge.get('from') or '')
        to_id = str(edge.get('to_node') or edge.get('to') or '')
        return from_id, to_id

    def edge_weight(e: Dict[str, Any]) -> float:
        # if length_m provided use it, else approximate using stored node coordinates
        if e.get('length_m') is not None:
            try:
                return float(e.get('length_m'))
            except Exception:
                pass
        from_id, to_id = edge_endpoints(e)
        a = node_by_id.get(from_id)
        b = node_by_id.get(to_id)
        if not (a and b):
            return 1.0
        dx = float(a.get('x', 0)) - float(b.get('x', 0))
        dy = float(a.get('y', 0)) - float(b.get('y', 0))
        # px -> m rough scale
        return math.hypot(dx, dy) * 0.05

    for e in edges:
        eid = str(e.get('id'))
        a, b = edge_endpoints(e)
        if not a or not b:
            continue
        if a not in node_by_id or b not in node_by_id:
            continue
        w = edge_weight(e)
        adj.setdefault(a, []).append((b, eid, w))
        adj.setdefault(b, []).append((a, eid, w))

    # Helper: Dijkstra shortest path returning list of edge_ids
    def shortest_path_edges(start: str, goal: str) -> Optional[List[str]]:
        if start == goal:
            return []
        if start not in adj or goal not in adj:
            return None
        import heapq

        pq: List[Tuple[float, str]] = [(0.0, start)]
        dist: Dict[str, float] = {start: 0.0}
        prev: Dict[str, Tuple[str, str]] = {}  # node -> (prev_node, edge_id)
        visited = set()

        while pq:
            d, u = heapq.heappop(pq)
            if u in visited:
                continue
            visited.add(u)
            if u == goal:
                break
            for v, eid, w in adj.get(u, []):
                nd = d + w
                if nd < dist.get(v, 1e18):
                    dist[v] = nd
                    prev[v] = (u, eid)
                    heapq.heappush(pq, (nd, v))

        if goal not in prev and goal != start:
            return None

        # reconstruct
        path_edges: List[str] = []
        cur = goal
        while cur != start:
            u, eid = prev[cur]
            path_edges.append(eid)
            cur = u
        path_edges.reverse()
        return path_edges

    # Accumulate per-edge cable areas by service
    per_edge_services: Dict[str, Dict[str, float]] = {str(e.get('id')): {} for e in edges}
    warnings: List[str] = []
    conductors = eff.material.get('conductors_by_uid', {})
    conductors_by_code = eff.material.get('conductors_by_code', {})
    routes: Dict[str, List[str]] = {}
    edge_to_circuits: Dict[str, List[str]] = {str(e.get('id')): [] for e in edges if e.get('id')}
    circuit_area_map: Dict[str, Dict[str, Any]] = {}

    circuits = list((project.circuits or {}).get('items') or [])
    for c in circuits:
        from_ref = str(c.get("from_node") or "")
        to_ref = str(c.get("to_node") or "")
        if not from_ref or not to_ref:
            continue
        from_node = resolve_node_id(from_ref, node_by_id)
        to_node = resolve_node_id(to_ref, node_by_id)
        if not from_node or not to_node:
            continue
        path = shortest_path_edges(from_node, to_node)
        if not path:
            continue
        cid = str(c.get("id") or "")
        if cid:
            routes[cid] = list(path)
            for eid in path:
                edge_to_circuits.setdefault(eid, []).append(cid)

        cref = str(c.get('cable_ref') or '')
        snap = c.get("cable_snapshot") if isinstance(c.get("cable_snapshot"), dict) else None
        od = None
        if snap:
            od = snap.get("outer_diameter_mm")
        if od is None:
            conductor = conductors.get(cref)
            if not conductor and cref:
                conductor = conductors_by_code.get(str(cref).strip().lower())
            if not conductor:
                warnings.append(f"CableRef '{cref}' no existe en bibliotecas (circuito '{c.get('name','')}')")
                continue
            od = conductor.get('outer_diameter_mm')
            if od is None:
                warnings.append(f"CableRef '{cref}' sin outer_diameter_mm")
                continue
        area = _cable_area_mm2(float(od))
        qty = int(c.get('qty', 1) or 1)
        service = str(c.get('service') or 'power')

        if cid:
            circuit_area_map[cid] = {
                "area_cable_mm2": area,
                "qty": qty,
                "cable_ref": cref,
                "circuit_name": str(c.get("name") or ""),
            }

        for eid in path:
            svc_map = per_edge_services.setdefault(eid, {})
            svc_map[service] = svc_map.get(service, 0.0) + area * qty

    canalizacion_assignments: Dict[str, List[Dict[str, Any]]] = {}
    for e in edges:
        eid = str(e.get("id") or "")
        if not eid:
            continue
        props = e.get("props") if isinstance(e.get("props"), dict) else {}
        qty = int(props.get("quantity") or 1)
        qty = max(1, qty)
        buckets: List[Dict[str, Any]] = [{"index": i, "cables": []} for i in range(qty)]
        circuit_ids = list(edge_to_circuits.get(eid, []) or [])
        for idx, cid in enumerate(circuit_ids):
            cable_info = circuit_area_map.get(str(cid) or "")
            if not cable_info:
                continue
            bucket = buckets[idx % qty]
            bucket["cables"].append({
                "circuit_id": str(cid),
                "circuit_name": cable_info.get("circuit_name", ""),
                "cable_ref": cable_info.get("cable_ref", ""),
                "area_cable_mm2": cable_info.get("area_cable_mm2", 0.0),
                "qty": cable_info.get("qty", 1),
            })
        canalizacion_assignments[eid] = buckets

    fill_results = _build_edge_fill_results(edges, per_edge_services, eff)

    return routes, edge_to_circuits, canalizacion_assignments, fill_results


def _build_edge_fill_results(
    edges: List[Dict[str, Any]],
    per_edge_services: Dict[str, Dict[str, float]],
    eff: EffectiveCatalog,
) -> Dict[str, Dict[str, Any]]:
    fill_results: Dict[str, Dict[str, Any]] = {}
    ducts = eff.material.get("ducts_by_uid") or {}
    ducts_by_code = eff.material.get("ducts_by_code") or {}
    epc = eff.material.get("epc_by_uid") or {}
    epc_by_code = eff.material.get("epc_by_code") or {}
    bpc = eff.material.get("bpc_by_uid") or {}
    bpc_by_code = eff.material.get("bpc_by_code") or {}

    def find_duct_material(duct_ref: str, size_label: str) -> Dict[str, Any]:
        if duct_ref and duct_ref in ducts:
            return dict(ducts.get(duct_ref) or {})
        if duct_ref:
            by_code = ducts_by_code.get(str(duct_ref).strip().lower())
            if by_code:
                return dict(by_code)
        size_norm = str(size_label or "").strip().casefold()
        if not size_norm:
            return {}
        for item in ducts.values():
            name = str(item.get("name") or "")
            nominal = str(item.get("nominal") or "")
            code = str(item.get("code") or "")
            if size_norm in (name.strip().casefold(), nominal.strip().casefold(), code.strip().casefold()):
                return dict(item)
        return {}

    def find_rect_material(kind: str, size_label: str) -> Dict[str, Any]:
        kind_norm = str(kind or "").strip().lower()
        items = epc if kind_norm == "epc" else bpc
        items_by_code = epc_by_code if kind_norm == "epc" else bpc_by_code
        size_norm = str(size_label or "").strip().casefold()
        if not size_norm:
            return {}
        for item in items.values():
            name = str(item.get("name") or "")
            nominal = str(item.get("nominal") or "")
            code = str(item.get("code") or "")
            if size_norm in (name.strip().casefold(), nominal.strip().casefold(), code.strip().casefold()):
                return dict(item)
        by_code = items_by_code.get(str(size_label or "").strip().lower())
        if by_code:
            return dict(by_code)
        return {}

    def scaled_material(material: Dict[str, Any], qty: int, is_duct: bool) -> Dict[str, Any]:
        if qty <= 1:
            return dict(material)
        mat = dict(material)
        if is_duct:
            inner = float(mat.get("inner_diameter_mm") or 0.0)
            usable = float(mat.get("usable_area_mm2") or 0.0)
            if usable <= 0 and inner > 0:
                usable = math.pi * (inner / 2.0) ** 2
        else:
            usable = float(mat.get("usable_area_mm2") or 0.0)
            if usable <= 0:
                w = float(mat.get("inner_width_mm") or 0.0)
                h = float(mat.get("inner_height_mm") or 0.0)
                usable = max(0.0, w * h)
        if usable > 0:
            mat["usable_area_mm2"] = usable * max(1, qty)
        return mat

    for e in edges:
        eid = str(e.get("id") or "")
        props = e.get("props") if isinstance(e.get("props"), dict) else {}
        conduit_type = str(props.get("conduit_type") or e.get("containment_kind") or "duct").strip()
        conduit_type_norm = conduit_type.lower()
        size = str(props.get("size") or "")
        duct_id = str(props.get("duct_uid") or props.get("duct_id") or "")
        snapshot = props.get("duct_snapshot") if isinstance(props.get("duct_snapshot"), dict) else None
        qty = int(props.get("quantity") or 1)
        svc_areas = per_edge_services.get(eid, {})
        total_area = sum(float(v) for v in (svc_areas or {}).values())

        if conduit_type_norm in ("ducto", "duct"):
            material = dict(snapshot) if snapshot else find_duct_material(duct_id, size)
            material = scaled_material(material, qty, is_duct=True)
            max_fill = get_material_max_fill_percent(material, DEFAULT_DUCT_MAX_FILL_PERCENT)
            fill_percent = calc_duct_fill(material, [{"area_mm2": total_area}]) if total_area > 0 else 0.0
        elif conduit_type_norm == "epc":
            material = find_rect_material("epc", size)
            material = scaled_material(material, qty, is_duct=False)
            max_fill = get_material_max_fill_percent(material, DEFAULT_TRAY_MAX_FILL_PERCENT)
            fill_percent = calc_tray_fill(material, [{"area_mm2": total_area}], has_separator=False) if total_area > 0 else 0.0
        else:
            material = find_rect_material("bpc", size)
            material = scaled_material(material, qty, is_duct=False)
            max_fill = get_material_max_fill_percent(material, DEFAULT_TRAY_MAX_FILL_PERCENT)
            fill_percent = calc_tray_fill(material, [{"area_mm2": total_area}], has_separator=False) if total_area > 0 else 0.0

        fill_over = bool(max_fill > 0 and fill_percent > max_fill + 1e-6)
        status = "No cumple" if fill_over else "OK"
        fill_results[eid] = {
            "fill_percent": round2(fill_percent),
            "fill_max_percent": round2(max_fill),
            "fill_over": fill_over,
            "fill_state": util_color(fill_percent, max_fill),
            "status": status,
        }

    return fill_results


def build_circuits_by_edge_index(project: Project) -> Dict[str, List[str]]:
    canvas = project.canvas or {"nodes": [], "edges": []}
    edges = list(canvas.get("edges") or [])
    nodes = list(canvas.get("nodes") or [])

    adj: Dict[str, List[Tuple[str, str, float]]] = {}
    node_by_id: Dict[str, Dict[str, Any]] = {str(n.get("id")): n for n in nodes if n.get("id")}

    def edge_endpoints(edge: Dict[str, Any]) -> Tuple[str, str]:
        from_id = str(edge.get("from_node") or edge.get("from") or "")
        to_id = str(edge.get("to_node") or edge.get("to") or "")
        return from_id, to_id

    def edge_weight(e: Dict[str, Any]) -> float:
        if e.get("length_m") is not None:
            try:
                return float(e.get("length_m"))
            except Exception:
                pass
        from_id, to_id = edge_endpoints(e)
        a = node_by_id.get(from_id)
        b = node_by_id.get(to_id)
        if not (a and b):
            return 1.0
        dx = float(a.get("x", 0)) - float(b.get("x", 0))
        dy = float(a.get("y", 0)) - float(b.get("y", 0))
        return math.hypot(dx, dy) * 0.05

    for e in edges:
        eid = str(e.get("id") or "")
        a, b = edge_endpoints(e)
        if not eid or not a or not b:
            continue
        w = edge_weight(e)
        adj.setdefault(a, []).append((b, eid, w))
        adj.setdefault(b, []).append((a, eid, w))

    def shortest_path_edges(start: str, goal: str) -> Optional[List[str]]:
        if start == goal:
            return []
        if start not in adj or goal not in adj:
            return None
        import heapq

        pq: List[Tuple[float, str]] = [(0.0, start)]
        dist: Dict[str, float] = {start: 0.0}
        prev: Dict[str, Tuple[str, str]] = {}
        visited = set()

        while pq:
            d, u = heapq.heappop(pq)
            if u in visited:
                continue
            visited.add(u)
            if u == goal:
                break
            for v, eid, w in adj.get(u, []):
                nd = d + w
                if nd < dist.get(v, 1e18):
                    dist[v] = nd
                    prev[v] = (u, eid)
                    heapq.heappush(pq, (nd, v))

        if goal not in prev and goal != start:
            return None

        path_edges: List[str] = []
        cur = goal
        while cur != start:
            u, eid = prev[cur]
            path_edges.append(eid)
            cur = u
        path_edges.reverse()
        return path_edges

    circuits_by_edge: Dict[str, List[str]] = {str(e.get("id") or ""): [] for e in edges if e.get("id")}
    circuits = list((project.circuits or {}).get("items") or [])
    for c in circuits:
        from_ref = str(c.get("from_node") or "")
        to_ref = str(c.get("to_node") or "")
        if not from_ref or not to_ref:
            continue
        from_node = resolve_node_id(from_ref, node_by_id)
        to_node = resolve_node_id(to_ref, node_by_id)
        if not from_node or not to_node:
            continue
        path = shortest_path_edges(from_node, to_node)
        if not path:
            continue
        label = str(c.get("name") or c.get("id") or "").strip()
        if not label:
            continue
        for eid in path:
            circuits_by_edge.setdefault(eid, []).append(label)

    return circuits_by_edge
