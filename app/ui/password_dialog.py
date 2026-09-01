"""Dialogs for the edit password: setting one, and asking for it."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout,
)

from .. import security
from .theme import S2, S3


class _Base(QDialog):
    def __init__(self, parent, title: str, explanation: str):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(430)
        self.setModal(True)

        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(S3 + 4, S3, S3 + 4, S3)
        self.layout_.setSpacing(S3)

        blurb = QLabel(explanation)
        blurb.setWordWrap(True)
        blurb.setObjectName("Hint")
        self.layout_.addWidget(blurb)

        self.form = QFormLayout()
        self.form.setHorizontalSpacing(S3)
        self.form.setVerticalSpacing(S2)
        self.layout_.addLayout(self.form)

        self.error = QLabel("")
        self.error.setWordWrap(True)
        self.error.setStyleSheet("color: #c0392b; font-size: 9.5pt;")
        self.error.hide()
        self.layout_.addWidget(self.error)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        self.buttons.accepted.connect(self._submit)
        self.buttons.rejected.connect(self.reject)
        self.layout_.addWidget(self.buttons)

    def _field(self, label: str) -> QLineEdit:
        edit = QLineEdit()
        edit.setEchoMode(QLineEdit.Password)
        edit.setMinimumHeight(34)
        edit.returnPressed.connect(self._submit)
        self.form.addRow(label, edit)
        return edit

    def _show_error(self, message: str):
        self.error.setText(message)
        self.error.show()

    def _submit(self):
        raise NotImplementedError


class SetPasswordDialog(_Base):
    """Used the first time an edit is attempted with no password on file."""

    def __init__(self, parent, changing: bool = False):
        super().__init__(
            parent,
            "Change edit password" if changing else "Set an edit password",
            "Saved reports open read-only. This password unlocks them for editing "
            "and is required to delete a report.\n\n"
            "It is stored only as a PBKDF2-SHA256 hash, so it cannot be read back "
            "out of the app - if it is forgotten, the only way to reset it is to "
            "delete security.json from the data folder.")

        self.changing = changing
        self.current = self._field("Current password:") if changing else None
        self.new = self._field("New password:")
        self.confirm = self._field("Confirm new password:")
        self.new.setFocus()

    def _submit(self):
        if self.new.text() != self.confirm.text():
            self._show_error("The two new passwords do not match.")
            self.confirm.selectAll()
            self.confirm.setFocus()
            return

        if self.changing:
            problem = security.change_password(self.current.text(), self.new.text())
        else:
            problem = security.set_password(self.new.text())

        if problem:
            self._show_error(problem)
            return
        self.accept()


class AskPasswordDialog(_Base):
    """Asked whenever a locked action is attempted."""

    def __init__(self, parent, action: str = "edit this report"):
        super().__init__(parent, "Password required",
                         f"Enter the edit password to {action}.")
        self.password = self._field("Password:")
        self.password.setFocus()
        self.attempts = 0

    def _submit(self):
        if security.verify(self.password.text()):
            self.accept()
            return
        self.attempts += 1
        self._show_error("That password is not correct.")
        self.password.selectAll()
        self.password.setFocus()


def request_unlock(parent, action: str = "edit this report") -> bool:
    """Ask for the password, offering to set one if none exists yet.

    Returns True only when the user proved they know it (or just set it)."""
    if not security.is_set():
        return SetPasswordDialog(parent).exec() == QDialog.Accepted
    return AskPasswordDialog(parent, action).exec() == QDialog.Accepted
