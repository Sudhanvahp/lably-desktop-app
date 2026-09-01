"""Vector icons drawn in code.

Bundling icon files would mean shipping assets and wiring them through
PyInstaller; drawing them with QPainter keeps the app a single file, guarantees
every icon shares one stroke weight, and lets any icon be recoloured or resized
on demand. All icons are drawn on a 24x24 grid with a 2px round-capped stroke.
"""
from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

GRID = 24.0


def _pen(color: str, width: float = 2.0) -> QPen:
    pen = QPen(QColor(color))
    pen.setWidthF(width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


# --------------------------------------------------------------------------
# individual glyphs, each drawing into a 24x24 painter
# --------------------------------------------------------------------------
def _draw_new_report(p: QPainter):
    p.drawRoundedRect(QRectF(4, 2.5, 13, 19), 2.5, 2.5)
    for y in (8.5, 12.0):
        p.drawLine(QPointF(7.5, y), QPointF(13.5, y))
    p.drawLine(QPointF(7.5, 15.5), QPointF(11, 15.5))
    # the "add" mark, sitting proud of the page corner
    p.drawLine(QPointF(18, 15), QPointF(18, 21))
    p.drawLine(QPointF(15, 18), QPointF(21, 18))


def _draw_history(p: QPainter):
    p.drawArc(QRectF(3.5, 3.5, 17, 17), 60 * 16, 280 * 16)
    p.drawLine(QPointF(12, 7.5), QPointF(12, 12))
    p.drawLine(QPointF(12, 12), QPointF(15.5, 14))
    # the arrow head that turns the arc into "go back in time"
    p.drawLine(QPointF(4.2, 4.5), QPointF(4.2, 8.5))
    p.drawLine(QPointF(4.2, 8.5), QPointF(8.2, 8.5))


def _draw_lab(p: QPainter):
    """A flask - reads as 'laboratory' faster than a gear does."""
    p.drawLine(QPointF(9, 2.8), QPointF(15, 2.8))
    path = QPainterPath()
    path.moveTo(10.5, 2.8)
    path.lineTo(10.5, 9.5)
    path.lineTo(5.2, 18.4)
    path.cubicTo(4.3, 19.9, 5.4, 21.5, 7.1, 21.5)
    path.lineTo(16.9, 21.5)
    path.cubicTo(18.6, 21.5, 19.7, 19.9, 18.8, 18.4)
    path.lineTo(13.5, 9.5)
    path.lineTo(13.5, 2.8)
    p.drawPath(path)
    p.drawLine(QPointF(7.6, 14.5), QPointF(16.4, 14.5))


def _draw_printer(p: QPainter):
    p.drawPolyline([QPointF(7, 8.5), QPointF(7, 3.5), QPointF(17, 3.5), QPointF(17, 8.5)])
    p.drawRoundedRect(QRectF(3.5, 8.5, 17, 8), 2, 2)
    p.drawRect(QRectF(7, 14, 10, 6.5))


def _draw_save(p: QPainter):
    p.drawRoundedRect(QRectF(3.5, 3.5, 17, 17), 2.5, 2.5)
    p.drawPolyline([QPointF(7.5, 3.5), QPointF(7.5, 9.5), QPointF(15.5, 9.5),
                    QPointF(15.5, 3.5)])
    p.drawRect(QRectF(8, 13.5, 8, 7))


def _draw_preview(p: QPainter):
    path = QPainterPath()
    path.moveTo(2.5, 12)
    path.cubicTo(6, 6, 18, 6, 21.5, 12)
    path.cubicTo(18, 18, 6, 18, 2.5, 12)
    p.drawPath(path)
    p.drawEllipse(QPointF(12, 12), 3.2, 3.2)


def _draw_pdf(p: QPainter):
    p.drawPolyline([QPointF(14, 2.5), QPointF(5.5, 2.5), QPointF(5.5, 21.5),
                    QPointF(18.5, 21.5), QPointF(18.5, 7)])
    p.drawPolyline([QPointF(14, 2.5), QPointF(18.5, 7), QPointF(14, 7),
                    QPointF(14, 2.5)])
    p.drawLine(QPointF(9, 12.5), QPointF(15, 12.5))
    p.drawLine(QPointF(9, 16), QPointF(15, 16))


def _draw_trash(p: QPainter):
    p.drawLine(QPointF(3.5, 6), QPointF(20.5, 6))
    p.drawPolyline([QPointF(9, 6), QPointF(9, 3.5), QPointF(15, 3.5), QPointF(15, 6)])
    p.drawPolyline([QPointF(5.5, 6), QPointF(6.8, 21), QPointF(17.2, 21),
                    QPointF(18.5, 6)])
    for x in (10, 14):
        p.drawLine(QPointF(x, 10), QPointF(x, 17))


def _draw_plus(p: QPainter):
    p.drawLine(QPointF(12, 5), QPointF(12, 19))
    p.drawLine(QPointF(5, 12), QPointF(19, 12))


def _draw_minus(p: QPainter):
    p.drawLine(QPointF(5, 12), QPointF(19, 12))


def _draw_copy(p: QPainter):
    p.drawRoundedRect(QRectF(8, 3.5, 12.5, 13), 2, 2)
    p.drawPolyline([QPointF(16, 20.5), QPointF(3.5, 20.5), QPointF(3.5, 8)])


def _draw_open(p: QPainter):
    p.drawPolyline([QPointF(13, 3.5), QPointF(20.5, 3.5), QPointF(20.5, 11)])
    p.drawLine(QPointF(20.5, 3.5), QPointF(11, 13))
    p.drawPolyline([QPointF(17, 14), QPointF(17, 20.5), QPointF(3.5, 20.5),
                    QPointF(3.5, 7), QPointF(10, 7)])


def _draw_search(p: QPainter):
    p.drawEllipse(QPointF(10.5, 10.5), 6.5, 6.5)
    p.drawLine(QPointF(15.3, 15.3), QPointF(20.5, 20.5))


def _draw_refresh(p: QPainter):
    p.drawArc(QRectF(4, 4, 16, 16), 40 * 16, 280 * 16)
    p.drawPolyline([QPointF(15.5, 3), QPointF(19.5, 6), QPointF(15.8, 9)])


def _draw_clear(p: QPainter):
    p.drawArc(QRectF(4, 4, 16, 16), 40 * 16, 280 * 16)
    p.drawPolyline([QPointF(15.5, 3), QPointF(19.5, 6), QPointF(15.8, 9)])
    p.drawLine(QPointF(9.5, 9.5), QPointF(14.5, 14.5))
    p.drawLine(QPointF(14.5, 9.5), QPointF(9.5, 14.5))


def _draw_lock(p: QPainter):
    p.drawRoundedRect(QRectF(4.5, 10.5, 15, 10.5), 2.5, 2.5)
    p.drawArc(QRectF(8, 3.2, 8, 9), 0, 180 * 16)
    p.drawLine(QPointF(8, 7.7), QPointF(8, 10.5))
    p.drawLine(QPointF(16, 7.7), QPointF(16, 10.5))


def _draw_unlock(p: QPainter):
    p.drawRoundedRect(QRectF(4.5, 10.5, 15, 10.5), 2.5, 2.5)
    p.drawArc(QRectF(11, 3.2, 8, 9), 0, 180 * 16)
    p.drawLine(QPointF(11, 7.7), QPointF(11, 10.5))


def _draw_beaker(p: QPainter):
    """A test-tube rack - the templates page defines what a test contains."""
    for x in (6.5, 12, 17.5):
        p.drawLine(QPointF(x - 2.4, 3.2), QPointF(x + 2.4, 3.2))
        path = QPainterPath()
        path.moveTo(x - 1.7, 3.2)
        path.lineTo(x - 1.7, 17.5)
        path.cubicTo(x - 1.7, 20.2, x + 1.7, 20.2, x + 1.7, 17.5)
        path.lineTo(x + 1.7, 3.2)
        p.drawPath(path)


def _draw_chevron_up(p: QPainter):
    p.drawPolyline([QPointF(5.5, 15), QPointF(12, 8.5), QPointF(18.5, 15)])


def _draw_chevron_down(p: QPainter):
    p.drawPolyline([QPointF(5.5, 9), QPointF(12, 15.5), QPointF(18.5, 9)])


DRAWERS = {
    "chevron-up": _draw_chevron_up,
    "chevron-down": _draw_chevron_down,
    "beaker": _draw_beaker,
    "lock": _draw_lock,
    "unlock": _draw_unlock,
    "new-report": _draw_new_report,
    "history": _draw_history,
    "lab": _draw_lab,
    "printer": _draw_printer,
    "save": _draw_save,
    "preview": _draw_preview,
    "pdf": _draw_pdf,
    "trash": _draw_trash,
    "plus": _draw_plus,
    "minus": _draw_minus,
    "copy": _draw_copy,
    "open": _draw_open,
    "search": _draw_search,
    "refresh": _draw_refresh,
    "clear": _draw_clear,
}


# --------------------------------------------------------------------------
def pixmap(name: str, color: str, size: int = 20, stroke: float = 2.0) -> QPixmap:
    """Render one glyph. Drawn at 3x and smooth-scaled so it stays crisp on
    high-DPI screens without needing a separate asset per scale factor."""
    scale = 3
    canvas = QPixmap(int(size * scale), int(size * scale))
    canvas.fill(Qt.transparent)

    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.scale(size * scale / GRID, size * scale / GRID)
    painter.setPen(_pen(color, stroke))
    painter.setBrush(Qt.NoBrush)
    drawer = DRAWERS.get(name)
    if drawer:
        drawer(painter)
    painter.end()

    return canvas.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def icon(name: str, color: str, size: int = 20, stroke: float = 2.0) -> QIcon:
    return QIcon(pixmap(name, color, size, stroke))


def logo_pixmap(size: int = 34) -> QPixmap:
    """The app mark: a blood drop with a pulse line through it."""
    scale = 3
    canvas = QPixmap(size * scale, size * scale)
    canvas.fill(Qt.transparent)

    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.scale(size * scale / GRID, size * scale / GRID)

    drop = QPainterPath()
    drop.moveTo(12, 2.2)
    drop.cubicTo(12, 2.2, 20.5, 11.6, 20.5, 15.6)
    drop.cubicTo(20.5, 20.3, 16.7, 22.4, 12, 22.4)
    drop.cubicTo(7.3, 22.4, 3.5, 20.3, 3.5, 15.6)
    drop.cubicTo(3.5, 11.6, 12, 2.2, 12, 2.2)
    painter.fillPath(drop, QColor("#e0414f"))

    painter.setPen(_pen("#ffffff", 1.7))
    painter.drawPolyline([QPointF(6.2, 16.4), QPointF(9.2, 16.4), QPointF(10.8, 13.2),
                          QPointF(13.2, 19.2), QPointF(14.8, 16.4), QPointF(17.8, 16.4)])
    painter.end()

    return canvas.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def icon_size(n: int) -> QSize:
    return QSize(n, n)
