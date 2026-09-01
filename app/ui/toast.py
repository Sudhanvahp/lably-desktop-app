"""A small in-window notification banner.

A modal QMessageBox on every save would mean an extra click on every single
report, which is exactly the wrong tax to put on the most frequent action. This
shows a coloured banner in the top-right of the window that fades out on its own.
"""
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import QGraphicsOpacityEffect, QHBoxLayout, QLabel, QWidget

from .theme import ACCENT_DARK, DANGER

SUCCESS_BG = "#1e7a4d"
INFO_BG = ACCENT_DARK
WARN_BG = "#b5730f"
ERROR_BG = DANGER

_STYLES = {"success": SUCCESS_BG, "info": INFO_BG, "warning": WARN_BG, "error": ERROR_BG}
_ICONS = {"success": "✓", "info": "ℹ", "warning": "!", "error": "✕"}


class Toast(QWidget):
    """One reusable banner per window. Showing a new message replaces the old one."""

    MARGIN = 18
    TOP_OFFSET = 74      # clears the app header bar
    DEFAULT_MSECS = 5000  # long enough to actually read the report number

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        # without this a plain QWidget subclass ignores its stylesheet background
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("ToastBanner")
        self.setWindowFlags(Qt.Widget | Qt.FramelessWindowHint)

        self.icon = QLabel()
        self.text = QLabel()
        for label in (self.icon, self.text):
            label.setStyleSheet("color: white; background: transparent; font-weight: 600;")
        self.icon.setStyleSheet(
            "color: white; background: transparent; font-size: 14pt; font-weight: 700;")

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 10, 18, 10)
        row.setSpacing(10)
        row.addWidget(self.icon)
        row.addWidget(self.text)

        self.effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.effect)
        self.effect.setOpacity(0.0)

        self.fade = QPropertyAnimation(self.effect, b"opacity", self)
        self.fade.setEasingCurve(QEasingCurve.InOutQuad)

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self._fade_out)

        # Connected once here rather than per fade: repeatedly connecting and
        # disconnecting `finished` warns when there is nothing to disconnect.
        self._fading_out = False
        self.fade.finished.connect(self._fade_finished)

        self.hide()

    # -----------------------------------------------------------------------
    def show_message(self, message: str, kind: str = "success", msecs: int = 0):
        msecs = msecs or self.DEFAULT_MSECS
        self.text.setText(message)
        self.icon.setText(_ICONS.get(kind, _ICONS["info"]))
        self.setStyleSheet(
            f"#ToastBanner {{ background: {_STYLES.get(kind, INFO_BG)};"
            f" border-radius: 6px; }}")
        self.adjustSize()
        self.reposition()
        self.show()
        self.raise_()

        self._fading_out = False
        self.fade.stop()
        self.fade.setDuration(180)
        self.fade.setStartValue(self.effect.opacity())
        self.fade.setEndValue(1.0)
        self.fade.start()

        self.hide_timer.start(msecs)

    def reposition(self):
        parent = self.parentWidget()
        if parent is None:
            return
        self.move(max(self.MARGIN, parent.width() - self.width() - self.MARGIN),
                  self.TOP_OFFSET)

    def _fade_out(self):
        self._fading_out = True
        self.fade.stop()
        self.fade.setDuration(420)
        self.fade.setStartValue(self.effect.opacity())
        self.fade.setEndValue(0.0)
        self.fade.start()

    def _fade_finished(self):
        """Only the fade-out ends with the banner hidden; the fade-in must not."""
        if self._fading_out:
            self._fading_out = False
            self.hide()
