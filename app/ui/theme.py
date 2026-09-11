"""The design system: one palette, one spacing rhythm, one stylesheet.

Everything visual resolves against the tokens here, so the app reads as one
product rather than a pile of separately styled widgets.
"""

# --------------------------------------------------------------------------
# palette
# --------------------------------------------------------------------------
INK = "#0f1b2a"          # primary text
INK_SOFT = "#334255"     # secondary text
MUTED = "#6b7d92"        # labels, hints
FAINT = "#94a5b8"        # placeholders

CANVAS = "#eef2f7"       # app background behind the cards
SURFACE = "#ffffff"      # cards, inputs, tables
SURFACE_ALT = "#f7f9fc"  # zebra rows, inset panels
LINE = "#e2e9f1"         # hairlines
FIELD_LINE = "#cfd9e5"   # input borders

# Ruled grids: the results and bill worksheets are read cell by cell, so
# their lines are near-black rather than the hairline used elsewhere.
GRID_LINE = "#101a26"    # black rules between rows and columns
GRID_HEAD = "#dfe6ee"    # header band behind the black rules

# Deep teal reads clinical without being the usual hospital blue.
NAVY = "#0b2a3a"         # sidebar
NAVY_DEEP = "#071e2b"
ACCENT = "#0d7d8f"
ACCENT_DARK = "#0a6373"
ACCENT_LIGHT = "#1a9db1"
ACCENT_SOFT = "#e2f1f4"
ACCENT_TINT = "#f2f9fa"

CRIMSON = "#c0303c"      # brand red: the printed report and the logo
SUCCESS = "#17734d"
WARNING = "#a15c07"
DANGER = "#c0392b"
DANGER_SOFT = "#fdf1f0"

FONT = "'Segoe UI', 'Inter', 'Helvetica Neue', Arial, sans-serif"
MONO = "'Cascadia Mono', 'Consolas', 'Courier New', monospace"

# 8px rhythm
S1, S2, S3, S4, S5 = 4, 8, 16, 24, 32


