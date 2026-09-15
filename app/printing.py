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
from PySide6.QtGui import QFont, QKeySequence, QPageLayout, QPageSize, QShortcut, QTextDocument
from PySide6.QtPrintSupport import (QPrintDialog, QPrinter, QPrintPreviewDialog,
                                    QPrintPreviewWidget)
from PySide6.QtWidgets import QLabel, QMainWindow, QToolBar


class Page(NamedTuple):
    size: QPageSize.PageSizeId
    orientation: QPageLayout.Orientation
    margins: QMarginsF
    # The document's base font. Qt sizes every table row by this, whatever
    # the stylesheet says, so it is what decides how many rows fit a page.
    font_pt: float = 10


REPORT_PAGE = Page(QPageSize.A4, QPageLayout.Portrait, QMarginsF(12, 8, 12, 8), 8)

# Tighter margins than the report: an A5 slip has little enough room as it is,
# and the bill draws its own ruled frame, so the paper margin only has to clear
# the printer's unprintable edge.
BILL_PAGE = Page(QPageSize.A5, QPageLayout.Landscape, QMarginsF(8, 7, 8, 7))


def _configure(printer: QPrinter, page: Page = REPORT_PAGE) -> None:
    printer.setPageLayout(QPageLayout(
        QPageSize(page.size),
        page.orientation,
        page.margins,
        QPageLayout.Millimeter,
    ))


def _document(html: str, printer: QPrinter, page: Page = REPORT_PAGE) -> QTextDocument:
    doc = QTextDocument()
    # A named default font keeps metrics stable across machines; the document
    # margin is zeroed because the page layout above already owns the margins.
    font = QFont("Segoe UI")
    font.setPointSizeF(page.font_pt)
    doc.setDefaultFont(font)
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
    _document(html, printer, page).print_(printer)
    return True


# How much one press of Zoom In / Zoom Out changes the preview by.
ZOOM_STEP = 1.25


def add_zoom_bar(dialog: QPrintPreviewDialog) -> QToolBar:
    """A plain, labelled zoom bar on the preview: Zoom In, Zoom Out, Fit Page,
    Fit Width, and the current zoom as a percentage.

    Qt's own preview toolbar has zoom on it, but as small unlabelled icons in
    a row of a dozen others, and the operators asked for something they could
    find. Ctrl + / Ctrl - / Ctrl 0 do the same from the keyboard, and Ctrl +
    mouse wheel already zooms the page itself."""
    preview = dialog.findChild(QPrintPreviewWidget)
    bar = QToolBar("Zoom", dialog)
    bar.setObjectName("ZoomBar")
    bar.setMovable(False)
    bar.setToolButtonStyle(Qt.ToolButtonTextOnly)

    percent = QLabel("")
    percent.setMinimumWidth(56)
    percent.setAlignment(Qt.AlignCenter)

    def show_zoom():
        percent.setText(f"{preview.zoomFactor() * 100:.0f}%")

    def zoom_in():
        preview.zoomIn(ZOOM_STEP)
        show_zoom()

    def zoom_out():
        preview.zoomOut(ZOOM_STEP)
        show_zoom()

    def fit_page():
        preview.fitInView()
        show_zoom()

    def fit_width():
        preview.fitToWidth()
        show_zoom()

    for text, tip, keys, slot in (
        ("Zoom Out  −", "Make the page smaller (Ctrl -)", QKeySequence.ZoomOut, zoom_out),
        ("Zoom In  +", "Make the page larger (Ctrl +)", QKeySequence.ZoomIn, zoom_in),
        ("Fit Page", "Show the whole page (Ctrl 0)", "Ctrl+0", fit_page),
        ("Fit Width", "Fill the window's width", "", fit_width),
    ):
        action = bar.addAction(text, slot)
        action.setToolTip(tip)
        if keys:
            action.setShortcut(QKeySequence(keys))
            # A second, dialog-wide binding: a QAction on a toolbar only fires
            # while the toolbar's window has focus, and the preview canvas
            # steals it as soon as the operator scrolls.
            QShortcut(QKeySequence(keys), dialog, slot)
    bar.addSeparator()
    bar.addWidget(percent)
    preview.previewChanged.connect(show_zoom)

    # The preview dialog is a QMainWindow inside a QDialog, and the main
    # window is where toolbars go; it has no public accessor, so it is looked
    # up. If a Qt build ever hides it, the bar goes above the dialog instead.
    window = dialog.findChild(QMainWindow)
    if window is not None:
        window.addToolBarBreak(Qt.TopToolBarArea)
        window.addToolBar(Qt.TopToolBarArea, bar)
    else:
        dialog.layout().insertWidget(0, bar)
    show_zoom()
    return bar


def preview_report(html: str, parent=None, title: str = "Print Preview",
                   page: Page = REPORT_PAGE) -> None:
    printer = QPrinter(QPrinter.HighResolution)
    _configure(printer, page)
    dialog = QPrintPreviewDialog(printer, parent)
    dialog.setWindowTitle(title)
    dialog.resize(900, 950)
    dialog.paintRequested.connect(lambda p: _document(html, p, page).print_(p))
    add_zoom_bar(dialog)
    dialog.exec()


def export_pdf(html: str, path: str, page: Page = REPORT_PAGE) -> None:
    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(path)
    _configure(printer, page)
    _document(html, printer, page).print_(printer)
