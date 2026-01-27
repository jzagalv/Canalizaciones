# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from domain.materials.material_ids import material_display_label


@dataclass
class EffectiveCatalog:
    material: Dict[str, Any]
    templates: Dict[str, Any]
    equipment: Dict[str, Any]
    warnings: List[str]


def _merge_by_id(items: List[Dict[str, Any]], warnings: List[str], scope: str) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for it in items:
        _id = it.get('id')
        if not _id:
            warnings.append(f"[{scope}] item sin id ignorado")
            continue
        if _id in out:
            warnings.append(f"[{scope}] id duplicado '{_id}' fue sobrescrito por una libreria con mayor prioridad")
        out[_id] = it
    return out


def _merge_by_uid(items: List[Dict[str, Any]], warnings: List[str], scope: str) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for it in items:
        uid = str(it.get("uid") or "").strip()
        if not uid:
            warnings.append(f"[{scope}] item sin uid ignorado")
            continue
        if uid in out:
            warnings.append(f"[{scope}] uid duplicado '{uid}' fue sobrescrito por una libreria con mayor prioridad")
        out[uid] = it
    return out


def merge_libs(loaded_libs: List[Tuple[str, Dict[str, Any]]]) -> EffectiveCatalog:
    """Recibe docs ya ordenados por prioridad (menor -> mayor) y produce catalogo efectivo."""
    warnings: List[str] = []

    conductors: List[Dict[str, Any]] = []
    ducts: List[Dict[str, Any]] = []
    epc: List[Dict[str, Any]] = []
    bpc: List[Dict[str, Any]] = []
    rules: Dict[str, Any] = {'separation': [], 'defaults': {}}

    profiles: List[Dict[str, Any]] = []
    equipment_templates: List[Dict[str, Any]] = []
    proposal_rules: Dict[str, Any] = {}

    equipment_items: List[Dict[str, Any]] = []

    code_sources = {
        "conductors": {},
        "ducts": {},
        "epc": {},
        "bpc": {},
    }

    def track_code(scope: str, item: Dict[str, Any], source_label: str) -> None:
        code = str(item.get("code") or "").strip()
        if not code:
            return
        norm = code.lower()
        prev = code_sources.get(scope, {}).get(norm)
        if prev and prev[0] != source_label:
            warnings.append(f"[{scope}] code duplicado '{code}' entre '{prev[0]}' y '{source_label}'")
        else:
            code_sources.get(scope, {})[norm] = (source_label, material_display_label(item))

    for source_label, doc in loaded_libs:
        kind = doc.get('kind')
        if kind == 'material_library':
            for item in (doc.get('conductors') or []):
                track_code("conductors", item, source_label)
                conductors.append(item)
            cont = doc.get('containments') or {}
            for item in (cont.get('ducts') or []):
                track_code("ducts", item, source_label)
                ducts.append(item)
            for item in (cont.get('epc') or []):
                track_code("epc", item, source_label)
                epc.append(item)
            for item in (cont.get('bpc') or []):
                track_code("bpc", item, source_label)
                bpc.append(item)

            r = doc.get('rules') or {}
            rules['separation'] += list(r.get('separation') or [])
            rules['defaults'].update(r.get('defaults') or {})

        elif kind == 'template_library':
            profiles += list(doc.get('substation_profiles') or [])
            equipment_templates += list(doc.get('equipment_templates') or [])
            proposal_rules.update(doc.get('proposal_rules') or {})
        elif kind == 'equipment_library':
            equipment_items += list(doc.get('items') or [])

    material = {
        'conductors_by_uid': _merge_by_uid(conductors, warnings, 'conductors'),
        'ducts_by_uid': _merge_by_uid(ducts, warnings, 'ducts'),
        'epc_by_uid': _merge_by_uid(epc, warnings, 'epc'),
        'bpc_by_uid': _merge_by_uid(bpc, warnings, 'bpc'),
        'conductors_by_code': {str(it.get("code") or "").strip().lower(): it for it in conductors if it.get("code")},
        'ducts_by_code': {str(it.get("code") or "").strip().lower(): it for it in ducts if it.get("code")},
        'epc_by_code': {str(it.get("code") or "").strip().lower(): it for it in epc if it.get("code")},
        'bpc_by_code': {str(it.get("code") or "").strip().lower(): it for it in bpc if it.get("code")},
        'rules': rules,
    }

    equipment = {
        'items_by_id': _merge_by_id(equipment_items, warnings, 'equipment_items'),
    }

    templates = {
        'profiles_by_id': _merge_by_id(profiles, warnings, 'profiles'),
        'equipment_templates_by_id': _merge_by_id(equipment_templates, warnings, 'equipment_templates'),
        'proposal_rules': proposal_rules,
    }

    return EffectiveCatalog(material=material, templates=templates, equipment=equipment, warnings=warnings)
