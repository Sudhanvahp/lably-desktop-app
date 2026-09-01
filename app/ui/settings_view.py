"""Lab profile editor. Everything here is stamped onto every printed report."""
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QScrollArea, QTextBrowser, QTextEdit,
    QVBoxLayout, QWidget,
)

from .. import storage
from ..billing import DEFAULT_BILL_NOTES
from ..models import LabProfile
from .. import validators as V
from ..report_html import CSS, letterhead
from . import icons
from .theme import MUTED, S2, S3
from .widgets import Card, PageHeader, icon_button

IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.bmp *.gif)"


class ImagePicker(QWidget):
    changed = Signal()

    def __init__(self, kind: str, caption: str):
        super().__init__()
        self.kind = kind
        self.caption = caption
        self.path = ""

        self.preview = QLabel("none")
        self.preview.setFixedSize(158, 62)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet(
            "border: 1.5px dashed #cfd9e5; border-radius: 8px;"
            "background: #f7f9fc; color: #94a5b8; font-size: 9pt;")

        choose = icon_button("open", "Choose...", "Pick an image file")
        choose.clicked.connect(self._choose)
        clear = icon_button("trash", "Remove", "Use no image", "Danger")
        clear.clicked.connect(self._clear)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.preview)
        row.addWidget(choose)
        row.addWidget(clear)
        row.addStretch(1)

    def _choose(self):
        path, _ = QFileDialog.getOpenFileName(self, self.caption, "", IMAGE_FILTER)
        if path:
            self.set_path(storage.import_asset(path, self.kind))
            self.changed.emit()

    def _clear(self):
        self.set_path("")
        self.changed.emit()

    def set_path(self, path: str):
        self.path = path or ""
        if self.path and os.path.isfile(self.path):
            from PySide6.QtGui import QPixmap
            pix = QPixmap(self.path)
            self.preview.setPixmap(
                pix.scaled(148, 58, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            self.preview.clear()
            self.preview.setText("none")


class SettingsView(QWidget):
    profile_saved = Signal()
    notify = Signal(str, str)

    FIELDS = [
        ("lab_name", "Laboratory Name"),
        ("address1", "Address Line 1"),
        ("address2", "Address Line 2"),
        ("phone", "Phone"),
        ("mobile", "Mobile"),
        ("email", "Email"),
        ("reg_no", "Registration No."),
        ("pathologist", "Pathologist / Signatory"),
        ("pathologist_degrees", "Degrees / Qualification"),
        ("footer_note", "Footer Note"),
        ("billed_by", "Billed By"),
    ]

    def __init__(self):
        super().__init__()
        self.edits = {}

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setHorizontalSpacing(S3)
        form.setVerticalSpacing(S2 + 2)
        patterns = {
            "phone": V.PHONE_PATTERN,
            "mobile": V.PHONE_PATTERN,
            "billed_by": V.DOCTOR_PATTERN,
            "email": V.EMAIL_PATTERN,
            "reg_no": V.REG_NO_PATTERN,
            "pathologist": V.DOCTOR_PATTERN,
            "lab_name": V.TEXT_LINE_PATTERN,
            "address1": V.TEXT_LINE_PATTERN,
            "address2": V.TEXT_LINE_PATTERN,
            "pathologist_degrees": V.TEXT_LINE_PATTERN,
            "footer_note": V.TEXT_LINE_PATTERN,
        }
        placeholders = {
            "phone": "+91 8025551234",
            "mobile": "+91 9845012345",
            "billed_by": "Name printed on the bill as Printed By / Billed By",
            "email": "lab@example.com",
            "pathologist": "Dr. A. Rao",
            "pathologist_degrees": "MD (Pathology)",
        }
        for key, label in self.FIELDS:
            edit = QLineEdit()
            if key in patterns:
                edit.setValidator(V.validator(patterns[key], self))
            if key in placeholders:
                edit.setPlaceholderText(placeholders[key])
            edit.setMaxLength(V.MAX_PHONE if key in ("phone", "mobile") else 120)
            edit.textChanged.connect(self._refresh_preview)
            self.edits[key] = edit
            form.addRow(label + ":", edit)

        # One note per line; the bill numbers them. A QLineEdit cannot hold this,
        # so it is built here rather than in the FIELDS loop above.
        self.bill_notes = QTextEdit()
        self.bill_notes.setAcceptRichText(False)
        self.bill_notes.setFixedHeight(96)
        self.bill_notes.setPlaceholderText(
            "One note per line, e.g.\n"
            "Please bring receipt while collecting the report\n"
            "Beyond 01 month reports will not be preserved")
        # The standard terms are one click away rather than magically appearing
        # whenever the box is empty. Prefilling on every blank would mean a lab
        # could never keep the notes cleared: the moment they saved anything
        # else, the defaults they had deleted would come back.
        self.use_standard_notes = icon_button(
            "copy", "Use standard terms",
            "Fill the box with the usual laboratory receipt terms")
        self.use_standard_notes.clicked.connect(
            lambda: self.bill_notes.setPlainText(DEFAULT_BILL_NOTES))

        notes_column = QVBoxLayout()
        notes_column.setContentsMargins(0, 0, 0, 0)
        notes_column.setSpacing(S2)
        notes_column.addWidget(self.bill_notes)
        notes_buttons = QHBoxLayout()
        notes_buttons.addWidget(self.use_standard_notes)
        notes_buttons.addStretch(1)
        notes_column.addLayout(notes_buttons)
        form.addRow("Bill Notes:", notes_column)

        self.logo = ImagePicker("logo", "Select laboratory logo")
        self.signature = ImagePicker("signature", "Select signature image")
        self.logo.changed.connect(self._refresh_preview)
        self.signature.changed.connect(self._refresh_preview)
        form.addRow("Logo:", self.logo)
        form.addRow("Signature:", self.signature)

        box = Card("Laboratory Details",
                   "printed on every report and every bill")
        box.add(form)

        self.preview = QTextBrowser()
        self.preview.setMinimumHeight(168)
        preview_box = Card("Letterhead Preview",
                           "exactly how the top of the report will print",
                           elevated=False)
        preview_box.add(self.preview)

        save = icon_button("save", "Save Laboratory Profile", "", "Primary")
        save.setIcon(icons.icon("save", "#ffffff", 17))
        save.setMinimumWidth(240)
        save.clicked.connect(self.save)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(S3)
        layout.setContentsMargins(0, 2, 2, 2)
        layout.addWidget(box)
        layout.addWidget(preview_box)
        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(inner)

        # the save button stays pinned below the scroll area so it is always reachable
        buttons = QHBoxLayout()
        hint = QLabel("Printed at the top of every report, and on every bill.")
        hint.setObjectName("Hint")
        buttons.addWidget(hint)
        buttons.addStretch(1)
        buttons.addWidget(save)

        self.header = PageHeader("Laboratory Profile",
                                 "Your letterhead, signature and contact details")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(S3)
        outer.addWidget(self.header)
        outer.addWidget(scroll, 1)
        outer.addLayout(buttons)

        self.load()

    def load(self):
        profile = storage.load_profile()
        for key, _ in self.FIELDS:
            self.edits[key].setText(getattr(profile, key, ""))
        # A brand-new profile - nothing saved yet - opens with the standing terms
        # already in place, so a bill printed on day one has a footer. Once the
        # lab has a profile, the box shows exactly what is stored, blank included:
        # what they saved is what they get.
        first_run = not profile.lab_name
        self.bill_notes.setPlainText(
            DEFAULT_BILL_NOTES if first_run and not profile.bill_notes
            else profile.bill_notes)
        self.logo.set_path(profile.logo_path)
        self.signature.set_path(profile.signature_path)
        self._refresh_preview()

    def current_profile(self) -> LabProfile:
        profile = LabProfile()
        for key, _ in self.FIELDS:
            setattr(profile, key, self.edits[key].text().strip())
        # Stored in one form, whatever shape it was typed in, so the letterhead
        # and the bill never show the same number two different ways.
        profile.phone = V.normalise_phone(profile.phone)
        profile.mobile = V.normalise_phone(profile.mobile)
        profile.bill_notes = self.bill_notes.toPlainText().strip()
        profile.logo_path = self.logo.path
        profile.signature_path = self.signature.path
        return profile

    def _refresh_preview(self):
        html = letterhead(self.current_profile())
        self.preview.setHtml(f"<html><head><style>{CSS}</style></head><body>{html}</body></html>")

    def save(self):
        profile = self.current_profile()
        problem = V.first_error(
            "Enter the laboratory name before saving." if not profile.lab_name else None,
            V.check_text_line(profile.lab_name, "Laboratory name"),
            V.check_text_line(profile.address1, "Address line 1"),
            V.check_text_line(profile.address2, "Address line 2"),
            V.check_phone(profile.phone, "laboratory phone number"),
            V.check_phone(profile.mobile, "mobile number"),
            V.check_email(profile.email),
            V.check_optional_name(profile.billed_by, "billed-by name"),
            V.check_bill_notes(profile.bill_notes),
            V.check_optional_name(profile.pathologist, "pathologist's name"),
            V.check_text_line(profile.pathologist_degrees, "Degrees"),
            V.check_text_line(profile.footer_note, "Footer note"),
        )
        if problem:
            self.notify.emit(problem, "warning")
            for key in ("lab_name", "mobile", "phone", "email", "pathologist"):
                if key.split("_")[0] in problem.lower() or (
                        key == "lab_name" and "laboratory" in problem.lower()):
                    self.edits[key].setFocus()
                    break
            return
        storage.save_profile(profile)
        for key in ("phone", "mobile"):
            self.edits[key].setText(getattr(profile, key))
        self.profile_saved.emit()
