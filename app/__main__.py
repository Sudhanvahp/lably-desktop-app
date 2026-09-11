"""Entry point: python -m app"""
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from . import storage
from .branding import APP_NAME, VENDOR
from .ui.icons import logo_pixmap
from .ui.main_window import MainWindow
from .ui.splash import HOLD_MS, Splash
from .ui.theme import stylesheet


def main() -> int:
    storage.ensure_dirs()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(VENDOR)
    app.setStyle("Fusion")
    # The drawn mark, at every size the taskbar / title bar / Alt-Tab asks for.
    app_icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        app_icon.addPixmap(logo_pixmap(size))
    app.setWindowIcon(app_icon)

    # Up before anything else so the vendor card is the first thing painted,
    # then held briefly over the finished window so it can actually be read.
    splash = Splash()
    splash.show()
    app.processEvents()

    app.setStyleSheet(stylesheet())
    window = MainWindow()
    window.show()
    QTimer.singleShot(HOLD_MS, lambda: splash.finish(window))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
