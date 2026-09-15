"""Test Templates: create and edit the panels offered on the New Report page."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from .. import billing, templates
from .. import validators as V
from . import icons
from .theme import ACCENT_DARK, DANGER, MUTED, S2, S3, SURFACE_ALT
from .widgets import Card, PageHeader, icon_button

KIND, NAME, UNIT, REF_M, REF_F = range(5)
COLS = ["Type", "Test / Heading", "Unit", "Range (Male)", "Range (Female)"]


class TemplatesView(QWidget):
    notify = Signal(str, str)
    panels_changed = Signal()

    def __init__(self):
        super().__init__()
        self.current_panel = ""
        self._loading = False
        self._dirty = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(S3)
        self.header = PageHeader(
            "Test Templates",
            "Build your own panels once - they appear on every new report")
        layout.addWidget(self.header)

        row = QHBoxLayout()
        row.setSpacing(S3)
        row.addWidget(self._build_panel_list(), 0)
        row.addWidget(self._build_editor(), 1)
        layout.addLayout(row, 1)

        self.reload()

    # ---------------------------------------------------------------- layout
    def _build_panel_list(self) -> Card:
        card = Card("Panels", elevated=False)
        card.setFixedWidth(300)

        self.panel_list = QListWidget()
        self.panel_list.setAlternatingRowColors(True)
        self.panel_list.currentItemChanged.connect(self._panel_selected)
        card.add(self.panel_list, 1)

        buttons = QHBoxLayout()
        buttons.setSpacing(S2)
        new = icon_button("plus", "New Panel", "Create an empty panel")
        new.clicked.connect(self.new_panel)
        buttons.addWidget(new, 1)

        # icon-only: three labelled buttons do not fit the rail's width, and Qt
        # elides them into "Renam" / "Remov"
        rename = icon_button("copy", "", "Rename this panel")
        rename.setFixedWidth(44)
        rename.clicked.connect(self.rename_panel)
        delete = icon_button("trash", "", "Remove this panel from new reports",
                             "Danger")
        delete.setFixedWidth(44)
        delete.clicked.connect(self.delete_panel)
        buttons.addWidget(rename)
        buttons.addWidget(delete)
        card.add(buttons)
        return card

    def _build_editor(self) -> Card:
        card = Card("Panel Contents",
                    "a heading is a section title - it has no result or range",
                    elevated=False)

        self.status = QLabel("")
        self.status.setObjectName("CardHint")
        card.add_header_widget(self.status)

        # The panel's standing charge. Typed once here, it fills the amount on
        # every bill that ticks the panel; the bill can still overwrite it.
        price_row = QHBoxLayout()
        price_row.setSpacing(S2)
        price_label = QLabel(f"Price ({billing.CURRENCY}):")
        price_label.setObjectName("FieldLabel")
        self.price = QLineEdit()
        self.price.setValidator(V.validator(V.AMOUNT_PATTERN, self))
        self.price.setMaxLength(10)
        self.price.setPlaceholderText("e.g. 250.00")
        self.price.setFixedWidth(140)
        self.price.textChanged.connect(self._mark_dirty_price)
        price_hint = QLabel("Charged automatically whenever this panel is added "
                            "to a report. Leave blank to type the amount each time.")
        price_hint.setObjectName("Hint")
        price_hint.setWordWrap(True)
        price_row.addWidget(price_label)
        price_row.addWidget(self.price)
        price_row.addWidget(price_hint, 1)
        card.add(price_row)

        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.verticalHeader().setVisible(True)   # Sl. No. down the side
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setSectionResizeMode(NAME, QHeaderView.Stretch)
        self.table.setColumnWidth(KIND, 88)
        self.table.setColumnWidth(UNIT, 110)
        self.table.setColumnWidth(REF_M, 150)
        self.table.setColumnWidth(REF_F, 150)
        self.table.horizontalHeader().setMinimumSectionSize(72)
        self.table.itemChanged.connect(self._mark_dirty)
        card.add(self.table, 1)

        buttons = QHBoxLayout()
        buttons.setSpacing(S2)
        for icon_name, text, tip, slot in (
            ("plus", "Test", "Add a test row to this panel", self.add_test),
            ("minus", "Sub-heading", "Add a section title", self.add_heading),
            ("trash", "Delete", "Remove the selected row", self.delete_row),
        ):
            button = icon_button(icon_name, text, tip)
            button.clicked.connect(slot)
            buttons.addWidget(button)

        # icon-only: the labels made the bar wider than the card and Qt then
        # elided every button's text
        for icon_name, tip, delta in (("chevron-up", "Move the selected row up", -1),
                                      ("chevron-down", "Move the selected row down", 1)):
            button = icon_button(icon_name, "", tip)
            button.setFixedWidth(42)
            button.clicked.connect(lambda _=False, d=delta: self.move_row(d))
            buttons.addWidget(button)

        buttons.addStretch(1)
        self.reset_button = icon_button(
            "refresh", "Reset", "Restore the tests this panel shipped with")
        self.reset_button.clicked.connect(self.reset_panel)
        buttons.addWidget(self.reset_button)

        save = icon_button("save", "Save Panel", "", "Primary")
        save.setIcon(icons.icon("save", "#ffffff", 17))
        save.clicked.connect(self.save_panel)
        buttons.addWidget(save)

        card.add(buttons)
        return card

    # ------------------------------------------------------------------ data
    def reload(self, select: str = ""):
        self._loading = True
        self.panel_list.clear()
        for name in templates.panel_names():
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, name)
            if templates.is_modified(name):
                item.setText(name + "   (edited)")
            elif not templates.is_builtin(name):
                item.setText(name + "   (yours)")
            self.panel_list.addItem(item)
        self._loading = False

        target = select or self.current_panel
        for i in range(self.panel_list.count()):
            if self.panel_list.item(i).data(Qt.UserRole) == target:
                self.panel_list.setCurrentRow(i)
                return
        if self.panel_list.count():
            self.panel_list.setCurrentRow(0)
        else:
            self.current_panel = ""
            self.table.setRowCount(0)

    def _panel_selected(self, current, _previous):
        if current is None or self._loading:
            return
        self.current_panel = current.data(Qt.UserRole)
        self.load_rows(templates.rows_for(self.current_panel))
        self._loading = True
        self.price.setText(templates.price_for(self.current_panel))
        self._loading = False
        builtin = templates.is_builtin(self.current_panel)
        self.reset_button.setEnabled(builtin)
        self.status.setText(
            "built-in panel" if builtin else "your own panel")
        self._dirty = False

    def load_rows(self, rows):
        self._loading = True
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self._write_row(r, row)
        self._loading = False

    def _write_row(self, r: int, row):
        heading = row.get("kind") == templates.HEADING
        values = ["Heading" if heading else "Test", row.get("name", ""),
                  row.get("unit", ""), row.get("ref_m", ""), row.get("ref_f", "")]
        for col, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            if col == KIND:
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            if heading and col in (UNIT, REF_M, REF_F):
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                item.setText("")
            self.table.setItem(r, col, item)
        if heading:
            self._tint_heading(r)

    def _tint_heading(self, r: int):
        from PySide6.QtGui import QBrush, QColor, QFont

        font = QFont()
        font.setBold(True)
        for col in range(self.table.columnCount()):
            item = self.table.item(r, col)
            item.setBackground(QBrush(QColor(SURFACE_ALT)))
            if col in (KIND, NAME):
                item.setFont(font)
                item.setForeground(QBrush(QColor(ACCENT_DARK)))

    def collect_rows(self):
        rows = []
        for r in range(self.table.rowCount()):
            name = (self.table.item(r, NAME).text() if self.table.item(r, NAME) else "").strip()
            if not name:
                continue
            if self._row_kind(r) == templates.HEADING:
                rows.append(templates.make_heading(name))
            else:
                rows.append(templates.make_test(
                    name,
                    (self.table.item(r, UNIT).text() if self.table.item(r, UNIT) else "").strip(),
                    (self.table.item(r, REF_M).text() if self.table.item(r, REF_M) else "").strip(),
                    (self.table.item(r, REF_F).text() if self.table.item(r, REF_F) else "").strip(),
                ))
        return rows

    def _row_kind(self, r: int) -> str:
        item = self.table.item(r, KIND)
        return templates.HEADING if item and item.text() == "Heading" else templates.TEST

    def _cell_problem(self, r: int, col: int):
        """The validation message for one editor cell, or None."""
        item = self.table.item(r, col)
        text = item.text() if item else ""
        heading = self._row_kind(r) == templates.HEADING
        if col == NAME:
            return V.check_test_name(
                text, "section title" if heading else "test name")
        if heading:
            return None            # a heading has no unit or range
        if col == UNIT:
            return V.check_unit(text)
        if col in (REF_M, REF_F):
            return V.check_reference(text)
        return None

    def _mark_cell(self, r: int, col: int):
        """Red text, not a tint - a stylesheet on ::item swallows background
        brushes set on the model."""
        from PySide6.QtGui import QBrush, QColor, QFont

        item = self.table.item(r, col)
        if item is None:
            return
        problem = self._cell_problem(r, col)
        heading = self._row_kind(r) == templates.HEADING
        font = QFont()
        font.setBold(bool(problem) or (heading and col in (KIND, NAME)))
        font.setItalic(bool(problem))
        item.setFont(font)
        if problem:
            item.setForeground(QBrush(QColor(DANGER)))
        elif heading and col in (KIND, NAME):
            item.setForeground(QBrush(QColor(ACCENT_DARK)))
        else:
            item.setForeground(QBrush(QColor("#000000")))
        item.setToolTip(problem or "")

    def _mark_dirty(self, item):
        if self._loading:
            return
        self._dirty = True
        self._mark_cell(item.row(), item.column())

    def _mark_dirty_price(self, _text):
        if not self._loading:
            self._dirty = True

    # --------------------------------------------------------------- actions
    def add_test(self):
        self._append(templates.make_test("New Test", "", "", ""))

    def add_heading(self):
        self._append(templates.make_heading("NEW SECTION"))

    def _append(self, row):
        self._loading = True
        r = self.table.rowCount()
        self.table.insertRow(r)
        self._write_row(r, row)
        self._loading = False
        self._dirty = True
        self.table.setCurrentCell(r, NAME)
        self.table.editItem(self.table.item(r, NAME))

    def delete_row(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        if not rows:
            self.notify.emit("Select a row to delete.", "warning")
            return
        for r in rows:
            self.table.removeRow(r)
        self._dirty = True

    def move_row(self, delta: int):
        r = self.table.currentRow()
        target = r + delta
        if r < 0 or not 0 <= target < self.table.rowCount():
            return
        rows = self.collect_rows()
        if not 0 <= r < len(rows):
            return
        rows[r], rows[target] = rows[target], rows[r]
        self.load_rows(rows)
        self.table.setCurrentCell(target, NAME)
        self._dirty = True

    def new_panel(self):
        name, ok = QInputDialog.getText(self, "New panel", "Name of the new test panel:")
        name = (name or "").strip()
        if not ok or not name:
            return
        problem = V.check_test_name(name, "panel name")
        if problem:
            self.notify.emit(problem, "warning")
            return
        if name in templates.panel_names():
            self.notify.emit(f"A panel called '{name}' already exists.", "warning")
            return
        templates.create_panel(name, [templates.make_test("New Test", "", "", "")])
        self.panels_changed.emit()
        self.reload(select=name)
        self.notify.emit(f"Panel '{name}' created. Add its tests, then Save Panel.",
                         "success")

    def rename_panel(self):
        if not self.current_panel:
            return
        name, ok = QInputDialog.getText(self, "Rename panel", "New name:",
                                        text=self.current_panel)
        name = (name or "").strip()
        if not ok or not name or name == self.current_panel:
            return
        problem = V.check_test_name(name, "panel name")
        if problem:
            self.notify.emit(problem, "warning")
            return
        if name in templates.panel_names():
            self.notify.emit(f"A panel called '{name}' already exists.", "warning")
            return

        was_builtin = templates.is_builtin(self.current_panel)
        templates.rename_panel(self.current_panel, name)
        self.panels_changed.emit()
        self.reload(select=name)
        self.notify.emit(
            f"Renamed to '{name}'." + (" The built-in panel was replaced by your copy."
                                       if was_builtin else ""), "success")

    def delete_panel(self):
        if not self.current_panel:
            return
        builtin = templates.is_builtin(self.current_panel)
        message = (f"Remove '{self.current_panel}' from the New Report page?\n\n"
                   + ("It is a built-in panel, so you can bring it back later with "
                      "Restore All Built-ins." if builtin
                      else "This panel is yours and cannot be recovered."))
        if QMessageBox.question(self, "Remove panel", message,
                                QMessageBox.Yes | QMessageBox.No,
                                QMessageBox.No) != QMessageBox.Yes:
            return
        gone = self.current_panel
        templates.delete_panel(gone)
        self.current_panel = ""
        self.panels_changed.emit()
        self.reload()
        self.notify.emit(f"'{gone}' removed.", "success")

    def reset_panel(self):
        if not templates.reset_panel(self.current_panel):
            self.notify.emit("Only built-in panels have a default to restore.",
                             "warning")
            return
        self.panels_changed.emit()
        self.reload(select=self.current_panel)
        self.notify.emit(f"'{self.current_panel}' restored to its original tests.",
                         "success")

    def save_panel(self):
        if not self.current_panel:
            return
        for r in range(self.table.rowCount()):
            for col in (NAME, UNIT, REF_M, REF_F):
                problem = self._cell_problem(r, col)
                if problem:
                    self.notify.emit(f"Row {r + 1}: {problem}", "warning")
                    self.table.setCurrentCell(r, col)
                    return

        rows = self.collect_rows()
        if not rows:
            self.notify.emit("Add at least one test before saving.", "warning")
            return
        if not any(r["kind"] == templates.TEST for r in rows):
            self.notify.emit("A panel needs at least one test, not only headings.",
                             "warning")
            return
        price = self.price.text().strip()
        problem = V.check_amount(price, "price") if price else None
        if problem:
            self.notify.emit(problem, "warning")
            self.price.setFocus()
            return
        templates.save_panel(self.current_panel, rows)
        templates.set_price(self.current_panel, price)
        self._dirty = False
        self.panels_changed.emit()
        self.reload(select=self.current_panel)
        self.notify.emit(
            f"'{self.current_panel}' saved - {len(rows)} row(s). "
            "New reports will use it from now on.", "success")
