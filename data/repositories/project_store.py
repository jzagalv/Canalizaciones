# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict

from domain.entities.models import LibraryRef, Project


class ProjectStoreError(Exception):
    pass


def load_project(path: str) -> Project:
    p = Path(path)
    if not p.exists():
        raise ProjectStoreError(f"No existe el proyecto: {path}")

    try:
        data = json.loads(p.read_text(encoding='utf-8'))
    except Exception as e:
        raise ProjectStoreError(f"JSON invalido: {e}")

    libs = [LibraryRef(**d) for d in (data.get('libraries') or [])]
    prj = Project(
        project_version=data.get('project_version','1.0'),
        name=data.get('name','Proyecto'),
        active_profile=data.get('active_profile','ss_conventional'),
        active_materiales_bd_path=data.get('active_materiales_bd_path',''),
        active_library_path=data.get('active_library_path',''),
        active_template_path=data.get('active_template_path',''),
        active_installation_type=data.get('active_installation_type',''),
        libraries=libs,
        canvas=data.get('canvas') or {
            'nodes': [],
            'edges': [],
            'background': {
                'path': '',
                'opacity': 1.0,
                'locked': True,
                'pos': [0.0, 0.0],
                'scale': 1.0,
                'image_data': '',
                'image_format': '',
            },
            'view': {},
        },
        circuits=data.get('circuits') or {'source': 'none', 'items': []},
        primary_equipment=data.get('primary_equipment') or [],
        troncales=data.get('troncales') or [],
        active_fill_rules_preset_id=data.get('active_fill_rules_preset_id',''),
    )
    return prj


def save_project(project: Project, path: str) -> None:
    p = Path(path)
    data = asdict(project)
    # dataclass LibraryRef -> dict OK
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
