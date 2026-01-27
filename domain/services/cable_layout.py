# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from typing import Dict, Iterable, List, Tuple


def assign_circuits_to_conduits(
    circuits: List[Dict[str, object]],
    conduits: List[Dict[str, object]],
    max_fill_percent: float = 40.0,
    w_over: float = 10.0,
    w_mismatch: float = 30.0,
) -> Tuple[Dict[str, str], Dict[str, Dict[str, float]]]:
    """Assign circuits to conduits minimizing fill + penalties."""
    assignments: Dict[str, str] = {}
    conduit_stats: Dict[str, Dict[str, float]] = {}
    used_by_tag: Dict[str, float] = {}

    for c in conduits:
        tag = str(c.get("tag") or "")
        util = float(c.get("area_util_mm2") or 0.0)
        conduit_stats[tag] = {
            "used_mm2": 0.0,
            "util_mm2": util,
            "fill_pct": 0.0,
            "avail_pct": 100.0,
        }
        used_by_tag[tag] = 0.0

    def _service_pref(conduit: Dict[str, object]) -> str:
        return str(conduit.get("service_pref") or "").strip()

    circuits_sorted = sorted(
        circuits or [],
        key=lambda c: float(c.get("area_mm2") or 0.0),
        reverse=True,
    )

    for circuit in circuits_sorted:
        area_i = float(circuit.get("area_mm2") or 0.0)
        service = str(circuit.get("service") or "").strip()
        tag = str(circuit.get("tag") or "")

        pref = []
        free = []
        rest = []
        for conduit in conduits:
            pref_value = _service_pref(conduit)
            if pref_value and pref_value != "Libre" and pref_value == service:
                pref.append(conduit)
            elif not pref_value or pref_value == "Libre":
                free.append(conduit)
            else:
                rest.append(conduit)
        candidates = pref + free + rest
        if not candidates:
            continue

        best = None
        best_score = None
        for conduit in candidates:
            ctag = str(conduit.get("tag") or "")
            util = float(conduit.get("area_util_mm2") or 0.0)
            if util <= 0:
                util = 1.0
            used = used_by_tag.get(ctag, 0.0)
            new_fill = (used + area_i) / util * 100.0
            penalty_over = max(0.0, new_fill - max_fill_percent) * w_over
            pref_value = _service_pref(conduit)
            mismatch = pref_value and pref_value != "Libre" and pref_value != service
            penalty_mismatch = w_mismatch if mismatch else 0.0
            score = new_fill + penalty_over + penalty_mismatch
            if best_score is None or score < best_score:
                best_score = score
                best = conduit

        if best is None:
            continue
        best_tag = str(best.get("tag") or "")
        assignments[tag] = best_tag
        used_by_tag[best_tag] = used_by_tag.get(best_tag, 0.0) + area_i

    for c in conduits:
        tag = str(c.get("tag") or "")
        util = float(c.get("area_util_mm2") or 0.0)
        used = used_by_tag.get(tag, 0.0)
        fill_pct = 0.0
        if util > 0:
            fill_pct = used / util * 100.0
        conduit_stats[tag] = {
            "used_mm2": used,
            "util_mm2": util,
            "fill_pct": fill_pct,
            "avail_pct": max(0.0, 100.0 - fill_pct),
        }

    return assignments, conduit_stats


