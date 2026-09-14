"""Printer / preview / PDF output.

Each document names the page it belongs on, and every path - preview, printer,
exported PDF - is handed the same setup, so what you see in the preview is
exactly what comes out of the printer.

Two page setups, because the app prints two different documents. The report is a
clinical record that goes in a file: A4 portrait. The bill is a counter slip:
A5 landscape, which is literally half an A4 sheet, so a lab can print two to a
page and cut, or feed pre-cut A5 stock.
"""
from typing import NamedTuple

from PySide6.QtCore import QMarginsF, QSizeF, Qt
from PySide6.QtGui import (QFont, QKeySequence, QPageLayout, QPageSize,
                           QShortcut, QTextDocument)
from PySide6.QtPrintSupport import (QPrintDialog, QPrinter,
                                    QPrintPreviewWidget)
from PySide6.QtWidgets import (QDialog, QFrame, QHBoxLayout, QLabel,
                               QPushButton, QVBoxLayout)


class Page(NamedTuple):
    size: QPageSize.PageSizeId
    orientation: QPageLayout.Orientation
    margins: QMarginsF


REPORT_PAGE = Page(QPageSize.A4, QPageLayout.Portrait, QMarginsF(14, 13, 14, 13))

# Tighter margins than the report: an A5 slip has little enough room as it is,
# and the bill draws its own ruled frame, so the paper margin only has to clear
# the printer's unprintable edge.
BILL_PAGE = Page(QPageSize.A5, QPageLayout.Landscape, QMarginsF(8, 7, 8, 7))


def _configure(printer: QPrinter, page: Page = REPORT_PAGE) -> None:
    """Put the printer on the page this document belongs on.

    Two goes at it, because one is not enough. A Windows print driver can refuse
    a whole QPageLayout it does not recognise and say so only through a return
    value nobody used to read - and a refusal is silent and total: the printer
    keeps whatever it had, which is usually Letter portrait. That is how an A5
    landscape bill ended up coming out down the middle of a US Letter sheet on
    any machine whose default printer does not advertise A5.

    Setting the three properties one at a time is accepted where the combined
    layout is not, so it is the fallback rather than the first attempt: the
    single call is atomic where it works, and cannot leave a half-applied page
    behind.
    """
    if printer.setPageLayout(QPageLayout(
        QPageSize(page.size),
        page.orientation,
        page.margins,
        QPageLayout.Millimeter,
    )):
        return
    printer.setPageSize(QPageSize(page.size))
    printer.setPageOrientation(page.orientation)
    printer.setPageMargins(page.margins, QPageLayout.Millimeter)


def _document(html: str, printer: QPrinter) -> QTextDocument:
    doc = QTextDocument()
    # A named default font keeps metrics stable across machines; the document
    # margin is zeroed because the page layout above already owns the margins.
    doc.setDefaultFont(QFont("Segoe UI", 10))
    doc.setDocumentMargin(0)
    doc.setHtml(html)
    rect = printer.pageRect(QPrinter.Point)
    doc.setPageSize(QSizeF(rect.width(), rect.height()))
    return doc


def print_report(html: str, parent=None, title: str = "Print Blood Report",
                 page: Page = REPORT_PAGE) -> bool:
    """Show the Windows printer picker and print. Returns True if printed.

    `title` names the document in the dialog, because the app prints two of
    them - the report and the bill - and the operator needs to see which one
    is about to come out of the printer."""
    printer = QPrinter(QPrinter.HighResolution)
    _configure(printer, page)
    dialog = QPrintDialog(printer, parent)
    dialog.setWindowTitle(title)
    if dialog.exec() != QPrintDialog.Accepted:
        return False
    _document(html, printer).print_(printer)
    return True


# Zoom limits. A quarter size fits two A4 pages side by side on a laptop
# screen; eight times is enough to settle an argument about a decimal point.
ZOOM_MIN, ZOOM_MAX = 0.25, 8.0
ZOOM_STEP = 1.25


