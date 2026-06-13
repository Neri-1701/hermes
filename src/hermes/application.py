from __future__ import annotations

import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication

from hermes.config import APP_TITLE
from hermes.ui.main_window import MainWindow


def create_application(argv: Sequence[str] | None = None) -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(list(argv) if argv is not None else sys.argv)
    app.setApplicationName(APP_TITLE)
    return app


def main(argv: Sequence[str] | None = None) -> int:
    app = create_application(argv)
    window = MainWindow()
    window.show()
    return app.exec()
