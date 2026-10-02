"""Lab profile editor. Everything here is stamped onto every printed report."""
import os

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QScrollArea, QTabWidget, QTextBrowser, QTextEdit,
    QVBoxLayout, QWidget,
)

from .. import bill_html, report_html, security, storage, text_style
from ..billing import DEFAULT_BILL_NOTES
from ..models import BillItem, Billing, LabProfile, Report, TestRow
from .. import validators as V
from . import icons
from .text_style_editor import TextStyleEditor
from .theme import (ACCENT, ACCENT_DARK, ACCENT_SOFT, FIELD_LINE, INK_SOFT,
                    MUTED, S2, S3, SURFACE_ALT)
from .widgets import Card, PageHeader, icon_button

IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.bmp *.gif)"

def sample_document() -> Report:
    """A stand-in report for the preview, carrying one of everything.

    Every region the appearance editor offers has to be visible in the preview or
    the control for it is a guess: hence a flagged result (for the H/L mark and
    its legend), a sub-heading inside the panel, remarks, and a part-paid bill.
    The figures are obvious nonsense so nobody mistakes the preview for a real
    report - "Sample Patient" against a made-up number.
    """
    return Report(
        report_no="BR-000123",
        title="Mrs.",
        patient_name="Sample Patient",
        age="34",
        sex="F",
        patient_id="HFCD-000123",
        phone="+91 9845012345",
        referred_by="Dr. Sample",
        sample_type="Blood",
        collected_on="01-01-2026 09:15 AM",
        reported_on="01-01-2026 11:40 AM",
        remarks="Sample remarks - please correlate clinically.",
        panels=["Complete Blood Count (CBC)"],
        rows=[
            TestRow("Complete Blood Count (CBC)", "Haemoglobin (Hb)",
                    "9.2", "g/dL", "12.0 - 15.0"),
            TestRow("Complete Blood Count (CBC)", "Total WBC Count",
                    "7,400", "/cmm", "4,000 - 11,000"),
            TestRow("Complete Blood Count (CBC)", "DIFFERENTIAL COUNT",
                    kind="heading"),
            TestRow("Complete Blood Count (CBC)", "Neutrophils",
                    "62", "%", "40 - 75"),
        ],
        billing=Billing(
            bill_no="CB-000123",
            bill_date="01-01-2026",
            net_deposit="400",
            items=[BillItem("Complete Blood Count (CBC)", "600")],
        ),
    )


