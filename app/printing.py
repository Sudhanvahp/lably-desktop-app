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
from PySide6.QtGui import (QFont, QKeySequence, QPageLayout, QPageSize, QShortcut,
                           QTextDocument, QTextTable)
from PySide6.QtPrintSupport import (QPrintDialog, QPrinter, QPrintPreviewDialog,
                                    QPrintPreviewWidget)
from PySide6.QtWidgets import QLabel, QMainWindow, QToolBar

from . import report_html


class Page(NamedTuple):
    size: QPageSize.PageSizeId
    orientation: QPageLayout.Orientation
    margins: QMarginsF
    # The document's base font. Qt sizes every table row by this, whatever
    # the stylesheet says, so it is what decides how many rows fit a page.
    font_pt: float = 10


# 6mm top and bottom rather than 8mm: the letterhead sets the lab name and its
# sub-heading at the same size, and a full panel with its bill and signatures
# still has to come out on one sheet. 6mm clears the unprintable edge on the
# office lasers this prints to, and the side margins are left wide.
REPORT_PAGE = Page(QPageSize.A4, QPageLayout.Portrait, QMarginsF(12, 6, 12, 6), 8)

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


def _laid_out(html: str, size: QSizeF, page: Page) -> QTextDocument:
    doc = QTextDocument()
    # A named default font keeps metrics stable across machines; the document
    # margin is zeroed because the page layout above already owns the margins.
    font = QFont("Segoe UI")
    font.setPointSizeF(page.font_pt)
    doc.setDefaultFont(font)
    doc.setDocumentMargin(0)
    doc.setHtml(html)
    doc.setPageSize(size)
    return doc


# Left clear under the pushed-down footer so a rounding error of a point or
# two cannot tip it onto a page of its own.
FOOT_CLEARANCE_PT = 3.0

# How many times the padding is refined. A spacer does not render at exactly
# its own point size - the line box around it is taller - so the gap cannot be
# computed in one go; it is closed in on instead. Ten passes settle a full
# sheet to under a quarter of a point, and a pass is a relayout of one page.
FOOT_PASSES = 10


def _footer_at_foot(html: str, size: QSizeF, page: Page) -> str:
    """Lay the document out repeatedly to drop the footer onto the foot of the
    last sheet.

    Qt's rich text has no `position: fixed`, so the only way to pin the footer
    down is to fill the gap above it. The first pass measures how much of the
    sheet is empty; each pass after that tries a padding and keeps it if the
    document still runs to the same number of pages, closing in on the largest
    that fits. A page break can move a whole block down in a way the measured
    height does not show, which is why the page count is re-checked every time
    rather than trusted once - a report gains white space under the signatures,
    never a blank sheet."""
    bare = html.replace(report_html.FOOTER_PAD, "")
    plain = _laid_out(bare, size, page)
    pages = plain.pageCount()
    low = 0.0
    high = (pages * size.height()
            - plain.documentLayout().documentSize().height()
            - FOOT_CLEARANCE_PT)
    if high <= 1:
        return bare

    best = bare
    for _ in range(FOOT_PASSES):
        pad = (low + high) / 2
        padded = html.replace(
            report_html.FOOTER_PAD,
            f'<div style="font-size:{pad:.2f}pt;">&nbsp;</div>')
        if _laid_out(padded, size, page).pageCount() == pages:
            best, low = padded, pad
        else:
            high = pad
    return best


# A results table is the only one on the report with five columns.
PANEL_COLUMNS = 5

# One pass per panel is enough - moving a panel down can only push the panels
# after it, never the ones before - with a little room over.
PANEL_PASSES = 8


def _panel_rects(doc: QTextDocument):
    """Where each panel's table sits in the laid-out document, in order."""
    layout = doc.documentLayout()
    return [layout.frameBoundingRect(frame)
            for frame in doc.rootFrame().childFrames()
            if isinstance(frame, QTextTable) and frame.columns() == PANEL_COLUMNS]


def _whole_panels_per_page(html: str, size: QSizeF, page: Page) -> str:
    """Start a panel on a fresh page rather than let it break across two.

    A panel split over a page boundary reads badly - the tail of it turns up
    overleaf under a repeated heading, sometimes as a single row - so any panel
    that would fit on a page of its own is moved to the next one instead of
    being broken. A panel too tall for one page has to break wherever it falls;
    those keep their repeating heading and are left alone.

    Each pass moves the panels that are split in the current layout and lays
    the document out again, because moving one panel down changes where the
    ones after it fall. Moved panels stay moved, so the passes settle."""
    height = size.height()
    moved = set()
    for _ in range(PANEL_PASSES):
        doc = _laid_out(report_html.with_page_breaks(html, moved), size, page)
        rects = _panel_rects(doc)
        if len(rects) != report_html.panel_count(html):
            return html          # not the document we think it is; leave it be
        spilling = {
            i for i, rect in enumerate(rects)
            if int(rect.top() // height) != int((rect.bottom() - 1) // height)
            and rect.height() <= height
        }
        if spilling <= moved:
            break
        moved |= spilling
    return report_html.with_page_breaks(html, moved)


def _resolve(html: str, size: QSizeF, page: Page) -> str:
    """The report as it will actually print: panels moved off page boundaries
    and the footer dropped to the foot of the last sheet.

    Both of those are measured by laying the document out and looking at where
    things landed, so this is the expensive part. The preview asks for the same
    document on every repaint, which is why the answer is remembered."""
    key = (html, round(size.width(), 1), round(size.height(), 1), page)
    if _resolved.get("key") != key:
        settled = html
        if report_html.panel_count(settled):
            settled = _whole_panels_per_page(settled, size, page)
        if report_html.FOOTER_PAD in settled:
            settled = _footer_at_foot(settled, size, page)
        _resolved.clear()
        _resolved.update(key=key, html=settled)
    return _resolved["html"]


# Last resolved document, so repainting the preview does not re-measure it.
_resolved: dict = {}


def _document(html: str, printer: QPrinter, page: Page = REPORT_PAGE) -> QTextDocument:
    rect = printer.pageRect(QPrinter.Point)
    size = QSizeF(rect.width(), rect.height())
    return _laid_out(_resolve(html, size, page), size, page)


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
