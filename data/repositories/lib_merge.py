# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


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


def merge_libs(loaded_libs: List[Dict[str, Any]]) -> EffectiveCatalog:
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

    for doc in loaded_libs:
        kind = doc.get('kind')
        if kind == 'material_library':
            conductors += list(doc.get('conductors') or [])
            cont = doc.get('containments') or {}
            ducts += list(cont.get('ducts') or [])
            epc += list(cont.get('epc') or [])
            bpc += list(cont.get('bpc') or [])

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
        'conductors_by_id': _merge_by_id(conductors, warnings, 'conductors'),
        'ducts_by_id': _merge_by_id(ducts, warnings, 'ducts'),
        'epc_by_id': _merge_by_id(epc, warnings, 'epc'),
        'bpc_by_id': _merge_by_id(bpc, warnings, 'bpc'),
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