# Every field that holds a phone number: validated, normalised and length-capped
# the same way, so the letterhead never shows two numbers in two styles.
PHONE_FIELDS = ("phone", "mobile")


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
        ("lab_subtitle", "Sub-heading"),
        ("address1", "Address Line 1"),
        ("address2", "Address Line 2"),
        ("phone", "Phone"),
        ("mobile", "Mobile"),
        ("email", "Email"),
        ("reg_no", "Registration No."),
        ("timings", "Lab Timings"),
        ("holidays", "Holidays"),
        ("pathologist", "Consultant Pathologist / Signatory"),
        ("pathologist_degrees", "Degrees / Qualification"),
        ("technician", "Lab Technician"),
        ("footer_note", "Footer Note"),
    ]

    def __init__(self):
        super().__init__()
        self.edits = {}
        # Built further down, but the field editors are wired to the preview as
        # they are created and the first keystroke must not outrun them.
        self.style_editor = None
        self.preview = None

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setHorizontalSpacing(S3)
        form.setVerticalSpacing(S2 + 2)
        patterns = {
            "phone": V.PHONE_PATTERN,
            "mobile": V.PHONE_PATTERN,
            "email": V.EMAIL_PATTERN,
            "reg_no": V.REG_NO_PATTERN,
            "timings": V.TEXT_LINE_PATTERN,
            "holidays": V.TEXT_LINE_PATTERN,
            "pathologist": V.DOCTOR_PATTERN,
            "technician": V.DOCTOR_PATTERN,
            "lab_name": V.TEXT_LINE_PATTERN,
            "lab_subtitle": V.TEXT_LINE_PATTERN,
            "address1": V.TEXT_LINE_PATTERN,
            "address2": V.TEXT_LINE_PATTERN,
            "pathologist_degrees": V.TEXT_LINE_PATTERN,
            "footer_note": V.TEXT_LINE_PATTERN,
        }
        placeholders = {
            "phone": "+91 8025551234",
            "mobile": "+91 9845012345",
            "email": "lab@example.com",
            "lab_subtitle": "e.g. Family Clinic - printed under the name",
            "timings": "Mon-Sat 7:00 AM - 8:00 PM, Sun 7:00 AM - 1:00 PM",
            "holidays": "Sundays and public holidays (optional)",
            "pathologist": "Dr. A. Rao",
            "pathologist_degrees": "MD (Pathology)",
            "technician": "Name printed and signed on the left of every report",
        }
        for key, label in self.FIELDS:
            edit = QLineEdit()
            if key in patterns:
                edit.setValidator(V.validator(patterns[key], self))
            if key in placeholders:
                edit.setPlaceholderText(placeholders[key])
            edit.setMaxLength(V.MAX_PHONE if key in PHONE_FIELDS else 120)
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
            "Working Hours : Weekdays : 7.00 am to 9.00 pm")
        # The notes print at the foot of the bill, so the Bill Preview must
        # follow them as they are typed like every other field does - before,
        # it kept showing the old notes until some other field was touched.
        self.bill_notes.textChanged.connect(self._refresh_preview)
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
        self.signature = ImagePicker("signature", "Select pathologist's signature image")
        self.technician_signature = ImagePicker(
            "technician_signature", "Select lab technician's signature image")
        for picker in (self.logo, self.signature, self.technician_signature):
            picker.changed.connect(self._refresh_preview)
        form.addRow("Logo:", self.logo)
        form.addRow("Consultant Pathologist Signature:", self.signature)
        form.addRow("Technician Signature:", self.technician_signature)
        form.addRow("Backup Folder:", self._build_backup_picker())

        box = Card("Laboratory Details",
                   "printed on every report and every bill")
        box.add(form)

        # The report and the bill each have their own appearance editor and
        # preview. Stacked one after another they made this page four screens
        # long, and it was easy to style the report while looking at the bill.
        # One card with a tab each keeps every control, pairs each editor with
        # the preview it drives, and halves the scrolling.
        self.style_editor = TextStyleEditor()
        self.style_editor.changed.connect(self._refresh_preview)
        self.preview = QTextBrowser()
        self.preview.setMinimumHeight(460)

        # The bill is styled on its own, from its own list of regions, so a
        # change made here can never move anything on the report - or back.
        self.bill_style_editor = TextStyleEditor(doc=text_style.BILL)
        self.bill_style_editor.changed.connect(self._refresh_preview)
        self.bill_preview = QTextBrowser()
        self.bill_preview.setMinimumHeight(420)

        self.appearance_tabs = QTabWidget()
        self.appearance_tabs.setDocumentMode(True)
        for editor, preview, tab, caption in (
                (self.style_editor, self.preview, "Report",
                 "Report Preview - exactly how the sheet will print"),
                (self.bill_style_editor, self.bill_preview, "Cash Bill",
                 "Bill Preview - exactly how the bill will print")):
            page = QWidget()
            column = QVBoxLayout(page)
            column.setContentsMargins(0, S2, 0, 0)
            column.setSpacing(S2)
            column.addWidget(editor)
            label = QLabel(caption)
            label.setObjectName("Hint")
            column.addWidget(label)
            column.addWidget(preview)
            self.appearance_tabs.addTab(page, tab)
        self.appearance_tabs.setTabToolTip(
            0, "Alignment, font, size and colour for the lab report")
        self.appearance_tabs.setTabToolTip(
            1, "The same controls, for the Cash Bill only")
        # The app theme has no tab styling, and Qt's own flat document-mode
        # tabs all but vanish on a white card - operators could not find the
        # Cash Bill side at all. Big pill tabs, the chosen one filled, read as
        # the two choices they are.
        self.appearance_tabs.setDocumentMode(False)
        self.appearance_tabs.tabBar().setCursor(Qt.PointingHandCursor)
        self.appearance_tabs.tabBar().setExpanding(False)
        self.appearance_tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: none; border-top: 2px solid {ACCENT};
                                top: -2px; }}
            QTabBar::tab {{
                background: {SURFACE_ALT}; color: {INK_SOFT};
                border: 1.5px solid {FIELD_LINE}; border-bottom: none;
                border-top-left-radius: 10px; border-top-right-radius: 10px;
                padding: 10px 34px; margin-right: 6px; min-width: 120px;
                font-size: 11pt; font-weight: 600;
            }}
            QTabBar::tab:hover:!selected {{
                background: {ACCENT_SOFT}; color: {ACCENT_DARK};
                border-color: {ACCENT};
            }}
            QTabBar::tab:selected {{
                background: {ACCENT}; color: #ffffff; border-color: {ACCENT};
            }}
        """)
        style_box = Card("Text Appearance",
                         "alignment, font, size, colour and bold / italic / "
                         "underline, region by region - pick Report or Cash "
                         "Bill below",
                         # holds the two previews, which are scroll areas: a
                         # drop shadow makes them paint outside the card
                         elevated=False)
        style_box.add(self.appearance_tabs)

        save = icon_button("save", "Save Laboratory Profile", "", "Primary")
        save.setIcon(icons.icon("save", "#ffffff", 17))
        save.setMinimumWidth(240)
        save.clicked.connect(self.save)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(S3)
        layout.setContentsMargins(0, 2, 2, 2)
        layout.addWidget(box)
        layout.addWidget(style_box)
        layout.addWidget(self._build_security_box())
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

    # --------------------------------------------------------------- backup
    def _build_backup_picker(self) -> QWidget:
        """A synced folder that every saved report is copied into.

        There is no Google API here on purpose: a one-file exe with no
        installer cannot carry OAuth credentials, and a lab counter has no one
        to renew them. Google Drive for desktop already mirrors a local folder
        to the cloud, so the app writes there and lets Drive do the uploading.
        The same works for OneDrive or any other sync client."""
        self.backup_edit = QLineEdit()
        self.backup_edit.setPlaceholderText(
            r"e.g. G:\My Drive\Lably  -  leave blank for no backup")
        self.backup_edit.textChanged.connect(self._refresh_backup_hint)

        detect = icon_button("copy", "Use Google Drive",
                             "Find the Google Drive folder on this PC")
        detect.clicked.connect(self._detect_drive)
        choose = icon_button("open", "Browse...", "Pick any folder")
        choose.clicked.connect(self._choose_backup)
        self.open_backup = icon_button(
            "open", "Open", "Open the backup folder in Explorer to see what is there")
        self.open_backup.clicked.connect(self._open_backup)
        clear = icon_button("trash", "Off", "Stop backing up", "Danger")
        clear.clicked.connect(lambda: self.backup_edit.setText(""))

        self.backup_hint = QLabel("")
        self.backup_hint.setObjectName("Hint")
        self.backup_hint.setWordWrap(True)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(S2)
        row.addWidget(self.backup_edit, 1)
        row.addWidget(detect)
        row.addWidget(choose)
        row.addWidget(self.open_backup)
        row.addWidget(clear)

        holder = QWidget()
        column = QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(4)
        column.addLayout(row)
        column.addWidget(self.backup_hint)
        self._refresh_backup_hint()
        return holder

    def _detect_drive(self):
        found = storage.find_google_drive()
        if found:
            self.backup_edit.setText(os.path.join(found, "Lably"))
            return
        answer = QMessageBox.question(
            self, "Google Drive not found",
            "Google Drive for desktop does not seem to be installed, or it "
            "is not signed in.\n\nOpen the Google Drive download page now? "
            "After installing and signing in, press Use Google Drive again - "
            "or use Browse... to pick any folder that is synced to the cloud.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if answer == QMessageBox.Yes:
            QDesktopServices.openUrl(QUrl(storage.DRIVE_DOWNLOAD_URL))

    def _open_backup(self):
        """Open whatever is typed in the box, saved or not, so the operator
        can check the folder before committing to it."""
        path = self.backup_edit.text().strip()
        if not path:
            self.notify.emit("No backup folder is set. Press Use Google Drive "
                             "or Browse... first.", "warning")
            return
        problem = storage.check_backup_dir(path)
        if problem:
            self.notify.emit(problem, "warning")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _choose_backup(self):
        start = self.backup_edit.text().strip() or storage.find_google_drive() or ""
        path = QFileDialog.getExistingDirectory(
            self, "Choose the folder reports are copied into", start)
        if path:
            self.backup_edit.setText(os.path.normpath(path))

    def _refresh_backup_hint(self):
        path = self.backup_edit.text().strip()
        self.open_backup.setEnabled(bool(path))
        if not path:
            self.backup_hint.setText(
                "Off. Reports stay only on this PC. Point this at a Google "
                "Drive (or OneDrive) folder and every saved report is also "
                "copied there as a PDF and a data file.")
        elif storage.is_google_drive_path(path):
            self.backup_hint.setText(
                "Google Drive folder. Each report you save is copied here and "
                "Drive uploads it to your Google account automatically.")
        else:
            self.backup_hint.setText(
                "Each report you save is copied into this folder. If the "
                "folder is synced by a cloud app, the copy goes online.")

    # ------------------------------------------------------------- security
    def _build_security_box(self) -> Card:
        """The edit password lives here rather than only behind a locked report.

        Before this, a password could be set but never changed and never
        cleared: the app had no screen for either, so a forgotten one left the
        lab unable to edit or delete anything ever again."""
        card = Card("Edit Password",
                    "asked before a saved report is edited or deleted",
                    elevated=False)

        self.security_state = QLabel("")
        self.security_state.setWordWrap(True)
        self.security_state.setObjectName("Hint")
        card.add(self.security_state)

        row = QHBoxLayout()
        row.setSpacing(S2)
        self.password_button = icon_button("lock", "Set Password", "")
        self.password_button.clicked.connect(self._change_password)
        row.addWidget(self.password_button)

        self.forgot_button = icon_button(
            "unlock", "Forgot Password?",
            "Clear a password nobody remembers, then set a new one", "Danger")
        self.forgot_button.clicked.connect(self._forgot_password)
        row.addWidget(self.forgot_button)

        folder = icon_button("open", "Open Data Folder",
                             "Show the folder holding the reports and settings")
        folder.clicked.connect(self._open_data_folder)
        row.addWidget(folder)
        row.addStretch(1)
        card.add(row)
        self._refresh_security()
        return card

    def _refresh_security(self):
        """Say which state the app is in - the buttons alone do not."""
        is_set = security.is_set()
        self.password_button.setText("Change Password" if is_set
                                     else "Set Password")
        self.password_button.setToolTip(
            "Change the password, proving the current one first" if is_set
            else "Set the password that will guard edits and deletes")
        self.forgot_button.setEnabled(is_set)
        self.security_state.setText(
            "A password is set. Saved reports open read-only and ask for it "
            "before an edit or a delete. It is stored as a PBKDF2-SHA256 hash "
            "and cannot be read back - if it is forgotten, use Forgot "
            "Password? to clear it and set a new one."
            if is_set else
            "No password is set. Saved reports still open read-only, but "
            "unlocking one will ask you to set a password first. Set one now "
            "if more than one person uses this machine."
        )

    def _change_password(self):
        from .password_dialog import change_password_flow

        if change_password_flow(self):
            self._refresh_security()
            self.notify.emit("Edit password saved.", "success")

    def _forgot_password(self):
        from .password_dialog import reset_password_flow

        changed = reset_password_flow(self)
        self._refresh_security()
        if changed and security.is_set():
            self.notify.emit("Password cleared and a new one set.", "success")
        elif not security.is_set():
            self.notify.emit(
                "Password cleared. The next edit or delete will ask you to set "
                "a new one.", "warning")

    @staticmethod
    def _open_data_folder():
        storage.ensure_dirs()
        QDesktopServices.openUrl(QUrl.fromLocalFile(storage.app_dir()))

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
        self.technician_signature.set_path(profile.technician_signature_path)
        self.backup_edit.setText(profile.backup_dir)
        self.style_editor.set_styles(profile.text_styles)
        self.bill_style_editor.set_styles(profile.bill_text_styles)
        self._refresh_preview()
        self._mark_saved()

    # ---------------------------------------------------------- unsaved edits
    def _snapshot(self) -> dict:
        return dict(vars(self.current_profile()))

    def _mark_saved(self):
        """Remember what is on screen as the saved state.

        Taken from the screen rather than from the stored profile, so that what
        load() fills in on a first run (the standard bill notes) does not count
        as an unsaved change nobody made."""
        self._saved_snapshot = self._snapshot()

    def has_unsaved_changes(self) -> bool:
        """True when the screen differs from what was last loaded or saved.

        The main window asks before closing on these: the profile is only
        written by the Save button, and closing used to drop an afternoon of
        letterhead and styling work without a word."""
        saved = getattr(self, "_saved_snapshot", None)
        return saved is not None and self._snapshot() != saved

    # Which field each save() complaint is about. Matched on the label text
    # the validators put in their messages. The old guess split key names on
    # "_" and looked for "lab" - which is also inside "laboratory phone
    # number", so a bad phone number put the cursor in the lab name. Footer,
    # backup and bill-note messages are handled first in _field_for.
    _PROBLEM_FIELDS = (
        ("laboratory name", "lab_name"),
        ("sub-heading", "lab_subtitle"),
        ("address line 1", "address1"),
        ("address line 2", "address2"),
        ("laboratory phone", "phone"),
        ("mobile", "mobile"),
        ("lab timings", "timings"),
        ("holidays", "holidays"),
        ("email", "email"),
        ("pathologist's name", "pathologist"),
        ("technician's name", "technician"),
        ("degrees", "pathologist_degrees"),
        ("footer note", "footer_note"),
    )

    def _field_for(self, problem: str):
        text = problem.lower()
        if "footer note" in text:
            return self.edits["footer_note"]
        # Matched on the exact labels save() hands the validators and the
        # wording of storage.check_backup_dir - a bare "note" / "folder" also
        # caught unrelated messages and sent the cursor to the wrong box.
        if "backup folder" in text:
            return self.backup_edit
        if "bill note" in text:
            return self.bill_notes
        for needle, key in self._PROBLEM_FIELDS:
            if needle in text:
                return self.edits[key]
        return None

    def current_profile(self) -> LabProfile:
        profile = LabProfile()
        for key, _ in self.FIELDS:
            setattr(profile, key, self.edits[key].text().strip())
        # Stored in one form, whatever shape it was typed in, so the letterhead
        # and the bill never show the same number two different ways.
        for key in PHONE_FIELDS:
            setattr(profile, key, V.normalise_phone(getattr(profile, key)))
        profile.bill_notes = self.bill_notes.toPlainText().strip()
        profile.logo_path = self.logo.path
        profile.signature_path = self.signature.path
        profile.technician_signature_path = self.technician_signature.path
        profile.backup_dir = self.backup_edit.text().strip()
        profile.text_styles = (self.style_editor.styles()
                               if self.style_editor else {})
        bill_editor = getattr(self, "bill_style_editor", None)
        profile.bill_text_styles = bill_editor.styles() if bill_editor else {}
        return profile

    def _refresh_preview(self):
        """Re-render the whole sample sheet through the real renderer.

        Through `report_html.build` rather than through a mock-up of it: a
        preview that agrees with the printer only because someone kept two
        layouts in step is a preview that will eventually lie."""
        if self.preview is None or getattr(self, "bill_preview", None) is None:
            return          # still being built; load() renders the first one
        profile = self.current_profile()
        sample = sample_document()
        self.preview.setHtml(
            report_html.build(sample, profile)
            .replace(report_html.FOOTER_PAD, ""))
        self.bill_preview.setHtml(bill_html.build(sample, profile))

    def save(self):
        profile = self.current_profile()
        problem = V.first_error(
            "Enter the laboratory name before saving." if not profile.lab_name else None,
            V.check_text_line(profile.lab_name, "Laboratory name"),
            V.check_text_line(profile.lab_subtitle, "Sub-heading"),
            V.check_text_line(profile.address1, "Address line 1"),
            V.check_text_line(profile.address2, "Address line 2"),
            V.check_phone(profile.phone, "laboratory phone number"),
            V.check_phone(profile.mobile, "mobile number"),
            V.check_text_line(profile.timings, "Lab timings"),
            V.check_text_line(profile.holidays, "Holidays"),
            V.check_email(profile.email),
            storage.check_backup_dir(profile.backup_dir),
            V.check_bill_notes(profile.bill_notes),
            V.check_optional_name(profile.pathologist, "pathologist's name"),
            V.check_optional_name(profile.technician, "lab technician's name"),
            V.check_text_line(profile.pathologist_degrees, "Degrees"),
            V.check_text_line(profile.footer_note, "Footer note"),
        )
        if problem:
            self.notify.emit(problem, "warning")
            field = self._field_for(problem)
            if field is not None:
                field.setFocus()
                if isinstance(field, QLineEdit):
                    field.selectAll()
            return
        try:
            storage.save_profile(profile)
        except OSError as exc:
            # Disk full or a locked file used to escape as an exception - and
            # from the close prompt the window then shut with the edits lost.
            self.notify.emit(
                "Could not save the profile: "
                f"{getattr(exc, 'strerror', None) or exc}. Check that the data "
                f"folder ({storage.app_dir()}) is writable, then save again.",
                "error")
            return False
        for key in PHONE_FIELDS:
            self.edits[key].setText(getattr(profile, key))
        self._mark_saved()
        self.profile_saved.emit()
        return True
