"""Reusable building blocks: cards, page headers, stat tiles, empty states.

Keeping these here means every screen gets the same padding, the same shadow and
the same title treatment, rather than each one re-inventing them slightly
differently.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSizePolicy, QStyledItemDelegate, QVBoxLayout, QWidget,
)

from . import icons
from .theme import (ACCENT, FAINT, GRID_LINE, INK, MUTED, S2, S3, S4)


def shadow(widget: QWidget, blur: int = 22, dy: int = 3, alpha: int = 26):
    """A soft drop shadow. Qt stylesheets cannot express box-shadow, so cards
    get their depth from a graphics effect instead."""
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setXOffset(0)
    effect.setYOffset(dy)
    effect.setColor(QColor(15, 27, 42, alpha))
    widget.setGraphicsEffect(effect)
    return effect


def hrule(parent=None) -> QFrame:
    line = QFrame(parent)
    line.setObjectName("CardRule")
    line.setFixedHeight(1)
    line.setFrameShape(QFrame.NoFrame)
    return line


class Card(QFrame):
    """A white rounded panel with an optional small-caps title and a right-hand
    slot for controls that belong to the section."""

    def __init__(self, title: str = "", hint: str = "", parent=None,
                 elevated: bool = True):
        """`elevated` must be False for any card holding a table or another
        scroll area: a QGraphicsEffect renders its children through an offscreen
        pixmap, and scroll-area children then paint outside the card's bounds."""
        super().__init__(parent)
        self.setObjectName("Card")
        if elevated:
            shadow(self)

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(S3, S2 + 4, S3, S2 + 4)
        self._outer.setSpacing(S2)

        self.header = QHBoxLayout()
        self.header.setSpacing(S2)
        self.title_label = QLabel(title.upper())
        self.title_label.setObjectName("CardTitle")
        self.header.addWidget(self.title_label)

        self.hint_label = QLabel(hint)
        self.hint_label.setObjectName("CardHint")
        self.header.addWidget(self.hint_label)
        self.header.addStretch(1)

        if title or hint:
            self._outer.addLayout(self.header)

        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(S2)
        self._outer.addLayout(self.body, 1)

    def add(self, item, stretch: int = 0):
        if isinstance(item, QWidget):
            self.body.addWidget(item, stretch)
        else:
            self.body.addLayout(item, stretch)

    def add_header_widget(self, widget: QWidget):
        self.header.addWidget(widget)

    def set_hint(self, text: str):
        self.hint_label.setText(text)


class PageHeader(QWidget):
    """Title, one-line explanation, and a slot on the right for page actions."""

    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(S3)

        text = QVBoxLayout()
        text.setSpacing(1)
        self.title = QLabel(title)
        self.title.setObjectName("PageTitle")
        self.subtitle = QLabel(subtitle)
        self.subtitle.setObjectName("PageSubtitle")
        text.addWidget(self.title)
        text.addWidget(self.subtitle)

        row.addLayout(text)
        row.addStretch(1)
        self.actions = QHBoxLayout()
        self.actions.setSpacing(S2)
        row.addLayout(self.actions)

    def add_action(self, widget: QWidget):
        self.actions.addWidget(widget)

    def set_subtitle(self, text: str):
        self.subtitle.setText(text)


