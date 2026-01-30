# -*- coding: utf-8 -*-
from __future__ import annotations

import inspect
import logging
from pathlib import Path


_LOGGER_NAME = "canalizaciones.events"
_LOG_DIR = Path("logs")
_LOG_FILE = _LOG_DIR / "canalizaciones_events.log"


def _get_logger() -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(_LOG_FILE, encoding="utf-8", mode="a")
    formatter = logging.Formatter(
        "[%(asctime)s.%(msecs)03d] [%(levelname)s] [%(event)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def log_event(event: str, message: str = "") -> None:
    try:
        stack = inspect.stack()
        frame = stack[1] if len(stack) > 1 else None
        location = ""
        if frame is not None:
            filename = Path(frame.filename).name
            location = f" ({filename}:{frame.lineno} {frame.function})"
        msg = f"{message}{location}"
        logger = _get_logger()
        logger.debug(msg, extra={"event": event})
    except Exception:
        try:
            logging.getLogger(__name__).exception("log_event failed")
        except Exception:
            pass
