"""Entry point: python -m app"""
import sys

from PySide6.QtWidgets import QApplication

from . import storage
from .branding import APP_NAME
from .ui.main_window import MainWindow
from .ui.theme import stylesheet


def main() -> int:
    storage.ensure_dirs()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setStyle("Fusion")
    app.setStyleSheet(stylesheet())
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