class StatTile(QFrame):
    """One number plus its label, for the summary strip above the history list."""

    def __init__(self, label: str, value: str = "0", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        shadow(self, 16, 2, 20)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(S3, S2 + 4, S3, S2 + 4)
        layout.setSpacing(0)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("StatValue")
        self.label_label = QLabel(label.upper())
        self.label_label.setObjectName("StatLabel")

        layout.addWidget(self.value_label)
        layout.addWidget(self.label_label)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

    def set_value(self, value):
        self.value_label.setText(str(value))


class EmptyState(QWidget):
    """Shown instead of a bare grid when there is genuinely nothing to list."""

    def __init__(self, icon_name: str, title: str, body: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(S2)

        glyph = QLabel()
        glyph.setPixmap(icons.pixmap(icon_name, "#b6c4d4", 54, 1.6))
        glyph.setAlignment(Qt.AlignCenter)

        heading = QLabel(title)
        heading.setObjectName("EmptyTitle")
        heading.setAlignment(Qt.AlignCenter)

        text = QLabel(body)
        text.setObjectName("EmptyBody")
        text.setAlignment(Qt.AlignCenter)
        text.setWordWrap(True)

        layout.addStretch(1)
        layout.addWidget(glyph)
        layout.addWidget(heading)
        layout.addWidget(text)
        layout.addStretch(1)


def icon_button(icon_name: str, text: str, tooltip: str = "",
                kind: str = "", size: int = 17) -> QPushButton:
    """A button with one of the drawn icons, tinted to match its role."""
    colors = {"Primary": "#ffffff", "Danger": "#c0392b", "": MUTED, "Ghost": MUTED}
    button = QPushButton(text)
    if kind:
        button.setObjectName(kind)
    button.setIcon(icons.icon(icon_name, colors.get(kind, MUTED), size))
    button.setIconSize(icons.icon_size(size))
    button.setCursor(Qt.PointingHandCursor)
    button.setMinimumHeight(38)
    if tooltip:
        button.setToolTip(tooltip)
    return button


def accent_icon_button(icon_name: str, text: str, tooltip: str = "") -> QPushButton:
    button = icon_button(icon_name, text, tooltip, "Primary")
    button.setIcon(icons.icon(icon_name, "#ffffff", 17))
    return button


__all__ = ["Card", "PageHeader", "StatTile", "EmptyState", "shadow", "hrule",
           "icon_button", "accent_icon_button", "AmountDelegate",
           "ACCENT", "S2", "S3", "S4"]


class AmountDelegate(QStyledItemDelegate):
    """Paints a money cell as an obvious input box.

    A bare table cell gives the operator nothing to aim at: the amount column
    looked like the read-only service name beside it, and the only way to find
    out it could be typed in was to try. So the cell is drawn as a bordered
    white box with a grey `0.00` inside it while it is empty - the same
    affordance every other editable field on the page has - and the figure is
    set bold and right-aligned once it is filled, so a column of amounts reads
    down its decimal point.

    The box is painted rather than styled because a Qt stylesheet on
    QTableWidget::item takes over item rendering and drops the model's own
    background brush, so a tint set on the item would simply never appear.
    """

    HINT = "0.00"

    def __init__(self, parent=None, validator_pattern: str = "", hint: str = ""):
        super().__init__(parent)
        self.validator_pattern = validator_pattern
        self.hint = hint or self.HINT

    def paint(self, painter, option, index):
        from PySide6.QtGui import QPainter, QPen

        text = str(index.data(Qt.DisplayRole) or "")
        rect = option.rect.adjusted(4, 3, -5, -4)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(GRID_LINE), 1.4))
        painter.setBrush(QColor("#ffffff"))
        painter.drawRoundedRect(rect, 5, 5)

        font = painter.font()
        if text.strip():
            font.setBold(True)
            painter.setFont(font)
            # The model's own colour carries the red on an unusable amount.
            brush = index.data(Qt.ForegroundRole)
            painter.setPen(brush.color() if brush is not None else QColor(INK))
            shown = text
        else:
            painter.setFont(font)
            painter.setPen(QColor(FAINT))
            shown = self.hint
        painter.drawText(rect.adjusted(6, 0, -7, 0),
                         Qt.AlignRight | Qt.AlignVCenter, shown)
        painter.restore()

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        editor.setPlaceholderText(self.hint)
        if self.validator_pattern:
            from .. import validators as V

            editor.setValidator(V.validator(self.validator_pattern, editor))
        return editor

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size.setHeight(max(size.height(), 30))
        return size
