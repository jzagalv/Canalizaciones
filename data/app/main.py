# -*- coding: utf-8 -*-
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _run_module() -> int:
    root = _repo_root()
    cmd = [sys.executable, "-m", "app"]
    return subprocess.call(cmd, cwd=str(root))


if __name__ == "__main__":
    print("No ejecutar data/app/main.py. Usa: python -m app")
    raise SystemExit(_run_module())

# Compatibilidad: importar main si alguien lo importa como módulo
try:
    from app.main import main  # noqa: F401
except Exception:
    # Importing may fail if run from an unexpected CWD; prefer module execution.
    pass