STYLESHEET = f"""
QWidget {{
    background: transparent;
    color: {INK};
    font-family: {FONT};
    font-size: 10.5pt;
}}
QMainWindow, #Canvas {{ background: {CANVAS}; }}

/* ---------------------------------------------------------------- sidebar */
#Sidebar {{
    background: {NAVY};
    border: none;
}}
#BrandName {{
    color: #ffffff;
    font-size: 17pt;
    font-weight: 600;
    letter-spacing: 0.5px;
}}
#BrandTag {{
    color: #7fb0bf;
    font-size: 8pt;
    letter-spacing: 1.1px;
}}
#NavButton {{
    background: transparent;
    border: none;
    border-radius: 8px;
    color: #b7cdd8;
    font-size: 11pt;
    font-weight: 500;
    padding: 11px 14px;
    text-align: left;
}}
#NavButton:hover {{ background: rgba(255, 255, 255, 0.07); color: #ffffff; }}
#NavButton:checked {{
    background: {ACCENT};
    color: #ffffff;
    font-weight: 600;
}}
#SidebarFoot {{ color: #5f8496; font-size: 8pt; }}
#SidebarRule {{ background: rgba(255, 255, 255, 0.09); }}

/* ------------------------------------------------------------ page header */
#PageTitle {{ font-size: 18pt; font-weight: 600; color: {INK}; }}
#PageSubtitle {{ font-size: 10pt; color: {MUTED}; }}
#LabChip {{
    background: {SURFACE};
    border: 1px solid {LINE};
    border-radius: 18px;
    padding: 7px 16px;
    color: {INK_SOFT};
    font-weight: 600;
}}

/* ------------------------------------------------------------------ cards */
#Card {{
    background: {SURFACE};
    border: 1px solid {LINE};
    border-radius: 12px;
}}
#CardTitle {{
    font-size: 9pt;
    font-weight: 700;
    color: {MUTED};
    letter-spacing: 1.3px;
    text-transform: uppercase;
}}
#CardHint {{ font-size: 9pt; color: {FAINT}; }}
#CardRule {{ background: {LINE}; }}

/* ------------------------------------------------------------- stat tiles */
#StatValue {{ font-size: 21pt; font-weight: 600; color: {ACCENT_DARK}; }}
#StatLabel {{ font-size: 8.5pt; color: {MUTED}; letter-spacing: 1.1px;
               text-transform: uppercase; }}

/* ----------------------------------------------------------------- inputs */
QLineEdit, QComboBox, QAbstractSpinBox {{
    background: {SURFACE};
    border: 1px solid {FIELD_LINE};
    border-radius: 8px;
    padding: 6px 11px;
    min-height: 20px;
    color: {INK};
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
}}
QLineEdit:hover, QComboBox:hover, QTextEdit:hover {{ border-color: #b4c4d6; }}
QLineEdit:focus, QComboBox:focus {{
    border: 1px solid {ACCENT};
    background: {ACCENT_TINT};
}}
/* Multi-line inputs get the same chrome, but no min-height: a stylesheet
   min-height overrides setFixedHeight, which silently collapsed the bill-notes
   box to a single line. */
QTextEdit {{
    background: {SURFACE};
    border: 1px solid {FIELD_LINE};
    border-radius: 8px;
    padding: 6px 9px;
    color: {INK};
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
}}
QTextEdit:focus {{ border: 1px solid {ACCENT}; background: {ACCENT_TINT}; }}

QLineEdit:read-only {{
    background: {SURFACE_ALT};
    color: {INK_SOFT};
    border-style: dashed;
    font-family: {MONO};
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    border: none;
    width: 24px;
}}
QComboBox::down-arrow {{ image: url("__CHEVRON__"); width: 11px; height: 11px; }}
QComboBox::down-arrow:on {{ top: 1px; }}
/* The popup is its own top-level window, so it does not inherit the card
   background - it has to be painted white explicitly or it shows through. */
QComboBox QAbstractItemView {{
    background: {SURFACE};
    border: 1px solid {LINE};
    border-radius: 8px;
    padding: 4px;
    color: {INK};
    selection-background-color: {ACCENT_SOFT};
    selection-color: {INK};
    outline: none;
}}
QComboBox QAbstractItemView::item {{
    min-height: 28px;
    padding: 4px 9px;
    border-radius: 5px;
}}
QComboBox QAbstractItemView::item:hover {{ background: {ACCENT_TINT}; }}
QComboBox QAbstractItemView::item:selected {{
    background: {ACCENT_SOFT}; color: {ACCENT_DARK};
}}
QComboBox QListView {{ background: {SURFACE}; }}
QComboBoxPrivateContainer {{
    background: {SURFACE};
    border: 1px solid {LINE};
    border-radius: 8px;
}}
QComboBoxPrivateContainer QScrollBar:vertical {{ background: {SURFACE}; }}
QLabel#FieldLabel {{ color: {MUTED}; font-size: 9.5pt; font-weight: 500; }}
QLabel#FieldHelp {{ color: {FAINT}; font-size: 8.5pt; }}
#LockBar {{
    background: #fdf6e7;
    border: 1px solid #efd9a8;
    border-radius: 10px;
}}
#LockBar QLabel {{ background: transparent; }}
QLabel#LockText {{ color: {WARNING}; font-size: 9.5pt; font-weight: 500; }}

/* ------------------------------------------------------------- checkboxes */
QCheckBox {{ spacing: 11px; padding: 5px 4px; font-size: 10.5pt; color: {INK_SOFT}; }}
QCheckBox:hover {{ color: {INK}; }}
QCheckBox::indicator {{
    width: 21px; height: 21px;
    border: 2px solid {FIELD_LINE};
    border-radius: 6px;
    background: {SURFACE};
}}
QCheckBox::indicator:hover {{ border-color: {ACCENT}; background: {ACCENT_TINT}; }}
QCheckBox::indicator:checked {{
    background: {ACCENT}; border-color: {ACCENT};
    image: url("__CHECK__");
}}

/* ---------------------------------------------------------- panel chips */
#PanelChip {{
    background: {SURFACE};
    border: 1.5px solid {LINE};
    border-radius: 10px;
}}
#PanelChip:hover {{ border-color: {ACCENT_LIGHT}; background: {ACCENT_TINT}; }}
#PanelChipOn {{
    background: {ACCENT_SOFT};
    border: 1.5px solid {ACCENT};
    border-radius: 10px;
}}

/* ---------------------------------------------------------------- buttons */
QPushButton {{
    background: {SURFACE};
    border: 1px solid {FIELD_LINE};
    border-radius: 8px;
    padding: 9px 16px;
    font-weight: 600;
    color: {INK_SOFT};
}}
QPushButton:hover {{
    background: {ACCENT_TINT}; border-color: {ACCENT_LIGHT}; color: {ACCENT_DARK};
}}
QPushButton:pressed {{ background: {ACCENT_SOFT}; }}
QPushButton:disabled {{ color: #a9b7c6; background: {SURFACE_ALT}; border-color: {LINE}; }}

QPushButton#Primary {{
    background: {ACCENT}; border: 1px solid {ACCENT}; color: #ffffff;
    padding: 10px 22px;
}}
QPushButton#Primary:hover {{
    background: {ACCENT_DARK}; border-color: {ACCENT_DARK}; color: #ffffff;
}}
QPushButton#Primary:disabled {{ background: #9dbfc7; border-color: #9dbfc7; color: #eef6f7; }}

QPushButton#Danger {{ color: {DANGER}; border-color: #eec4bf; }}
QPushButton#Danger:hover {{ background: {DANGER_SOFT}; border-color: {DANGER}; color: {DANGER}; }}
QPushButton#Danger:disabled {{ color: #c9b3b0; border-color: {LINE}; background: {SURFACE_ALT}; }}

QPushButton#Ghost {{
    background: transparent; border: none; color: {MUTED}; padding: 7px 10px;
}}
QPushButton#Ghost:hover {{ background: {ACCENT_SOFT}; color: {ACCENT_DARK}; }}

/* ----------------------------------------------------------------- tables */
QTableWidget {{
    background: {SURFACE};
    alternate-background-color: {SURFACE_ALT};
    border: 1px solid {LINE};
    border-radius: 10px;
    gridline-color: transparent;
    selection-background-color: {ACCENT_SOFT};
    selection-color: {INK};
    outline: none;
}}
QTableWidget::item {{
    padding: 7px 9px;
    border: none;
    border-bottom: 1px solid {LINE};
}}
QTableWidget::item:selected {{ background: {ACCENT_SOFT}; color: {INK}; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{
    background: {SURFACE_ALT};
    color: {MUTED};
    border: none;
    border-bottom: 1px solid {LINE};
    padding: 11px 9px;
    font-size: 8.5pt;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
}}
QTableCornerButton::section {{ background: {SURFACE_ALT}; border: none; }}
QTableWidget::indicator {{
    width: 20px; height: 20px;
    border: 2px solid {FIELD_LINE};
    border-radius: 6px;
    background: {SURFACE};
    margin-left: 15px; margin-right: 15px;
}}
QTableWidget::indicator:hover {{ border-color: {ACCENT}; }}
QTableWidget::indicator:checked {{
    background: {ACCENT}; border-color: {ACCENT};
    image: url("__CHECK__");
}}

/* ------------------------------------------------- ruled data-entry grids */
/* The results grid and the bill are worksheets: the operator types into them,
   reads a value back against its row, and checks a column of figures down the
   page. Hairlines are right for a list you only read - here the cell itself has
   to be findable, so these two tables get a ruled black grid, rows and columns
   both, and the header is boxed in the same ink. */
QTableWidget#GridTable {{
    gridline-color: {GRID_LINE};
    border: 2px solid {GRID_LINE};
    border-radius: 6px;
    background: {SURFACE};
    alternate-background-color: {SURFACE_ALT};
}}
QTableWidget#GridTable::item {{
    padding: 5px 8px;
    border: none;
    border-right: 1px solid {GRID_LINE};
    border-bottom: 1px solid {GRID_LINE};
    color: {INK};
}}
QTableWidget#GridTable::item:selected {{
    background: {ACCENT_SOFT};
    color: {INK};
}}
QTableWidget#GridTable QHeaderView::section {{
    background: {GRID_HEAD};
    color: {INK};
    font-weight: 700;
    border: none;
    border-right: 1px solid {GRID_LINE};
    border-bottom: 2px solid {GRID_LINE};
    padding: 9px 8px;
}}
QTableWidget#GridTable QHeaderView::section:last {{ border-right: none; }}

/* ------------------------------------------------------------------ lists */
QListWidget {{
    background: {SURFACE};
    alternate-background-color: {SURFACE_ALT};
    border: 1px solid {LINE};
    border-radius: 10px;
    padding: 4px;
    outline: none;
}}
QListWidget::item {{
    padding: 9px 10px;
    border-radius: 6px;
    color: {INK_SOFT};
}}
QListWidget::item:hover {{ background: {ACCENT_TINT}; color: {INK}; }}
QListWidget::item:selected {{
    background: {ACCENT_SOFT};
    color: {ACCENT_DARK};
    font-weight: 600;
}}

/* -------------------------------------------------------------- scrollbars */
QScrollBar:vertical {{ background: transparent; width: 11px; margin: 2px; }}
QScrollBar::handle:vertical {{
    background: #c6d3e0; border-radius: 5px; min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{ background: {ACCENT_LIGHT}; }}
QScrollBar:horizontal {{ background: transparent; height: 11px; margin: 2px; }}
QScrollBar::handle:horizontal {{
    background: #c6d3e0; border-radius: 5px; min-width: 32px;
}}
QScrollBar::handle:horizontal:hover {{ background: {ACCENT_LIGHT}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ------------------------------------------------------------------- misc */
QScrollArea {{ border: none; background: transparent; }}
QTextBrowser {{ background: {SURFACE}; border: 1px solid {LINE}; border-radius: 10px; }}
QStatusBar {{
    background: {SURFACE}; color: {MUTED};
    border-top: 1px solid {LINE}; font-size: 9pt;
}}
QStatusBar::item {{ border: none; }}
QMenuBar {{ background: {NAVY_DEEP}; color: #cfe0e8; }}
QMenuBar::item {{ padding: 7px 13px; background: transparent; }}
QMenuBar::item:selected {{ background: {ACCENT}; color: #ffffff; }}
QMenu {{ background: {SURFACE}; border: 1px solid {LINE}; border-radius: 8px; padding: 5px; }}
QMenu::item {{ padding: 8px 28px; border-radius: 5px; }}
QMenu::item:selected {{ background: {ACCENT_SOFT}; color: {ACCENT_DARK}; }}
QSplitter::handle {{ background: transparent; height: 10px; }}
/* ------------------------------------------------------- calendar popup */
/* The date pickers open a QCalendarWidget in its own top-level window. It
   inherits the transparent QWidget background above and nothing else paints
   behind it, so without these rules Fusion hands back a black box. Every part
   of it has to be named: the frame, the navigation bar, the day grid and the
   month/year editors are separate widgets. */
QCalendarWidget {{ background: {SURFACE}; }}
QCalendarWidget QWidget {{ background: {SURFACE}; color: {INK}; }}
QCalendarWidget QAbstractItemView {{
    background: {SURFACE};
    color: {INK};
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
    outline: none;
    font-size: 10pt;
}}
/* Days spilling in from the neighbouring months, and dates outside the
   allowed range: present but clearly not selectable. */
QCalendarWidget QAbstractItemView:disabled {{ color: {FAINT}; }}
QCalendarWidget QWidget#qt_calendar_navigationbar {{
    background: {ACCENT};
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    min-height: 32px;
}}
QCalendarWidget #qt_calendar_navigationbar QToolButton {{
    background: transparent;
    border: none;
    border-radius: 5px;
    color: #ffffff;
    font-size: 10.5pt;
    font-weight: 600;
    padding: 4px 10px;
}}
QCalendarWidget #qt_calendar_navigationbar QToolButton:hover {{
    background: rgba(255, 255, 255, 0.18);
}}
QCalendarWidget #qt_calendar_navigationbar QToolButton::menu-indicator {{ image: none; }}
QCalendarWidget QSpinBox {{
    background: {SURFACE};
    color: {INK};
    border: 1px solid {FIELD_LINE};
    border-radius: 5px;
    padding: 1px 4px;
}}
/* The month list dropped down from the navigation bar. */
QCalendarWidget QMenu {{
    background: {SURFACE};
    border: 1px solid {LINE};
    color: {INK};
}}
QCalendarWidget QTableView {{
    background: {SURFACE};
    alternate-background-color: {SURFACE};
    gridline-color: transparent;
}}

QToolTip {{
    background: {INK}; color: #ffffff; border: none;
    border-radius: 6px; padding: 6px 9px;
}}

/* ---------------------------------------------------------------- dialogs */
/* Same reason as the combo popup: dialogs are separate windows and would
   otherwise fall through to the transparent QWidget default. */
QDialog, QMessageBox, QInputDialog, QFileDialog, QProgressDialog {{
    background: {SURFACE};
    color: {INK};
}}
QDialog QWidget, QMessageBox QWidget {{ background: transparent; }}
QMessageBox QLabel, QDialog QLabel {{ background: transparent; color: {INK}; }}
QMessageBox QLabel#qt_msgbox_label {{ font-size: 11pt; color: {INK}; }}
QMessageBox QLabel#qt_msgbox_informativelabel {{ font-size: 10pt; color: {MUTED}; }}
QMessageBox {{ min-width: 340px; }}
QMessageBox QPushButton, QDialog QDialogButtonBox QPushButton {{
    min-width: 88px;
    padding: 8px 18px;
}}
QDialogButtonBox QPushButton:default {{
    background: {ACCENT}; border-color: {ACCENT}; color: #ffffff;
}}
QDialogButtonBox QPushButton:default:hover {{
    background: {ACCENT_DARK}; border-color: {ACCENT_DARK}; color: #ffffff;
}}

QWidget#Bare {{ background: transparent; }}
#Card QLabel, #Card QCheckBox {{ background: transparent; }}
QLabel#Hint {{ color: {MUTED}; font-size: 9.5pt; }}
QLabel#KeyValue {{
    color: {CRIMSON}; font-weight: 700; font-size: 13pt; font-family: {MONO};
}}

/* -------------------------------------------------------------- bill totals */
#BillTotals {{
    background: {SURFACE_ALT};
    border: 1px solid {LINE};
    border-radius: 10px;
}}
#BillTotals QLabel {{ background: transparent; }}
/* An amount box is the one field on the page that money is typed into, so it
   is ruled in the same black as the grids and set in a size that survives a
   glance across the counter. */
QLineEdit#AmountField {{
    border: 2px solid {GRID_LINE};
    border-radius: 6px;
    background: #ffffff;
    font-size: 12pt;
    font-weight: 700;
    color: {INK};
    padding: 4px 9px;
}}
QLineEdit#AmountField:focus {{
    border: 2px solid {ACCENT};
    background: {ACCENT_TINT};
}}
QLineEdit#AmountField:read-only {{
    background: {SURFACE_ALT};
    border: 2px solid {FIELD_LINE};
    color: {INK_SOFT};
}}
QLabel#AmountSign {{ color: {INK}; font-size: 12pt; font-weight: 700; }}
QLabel#BillLabel {{ color: {MUTED}; font-size: 9.5pt; }}
QLabel#BillLabelStrong {{
    color: {INK_SOFT}; font-size: 9pt; font-weight: 700; letter-spacing: 1.2px;
}}
QLabel#BillValue {{
    color: {INK}; font-size: 10.5pt; font-weight: 600; font-family: {MONO};
}}
/* The balance is the figure the patient asks about, so it is the one number on
   the page that changes colour: crimson while it is owed, green once settled. */
QLabel#BillBalance {{
    color: {CRIMSON}; font-size: 13pt; font-weight: 700; font-family: {MONO};
}}
QLabel#BillBalanceClear {{
    color: {SUCCESS}; font-size: 13pt; font-weight: 700; font-family: {MONO};
}}

/* ----------------------------------------------------------- app footer */
QLabel#AppFooterName {{
    color: {DANGER};
    font-size: 10.5pt;
    font-weight: 900;
    letter-spacing: 3px;
}}
QLabel#AppFooterMeta {{ color: {INK_SOFT}; font-size: 8.5pt; font-weight: 700;
                        letter-spacing: 1.1px; }}

QLabel#EmptyTitle {{ font-size: 13pt; font-weight: 600; color: {INK_SOFT}; }}
QLabel#EmptyBody {{ font-size: 10pt; color: {MUTED}; }}
"""


