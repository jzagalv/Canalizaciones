# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from data.repositories.lib_merge import EffectiveCatalog
from domain.entities.models import Project


def _cable_area_mm2(outer_diameter_mm: float) -> float:
    r = float(outer_diameter_mm) / 2.0
    return math.pi * r * r


def compute_project_solutions(project: Project, eff: EffectiveCatalog) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    """Compute per-edge solutions.

    Returns:
        solutions: edge_id -> dict with keys {proposal, fill, status, notes, badge}
        warnings: list of warning strings
    """
    warnings: List[str] = []
    canvas = project.canvas or {'nodes': [], 'edges': []}
    edges = list(canvas.get('edges') or [])
    nodes = list(canvas.get('nodes') or [])

    # Build graph adjacency: node_id -> list[(to_node, edge_id, weight_m)]
    adj: Dict[str, List[Tuple[str, str, float]]] = {}
    edge_by_id: Dict[str, Dict[str, Any]] = {str(e.get('id')): e for e in edges}

    def edge_weight(e: Dict[str, Any]) -> float:
        # if length_m provided use it, else approximate using stored node coordinates
        if e.get('length_m') is not None:
            try:
                return float(e.get('length_m'))
            except Exception:
                pass
        a = next((n for n in nodes if n.get('id') == e.get('from_node')), None)
        b = next((n for n in nodes if n.get('id') == e.get('to_node')), None)
        if not (a and b):
            return 1.0
        dx = float(a.get('x', 0)) - float(b.get('x', 0))
        dy = float(a.get('y', 0)) - float(b.get('y', 0))
        # px -> m rough scale
        return math.hypot(dx, dy) * 0.05

    for e in edges:
        eid = str(e.get('id'))
        a = str(e.get('from_node'))
        b = str(e.get('to_node'))
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
    conductors = eff.material.get('conductors_by_id', {})

    circuits = list((project.circuits or {}).get('items') or [])
    for c in circuits:
        from_node = str(c.get('from_node') or '')
        to_node = str(c.get('to_node') or '')
        if not from_node or not to_node:
            continue
        path = shortest_path_edges(from_node, to_node)
        if not path:
            if path is None:
                warnings.append(f"Circuito '{c.get('name','')}' sin ruta entre {from_node}->{to_node}")
            continue

        cref = str(c.get('cable_ref') or '')
        conductor = conductors.get(cref)
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

        for eid in path:
            svc_map = per_edge_services.setdefault(eid, {})
            svc_map[service] = svc_map.get(service, 0.0) + area * qty

    # Proposal per edge
    rules = eff.material.get('rules', {})
    defaults = rules.get('defaults', {})

    ducts = list(eff.material.get('ducts_by_id', {}).values())
    epc = list(eff.material.get('epc_by_id', {}).values())

    # sort catalogs by usable area
    def duct_area(duct_item: Dict[str, Any]) -> float:
        # compute from ID if usable_area_mm2 not given
        ua = duct_item.get('usable_area_mm2')
        if ua:
            return float(ua)
        d = duct_item.get('inner_diameter_mm')
        if not d:
            return 0.0
        r = float(d) / 2.0
        return math.pi * r * r

    def rect_area(item: Dict[str, Any]) -> float:
        ua = item.get('usable_area_mm2')
        if ua:
            return float(ua)
        w = float(item.get('inner_width_mm') or 0.0)
        h = float(item.get('inner_height_mm') or 0.0)
        return w * h

    ducts_sorted = sorted(ducts, key=duct_area)
    epc_sorted = sorted(epc, key=rect_area)

    solutions: Dict[str, Dict[str, Any]] = {}

    # simple separation: do not mix services if both present and rule says separate
    def must_separate(svc_a: str, svc_b: str) -> bool:
        for rule in (rules.get('separation') or []):
            s = set(rule.get('if_services') or [])
            if svc_a in s and svc_b in s:
                return str(rule.get('requires')) == 'separate_containment'
        return False

    for e in edges:
        eid = str(e.get('id'))
        kind = str(e.get('containment_kind') or 'duct')
        svc_areas = per_edge_services.get(eid, {})
        if not svc_areas:
            solutions[eid] = {
                'proposal': '(sin circuitos)',
                'fill': '0%',
                'status': 'none',
                'notes': '',
                'badge': '',
            }
            continue

        # group services (separation)
        groups: List[List[str]] = []
        for svc in svc_areas.keys():
            placed = False
            for g in groups:
                if any(must_separate(svc, s2) for s2 in g):
                    continue
                g.append(svc)
                placed = True
                break
            if not placed:
                groups.append([svc])

        group_summaries: List[str] = []
        overall_status = 'ok'
        badge_parts: List[str] = []
        notes: List[str] = []
        fill_texts: List[str] = []

        for g in groups:
            area_sum = sum(svc_areas[s] for s in g)
            # max fill percent: use min over involved services, fallback 40
            max_fill = min([
                float((defaults.get(s) or {}).get('max_fill_percent', 40))
                for s in g
            ] or [40.0])

            if kind == 'epc':
                catalog = epc_sorted
                cap_area_fn = rect_area
                label_prefix = 'EPC'
            else:
                catalog = ducts_sorted
                cap_area_fn = duct_area
                label_prefix = 'D'

            if not catalog:
                overall_status = 'error'
                notes.append('No hay catalogo para este tipo de canalizacion en bibliotecas.')
                continue

            chosen = None
            n_parallel = 1
            for item in catalog:
                cap = cap_area_fn(item) * (max_fill / 100.0)
                if cap <= 0:
                    continue
                if area_sum <= cap:
                    chosen = item
                    n_parallel = 1
                    break
                # try multiple parallel
                n_need = int(math.ceil(area_sum / cap))
                if n_need <= 6:  # hard limit for UI sanity
                    chosen = item
                    n_parallel = n_need
                    break

            if not chosen:
                overall_status = 'error'
                notes.append(f"No cabe ni con el maximo probado (servicios {g}).")
                continue

            cap = cap_area_fn(chosen) * (max_fill / 100.0) * n_parallel
            fill = 0.0 if cap <= 0 else (area_sum / cap) * 100.0

            if fill > 100.0 + 1e-6:
                st = 'error'
                overall_status = 'error'
            elif fill > 85.0:
                st = 'warn'
                if overall_status != 'error':
                    overall_status = 'warn'
            else:
                st = 'ok'

            label = chosen.get('name') or chosen.get('id')
            group_summaries.append(f"{n_parallel}x {label_prefix} {label} ({'/'.join(g)})")
            fill_texts.append(f"{fill:.0f}%")
            badge_parts.append(f"{n_parallel}x")

        proposal = ' + '.join(group_summaries)
        fill_str = ' / '.join(fill_texts) if fill_texts else ''
        badge = proposal if len(proposal) <= 20 else (fill_str or overall_status)

        solutions[eid] = {
            'proposal': proposal,
            'fill': fill_str,
            'status': overall_status,
            'notes': ' | '.join(notes),
            'badge': badge,
        }

    return solutions, warnings
