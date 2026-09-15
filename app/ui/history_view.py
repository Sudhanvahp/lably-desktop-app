"""Past reports browser, driven by the cached index so it opens instantly."""
from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QStackedWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from .. import printing, storage
from ..report_html import build
from ..util import safe_filename
from . import icons
from .theme import MUTED, S2, S3
from .widgets import Card, EmptyState, PageHeader, StatTile, icon_button

CHECK, REPORT_NO, PATIENT_ID, DATE, PATIENT, AGE_SEX, DOCTOR, PANELS = range(8)
COLS = ["", "Report No", "Patient ID", "Date", "Patient", "Age / Sex",
        "Referred By", "Panels"]

LIST_PAGE, EMPTY_PAGE, NO_MATCH_PAGE = 0, 1, 2


class HistoryView(QWidget):
    open_requested = Signal(object, bool)     # (Report, as_copy)
    reports_deleted = Signal(list)            # ids that were removed
    notify = Signal(str, str)                 # (message, kind)

    def __init__(self):
        super().__init__()
        self.entries = []
        self._filling = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(S3)

        self.header = PageHeader("Report History", "Every report you have saved")
        layout.addWidget(self.header)
        # Search first: it is what the page is for. The tiles are a glance.
        layout.addLayout(self._build_search())
        layout.addLayout(self._build_stats())
        layout.addWidget(self._build_list_card(), 1)

        self.reload()

    def set_lab_name(self, name: str):
        self.header.set_subtitle(
            f"{name} - every report you have saved" if name
            else "Every report you have saved")

    # ---------------------------------------------------------------- layout
    def _build_search(self) -> QHBoxLayout:
        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "Search by patient name, patient ID, report no. or referring doctor")
        self.search.setClearButtonEnabled(True)
        self.search.addAction(icons.icon("search", MUTED, 16), QLineEdit.LeadingPosition)
        self.search.textChanged.connect(self._refill)
        self.search.setMinimumHeight(40)

        refresh = icon_button("refresh", "Refresh", "Re-read the reports folder")
        refresh.clicked.connect(self.reload)

        top = QHBoxLayout()
        top.setSpacing(S2)
        top.addWidget(self.search, 1)
        top.addWidget(refresh)
        return top

    def _build_stats(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(S3)
        self.stat_total = StatTile("Total reports")
        self.stat_today = StatTile("Saved today")
        self.stat_patients = StatTile("Patients")
        for tile in (self.stat_total, self.stat_today, self.stat_patients):
            tile.setMinimumWidth(170)
            row.addWidget(tile)
        row.addStretch(1)
        return row

    def _build_list_card(self) -> Card:
        card = Card("Saved Reports", elevated=False)

        self.count = QLabel("")
        self.count.setObjectName("CardHint")
        card.add_header_widget(self.count)

        self.table = self._build_table()
        self.empty = EmptyState(
            "history", "No reports yet",
            "Saved reports appear here. Create one from the New Report page.")
        self.no_match = EmptyState(
            "search", "No matches",
            "No saved report matches that search. Try a different name or number.")

        self.pages = QStackedWidget()
        for page in (self.table, self.empty, self.no_match):
            self.pages.addWidget(page)
        card.add(self.pages, 1)

        card.add(self._build_action_bar())
        return card

    def _build_table(self) -> QTableWidget:
        table = QTableWidget(0, len(COLS))
        table.setHorizontalHeaderLabels(COLS)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.verticalHeader().setVisible(True)   # Sl. No. down the side
        table.verticalHeader().setDefaultSectionSize(38)
        table.horizontalHeader().setSectionResizeMode(CHECK, QHeaderView.Fixed)
        table.setColumnWidth(CHECK, 58)
        table.horizontalHeader().setSectionResizeMode(PATIENT, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(PANELS, QHeaderView.Stretch)
        table.horizontalHeader().setHighlightSections(False)
        table.doubleClicked.connect(self._double_clicked)
        table.itemChanged.connect(self._item_changed)
        return table

    def _build_action_bar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(S2)

        self.select_all = QCheckBox("Select all")
        self.select_all.setToolTip("Tick every report currently listed")
        self.select_all.clicked.connect(self._toggle_all)
        row.addWidget(self.select_all)

        self.selection_label = QLabel("")
        self.selection_label.setObjectName("Hint")
        row.addWidget(self.selection_label)

        self.delete_selected_btn = icon_button(
            "trash", "Delete Selected", "Permanently delete the ticked reports", "Danger")
        self.delete_selected_btn.setEnabled(False)
        self.delete_selected_btn.clicked.connect(self.delete_checked)
        row.addWidget(self.delete_selected_btn)

        row.addStretch(1)
        # Same switch as the form: a reprint is the lab report alone unless
        # the operator asks for the bill summary on the same sheet.
        self.attach_bill = QCheckBox("Attach bill summary")
        self.attach_bill.setToolTip(
            "Print the bill summary under the results when previewing, "
            "exporting or reprinting")
        row.addWidget(self.attach_bill)
        for icon_name, text, tip, slot, kind in (
            ("copy", "Duplicate", "Same patient, blank results", self.duplicate_selected, "Danger"),
            ("preview", "Preview", "See it before printing", self.preview_selected, ""),
            ("pdf", "Export PDF", "Save as a PDF file", self.export_selected, ""),
            ("printer", "Reprint", "Send to the printer again", self.print_selected, ""),
            ("open", "Open", "Load it back into the form", self.open_selected, "Primary"),
        ):
            button = icon_button(icon_name, text, tip, kind)
            if kind == "Primary":
                button.setIcon(icons.icon(icon_name, "#ffffff", 17))
            button.clicked.connect(slot)
            row.addWidget(button)
        return row

    # ------------------------------------------------------------------ data
    def reload(self):
        self.entries = list(storage.load_index())
        self._refill()

    def _visible_entries(self):
        term = self.search.text().strip().lower()
        if not term:
            return list(self.entries)
        fields = ("patient_name", "report_no", "patient_id", "referred_by")
        return [e for e in self.entries
                if any(term in str(e.get(f, "")).lower() for f in fields)]

    def _refill(self):
        self._filling = True
        rows = self._visible_entries()
        self.table.setRowCount(len(rows))
        for r, e in enumerate(rows):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            check.setCheckState(Qt.Unchecked)
            check.setData(Qt.UserRole, e.get("id", ""))
            self.table.setItem(r, CHECK, check)

            values = {
                REPORT_NO: e.get("report_no", ""),
                PATIENT_ID: e.get("patient_id", ""),
                DATE: e.get("reported_on") or str(e.get("created_at", "")).replace("T", " "),
                PATIENT: e.get("patient_name", ""),
                AGE_SEX: " / ".join(x for x in (e.get("age", ""), e.get("sex", "")) if x),
                DOCTOR: e.get("referred_by", ""),
                PANELS: ", ".join(p.split("(")[0].strip() for p in e.get("panels", [])),
            }
            for col, value in values.items():
                self.table.setItem(r, col, QTableWidgetItem(str(value)))

        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(CHECK, 58)
        self.table.horizontalHeader().setSectionResizeMode(PATIENT, QHeaderView.Stretch)
        self.count.setText(f"{len(rows)} of {len(self.entries)} shown")
        self._filling = False
        self._show_right_page(len(rows))
        self._refresh_stats()
        self._selection_changed()

    def _show_right_page(self, visible: int):
        """A blank grid tells the operator nothing; say which kind of empty it is."""
        if visible:
            self.pages.setCurrentIndex(LIST_PAGE)
        elif self.entries:
            self.pages.setCurrentIndex(NO_MATCH_PAGE)
        else:
            self.pages.setCurrentIndex(EMPTY_PAGE)

    def _refresh_stats(self):
        today = date.today().isoformat()
        self.stat_total.set_value(len(self.entries))
        self.stat_today.set_value(
            sum(1 for e in self.entries
                if str(e.get("created_at", "")).startswith(today)))
        self.stat_patients.set_value(
            len({e.get("patient_id") for e in self.entries if e.get("patient_id")}))

    # ------------------------------------------------------------- selection
    def checked_ids(self):
        ids = []
        for r in range(self.table.rowCount()):
            item = self.table.item(r, CHECK)
            if item is not None and item.checkState() == Qt.Checked:
                ids.append(item.data(Qt.UserRole))
        return ids

    def _toggle_all(self):
        """Ticks only what is currently listed, so a search term scopes the action."""
        state = Qt.Checked if self.select_all.isChecked() else Qt.Unchecked
        self._filling = True
        for r in range(self.table.rowCount()):
            item = self.table.item(r, CHECK)
            if item is not None:
                item.setCheckState(state)
        self._filling = False
        self._selection_changed()

    def _item_changed(self, item):
        if not self._filling and item.column() == CHECK:
            self._selection_changed()

    def _selection_changed(self):
        n = len(self.checked_ids())
        total = self.table.rowCount()
        self.delete_selected_btn.setEnabled(n > 0)
        self.delete_selected_btn.setText(
            f"Delete Selected ({n})" if n else "Delete Selected")
        self.selection_label.setText(f"{n} selected" if n else "")
        self.select_all.blockSignals(True)
        self.select_all.setChecked(bool(total) and n == total)
        self.select_all.blockSignals(False)

    # --------------------------------------------------------------- helpers
    def _double_clicked(self, index):
        if index.column() != CHECK:
            self.open_selected()

    def _selected_report(self):
        r = self.table.currentRow()
        if r < 0:
            self.notify.emit("Select a report from the list first.", "warning")
            return None
        item = self.table.item(r, CHECK)
        report = storage.load_report(item.data(Qt.UserRole)) if item else None
        if report is None:
            self.notify.emit("That report file could not be read.", "error")
            self.reload()
        return report

    def _html(self, report):
        return build(report, storage.load_profile(),
                     with_bill=self.attach_bill.isChecked())

    # --------------------------------------------------------------- actions
    def open_selected(self):
        report = self._selected_report()
        if report:
            self.open_requested.emit(report, False)

    def duplicate_selected(self):
        report = self._selected_report()
        if report:
            self.open_requested.emit(report, True)

    def preview_selected(self):
        report = self._selected_report()
        if report:
            printing.preview_report(self._html(report), self)

    def print_selected(self):
        report = self._selected_report()
        if not report:
            return
        if printing.print_report(self._html(report), self):
            self.notify.emit(f"Report {report.report_no} sent to the printer.", "success")

    def export_selected(self):
        report = self._selected_report()
        if not report:
            return
        default = safe_filename(f"{report.report_no}_{report.patient_name}") + ".pdf"
        path, _ = QFileDialog.getSaveFileName(self, "Export PDF", default, "PDF (*.pdf)")
        if path:
            printing.export_pdf(self._html(report), path)
            self.notify.emit(f"PDF exported to {path}", "success")

    def delete_checked(self):
        ids = self.checked_ids()
        if not ids:
            self.notify.emit("Tick the reports you want to delete first.", "warning")
            return

        if len(ids) == 1:
            report = storage.load_report(ids[0])
            what = (f"{report.report_no} ({report.patient_name})"
                    if report else "this report")
            question = f"Permanently delete {what}?"
        else:
            question = f"Permanently delete these {len(ids)} reports?"

        confirm = QMessageBox.question(
            self, "Delete reports",
            f"{question}\n\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        # Deleting a finished report is as irreversible as editing one, so it
        # sits behind the same password gate.
        from .password_dialog import request_unlock

        what = ("delete this report" if len(ids) == 1
                else f"delete these {len(ids)} reports")
        if not request_unlock(self, what):
            self.notify.emit("Nothing was deleted.", "info")
            return

        removed = storage.delete_reports(ids)
        self.reload()
        self.reports_deleted.emit(ids)
        self.notify.emit(
            f"{removed} report{'s' if removed != 1 else ''} deleted.", "success")