class PreviewDialog(QDialog):
    """Print preview, with zoom controls that are actually on the screen.

    Qt's own QPrintPreviewDialog puts its zoom controls in a toolbar of
    icon-only buttons whose images come from a resource bundle compiled into
    Qt's print-support plugin. When that bundle is absent - which is the normal
    outcome of a PyInstaller build, and what this app shipped - the buttons are
    still there but draw nothing, so the operator gets a preview that looks as
    though it cannot be zoomed at all.

    So the dialog is built here instead, around the same QPrintPreviewWidget Qt
    uses, with buttons that carry their own text. Text cannot go missing, and it
    also names what each control does for staff who have never used the app
    before - which is most of the people who use it.
    """

    def __init__(self, html: str, parent=None, title: str = "Print Preview",
                 page: Page = REPORT_PAGE):
        super().__init__(parent)
        self._html = html
        self.setWindowTitle(title)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)

        self.printer = QPrinter(QPrinter.HighResolution)
        _configure(self.printer, page)

        self.view = QPrintPreviewWidget(self.printer, self)
        self.view.paintRequested.connect(self._paint)
        # Fires whenever the widget re-lays the page out - including a window
        # resize while fitting - so the percentage never goes stale.
        self.view.previewChanged.connect(self._show_zoom)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addLayout(self._build_toolbar())
        layout.addWidget(self.view, 1)

        for keys, slot in (
            (QKeySequence.ZoomIn, self.zoom_in),
            ("Ctrl+=", self.zoom_in),      # the + key without a shift, as typed
            ("Ctrl++", self.zoom_in),
            (QKeySequence.ZoomOut, self.zoom_out),
            ("Ctrl+-", self.zoom_out),
            ("Ctrl+0", self.zoom_reset),
        ):
            QShortcut(QKeySequence(keys), self, activated=slot)

        self.resize(980, 900)
        self.view.fitInView()
        self._show_zoom()

    # -------------------------------------------------------------- toolbar
    def _build_toolbar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(6)

        def button(text: str, tip: str, slot, name: str = "") -> QPushButton:
            btn = QPushButton(text)
            btn.setToolTip(tip)
            btn.setObjectName(name)
            btn.setAutoDefault(False)     # or Enter would fire the first one
            btn.clicked.connect(slot)
            row.addWidget(btn)
            return btn

        self.zoom_out_button = button(
            "−  Zoom Out", "Show the page smaller (Ctrl and -)", self.zoom_out)
        self.zoom_label = QLabel("100%")
        self.zoom_label.setAlignment(Qt.AlignCenter)
        self.zoom_label.setMinimumWidth(62)
        self.zoom_label.setToolTip("Current zoom")
        row.addWidget(self.zoom_label)
        self.zoom_in_button = button(
            "+  Zoom In", "Show the page larger (Ctrl and +)", self.zoom_in)

        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Plain)
        separator.setFixedWidth(1)
        row.addWidget(separator)

        button("Fit Page", "Fit the whole page in the window", self.fit_page)
        button("Fit Width", "Fit the page across the window", self.fit_width)
        button("100%", "Actual size (Ctrl and 0)", self.zoom_reset)

        row.addStretch(1)
        button("Print...", "Send this to the printer", self.print_now, "Primary")
        button("Close", "Close the preview", self.reject)
        return row

    # ----------------------------------------------------------------- zoom
    def _paint(self, printer: QPrinter) -> None:
        _document(self._html, printer).print_(printer)

    def _show_zoom(self) -> None:
        self.zoom_label.setText(f"{round(self.view.zoomFactor() * 100)}%")
        # A control that cannot do anything says so rather than clicking dead.
        self.zoom_in_button.setEnabled(self.view.zoomFactor() < ZOOM_MAX)
        self.zoom_out_button.setEnabled(self.view.zoomFactor() > ZOOM_MIN)

    def set_zoom(self, factor: float) -> None:
        """Clamped, so a held-down key cannot zoom to a blank page either way."""
        self.view.setZoomFactor(max(ZOOM_MIN, min(ZOOM_MAX, factor)))
        self._show_zoom()

    def zoom_in(self) -> None:
        self.set_zoom(self.view.zoomFactor() * ZOOM_STEP)

    def zoom_out(self) -> None:
        self.set_zoom(self.view.zoomFactor() / ZOOM_STEP)

    def zoom_reset(self) -> None:
        self.set_zoom(1.0)

    def fit_page(self) -> None:
        self.view.fitInView()
        self._show_zoom()

    def fit_width(self) -> None:
        self.view.fitToWidth()
        self._show_zoom()

    # ---------------------------------------------------------------- print
    def print_now(self) -> bool:
        """Print what is being previewed, on the page setup it was previewed at.

        The operator is already looking at the thing they want on paper, so the
        preview offers the printer directly rather than making them close it and
        find the Print button again."""
        dialog = QPrintDialog(self.printer, self)
        dialog.setWindowTitle(self.windowTitle().replace("Preview", "Print").strip()
                              or "Print")
        if dialog.exec() != QPrintDialog.Accepted:
            return False
        _document(self._html, self.printer).print_(self.printer)
        self.accept()
        return True


def preview_report(html: str, parent=None, title: str = "Print Preview",
                   page: Page = REPORT_PAGE) -> None:
    PreviewDialog(html, parent, title, page).exec()


def export_pdf(html: str, path: str, page: Page = REPORT_PAGE) -> None:
    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(path)
    _configure(printer, page)
    _document(html, printer).print_(printer)
