"""Application shell: sidebar rail on the left, one page at a time on the right."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMainWindow, QMessageBox, QStackedWidget, QVBoxLayout,
    QWidget,
)

from .. import storage
from ..branding import (APP_NAME, APP_TAGLINE, APP_VERSION, NAV_TAGLINE,
                        ORIGIN, VENDOR, footer_meta)
from .history_view import HistoryView
from .report_form import ReportForm
from .settings_view import SettingsView
from .templates_view import TemplatesView
from .sidebar import Sidebar
from .theme import S2, S3, S4
from .toast import Toast

NEW, HISTORY, TEMPLATES, SETTINGS = 0, 1, 2, 3


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} - {APP_TAGLINE}")
        self.setMinimumSize(1080, 640)
        self._fit_to_screen(1280, 860)

        self.form = ReportForm()
        self.history = HistoryView()
        self.settings = SettingsView()
        self.templates = TemplatesView()

        self.stack = QStackedWidget()
        for page in (self.form, self.history, self.templates, self.settings):
            self.stack.addWidget(page)

        self.nav = Sidebar(APP_NAME, NAV_TAGLINE, APP_VERSION)
        self.nav.navigated.connect(self.go_to)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(S4, S4, S4, S3)
        # The stack takes the stretch and the footer sits under it, outside the
        # stack, so one footer serves all four pages rather than each page
        # carrying its own copy.
        body_layout.addWidget(self.stack, 1)
        body_layout.addWidget(self._build_footer())

        central = QWidget()
        central.setObjectName("Canvas")
        row = QHBoxLayout(central)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(self.nav)
        row.addWidget(body, 1)
        self.setCentralWidget(central)

        self.toast = Toast(self)

        self.form.saved.connect(self._on_saved)
        self.form.notify.connect(self.toast.show_message)
        self.history.notify.connect(self.toast.show_message)
        self.settings.notify.connect(self.toast.show_message)
        self.templates.notify.connect(self.toast.show_message)
        self.templates.panels_changed.connect(self.form.refresh_panels)
        self.history.open_requested.connect(self._on_open_requested)
        self.history.reports_deleted.connect(self._on_reports_deleted)
        self.settings.profile_saved.connect(self._on_profile_saved)
        self.stack.currentChanged.connect(self._page_changed)

        self._build_menu()
        self.statusBar().addPermanentWidget(QLabel(f"Data folder: {storage.app_dir()}   "))
        self._refresh_lab_name()
        self._prompt_first_run()

    # ---------------------------------------------------------------- footer
    def _build_footer(self) -> QWidget:
        """Vendor name over version / origin / release stage, centred.

        Deliberately quiet: it is a signature, not a control, so it is small,
        muted and never competes with the page above it."""
        holder = QWidget()
        holder.setObjectName("Bare")
        column = QVBoxLayout(holder)
        column.setContentsMargins(0, S2, 0, 0)
        column.setSpacing(0)

        name = QLabel(VENDOR)
        name.setObjectName("AppFooterName")
        name.setAlignment(Qt.AlignCenter)

        meta = QLabel(footer_meta())
        meta.setObjectName("AppFooterMeta")
        meta.setAlignment(Qt.AlignCenter)
        meta.setToolTip(f"{APP_NAME} {APP_VERSION} - {ORIGIN}")

        column.addWidget(name)
        column.addWidget(meta)
        return holder

    # ------------------------------------------------------------------ menu
    def _build_menu(self):
        file_menu = self.menuBar().addMenu("&File")
        # The report actions belong to the New Report page. Pressed from
        # History or Templates they used to clear / print a form nobody could
        # see, so each one now brings that page forward first.
        for text, shortcut, slot in (
            ("&New Report", QKeySequence.New, self._on_form(self.form.clear_clicked)),
            ("&Save", QKeySequence.Save, self.save_current),
            ("Print Pre&view", "Ctrl+Shift+P", self._on_form(self.form.preview)),
            ("&Print", QKeySequence.Print, self._on_form(self.form.print_report)),
            ("Bill Previe&w", "Ctrl+Shift+B", self._on_form(self.form.preview_bill)),
            ("Print &Bill", "Ctrl+B", self._on_form(self.form.print_bill)),
        ):
            action = QAction(text, self)
            action.setShortcut(shortcut)
            action.triggered.connect(slot)
            file_menu.addAction(action)
        file_menu.addSeparator()

        backup = QAction("Open &Backup Folder (Google Drive)", self)
        backup.setToolTip("Show the folder your saved reports are copied into.")
        backup.triggered.connect(self._open_backup_folder)
        file_menu.addAction(backup)

        rebuild = QAction("Rebuild History Index", self)
        rebuild.setToolTip("Re-scan the reports folder if the history list looks wrong.")
        rebuild.triggered.connect(self._rebuild_index)
        file_menu.addAction(rebuild)

        quit_action = QAction("E&xit", self)
        quit_action.setShortcut(QKeySequence.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        go_menu = self.menuBar().addMenu("&Go")
        for i, (label, key) in enumerate((("&New Report", "Ctrl+1"),
                                          ("Report &History", "Ctrl+2"),
                                          ("&Test Templates", "Ctrl+3"),
                                          ("&Laboratory Profile", "Ctrl+4"))):
            action = QAction(label, self)
            action.setShortcut(key)
            action.triggered.connect(lambda _=False, index=i: self.go_to(index))
            go_menu.addAction(action)

    def _on_form(self, slot):
        def run(*_):
            self.go_to(NEW)
            slot()
        return run

    def _fit_to_screen(self, width: int, height: int):
        """Open at the preferred size, but never bigger than the screen.

        860 px is taller than a 1366x768 laptop once the taskbar is counted, so
        the window opened with its bottom - the footer and the pinned Save
        buttons - hidden under the taskbar."""
        screen = self.screen()
        if screen is not None:
            area = screen.availableGeometry()
            if area.width() > 0 and area.height() > 0:
                # leave room for the title bar, which the frame adds on top
                width = min(width, area.width())
                height = min(height, area.height() - 40)
                # A 768-px screen leaves ~688 px; a fixed 700-px minimum would
                # push the bottom back under the taskbar, so the minimum
                # gives way to the screen too.
                self.setMinimumSize(min(self.minimumWidth(), area.width()),
                                    min(self.minimumHeight(), height))
        self.resize(max(width, self.minimumWidth()),
                    max(height, self.minimumHeight()))

    def save_current(self):
        """Ctrl+S saves the page you are looking at.

        It was wired to the report form alone, so pressing it on Laboratory
        Profile quietly saved (or complained about) a half-typed report on a
        page nobody could see, and the profile itself stayed unsaved."""
        if self.stack.currentIndex() == SETTINGS:
            self.settings.save()
        elif self.stack.currentIndex() == TEMPLATES:
            # same trap on Test Templates: Ctrl+S there means Save Panel
            self.templates.save_panel()
        elif self.stack.currentIndex() == HISTORY:
            # History has nothing to save; saving the hidden form from here
            # would be a surprise, so say where Ctrl+S works instead.
            self.toast.show_message(
                "Nothing to save on this page. Open a report first, then "
                "press Ctrl+S on the New Report page.", "info")
        else:
            self.form.save()

    def closeEvent(self, event):
        """Ask before throwing away an unsaved Laboratory Profile.

        Only when the window is on screen: a window nobody can see has nobody
        to answer the question."""
        try:
            self._confirm_close(event)
        except Exception:
            # Anything going wrong while asking must keep the window open:
            # closing anyway is exactly how unsaved edits get lost.
            event.ignore()

    def _confirm_close(self, event):
        if self.isVisible() and self.settings.has_unsaved_changes():
            self.go_to(SETTINGS)
            choice = QMessageBox.question(
                self, "Unsaved Laboratory Profile",
                "The Laboratory Profile has changes that are not saved yet.\n\n"
                "Save them before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save)
            if choice == QMessageBox.Cancel:
                event.ignore()
                return
            if choice == QMessageBox.Save:
                if not self.settings.save() or self.settings.has_unsaved_changes():
                    # save() refused and already said why in a toast
                    event.ignore()
                    return
        if self.isVisible() and self.templates.has_unsaved_changes():
            # An edited test panel was lost on close just as silently.
            self.go_to(TEMPLATES)
            choice = QMessageBox.question(
                self, "Unsaved test panel",
                f"The panel '{self.templates.current_panel}' has changes that "
                "are not saved yet.\n\nSave them before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save)
            if choice == QMessageBox.Cancel:
                event.ignore()
                return
            if choice == QMessageBox.Save:
                self.templates.save_panel()
                if self.templates.has_unsaved_changes():
                    event.ignore()   # refused; the toast said why
                    return
        super().closeEvent(event)

    # ------------------------------------------------------------- navigation
    def go_to(self, index: int):
        self.stack.setCurrentIndex(index)
        self.nav.set_current(index)

    def new_report(self):
        self.form.new_report()
        self.go_to(NEW)

    def _page_changed(self, index: int):
        if index == HISTORY:
            self.history.reload()

    # --------------------------------------------------------------- handlers
    def _refresh_lab_name(self):
        name = storage.load_profile().lab_name
        self.form.set_lab_name(name)
        self.history.set_lab_name(name)

    def _on_saved(self):
        self.history.reload()
        self.statusBar().showMessage(
            f"Saved report {self.form.current_report_no}.", 5000)

    def _on_profile_saved(self):
        self._refresh_lab_name()
        self.toast.show_message("Laboratory profile saved.", "success")

    def _on_open_requested(self, report, as_copy):
        self.form.load_report(report, as_copy)
        self.go_to(NEW)
        self.toast.show_message(
            ("Duplicated " if as_copy else "Opened ") + report.report_no, "info")

    def _on_reports_deleted(self, deleted_ids):
        """A report open in the form must not survive being deleted from
        History - otherwise saving it again would silently bring it back."""
        if self.form.forget_if_deleted(deleted_ids):
            self.toast.show_message(
                "The report open in the form was deleted - the form has been reset.",
                "warning", 6000)

    def _open_backup_folder(self):
        if not storage.open_backup_folder():
            self.toast.show_message("No backup folder is set. Choose one in Laboratory "
                            "Profile > Backup Folder.", "warning")

    def _rebuild_index(self):
        entries = storage.rebuild_index()
        self.history.reload()
        self.toast.show_message(
            f"History index rebuilt - {len(entries)} report(s) found.", "success")

    def _prompt_first_run(self):
        if not storage.load_profile().lab_name:
            self.go_to(SETTINGS)
            self.statusBar().showMessage(
                "Set up your laboratory profile first - it appears on every report.",
                12000)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.toast.reposition()
