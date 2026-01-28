# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Optional

from PyQt5.QtWidgets import QFrame, QWidget


class CardFrame(QFrame):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setProperty("card", True)