def style_combo(combo):
    """Give a combo box an explicitly white, opaque popup.

    Qt hands the drop-down its own top-level window; on Windows that window can
    come up translucent, which leaks whatever is behind the app through the
    list. Installing a plain QListView and clearing the translucency attribute
    keeps the popup a solid white card that the stylesheet can paint.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QListView

    view = QListView()
    view.setUniformItemSizes(True)
    combo.setView(view)
    popup = view.window()
    popup.setAttribute(Qt.WA_TranslucentBackground, False)
    popup.setAttribute(Qt.WA_NoSystemBackground, False)
    popup.setAutoFillBackground(True)
    popup.setStyleSheet(
        f"background: {SURFACE}; border: 1px solid {LINE}; border-radius: 8px;")
    return combo


def _check_icon_path() -> str:
    """Qt stylesheets can only reference a tick by file path, and the built-in
    Qt tick is green - which clashes with the accent box. Draw a white one once
    and cache it next to the app's data."""
    import os

    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QImage, QPainter, QPen

    from .. import storage

    storage.ensure_dirs()
    path = os.path.join(storage.assets_dir(), "_check.png")
    if not os.path.isfile(path):
        size = 40  # drawn oversized, Qt scales it down into the indicator
        image = QImage(size, size, QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(Qt.white)
        pen.setWidth(6)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawPolyline([QPointF(9, 21), QPointF(17, 29), QPointF(31, 12)])
        painter.end()
        image.save(path, "PNG")
    return path.replace("\\", "/")


def _chevron_icon_path() -> str:
    """Styling QComboBox with a stylesheet drops the native arrow, so draw the
    chevron once ourselves and cache it beside the tick."""
    import os

    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QImage, QPainter, QPen

    from .. import storage

    storage.ensure_dirs()
    path = os.path.join(storage.assets_dir(), "_chevron.png")
    if not os.path.isfile(path):
        size = 32  # drawn oversized, Qt scales it down into the drop-down
        image = QImage(size, size, QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(MUTED))
        pen.setWidth(4)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawPolyline([QPointF(8, 12), QPointF(16, 21), QPointF(24, 12)])
        painter.end()
        image.save(path, "PNG")
    return path.replace("\\", "/")


def stylesheet() -> str:
    """The app stylesheet with runtime-generated assets resolved."""
    return (STYLESHEET
            .replace("__CHECK__", _check_icon_path())
            .replace("__CHEVRON__", _chevron_icon_path()))
