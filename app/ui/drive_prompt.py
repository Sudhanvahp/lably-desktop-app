"""The 'Save to Google Drive?' question asked on the first save.

Asked at the moment it matters - a report has just been written and exists
only on this PC - rather than hoping the operator finds the setting. Once a
folder is chosen every later save copies there without asking; 'Not now' asks
again next save; the checkbox stops it for good.
"""
import os
from typing import NamedTuple

from PySide6.QtWidgets import QCheckBox, QFileDialog, QMessageBox

from .. import storage


class Answer(NamedTuple):
    folder: str          # chosen backup folder, or "" for none
    stop_asking: bool    # the operator ticked "Don't ask again"


def ask_for_drive(parent=None) -> Answer:
    found = storage.find_google_drive()
    box = QMessageBox(parent)
    box.setWindowTitle("Save to Google Drive?")
    box.setIcon(QMessageBox.Question)
    if found:
        box.setText("Also keep a copy of every report in Google Drive?")
        box.setInformativeText(
            f"Google Drive was found at {found}. Reports will be copied to "
            f"{os.path.join(found, 'Lably')} as a PDF and a data file, and "
            "Drive will upload them to your Google account automatically.")
        use = box.addButton("Use Google Drive", QMessageBox.AcceptRole)
    else:
        box.setText("Google Drive for desktop was not found on this PC.")
        box.setInformativeText(
            "Install and sign in to Google Drive, or pick any other folder "
            "that is synced to the cloud, and every saved report will be "
            "copied there.")
        use = None
    browse = box.addButton("Choose a Folder...", QMessageBox.ActionRole)
    box.addButton("Not Now", QMessageBox.RejectRole)
    check = QCheckBox("Don't ask again")
    box.setCheckBox(check)
    box.setDefaultButton(use or browse)
    # The app stylesheet gives dialog buttons a fixed padding that Qt's message
    # box then squeezes; size each one to its own label so none is clipped.
    for button in box.buttons():
        button.setMinimumWidth(
            button.fontMetrics().horizontalAdvance(button.text()) + 44)
    box.exec()
    clicked = box.clickedButton()

    chosen = ""
    if use is not None and clicked is use:
        chosen = os.path.join(found, "Lably")
    elif clicked is browse:
        chosen = QFileDialog.getExistingDirectory(
            parent, "Choose the folder reports are copied into", found or "")
    return Answer(os.path.normpath(chosen) if chosen else "", check.isChecked())


def apply_answer(answer: Answer) -> str:
    """Store what was decided. Returns a problem to show, or ""."""
    if answer.folder:
        problem = storage.check_backup_dir(answer.folder)
        if problem:
            return problem
        storage.set_backup_dir(answer.folder)
    elif answer.stop_asking:
        storage.decline_backup_prompt()
    return ""