def layout_cables_in_circle(
    conduit_geom: Dict[str, float],
    cable_items: List[Dict[str, object]],
    spacing_mm: float = 1.0,
) -> List[Dict[str, object]]:
    positions: List[Dict[str, object]] = []
    cx = float(conduit_geom.get("cx") or 0.0)
    cy = float(conduit_geom.get("cy") or 0.0)
    inner_d = float(conduit_geom.get("inner_diameter_mm") or 0.0)
    if inner_d <= 0:
        return positions
    radius = inner_d / 2.0
    margin = max(0.0, float(spacing_mm))
    usable_r = max(0.0, radius - margin)

    items = sorted(cable_items or [], key=lambda c: float(c.get("d_mm") or 0.0), reverse=True)
    if not items:
        return positions

    diameters = [max(0.0, float(c.get("d_mm") or 0.0)) for c in items]
    if not any(diameters):
        return positions

    def _initial_positions(mode: str, phase: float) -> List[Tuple[float, float]]:
        coords: List[Tuple[float, float]] = []
        max_d = max(diameters)
        step = max_d + margin
        if mode == "rings":
            coords.append((0.0, 0.0))
            idx = 1
            ring = 1
            while idx < len(items):
                ring_r = ring * step
                circumference = 2 * math.pi * ring_r
                count = max(1, int(circumference / max(step, 1e-6)))
                for i in range(count):
                    if idx >= len(items):
                        break
                    angle = phase + (2 * math.pi * i) / count
                    coords.append((ring_r * math.cos(angle), ring_r * math.sin(angle)))
                    idx += 1
                ring += 1
            return coords

        # spiral fallback
        angle = phase
        r = 0.0
        for _ in items:
            coords.append((r * math.cos(angle), r * math.sin(angle)))
            r += step * 0.5
            angle += 0.7
        return coords

    def _relax(coords: List[Tuple[float, float]], max_iters: int = 160) -> Tuple[List[Tuple[float, float]], float]:
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        rs = [d / 2.0 for d in diameters]
        n = len(xs)
        if n <= 1:
            return coords, 0.0

        for _ in range(max_iters):
            moved = 0.0
            for i in range(n):
                for j in range(i + 1, n):
                    dx = xs[j] - xs[i]
                    dy = ys[j] - ys[i]
                    dist = math.hypot(dx, dy) or 1e-6
                    min_dist = rs[i] + rs[j] + margin
                    if dist < min_dist:
                        push = (min_dist - dist) * 0.5
                        ux = dx / dist
                        uy = dy / dist
                        xs[i] -= ux * push
                        ys[i] -= uy * push
                        xs[j] += ux * push
                        ys[j] += uy * push
                        moved += push * 2.0
            for i in range(n):
                dist = math.hypot(xs[i], ys[i]) or 1e-6
                limit = usable_r - rs[i]
                if limit < 0:
                    continue
                if dist > limit:
                    push = dist - limit
                    xs[i] -= (xs[i] / dist) * push
                    ys[i] -= (ys[i] / dist) * push
                    moved += push
            if moved < 1e-3:
                break

        overflow = 0.0
        overlaps = 0.0
        for i in range(n):
            dist = math.hypot(xs[i], ys[i])
            limit = usable_r - rs[i]
            if dist > limit + 1e-6:
                overflow += dist - limit
        for i in range(n):
            for j in range(i + 1, n):
                dx = xs[j] - xs[i]
                dy = ys[j] - ys[i]
                dist = math.hypot(dx, dy) or 1e-6
                min_dist = rs[i] + rs[j] + margin
                if dist < min_dist - 1e-6:
                    overlaps += (min_dist - dist)

        return list(zip(xs, ys)), overflow + overlaps * 1.5

    best_coords: List[Tuple[float, float]] = []
    best_score = None
    tries = 6
    for t in range(tries):
        phase = (2 * math.pi / max(1, tries)) * t
        mode = "rings" if t % 2 == 0 else "spiral"
        coords = _initial_positions(mode, phase)
        coords, score = _relax(coords)
        if best_score is None or score < best_score:
            best_score = score
            best_coords = coords
            if score <= 1e-3:
                break

    for idx, item in enumerate(items):
        x = cx + best_coords[idx][0]
        y = cy + best_coords[idx][1]
        d = float(item.get("d_mm") or 0.0)
        r = d / 2.0
        dist = math.hypot(x - cx, y - cy)
        overflow = dist + r > usable_r + 1e-6
        positions.append({
            "x_mm": x,
            "y_mm": y,
            "d_mm": d,
            "circuit_tag": item.get("circuit_tag") or "",
            "overflow": overflow,
        })

    return positions


def layout_cables_in_rect(
    conduit_geom: Dict[str, float],
    cable_items: List[Dict[str, object]],
    spacing_mm: float = 1.0,
) -> List[Dict[str, object]]:
    positions: List[Dict[str, object]] = []
    x0 = float(conduit_geom.get("x0") or 0.0)
    y0 = float(conduit_geom.get("y0") or 0.0)
    w = float(conduit_geom.get("width_mm") or 0.0)
    h = float(conduit_geom.get("height_mm") or 0.0)
    if w <= 0 or h <= 0:
        return positions

    items = sorted(cable_items or [], key=lambda c: float(c.get("d_mm") or 0.0), reverse=True)
    cursor_x = x0 + spacing_mm
    cursor_y = y0 + spacing_mm
    row_height = 0.0

    for item in items:
        d = float(item.get("d_mm") or 0.0)
        r = d / 2.0
        if d <= 0:
            continue
        if cursor_x + d + spacing_mm > x0 + w:
            cursor_x = x0 + spacing_mm
            cursor_y = cursor_y + row_height + spacing_mm
            row_height = 0.0
        overflow = False
        if cursor_y + d + spacing_mm > y0 + h:
            overflow = True
        positions.append({
            "x_mm": cursor_x + r,
            "y_mm": cursor_y + r,
            "d_mm": d,
            "circuit_tag": item.get("circuit_tag") or "",
            "overflow": overflow,
        })
        cursor_x = cursor_x + d + spacing_mm
        row_height = max(row_height, d)

    return positions


def expand_cable_items(
    circuit_tag: str,
    outer_diameter_mm: float,
    qty: int,
) -> List[Dict[str, object]]:
    items: List[Dict[str, object]] = []
    qty = max(1, int(qty or 1))
    d = float(outer_diameter_mm or 0.0)
    if d <= 0:
        return items
    if qty <= 10:
        for _ in range(qty):
            items.append({"d_mm": d, "circuit_tag": circuit_tag})
    else:
        area_total = math.pi * (d / 2.0) ** 2 * qty
        d_eq = math.sqrt((4.0 * area_total) / math.pi)
        items.append({"d_mm": d_eq, "circuit_tag": circuit_tag})
    return items
