"""The control panel for how printed text looks: pick a region, restyle it.

One region at a time, with the whole sheet previewed beside it. The alternative -
a row of controls against every one of the eighteen regions - is a wall of
eighty-odd widgets in a screen that is already long, and an operator who wants
the footer centred would have to find it in that wall first.

Every control here works the way the same control works in a spreadsheet, which
is the one place a lab counter has already met this: three alignment buttons, a
font, a size, a colour, and B / I / U. What it writes, though, is deliberately
sparse - see `app.text_style`. A control put back where it started is stored as
nothing at all, so the profile only ever carries the lab's actual departures
from the printed default.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QButtonGroup, QColorDialog, QComboBox, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from .. import text_style as TS
from . import theme as T
from .theme import FAINT, FIELD_LINE, S1, S2, S3
from .widgets import icon_button

ALIGN_LABELS = (("left", "Left", "Range this text to the left"),
                ("center", "Centre", "Centre this text"),
                ("right", "Right", "Range this text to the right"))

EFFECTS = (("bold", "B", "Bold"), ("italic", "I", "Italic"),
           ("underline", "U", "Underline"))

# The sizes offered, in half points where a printed report actually lives
# (7pt to 12pt is the whole body of the page) and in whole ones above it, where
# the letterhead is and half a point is invisible.
SIZES = ([5, 5.5, 6, 6.5, 7, 7.5, 8, 8.5, 9, 9.5, 10, 10.5, 11, 11.5, 12, 13]
         + [14, 15, 16, 18, 20, 22, 24, 28, 32, 36, 40, 44, 48])


def _toggle(text: str, tooltip: str, width: int = 44) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("Toggle")
    button.setCheckable(True)
    button.setToolTip(tooltip)
    button.setCursor(Qt.PointingHandCursor)
    button.setMinimumHeight(34)
    button.setFixedWidth(width)
    return button


class TextStyleEditor(QWidget):
    """Edits one `text_styles` table. `styles()` is what belongs in the profile."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._styles = {}
        self._loading = False

        self.picker = T.style_combo(QComboBox())
        self.picker.setMinimumWidth(240)
        for slot in TS.SLOTS:
            self.picker.addItem(slot.label, slot.key)
        self.picker.currentIndexChanged.connect(self._show_slot)

        self.slot_hint = QLabel("")
        self.slot_hint.setObjectName("Hint")
        self.slot_hint.setWordWrap(True)
        self.slot_hint.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        # ---------------------------------------------------------- alignment
        self.align_buttons = {}
        self.align_group = QButtonGroup(self)
        self.align_group.setExclusive(True)
        align_row = QHBoxLayout()
        align_row.setSpacing(S1 + 2)
        for value, label, tip in ALIGN_LABELS:
            button = _toggle(label, tip, 74)
            self.align_group.addButton(button)
            self.align_buttons[value] = button
            button.clicked.connect(self._collect)
            align_row.addWidget(button)
        align_row.addStretch(1)

        # ------------------------------------------------------------ effects
        self.effect_buttons = {}
        effect_row = QHBoxLayout()
        effect_row.setSpacing(S1 + 2)
        for name, label, tip in EFFECTS:
            button = _toggle(label, tip)
            font = button.font()
            font.setBold(name == "bold")
            font.setItalic(name == "italic")
            font.setUnderline(name == "underline")
            button.setFont(font)
            self.effect_buttons[name] = button
            button.clicked.connect(self._collect)
            effect_row.addWidget(button)
        effect_row.addStretch(1)

        # ------------------------------------------------------- font and size
        self.font_box = T.style_combo(QComboBox())
        self.font_box.setMinimumWidth(190)
        self.font_box.addItem("Document default", "")
        for family in TS.FONTS:
            self.font_box.addItem(family, family)
            # Each family shown in itself: the point of a font picker is to see
            # the face, not to read its name.
            self.font_box.setItemData(self.font_box.count() - 1,
                                      QFont(family, 10), Qt.FontRole)
        self.font_box.currentIndexChanged.connect(self._collect)

        # A list rather than a spin box: every other input in the app is a
        # combo or a line edit, and a lab picks 18pt off a list the way they do
        # in Word - they do not step to it half a point at a time.
        self.size_box = T.style_combo(QComboBox())
        self.size_box.setMinimumWidth(150)
        self.size_box.addItem("Default size", "")
        for size in SIZES:
            self.size_box.addItem(f"{size:g} pt", f"{size:g}")
        self.size_box.currentIndexChanged.connect(self._collect)

        # -------------------------------------------------------------- colour
        self._color = ""
        self.color_swatch = QLabel()
        self.color_swatch.setFixedSize(34, 30)
        self.color_swatch.setAlignment(Qt.AlignCenter)
        self.color_pick = QPushButton("Colour...")
        self.color_pick.setMinimumHeight(34)
        self.color_pick.setToolTip("Pick the colour this text prints in")
        self.color_pick.clicked.connect(self._choose_color)
        self.color_clear = QPushButton("Default")
        self.color_clear.setObjectName("Ghost")
        self.color_clear.setToolTip("Print this text in the colour the report "
                                    "normally uses")
        self.color_clear.clicked.connect(self._clear_color)

        color_row = QHBoxLayout()
        color_row.setSpacing(S2)
        color_row.addWidget(self.color_swatch)
        color_row.addWidget(self.color_pick)
        color_row.addWidget(self.color_clear)
        color_row.addStretch(1)

        # ------------------------------------------------------------ the grid
        grid = QGridLayout()
        grid.setHorizontalSpacing(S3)
        grid.setVerticalSpacing(S2)
        grid.setContentsMargins(0, 0, 0, 0)

        def caption(text: str) -> QLabel:
            label = QLabel(text)
            label.setObjectName("FieldLabel")
            label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            return label

        grid.addWidget(caption("Alignment:"), 0, 0)
        grid.addLayout(align_row, 0, 1)
        grid.addWidget(caption("Style:"), 1, 0)
        grid.addLayout(effect_row, 1, 1)

        face_row = QHBoxLayout()
        face_row.setSpacing(S2)
        face_row.addWidget(self.font_box)
        face_row.addWidget(self.size_box)
        face_row.addStretch(1)
        grid.addWidget(caption("Font:"), 2, 0)
        grid.addLayout(face_row, 2, 1)

        grid.addWidget(caption("Colour:"), 3, 0)
        grid.addLayout(color_row, 3, 1)
        grid.setColumnStretch(1, 1)

        # ------------------------------------------------------------- footer
        self.reset_one = icon_button(
            "refresh", "Reset this text",
            "Print this one region the way the report normally does")
        self.reset_one.clicked.connect(self._reset_one)
        self.reset_all = icon_button(
            "trash", "Reset everything",
            "Drop every appearance change and print the standard layout",
            "Danger")
        self.reset_all.clicked.connect(self._reset_all)

        self.state = QLabel("")
        self.state.setObjectName("Hint")
        self.state.setWordWrap(True)

        buttons = QHBoxLayout()
        buttons.setSpacing(S2)
        buttons.addWidget(self.state, 1)
        buttons.addWidget(self.reset_one)
        buttons.addWidget(self.reset_all)

        picker_row = QHBoxLayout()
        picker_row.setSpacing(S2)
        picker_row.addWidget(QLabel("Text:"))
        picker_row.addWidget(self.picker)
        picker_row.addWidget(self.slot_hint, 1)

        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(S2 + 2)
        column.addLayout(picker_row)
        column.addLayout(grid)
        column.addLayout(buttons)

        self._show_slot()

    # ------------------------------------------------------------------ state
    def slot_key(self) -> str:
        return self.picker.currentData() or TS.SLOTS[0].key

    def styles(self) -> dict:
        """What to store on the profile: a copy, so the caller cannot edit ours
        behind our back."""
        return {key: dict(value) for key, value in self._styles.items() if value}

    def set_styles(self, styles) -> None:
        self._styles = {key: dict(value)
                        for key, value in TS.load(styles).items()}
        self._show_slot()

    # ------------------------------------------------------------- the screen
    def _show_slot(self) -> None:
        """Load the picked region into the controls.

        `_loading` is what stops this from being read straight back out again:
        setting a widget's value fires its signal, and without the guard every
        redraw would write the region it had only just read.
        """
        key = self.slot_key()
        slot = TS.BY_KEY[key]
        style = TS.effective(_Holder(self._styles), key)

        self._loading = True
        self.align_buttons[style.align or slot.align].setChecked(True)
        for name, button in self.effect_buttons.items():
            button.setChecked(getattr(style, name) == TS.ON)
        index = self.font_box.findData(style.font)
        self.font_box.setCurrentIndex(index if index >= 0 else 0)
        self._set_size(style.size)
        self._set_color(style.color)
        self._loading = False

        self.slot_hint.setText(f"{slot.hint}.")
        self._refresh_state()

    def _refresh_state(self) -> None:
        """Say what is customised, here and overall.

        Without this the screen cannot answer the one question an operator
        actually has - "what have I changed?" - because the controls always show
        something, whether it was chosen or merely inherited."""
        key = self.slot_key()
        holder = _Holder(self._styles)
        mine = TS.summary(holder, key)
        styled = TS.styled_slots(holder)
        self.reset_one.setEnabled(bool(self._styles.get(key)))
        self.reset_all.setEnabled(bool(styled))
        if styled:
            names = ", ".join(TS.BY_KEY[k].label for k in styled)
            overall = f"{len(styled)} of {len(TS.SLOTS)} customised: {names}."
        else:
            overall = ("Nothing customised - every line prints in the standard "
                       "layout.")
        self.state.setText(f"This text: {mine}.  {overall}")

        # The picker marks the regions that carry styling, so they can be found
        # again without opening each one in turn.
        for i in range(self.picker.count()):
            slot_key = self.picker.itemData(i)
            label = TS.BY_KEY[slot_key].label
            self.picker.setItemText(
                i, f"{label}  *" if slot_key in styled else label)

    def _set_size(self, size: str) -> None:
        """Show a stored size, adding it to the list if it is not one of ours.

        A profile edited by hand - or written by a later version with a longer
        list - must not come back silently rounded to the nearest offered size.
        """
        index = self.size_box.findData(size or "")
        if index < 0:
            self.size_box.addItem(f"{size} pt", size)
            index = self.size_box.count() - 1
        self.size_box.setCurrentIndex(index)

    # ------------------------------------------------------------------ colour
    def _set_color(self, value: str) -> None:
        self._color = value or ""
        if self._color:
            self.color_swatch.setText("")
            self.color_swatch.setStyleSheet(
                f"background: {self._color}; border: 1px solid {FIELD_LINE};"
                "border-radius: 6px;")
            self.color_swatch.setToolTip(f"Prints in {self._color}")
        else:
            self.color_swatch.setText("A")
            self.color_swatch.setStyleSheet(
                f"border: 1.5px dashed {FIELD_LINE}; border-radius: 6px;"
                f"color: {FAINT}; background: #ffffff;")
            self.color_swatch.setToolTip("Prints in the standard colour")
        self.color_clear.setEnabled(bool(self._color))

    def _choose_color(self) -> None:
        start = QColor(self._color) if self._color else QColor("#000000")
        picked = QColorDialog.getColor(start, self, "Colour for this text")
        if picked.isValid():
            self._set_color(picked.name())
            self._collect()

    def _clear_color(self) -> None:
        self._set_color("")
        self._collect()

    # ------------------------------------------------------------- collecting
    def _collect(self) -> None:
        """Read the controls back into the region they belong to."""
        if self._loading:
            return
        key = self.slot_key()
        align = next((value for value, button in self.align_buttons.items()
                      if button.isChecked()), "")
        style = TS.TextStyle(
            align=align,
            font=self.font_box.currentData() or "",
            size=self.size_box.currentData() or "",
            color=self._color,
            bold=TS.ON if self.effect_buttons["bold"].isChecked() else TS.OFF,
            italic=TS.ON if self.effect_buttons["italic"].isChecked() else TS.OFF,
            underline=(TS.ON if self.effect_buttons["underline"].isChecked()
                       else TS.OFF),
        )
        kept = TS.trimmed(key, style)
        if kept:
            self._styles[key] = kept
        else:
            self._styles.pop(key, None)
        self._refresh_state()
        self.changed.emit()

    def _reset_one(self) -> None:
        self._styles.pop(self.slot_key(), None)
        self._show_slot()
        self.changed.emit()

    def _reset_all(self) -> None:
        self._styles.clear()
        self._show_slot()
        self.changed.emit()


class _Holder:
    """Stands in for a LabProfile so `text_style` can read styles being edited.

    Everything in `text_style` reads its styling off `lab.text_styles`, which is
    exactly the right shape for the saved profile and the wrong shape for a
    half-finished edit. This is the one attribute it needs."""

    def __init__(self, styles):
        self.text_styles = styles
