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

from PySide6.QtCore import QMarginsF, QSizeF
from PySide6.QtGui import QFont, QPageLayout, QPageSize, QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter, QPrintPreviewDialog


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


def preview_report(html: str, parent=None, title: str = "Print Preview",
                   page: Page = REPORT_PAGE) -> None:
    printer = QPrinter(QPrinter.HighResolution)
    _configure(printer, page)
    dialog = QPrintPreviewDialog(printer, parent)
    dialog.setWindowTitle(title)
    dialog.resize(900, 950)
    dialog.paintRequested.connect(lambda p: _document(html, p, page).print_(p))
    dialog.exec()


def export_pdf(html: str, path: str, page: Page = REPORT_PAGE) -> None:
    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(path)
    _configure(printer, page)
    _document(html, printer, page).print_(printer)
