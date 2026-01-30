# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Callable, Optional, Set, List

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from ui.utils.event_logger import log_event

class RecalcScheduler(QObject):
    calc_started = pyqtSignal(list)
    calc_finished = pyqtSignal(bool)
    calc_state_changed = pyqtSignal(bool)

    def __init__(
        self,
        callback: Callable[[], None],
        parent: Optional[QObject] = None,
        delay_ms: int = 350,
    ) -> None:
        super().__init__(parent)
        self._callback = callback
        self._delay_ms = max(0, int(delay_ms))
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._run)
        self._reasons: Set[str] = set()
        self._running = False
        self._pending = False

    def schedule(self, reason: str) -> None:
        if reason:
            self._reasons.add(str(reason))
        log_event("schedule_called", str(reason or ""))
        self.calc_state_changed.emit(True)
        if self._running:
            self._pending = True
            return
        if not self._timer.isActive():
            self._timer.start(self._delay_ms)

    def force(self, reason: str) -> None:
        if reason:
            self._reasons.add(str(reason))
        log_event("force_recalc", str(reason or ""))
        self.calc_state_changed.emit(True)
        if self._running:
            self._pending = True
            return
        self._timer.stop()
        self._run()

    def take_reasons(self) -> List[str]:
        reasons = sorted(self._reasons)
        self._reasons.clear()
        return reasons

    def peek_reasons(self) -> List[str]:
        return sorted(self._reasons)

    def _run(self) -> None:
        if self._running:
            self._pending = True
            return
        self._running = True
        reasons = self.take_reasons()
        log_event("recalc_execute", ",".join(reasons))
        self.calc_started.emit(reasons)
        ok = True
        try:
            self._callback()
        except Exception:
            ok = False
        self.calc_finished.emit(ok)
        self._running = False
        if self._pending:
            self._pending = False
            self._timer.start(0)
