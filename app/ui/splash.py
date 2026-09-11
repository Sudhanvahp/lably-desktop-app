"""The card shown while the app starts: product name, and who developed it.

A one-file exe unpacks itself before the first window can paint, which on a
slow counter PC is a few seconds of nothing. The splash fills that gap and, in
the same breath, credits the vendor - it is the one moment every user of the
exe is guaranteed to see the name.
"""
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QSplashScreen

from ..branding import APP_NAME, APP_TAGLINE, APP_VERSION, DEVELOPED_BY, ORIGIN
from .icons import logo_pixmap

WIDTH, HEIGHT = 460, 250
PAPER = "#ffffff"
INK = "#0f1b2a"
MUTED = "#6a7b8a"
ACCENT = "#0d7d8f"
CRIMSON = "#b3202c"
BAND = "#0b2a3a"

# How long the card stays up after the main window is ready. Long enough to be
# read, short enough that nobody reaches for the mouse.
HOLD_MS = 1600


def _paint() -> QPixmap:
    pix = QPixmap(WIDTH, HEIGHT)
    pix.fill(QColor(PAPER))
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)

    # The same three-colour ribbon that tops every printed report.
    p.fillRect(QRect(0, 0, int(WIDTH * 0.46), 7), QColor(CRIMSON))
    p.fillRect(QRect(int(WIDTH * 0.46), 0, int(WIDTH * 0.18), 7), QColor(BAND))
    p.fillRect(QRect(int(WIDTH * 0.64), 0, WIDTH - int(WIDTH * 0.64), 7), QColor(ACCENT))

    mark = logo_pixmap(44)
    p.drawPixmap(WIDTH // 2 - 70, 44, mark)
    p.setPen(QColor(INK))
    p.setFont(QFont("Segoe UI", 30, QFont.Bold))
    p.drawText(QRect(WIDTH // 2 - 20, 40, 140, 52), Qt.AlignVCenter | Qt.AlignLeft, APP_NAME)

    p.setPen(QColor(MUTED))
    p.setFont(QFont("Segoe UI", 11))
    p.drawText(QRect(0, 92, WIDTH, 24), Qt.AlignCenter, APP_TAGLINE)

    p.fillRect(QRect(WIDTH // 2 - 24, 128, 48, 2), QColor(ACCENT))

    p.setPen(QColor(CRIMSON))
    p.setFont(QFont("Segoe UI", 12, QFont.Black))
    p.drawText(QRect(0, 144, WIDTH, 28), Qt.AlignCenter, DEVELOPED_BY.upper())

    p.setPen(QColor(INK))
    p.setFont(QFont("Segoe UI", 9, QFont.Bold))
    p.drawText(QRect(0, 176, WIDTH, 20), Qt.AlignCenter, f"{APP_VERSION}   |   {ORIGIN}")

    p.setPen(QColor("#dde4ec"))
    p.drawRect(QRect(0, 0, WIDTH - 1, HEIGHT - 1))
    p.end()
    return pix


class Splash(QSplashScreen):
    def __init__(self):
        super().__init__(_paint())
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.showMessage("Starting...", Qt.AlignBottom | Qt.AlignHCenter, QColor(MUTED))
