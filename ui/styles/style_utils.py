# -*- coding: utf-8 -*-
from __future__ import annotations

from PyQt5.QtWidgets import QWidget


def repolish(widget: QWidget) -> None:
    if widget is None:
        return
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def repolish_tree(root: QWidget) -> None:
    if root is None:
        return
    repolish(root)
    for child in root.findChildren(QWidget):
        repolish(child)
