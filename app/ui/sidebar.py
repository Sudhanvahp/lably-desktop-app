"""The left navigation rail.

A sidebar rather than a tab bar: there are only three destinations, they are
permanent, and a rail leaves the full window width for the results grid - which
is the widest thing in the app.
"""
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from . import icons
from .theme import S2, S3, S4

WIDTH = 248
ON = "#ffffff"
OFF = "#a8c2ce"


class NavButton(QPushButton):
    def __init__(self, icon_name: str, text: str, parent=None):
        super().__init__(text, parent)
        self.icon_name = icon_name
        self.setObjectName("NavButton")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setIconSize(QSize(19, 19))
        self.setMinimumHeight(44)
        self.toggled.connect(self._retint)
        self._retint(False)

    def _retint(self, checked: bool):
        """Qt stylesheets cannot recolour an icon, so the pixmap is redrawn
        whenever the button's state changes."""
        self.setIcon(icons.icon(self.icon_name, ON if checked else OFF, 19))


class Sidebar(QFrame):
    navigated = Signal(int)

    def __init__(self, app_name: str, tagline: str, version: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(S3, S4, S3, S3)
        layout.setSpacing(S2)

        layout.addWidget(self._build_brand(app_name, tagline))
        layout.addSpacing(S3)

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons = []
        layout.addLayout(self._build_nav())

        layout.addStretch(1)

        rule = QFrame()
        rule.setObjectName("SidebarRule")
        rule.setFixedHeight(1)
        layout.addWidget(rule)

        foot = QLabel(f"{app_name} {version}".strip())
        foot.setObjectName("SidebarFoot")
        layout.addWidget(foot)

    def _build_brand(self, app_name: str, tagline: str) -> QWidget:
        brand = QWidget()
        row = QHBoxLayout(brand)
        row.setContentsMargins(S2 - 2, 0, 0, 0)
        row.setSpacing(S2 + 2)

        mark = QLabel()
        mark.setPixmap(icons.logo_pixmap(36))
        row.addWidget(mark)

        text = QVBoxLayout()
        text.setSpacing(0)
        name = QLabel(app_name)
        name.setObjectName("BrandName")
        tag = QLabel(tagline.upper())
        tag.setObjectName("BrandTag")
        text.addWidget(name)
        text.addWidget(tag)

        row.addLayout(text)
        row.addStretch(1)
        return brand

    def _build_nav(self) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(4)
        for index, (icon_name, label) in enumerate((
            ("new-report", "  New Report"),
            ("history", "  Report History"),
            ("beaker", "  Test Templates"),
            ("lab", "  Laboratory Profile"),
        )):
            button = NavButton(icon_name, label)
            button.clicked.connect(lambda _, i=index: self.navigated.emit(i))
            self.group.addButton(button, index)
            self.buttons.append(button)
            column.addWidget(button)
        self.buttons[0].setChecked(True)
        return column

    def set_current(self, index: int):
        if 0 <= index < len(self.buttons):
            self.buttons[index].setChecked(True)

    def current(self) -> int:
        return self.group.checkedId()

    def label(self, index: int) -> str:
        return self.buttons[index].text().strip()
