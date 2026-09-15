"""Widget-level behaviour, driven headlessly through the offscreen Qt platform.

Covers the form, the history list and how the two stay in sync - which is where
the reported bugs lived.
"""
import os
import unittest

from tests.base import SandboxCase

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractItemView, QApplication

from app import validators as V
from app.models import LabProfile
from app.ui.report_form import FIELD_HELP
from app.ui.theme import DANGER

CBC = "Complete Blood Count (CBC)"
LIPID = "Lipid Profile"

# Patient names must be letters only, so fixtures cannot use "P0", "P1", ...
NAMES = ["Anita Rao", "Bharat Shah", "Chetan Iyer", "Divya Nair", "Esha Menon"]


def app():
    return QApplication.instance() or QApplication([])


class UICase(SandboxCase):
    def setUp(self):
        super().setUp()
        self.app = app()
        from app.ui.main_window import MainWindow

        self.storage.save_profile(LabProfile(lab_name="Test Lab"))
        # The first-save Google Drive question is a modal dialog; answer it
        # silently here, and let a test that wants it set drive_answers itself.
        from app.ui.drive_prompt import Answer
        from app.ui.report_form import ReportForm
        self.drive_answers = []
        self.drive_prompts = 0

        def fake_prompt(parent=None):
            self.drive_prompts += 1
            return self.drive_answers.pop(0) if self.drive_answers else Answer("", False)
        original = ReportForm.drive_prompt
        ReportForm.drive_prompt = staticmethod(fake_prompt)
        self.addCleanup(setattr, ReportForm, "drive_prompt", staticmethod(original))
        self.window = MainWindow()
        self.form = self.window.form
        self.history = self.window.history
        self.messages = []
        self.window.toast.show_message = lambda msg, kind="success", msecs=0: \
            self.messages.append((msg, kind))
        # re-point the signals at the stub
        for widget in (self.form, self.history, self.window.settings):
            widget.notify.disconnect()
            widget.notify.connect(
                lambda msg, kind: self.messages.append((msg, kind)))

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        super().tearDown()

    def fill(self, name="Jane Doe", panel=CBC, result="14.0"):
        self.form.f_name.setText(name)
        self.form.f_age.setText("34")
        self.form.panel_boxes[panel].setChecked(True)
        if result is not None:
            self.form.table.item(0, 1).setText(result)

    def last_message(self):
        return self.messages[-1] if self.messages else (None, None)

    def stub_print(self, sink, accepted=True):
        """Answer the printer picker without showing it. A modal dialog reached
        with no stub hangs the suite rather than failing it."""
        from app import printing

        original = printing.print_report
        printing.print_report = lambda html, parent=None, title="", page=None: (
            sink.append((html, title, page)) or accepted)
        self.addCleanup(setattr, printing, "print_report", original)

    def stub_preview(self, sink):
        from app import printing

        original = printing.preview_report
        printing.preview_report = (
            lambda html, parent=None, title="", page=None:
            sink.append((html, title, page)))
        self.addCleanup(setattr, printing, "preview_report", original)

    def allow_unlock(self, allowed=True):
        """Answer the password dialog without showing it.

        The dialog is modal, so a test that reaches it with no stub hangs
        forever rather than failing."""
        import app.ui.password_dialog as pd

        # Both call sites import request_unlock inside the method, so they
        # resolve it from the module at call time and see this stub.
        self._orig_unlock = pd.request_unlock
        pd.request_unlock = lambda *a, **k: allowed
        self.addCleanup(setattr, pd, "request_unlock", self._orig_unlock)


class PanelLoadingTests(UICase):
    def test_ticking_a_panel_loads_its_rows(self):
        self.form.panel_boxes[CBC].setChecked(True)
        self.assertGreater(self.form.table.rowCount(), 0)
        self.assertEqual(self.form.table.item(0, 0).text(), "Haemoglobin (Hb)")

    def test_unticking_removes_only_that_panel(self):
        self.form.panel_boxes[CBC].setChecked(True)
        cbc_rows = self.form.table.rowCount()
        self.form.panel_boxes[LIPID].setChecked(True)
        self.form.panel_boxes[CBC].setChecked(False)

        self.assertEqual(self.form.table.rowCount(),
                         self.form.table.rowCount())
        remaining = {self.form.table.item(r, 0).data(Qt.UserRole)
                     for r in range(self.form.table.rowCount())}
        self.assertEqual(remaining, {LIPID})
        self.assertNotEqual(self.form.table.rowCount(), cbc_rows + 0)

    def test_changing_sex_updates_sex_specific_ranges(self):
        self.form.panel_boxes[CBC].setChecked(True)
        self.assertEqual(self.form.table.item(0, 3).text(), "13.0 - 17.0")
        self.form.f_sex.setCurrentText("F")
        self.assertEqual(self.form.table.item(0, 3).text(), "12.0 - 15.0")

    def test_out_of_range_result_is_marked_red(self):
        self.form.panel_boxes[CBC].setChecked(True)
        self.form.table.item(0, 1).setText("9.2")
        item = self.form.table.item(0, 1)
        self.assertTrue(item.font().bold())
        self.assertEqual(item.foreground().color().name(), "#c00000")

    def test_in_range_result_is_not_marked(self):
        self.form.panel_boxes[CBC].setChecked(True)
        self.form.table.item(0, 1).setText("14.0")
        self.assertFalse(self.form.table.item(0, 1).font().bold())

    def test_custom_rows_can_be_added_and_deleted(self):
        from app.models import TestRow

        self.form._append_row(TestRow("Investigations", "Custom Test", "5", "u", "1 - 10"))
        self.assertEqual(self.form.table.rowCount(), 1)

        row = self.form.collect().rows[0]
        self.assertEqual(row.name, "Custom Test")
        self.assertEqual(row.panel, "Investigations")

        self.form.table.setCurrentCell(0, 0)
        self.form._delete_row()
        self.assertEqual(self.form.table.rowCount(), 0)

    def test_blank_rows_are_dropped_on_collect(self):
        from app.models import TestRow

        self.form._append_row(TestRow("Investigations", "", "", "", ""))
        self.form._append_row(TestRow("Investigations", "Real Test", "1", "u", "0 - 2"))
        self.assertEqual(len(self.form.collect().rows), 1)


class SelectionTests(UICase):
    def test_results_grid_selects_cells_not_rows(self):
        """Reported bug: selecting one cell highlighted the whole row."""
        self.assertEqual(self.form.table.selectionBehavior(),
                         QAbstractItemView.SelectItems)
        self.form.panel_boxes[CBC].setChecked(True)
        self.form.table.setCurrentCell(1, 1)
        selected = self.form.table.selectedIndexes()
        self.assertEqual(len(selected), 1)
        self.assertEqual((selected[0].row(), selected[0].column()), (1, 1))

    def test_history_still_selects_whole_rows(self):
        self.assertEqual(self.history.table.selectionBehavior(),
                         QAbstractItemView.SelectRows)


class PatientIdTests(UICase):
    def test_patient_id_is_read_only_and_prefilled(self):
        self.assertTrue(self.form.f_pid.isReadOnly())
        self.assertEqual(self.form.f_pid.text(), "HFCD-000001")

    def test_each_saved_report_gets_a_unique_id(self):
        ids = []
        for name in NAMES[:3]:
            self.form.new_report()
            self.fill(name=name)
            self.assertTrue(self.form.save())
            ids.append(self.form.f_pid.text())
        self.assertEqual(len(set(ids)), 3)

    def test_reopening_keeps_the_same_id(self):
        self.fill()
        self.form.save()
        original = self.form.f_pid.text()
        report = self.storage.load_report(self.form.current_id)
        self.form.load_report(report)
        self.assertEqual(self.form.f_pid.text(), original)

    def test_duplicate_as_new_reuses_the_patient_id(self):
        self.fill()
        self.form.save()
        report = self.storage.load_report(self.form.current_id)
        self.form.load_report(report, as_copy=True)

        self.assertEqual(self.form.f_pid.text(), report.patient_id)
        self.assertEqual(self.form.current_id, "", "must save as a new report")
        self.assertTrue(all(self.form.table.item(r, 1).text() == ""
                            for r in range(self.form.table.rowCount())),
                        "results must be blank on a duplicate")


class NotificationTests(UICase):
    def test_saving_reports_success(self):
        """Reported bug: saving gave almost no feedback."""
        self.fill()
        self.form.save()
        message, kind = self.last_message()
        self.assertEqual(kind, "success")
        self.assertIn("BR-000001", message)
        self.assertIn("Jane Doe", message)

    def test_clearing_reports_success(self):
        """Reported bug: clearing gave no feedback."""
        self.form.clear_clicked()
        message, kind = self.last_message()
        self.assertEqual(kind, "info")
        self.assertIn("cleared", message.lower())

    def test_saving_without_a_name_warns_and_does_not_save(self):
        self.form.panel_boxes[CBC].setChecked(True)
        self.assertFalse(self.form.save())
        self.assertEqual(self.last_message()[1], "warning")
        self.assertEqual(self.storage.load_index(), [])

    def test_saving_without_any_rows_warns(self):
        self.form.f_name.setText("Jane")
        self.assertFalse(self.form.save())
        self.assertEqual(self.last_message()[1], "warning")

    def test_deleting_reports_success(self):
        self.fill()
        self.form.save()
        self.history.reload()
        self.history.table.item(0, 0).setCheckState(Qt.Checked)
        self.allow_unlock()
        self.history.delete_checked = self._auto_confirm(self.history.delete_checked)
        self.history.delete_checked()
        self.assertEqual(self.last_message()[1], "success")

    def _auto_confirm(self, func):
        """Run a method with the confirmation dialog answered Yes."""
        from PySide6.QtWidgets import QMessageBox

        def wrapper(*args, **kwargs):
            original = QMessageBox.question
            QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
            try:
                return func(*args, **kwargs)
            finally:
                QMessageBox.question = original
        return wrapper


class AgeUnitTests(UICase):
    def test_units_are_spelled_out_for_the_operator(self):
        shown = [self.form.f_age_unit.itemText(i)
                 for i in range(self.form.f_age_unit.count())]
        self.assertEqual(shown, ["Years", "Months", "Days"])

    def test_stored_code_stays_short(self):
        """The file format keeps Y/M/D; only the display changed."""
        for code, word in (("Y", "Years"), ("M", "Months"), ("D", "Days")):
            self.form.set_age_unit(code)
            self.assertEqual(self.form.f_age_unit.currentText(), word)
            self.assertEqual(self.form.age_unit_code(), code)

    def test_saved_report_records_the_code(self):
        self.fill()
        self.form.set_age_unit("M")
        self.form.f_age.setText("6")
        self.assertTrue(self.form.save())
        self.assertEqual(self.storage.load_report(self.form.current_id).age_unit, "M")

    def test_reopening_restores_the_word(self):
        self.fill()
        self.form.set_age_unit("D")
        self.form.f_age.setText("10")
        self.form.save()
        report = self.storage.load_report(self.form.current_id)
        self.form.load_report(report)
        self.assertEqual(self.form.f_age_unit.currentText(), "Days")

    def test_unknown_code_falls_back_to_years(self):
        self.form.set_age_unit("Z")
        self.assertEqual(self.form.age_unit_code(), "Y")


class FieldDescriptionTests(UICase):
    def test_every_patient_field_has_a_description(self):
        from app.ui.report_form import FIELD_HELP

        for key, text in FIELD_HELP.items():
            self.assertTrue(text.strip(), f"{key} has no description")
            self.assertTrue(text.strip().endswith("."), f"{key} is not a sentence")

    def test_descriptions_are_visible_on_the_page(self):
        from PySide6.QtWidgets import QLabel

        from app.ui.report_form import FIELD_HELP

        shown = {w.text() for w in self.form.findChildren(QLabel)
                 if w.objectName() == "FieldHelp"}
        for text in FIELD_HELP.values():
            self.assertIn(text, shown)


class FieldValidationTests(UICase):
    """The rules must be enforced by the widgets, not just by the functions.

    Typing is what the validator filters - setText() deliberately bypasses it,
    so that loading an old stored report never silently wipes its patient name.
    """

    @staticmethod
    def type_into(widget, text):
        from PySide6.QtTest import QTest

        widget.clear()
        QTest.keyClicks(widget, text)
        return widget.text()

    def test_typing_digits_into_the_name_is_blocked(self):
        self.assertEqual(self.type_into(self.form.f_name, "Patient 1"), "Patient ")

    def test_typing_symbols_into_the_name_is_blocked(self):
        self.assertEqual(self.type_into(self.form.f_name, "Jane@Doe"), "JaneDoe")

    def test_typing_real_names_works(self):
        for name in ("M. K. Sharma", "D'Souza", "Baby of Sunita"):
            self.assertEqual(self.type_into(self.form.f_name, name), name)

    def test_typing_letters_into_the_age_is_blocked(self):
        self.assertEqual(self.type_into(self.form.f_age, "34y"), "34")

    def test_typing_digits_into_the_age_works(self):
        self.assertEqual(self.type_into(self.form.f_age, "34"), "34")

    def test_age_is_capped_at_three_digits(self):
        self.assertEqual(self.type_into(self.form.f_age, "12345"), "123")

    def test_typing_digits_into_the_doctor_field_is_blocked(self):
        self.assertEqual(self.type_into(self.form.f_ref, "Dr 99"), "Dr ")

    def test_loading_a_stored_name_is_never_silently_altered(self):
        """setText must not be filtered, or reopening an old report would
        quietly change the patient's name on their record."""
        from app.models import Report, TestRow

        legacy = self.storage.save_report(Report(
            patient_name="Bed 12 Patient", age="40", sex="M",
            rows=[TestRow("CBC", "Hb", "14", "g/dL", "13 - 17")]))
        self.form.load_report(legacy)
        self.assertEqual(self.form.f_name.text(), "Bed 12 Patient")

    def test_saving_without_an_age_is_blocked(self):
        self.form.f_name.setText("Jane Doe")
        self.form.panel_boxes[CBC].setChecked(True)
        self.assertFalse(self.form.save())
        self.assertIn("age", self.last_message()[0].lower())

    def test_saving_an_implausible_age_is_blocked(self):
        self.fill()
        self.form.f_age.setText("300")
        self.assertFalse(self.form.save())
        self.assertIn("age", self.last_message()[0].lower())

    def test_age_unit_changes_what_counts_as_plausible(self):
        self.fill()
        self.form.f_age.setText("60")
        self.assertTrue(self.form.save())          # 60 years is fine

        self.form.set_age_unit("M")                # 60 months is not
        self.assertFalse(self.form.save())

    def test_implausible_age_tints_the_field(self):
        self.form.f_age.setText("300")
        self.assertIn("c0392b", self.form.f_age.styleSheet())
        self.form.f_age.setText("30")
        self.assertEqual(self.form.f_age.styleSheet(), "")

    def test_qualitative_results_are_still_accepted(self):
        """Results are not numbers-only - 'Nil' must save."""
        self.fill(result=None)
        self.form.f_age.setText("34")
        self.form.table.item(0, 1).setText("Nil")
        self.assertTrue(self.form.save())
        saved = self.storage.load_report(self.form.current_id)
        self.assertEqual(saved.rows[0].result, "Nil")

    def test_absurdly_long_result_is_blocked(self):
        self.fill()
        self.form.table.item(0, 1).setText("x" * 60)
        self.assertFalse(self.form.save())
        self.assertIn("too long", self.last_message()[0].lower())


class ProfileValidationTests(UICase):
    def test_bad_email_blocks_saving(self):
        settings = self.window.settings
        settings.edits["lab_name"].setText("Test Lab")
        settings.edits["email"].setText("not-an-email")
        settings.save()
        self.assertIn("email", self.last_message()[0].lower())

    def test_a_phone_number_is_stored_in_one_form(self):
        """However it was typed. The letterhead and the bill must not show the
        same number two different ways."""
        settings = self.window.settings
        settings.edits["lab_name"].setText("Test Lab")
        settings.edits["phone"].setText("0821 2529999")
        settings.edits["mobile"].setText("+919964725222")
        settings.save()

        profile = self.storage.load_profile()
        self.assertEqual(profile.phone, "+91 8212529999")
        self.assertEqual(profile.mobile, "+91 9964725222")
        # and the boxes show what was actually stored
        self.assertEqual(settings.edits["phone"].text(), "+91 8212529999")

    def test_a_phone_number_of_the_wrong_length_blocks_saving(self):
        settings = self.window.settings
        settings.edits["lab_name"].setText("Test Lab")
        for wrong in ("984501234", "98450123456"):
            settings.edits["phone"].setText(wrong)
            settings.save()
            self.assertEqual(self.last_message()[1], "warning", wrong)
            self.assertIn("10", self.last_message()[0], wrong)

    def test_short_phone_blocks_saving(self):
        settings = self.window.settings
        settings.edits["lab_name"].setText("Test Lab")
        settings.edits["phone"].setText("123")
        settings.save()
        self.assertIn("phone", self.last_message()[0].lower())

    def test_typing_letters_into_the_phone_is_blocked(self):
        from PySide6.QtTest import QTest

        field = self.window.settings.edits["phone"]
        field.clear()
        QTest.keyClicks(field, "call me")
        self.assertEqual(field.text(), "")

    def test_typing_a_real_phone_number_works(self):
        from PySide6.QtTest import QTest

        field = self.window.settings.edits["phone"]
        field.clear()
        QTest.keyClicks(field, "080-2555 1234")
        self.assertEqual(field.text(), "080-2555 1234")

    def test_valid_profile_saves(self):
        settings = self.window.settings
        settings.edits["lab_name"].setText("Sunrise Diagnostics")
        settings.edits["phone"].setText("080-2555 1234")
        settings.edits["email"].setText("lab@example.com")
        settings.save()
        self.assertEqual(self.storage.load_profile().lab_name, "Sunrise Diagnostics")


class DesignSystemTests(UICase):
    """Cheap guards on the chrome, so a future tweak cannot silently break it."""

    def test_every_named_icon_renders(self):
        from app.ui import icons

        for name in icons.DRAWERS:
            self.assertFalse(icons.pixmap(name, "#000000", 20).isNull(), name)

    def test_logo_renders(self):
        from app.ui import icons

        self.assertFalse(icons.logo_pixmap(32).isNull())

    def test_stylesheet_has_no_unresolved_placeholders(self):
        from app.ui.theme import stylesheet

        sheet = stylesheet()
        self.assertNotIn("__CHECK__", sheet)
        self.assertNotIn("{", sheet.replace("{{", "").replace("}}", "")
                         .split("QWidget")[0])

    def test_cards_holding_a_scroll_area_are_not_elevated(self):
        """A QGraphicsEffect makes scroll-area children paint outside the card.

        Only embedded scroll areas count - a QComboBox owns a QListView popup,
        which is never painted inside the card and so is irrelevant here."""
        from PySide6.QtWidgets import QScrollArea, QTableWidget, QTextBrowser

        from app.ui.widgets import Card

        embedded = (QTableWidget, QTextBrowser, QScrollArea)
        for page in (self.form, self.history, self.window.settings):
            for card in page.findChildren(Card):
                if any(card.findChildren(kind) for kind in embedded):
                    self.assertIsNone(
                        card.graphicsEffect(),
                        f"{card.title_label.text()} holds a scroll area but is elevated")

    def test_results_grid_never_overlaps_its_buttons(self):
        """Regression: a squeezed layout used to paint the grid over the row
        buttons. The page scrolls instead of shrinking past its minimum."""
        # geometry is only meaningful once the window has been laid out
        self.window.resize(1100, 700)
        self.window.show()
        self.form.panel_boxes[CBC].setChecked(True)
        self.app.processEvents()
        self.addCleanup(self.window.hide)

        table_bottom = self.form.table.mapTo(
            self.form, self.form.table.rect().bottomLeft()).y()
        buttons_top = self.form.row_count_label.mapTo(
            self.form, self.form.row_count_label.rect().topLeft()).y()
        self.assertLess(table_bottom, buttons_top,
                        "results grid overlaps the Add / Delete Row bar")

    def test_panel_chip_highlights_with_its_checkbox(self):
        chip = self.form.panel_chips[CBC]
        self.assertEqual(chip.objectName(), "PanelChip")
        self.form.panel_boxes[CBC].setChecked(True)
        self.assertEqual(chip.objectName(), "PanelChipOn")
        self.form.panel_boxes[CBC].setChecked(False)
        self.assertEqual(chip.objectName(), "PanelChip")

    def test_row_counter_tracks_the_grid(self):
        self.assertEqual(self.form.row_count_label.text(), "")
        self.form.panel_boxes[CBC].setChecked(True)
        self.assertIn(str(self.form.table.rowCount()), self.form.row_count_label.text())


class HistoryChromeTests(UICase):
    def test_empty_state_when_there_are_no_reports(self):
        self.assertEqual(self.history.pages.currentIndex(), 1)

    def test_list_shows_once_a_report_exists(self):
        self.fill()
        self.form.save()
        self.history.reload()
        self.assertEqual(self.history.pages.currentIndex(), 0)

    def test_no_match_state_is_distinct_from_empty(self):
        self.fill()
        self.form.save()
        self.history.reload()
        self.history.search.setText("nobody by that name")
        self.assertEqual(self.history.pages.currentIndex(), 2)

    def test_stat_tiles_count_reports_and_patients(self):
        for name in NAMES[:3]:
            self.form.new_report()
            self.fill(name=name)
            self.form.save()
        self.history.reload()

        self.assertEqual(self.history.stat_total.value_label.text(), "3")
        self.assertEqual(self.history.stat_patients.value_label.text(), "3")
        self.assertEqual(self.history.stat_today.value_label.text(), "3")


class ReadOnlyTests(UICase):
    """A saved report is a medical record that has already been handed over."""

    def saved_report(self):
        self.fill()
        self.form.save()
        return self.storage.load_report(self.form.current_id)

    def test_a_new_report_is_editable(self):
        self.assertFalse(self.form.read_only)
        self.assertTrue(self.form.lock_bar.isHidden())

    def test_opening_a_saved_report_locks_it(self):
        report = self.saved_report()
        self.form.load_report(report)

        self.assertTrue(self.form.read_only)
        self.assertTrue(self.form.f_name.isReadOnly())
        self.assertFalse(self.form.f_sex.isEnabled())
        self.assertFalse(self.form.add_row_button.isEnabled())
        self.assertIn(report.report_no, self.form.lock_message.text())

    def test_a_locked_report_refuses_to_save(self):
        report = self.saved_report()
        self.form.load_report(report)
        self.assertFalse(self.form.save())
        self.assertIn("read-only", self.last_message()[0].lower())

    def test_the_grid_is_not_editable_while_locked(self):
        from PySide6.QtWidgets import QAbstractItemView

        self.form.load_report(self.saved_report())
        self.assertEqual(self.form.table.editTriggers(),
                         QAbstractItemView.NoEditTriggers)

    def test_the_right_password_unlocks_it(self):
        self.form.load_report(self.saved_report())
        self.allow_unlock(True)
        self.assertTrue(self.form.request_edit_access())

        self.assertFalse(self.form.read_only)
        self.assertFalse(self.form.f_name.isReadOnly())
        self.assertTrue(self.form.add_row_button.isEnabled())

    def test_a_refused_password_leaves_it_locked(self):
        self.form.load_report(self.saved_report())
        self.allow_unlock(False)
        self.assertFalse(self.form.request_edit_access())
        self.assertTrue(self.form.read_only)
        self.assertFalse(self.form.save())

    def test_a_locked_report_can_still_be_printed(self):
        """Printing does not change the record, so it must not need the password."""
        from app import printing

        self.form.load_report(self.saved_report())
        calls = []
        original = printing.print_report
        printing.print_report = lambda html, parent=None: calls.append(html) or True
        self.addCleanup(setattr, printing, "print_report", original)

        self.form.print_report()
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.last_message()[1], "success")

    def test_the_page_title_says_which_mode_it_is_in(self):
        self.assertEqual(self.form.header.title.text(), "New Report")
        self.form.load_report(self.saved_report())
        self.assertEqual(self.form.header.title.text(), "Saved Report")
        self.assertEqual(self.form.print_button.text(), "Print")

        self.form.new_report()
        self.assertEqual(self.form.header.title.text(), "New Report")
        self.assertEqual(self.form.print_button.text(), "Save and Print")

    def test_duplicate_as_new_is_not_locked(self):
        """A duplicate is a brand new report, not the stored one."""
        self.form.load_report(self.saved_report(), as_copy=True)
        self.assertFalse(self.form.read_only)

    def test_starting_a_new_report_clears_the_lock(self):
        self.form.load_report(self.saved_report())
        self.form.new_report()
        self.assertFalse(self.form.read_only)
        self.assertTrue(self.form.lock_bar.isHidden())


class TemplateWorkflowTests(UICase):
    """The whole point of the feature: define a panel once, use it forever."""

    def templates_page(self):
        return self.window.templates

    def test_built_in_panels_appear_as_chips(self):
        self.assertIn(CBC, self.form.panel_boxes)

    def test_a_new_panel_shows_up_on_the_form(self):
        from app import templates

        templates.create_panel("Urine Routine", [
            templates.make_heading("PHYSICAL"),
            templates.make_test("Colour", "", "Pale yellow"),
        ])
        self.form.refresh_panels()

        self.assertIn("Urine Routine", self.form.panel_boxes)
        self.form.panel_boxes["Urine Routine"].setChecked(True)
        self.assertEqual(self.form.table.rowCount(), 2)
        self.assertTrue(self.form.is_heading_row(0))
        self.assertFalse(self.form.is_heading_row(1))

    def test_an_edited_panel_is_used_by_the_next_report(self):
        from app import templates

        rows = templates.rows_for(CBC)
        rows[0]["ref_m"] = "14.0 - 18.0"
        rows.insert(1, templates.make_heading("DIFFERENTIAL COUNT"))
        templates.save_panel(CBC, rows)

        self.form.refresh_panels()
        self.form.panel_boxes[CBC].setChecked(True)

        self.assertEqual(self.form.table.item(0, 3).text(), "14.0 - 18.0")
        self.assertTrue(self.form.is_heading_row(1))

    def test_refresh_keeps_the_operators_typed_results(self):
        self.form.panel_boxes[CBC].setChecked(True)
        self.form.table.item(0, 1).setText("13.4")
        self.form.refresh_panels()

        self.assertTrue(self.form.panel_boxes[CBC].isChecked())
        self.assertEqual(self.form.table.item(0, 1).text(), "13.4")

    def test_headings_are_saved_and_reloaded_with_the_report(self):
        from app import templates

        templates.create_panel("P", [templates.make_heading("SECTION"),
                                     templates.make_test("A", "u", "1 - 2")])
        self.form.refresh_panels()
        self.form.f_name.setText("Jane Doe")
        self.form.f_age.setText("30")
        self.form.panel_boxes["P"].setChecked(True)
        self.form.table.item(1, 1).setText("1.5")
        self.assertTrue(self.form.save())

        stored = self.storage.load_report(self.form.current_id)
        self.assertTrue(stored.rows[0].is_heading())
        self.assertEqual(stored.rows[0].name, "SECTION")
        self.assertEqual(stored.rows[1].result, "1.5")

    def test_headings_print_as_a_section_row(self):
        from app import templates
        from app.report_html import build

        templates.create_panel("P", [templates.make_heading("SECTION"),
                                     templates.make_test("A", "u", "1 - 2")])
        self.form.refresh_panels()
        self.form.f_name.setText("Jane Doe")
        self.form.f_age.setText("30")
        self.form.panel_boxes["P"].setChecked(True)
        self.form.table.item(1, 1).setText("1.5")

        html = build(self.form.collect(), self.storage.load_profile())
        self.assertIn("subhead", html)
        self.assertIn("SECTION", html)

    def test_headings_are_never_flagged_or_counted(self):
        from app import templates

        templates.create_panel("P", [templates.make_heading("SECTION"),
                                     templates.make_test("A", "u", "1 - 2")])
        self.form.refresh_panels()
        self.form.panel_boxes["P"].setChecked(True)
        self.assertIn("1 test", self.form.row_count_label.text())

    def test_the_editor_page_lists_every_panel(self):
        from app import templates

        page = self.templates_page()
        page.reload()
        self.assertEqual(page.panel_list.count(), len(templates.panel_names()))

    def test_saving_from_the_editor_updates_the_form(self):
        page = self.templates_page()
        page.reload(select=CBC)
        page.add_heading()
        page.table.item(page.table.rowCount() - 1, 1).setText("EXTRA SECTION")
        page.save_panel()

        self.assertIn(CBC, self.form.panel_boxes)
        self.form.panel_boxes[CBC].setChecked(True)
        names = [self.form.table.item(r, 0).text()
                 for r in range(self.form.table.rowCount())]
        self.assertIn("EXTRA SECTION", names)


class GridConstraintTests(UICase):
    """Unit and reference cells are not free text."""

    def setup_row(self):
        self.fill()
        return 0

    def test_a_bad_unit_blocks_saving(self):
        self.setup_row()
        self.form.table.item(0, 2).setText("!!!")
        self.assertFalse(self.form.save())
        self.assertIn("unit", self.last_message()[0].lower())

    def test_a_bad_reference_blocks_saving(self):
        self.setup_row()
        self.form.table.item(0, 3).setText("13 abc")
        self.assertFalse(self.form.save())
        self.assertIn("reference", self.last_message()[0].lower())

    def test_a_bad_test_name_blocks_saving(self):
        self.setup_row()
        self.form.table.item(0, 0).setText("<script>")
        self.assertFalse(self.form.save())
        self.assertIn("test", self.last_message()[0].lower())

    def test_a_blank_sub_heading_blocks_saving(self):
        from app.models import TestRow

        self.fill()
        self.form._append_row(TestRow("Investigations", "", "", "", "", "heading"))
        self.assertFalse(self.form.save())
        self.assertIn("sub-heading", self.last_message()[0].lower())

    def test_valid_units_and_ranges_save(self):
        self.setup_row()
        self.form.table.item(0, 2).setText("g/dL")
        self.form.table.item(0, 3).setText("13.0 - 17.0")
        self.assertTrue(self.form.save())

    def test_qualitative_ranges_still_save(self):
        self.setup_row()
        self.form.table.item(0, 2).setText("")
        self.form.table.item(0, 3).setText("Absent")
        self.form.table.item(0, 1).setText("Absent")
        self.assertTrue(self.form.save())

    def test_a_bad_cell_is_marked_red(self):
        """A background tint is swallowed by the ::item stylesheet, so the
        marking has to be foreground colour."""
        from app.ui.theme import DANGER

        self.setup_row()
        self.form.table.item(0, 3).setText("13 abc")
        item = self.form.table.item(0, 3)
        self.assertEqual(item.foreground().color().name(), DANGER)
        self.assertTrue(item.font().bold())
        self.assertIn("reference range", item.toolTip())

    def test_marking_invalid_cells_does_not_wipe_the_flag(self):
        """Regression: the valid-cell reset used to clear the H / L red."""
        self.setup_row()
        self.form.table.item(0, 1).setText("9.2")        # below 13.0 - 17.0
        self.form.table.item(0, 2).setText("!!!")        # invalid unit nearby

        result = self.form.table.item(0, 1)
        self.assertEqual(result.foreground().color().name(), "#c00000")
        self.assertTrue(result.font().bold())

    def test_an_invalid_result_beats_the_high_low_flag(self):
        self.setup_row()
        self.form.table.item(0, 1).setText("x" * 60)
        self.assertIn("too long", self.form.table.item(0, 1).toolTip())

    def test_fixing_a_cell_clears_the_marking(self):
        self.setup_row()
        self.form.table.item(0, 3).setText("13 abc")
        self.form.table.item(0, 3).setText("13 - 17")
        self.assertNotEqual(self.form.table.item(0, 3).toolTip(), "13 abc")
        self.assertEqual(self.form.table.item(0, 3).toolTip(), "")

    def test_headings_are_exempt(self):
        """A heading has no unit or range, so it must not be validated as one."""
        from app.models import TestRow

        self.fill()
        self.form._append_row(TestRow("Investigations", "SECTION", "", "", "", "heading"))
        self.assertTrue(self.form.save())


class DateFieldTests(UICase):
    """Dates are pickers, so an unparseable date is unreachable."""

    def test_dates_are_pickers_not_text_boxes(self):
        from PySide6.QtWidgets import QDateTimeEdit

        self.assertIsInstance(self.form.f_collected, QDateTimeEdit)
        self.assertIsInstance(self.form.f_reported, QDateTimeEdit)

    def test_a_new_report_defaults_to_now(self):
        from PySide6.QtCore import QDateTime

        delta = abs(self.form.f_collected.dateTime().secsTo(QDateTime.currentDateTime()))
        self.assertLess(delta, 60)

    def test_the_saved_date_is_formatted_not_freeform(self):
        import re

        self.fill()
        self.form.save()
        stored = self.storage.load_report(self.form.current_id)
        self.assertRegex(stored.collected_on,
                         r"^\d{2}-\d{2}-\d{4} \d{2}:\d{2} (AM|PM)$")

    def test_reopening_restores_the_date(self):
        self.fill()
        self.form.save()
        stored = self.storage.load_report(self.form.current_id)
        self.form.load_report(stored)
        self.assertEqual(
            self.form.f_collected.dateTime().toString("dd-MM-yyyy hh:mm AP"),
            stored.collected_on)

    def test_an_older_unreadable_date_falls_back_to_now(self):
        """Reports saved before the pickers existed may hold anything."""
        from app.models import Report, TestRow

        legacy = self.storage.save_report(Report(
            patient_name="Old Record", age="40", sex="M", collected_on="asdf",
            rows=[TestRow("CBC", "Hb", "14", "g/dL", "13 - 17")]))
        self.form.load_report(legacy)
        self.assertTrue(self.form.f_collected.dateTime().isValid())


class TemplateConstraintTests(UICase):
    def page(self):
        page = self.window.templates
        page.reload(select=CBC)
        return page

    def test_a_bad_unit_blocks_the_panel_save(self):
        page = self.page()
        page.table.item(0, 2).setText("!!!")
        page.save_panel()
        self.assertIn("unit", self.last_message()[0].lower())

    def test_a_bad_range_blocks_the_panel_save(self):
        page = self.page()
        page.table.item(0, 3).setText("about 13")
        page.save_panel()
        self.assertIn("reference range", self.last_message()[0].lower())

    def test_a_panel_of_only_headings_is_refused(self):
        from app import templates

        templates.create_panel("Empty", [templates.make_heading("ONLY A TITLE")])
        page = self.window.templates
        page.reload(select="Empty")
        page.save_panel()
        self.assertIn("at least one test", self.last_message()[0].lower())

    def test_a_valid_edit_saves(self):
        page = self.page()
        page.table.item(0, 3).setText("14.0 - 18.0")
        page.save_panel()
        self.assertEqual(self.last_message()[1], "success")

    def test_headings_are_exempt_from_unit_rules(self):
        page = self.page()
        page.add_heading()
        r = page.table.rowCount() - 1
        page.table.item(r, 1).setText("DIFFERENTIAL COUNT")
        page.save_panel()
        self.assertEqual(self.last_message()[1], "success")


class ProfileConstraintTests(UICase):
    def test_control_characters_are_refused(self):
        settings = self.window.settings
        settings.edits["lab_name"].setText("Lab" + chr(0) + "Name")
        settings.save()
        self.assertEqual(self.last_message()[1], "warning")

    def test_the_address_field_caps_its_own_length(self):
        """The field enforces the limit itself, so over-long text never
        reaches the save-time check."""
        field = self.window.settings.edits["address1"]
        field.setText("x" * 200)
        self.assertLessEqual(len(field.text()), V.MAX_TEXT_LINE)

    def test_every_profile_field_has_a_length_cap(self):
        for key, edit in self.window.settings.edits.items():
            self.assertGreater(edit.maxLength(), 0, key)
            self.assertLessEqual(edit.maxLength(), 200, key)

    def test_a_normal_profile_saves(self):
        settings = self.window.settings
        settings.edits["lab_name"].setText("Sunrise Diagnostics")
        settings.edits["address1"].setText("#42, MG Road, Bengaluru 560001")
        settings.edits["pathologist_degrees"].setText("MD (Pathology)")
        settings.save()
        self.assertEqual(self.storage.load_profile().lab_name, "Sunrise Diagnostics")


class ToastTests(UICase):
    def test_default_duration_is_five_seconds(self):
        from app.ui.toast import Toast

        self.assertEqual(Toast.DEFAULT_MSECS, 5000)

    def test_showing_a_message_uses_the_default_duration(self):
        from app.ui.toast import Toast

        toast = Toast(self.window)
        toast.show_message("Saved")
        self.assertEqual(toast.hide_timer.interval(), Toast.DEFAULT_MSECS)

    def test_an_explicit_duration_still_wins(self):
        from app.ui.toast import Toast

        toast = Toast(self.window)
        toast.show_message("Saved", "success", 9000)
        self.assertEqual(toast.hide_timer.interval(), 9000)

    def test_repeated_show_and_fade_emits_no_qt_warnings(self):
        """Regression: reconnecting the fade signal each time warned on stderr."""
        import warnings

        from app.ui.toast import Toast

        toast = Toast(self.window)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            for _ in range(3):
                toast.show_message("Saved")
                toast._fade_out()
                toast._fade_finished()
        self.assertEqual([str(w.message) for w in caught], [])

    def test_banner_hides_only_after_fading_out(self):
        from app.ui.toast import Toast

        toast = Toast(self.window)
        # isVisible() is False while the parent window itself is unshown, so
        # isHidden() is what actually reflects the explicit hide() call.
        toast.show_message("Saved")
        toast._fade_finished()                 # end of the fade-IN
        self.assertFalse(toast.isHidden(), "must stay shown after fading in")

        toast._fade_out()
        toast._fade_finished()                 # end of the fade-OUT
        self.assertTrue(toast.isHidden())

    def test_toast_clears_the_header_bar(self):
        from app.ui.toast import Toast

        toast = Toast(self.window)
        toast.show_message("Saved")
        self.assertGreaterEqual(toast.y(), 62)


class DirtyStateTests(UICase):
    def test_a_fresh_form_is_not_dirty(self):
        self.assertFalse(self.form.is_dirty())

    def test_typing_a_name_makes_it_dirty(self):
        self.form.f_name.setText("Jane")
        self.assertTrue(self.form.is_dirty())

    def test_loading_a_panel_makes_it_dirty(self):
        self.form.panel_boxes[CBC].setChecked(True)
        self.assertTrue(self.form.is_dirty())

    def test_clearing_makes_it_clean_again(self):
        self.fill()
        self.form.new_report()
        self.assertFalse(self.form.is_dirty())


class HistorySelectionTests(UICase):
    def seed(self, count=3):
        for name in NAMES[:count]:
            self.form.new_report()
            self.fill(name=name)
            self.form.save()
        self.history.reload()

    def test_history_lists_saved_reports(self):
        self.seed()
        self.assertEqual(self.history.table.rowCount(), 3)

    def test_checkboxes_start_unticked(self):
        self.seed()
        self.assertEqual(self.history.checked_ids(), [])
        self.assertFalse(self.history.delete_selected_btn.isEnabled())

    def test_ticking_enables_the_delete_button(self):
        self.seed()
        self.history.table.item(0, 0).setCheckState(Qt.Checked)
        self.assertEqual(len(self.history.checked_ids()), 1)
        self.assertTrue(self.history.delete_selected_btn.isEnabled())
        self.assertIn("(1)", self.history.delete_selected_btn.text())

    def test_select_all_ticks_everything(self):
        self.seed()
        self.history.select_all.setChecked(True)
        self.history._toggle_all()
        self.assertEqual(len(self.history.checked_ids()), 3)

    def test_select_all_only_covers_filtered_rows(self):
        """A search term must scope the bulk action, or it silently deletes
        reports the operator cannot even see."""
        self.seed()
        self.history.search.setText(NAMES[1])
        self.assertEqual(self.history.table.rowCount(), 1)
        self.history.select_all.setChecked(True)
        self.history._toggle_all()
        self.assertEqual(len(self.history.checked_ids()), 1)

    def test_search_matches_patient_id_and_report_no(self):
        self.seed()
        entry = self.storage.load_index()[0]
        self.history.search.setText(entry["patient_id"])
        self.assertEqual(self.history.table.rowCount(), 1)
        self.history.search.setText(entry["report_no"])
        self.assertEqual(self.history.table.rowCount(), 1)

    def test_search_is_case_insensitive(self):
        self.seed()
        self.history.search.setText(NAMES[0].lower())
        self.assertEqual(self.history.table.rowCount(), 1)

    def test_ticks_reset_when_the_list_is_refilled(self):
        self.seed()
        self.history.table.item(0, 0).setCheckState(Qt.Checked)
        self.history.reload()
        self.assertEqual(self.history.checked_ids(), [])


class BulkDeleteTests(UICase):
    def seed(self, count=4):
        for name in NAMES[:count]:
            self.form.new_report()
            self.fill(name=name)
            self.form.save()
        self.history.reload()

    def confirm_yes(self, unlocked=True):
        from PySide6.QtWidgets import QMessageBox
        self._orig_question = QMessageBox.question
        QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
        self.allow_unlock(unlocked)

    def confirm_no(self):
        from PySide6.QtWidgets import QMessageBox
        self._orig_question = QMessageBox.question
        QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.No)

    def tearDown(self):
        if hasattr(self, "_orig_question"):
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.question = self._orig_question
        super().tearDown()

    def test_deleting_several_at_once(self):
        self.seed()
        for r in (0, 2):
            self.history.table.item(r, 0).setCheckState(Qt.Checked)
        self.confirm_yes()
        self.history.delete_checked()

        self.assertEqual(self.history.table.rowCount(), 2)
        self.assertEqual(len(self.storage.load_index()), 2)

    def test_deleting_everything(self):
        self.seed()
        self.history.select_all.setChecked(True)
        self.history._toggle_all()
        self.confirm_yes()
        self.history.delete_checked()

        self.assertEqual(self.history.table.rowCount(), 0)
        self.assertEqual(self.storage.load_index(), [])

    def test_declining_the_confirmation_deletes_nothing(self):
        self.seed()
        self.history.table.item(0, 0).setCheckState(Qt.Checked)
        self.confirm_no()
        self.history.delete_checked()
        self.assertEqual(len(self.storage.load_index()), 4)

    def test_deletion_is_refused_without_the_password(self):
        self.seed()
        self.history.table.item(0, 0).setCheckState(Qt.Checked)
        self.confirm_yes(unlocked=False)
        self.history.delete_checked()
        self.assertEqual(len(self.storage.load_index()), 4)

    def test_delete_with_nothing_ticked_warns(self):
        self.seed()
        self.history.delete_checked()
        self.assertEqual(self.last_message()[1], "warning")
        self.assertEqual(len(self.storage.load_index()), 4)


class StaleFormTests(UICase):
    """Reported bug: after deleting the history the form still showed the old
    report, and saving it would have resurrected the deleted record."""

    def test_form_resets_when_the_open_report_is_deleted(self):
        self.fill()
        self.form.save()
        report_id = self.form.current_id
        self.assertNotEqual(report_id, "")

        self.history.reload()
        self.history.select_all.setChecked(True)
        self.history._toggle_all()
        self.allow_unlock()
        from PySide6.QtWidgets import QMessageBox
        original = QMessageBox.question
        QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
        try:
            self.history.delete_checked()
        finally:
            QMessageBox.question = original

        self.assertEqual(self.form.current_id, "")
        self.assertEqual(self.form.f_name.text(), "")
        self.assertEqual(self.form.table.rowCount(), 0)
        self.assertFalse(self.form.is_dirty())

    def test_a_different_report_being_deleted_leaves_the_form_alone(self):
        self.fill(name="Keep Me")
        self.form.save()
        kept_id = self.form.current_id

        self.assertFalse(self.form.forget_if_deleted(["some-other-id"]))
        self.assertEqual(self.form.current_id, kept_id)
        self.assertEqual(self.form.f_name.text(), "Keep Me")

    def test_forget_if_deleted_is_a_no_op_for_an_unsaved_form(self):
        self.fill()
        self.assertFalse(self.form.forget_if_deleted([""]))
        self.assertEqual(self.form.f_name.text(), "Jane Doe")

    def test_deleted_report_cannot_be_resurrected_by_saving(self):
        self.fill()
        self.form.save()
        report_id = self.form.current_id
        self.storage.delete_reports([report_id])
        self.window._on_reports_deleted([report_id])

        self.assertEqual(self.storage.load_index(), [])
        self.assertEqual(self.form.current_id, "")


class MainWindowTests(UICase):
    def test_sidebar_lists_every_destination(self):
        labels = [self.window.nav.label(i)
                  for i in range(len(self.window.nav.buttons))]
        self.assertEqual(labels, ["New Report", "Report History",
                                  "Test Templates", "Laboratory Profile"])

    def test_every_destination_has_a_page(self):
        self.assertEqual(self.window.stack.count(), len(self.window.nav.buttons))

    def test_sidebar_and_page_stay_in_sync(self):
        self.window.go_to(1)
        self.assertEqual(self.window.stack.currentIndex(), 1)
        self.assertEqual(self.window.nav.current(), 1)

        self.window.nav.buttons[3].click()
        self.assertEqual(self.window.stack.currentIndex(), 3)

    def test_page_headers_show_the_lab_name(self):
        self.assertIn("Test Lab", self.window.form.header.subtitle.text())
        self.assertIn("Test Lab", self.window.history.header.subtitle.text())

    def test_saving_a_report_refreshes_history(self):
        self.fill()
        self.form.save()
        self.assertEqual(self.history.table.rowCount(), 1)

    def test_opening_from_history_switches_to_the_form(self):
        self.fill(name="Ravi")
        self.form.save()
        self.history.reload()
        self.history.table.selectRow(0)
        self.history.open_selected()

        self.assertEqual(self.window.stack.currentIndex(), 0)
        self.assertEqual(self.window.nav.current(), 0)
        self.assertEqual(self.form.f_name.text(), "Ravi")

    def test_first_run_lands_on_the_profile_page(self):
        self.storage.save_profile(LabProfile())
        from app.ui.main_window import MainWindow
        from app.ui.main_window import SETTINGS
        window = MainWindow()
        try:
            self.assertEqual(window.stack.currentIndex(), SETTINGS)
            self.assertEqual(window.nav.current(), SETTINGS)
        finally:
            window.close()


class PrintingTests(UICase):
    def test_pdf_export_produces_a_real_file(self):
        from app import printing
        from app.report_html import build

        self.fill()
        self.form.save()
        report = self.storage.load_report(self.form.current_id)
        path = os.path.join(self.sandbox, "out.pdf")
        printing.export_pdf(build(report, self.storage.load_profile()), path)

        self.assertTrue(os.path.isfile(path))
        self.assertGreater(os.path.getsize(path), 1000)
        with open(path, "rb") as fh:
            self.assertTrue(fh.read(4).startswith(b"%PDF"))


class BillingFormTests(UICase):
    """The billing section of the New Report page, walked through the way an
    operator uses it. These are the acceptance criteria for the change request."""

    def price(self, service, amount):
        for row in range(self.form.bill_table.rowCount()):
            if self.form.bill_table.item(row, 0).text() == service:
                self.form.bill_table.item(row, 1).setText(amount)
                return
        self.fail(f"{service} is not on the bill")

    def services(self):
        return [self.form.bill_table.item(r, 0).text()
                for r in range(self.form.bill_table.rowCount())]

    def amounts(self):
        return {self.form.bill_table.item(r, 0).text():
                self.form.bill_table.item(r, 1).text()
                for r in range(self.form.bill_table.rowCount())}

    # AC-01 -----------------------------------------------------------------
    def test_the_billing_section_is_part_of_the_new_report_page(self):
        for widget in (self.form.f_bill_no, self.form.f_bill_date,
                       self.form.bill_table, self.form.f_deposit):
            self.assertIsNotNone(widget)
            self.assertIs(widget.window(), self.window)

    def test_a_blank_form_starts_with_an_empty_bill(self):
        self.assertEqual(self.form.bill_table.rowCount(), 0)
        self.assertEqual(self.form.l_total.text(), "0.00")
        self.assertEqual(self.form.l_balance.text(), "0.00")

    # AC-02 -----------------------------------------------------------------
    def test_a_bill_number_and_date_are_offered_before_anything_is_typed(self):
        self.assertEqual(self.form.f_bill_no.text(), self.storage.peek_bill_no())
        self.assertTrue(self.form.f_bill_date.date().isValid())

    def test_the_bill_number_can_be_overwritten_by_the_lab(self):
        self.fill()
        self.form.f_bill_no.setText("CASH-42")
        self.assertTrue(self.form.save())
        self.assertEqual(
            self.storage.load_report(self.form.current_id).billing.bill_no, "CASH-42")

    def test_a_blank_bill_number_is_filled_in_on_save(self):
        self.fill()
        self.form.f_bill_no.clear()
        self.assertTrue(self.form.save())
        self.assertTrue(self.form.f_bill_no.text().startswith("BILL-"))

    # AC-03 / AC-10 ---------------------------------------------------------
    def test_ticking_a_panel_adds_it_to_the_bill(self):
        self.fill()
        self.assertEqual(self.services(), [CBC])

    def test_a_second_panel_adds_a_second_line(self):
        self.fill()
        self.form.panel_boxes[LIPID].setChecked(True)
        self.assertEqual(self.services(), [CBC, LIPID])

    def test_unticking_a_panel_takes_its_line_off_the_bill(self):
        self.fill()
        self.form.panel_boxes[LIPID].setChecked(True)
        self.form.panel_boxes[LIPID].setChecked(False)
        self.assertEqual(self.services(), [CBC])

    def test_a_panel_bills_once_however_many_tests_it_holds(self):
        self.fill()
        self.assertGreater(self.form.table.rowCount(), 5)
        self.assertEqual(len(self.services()), 1)

    def test_changing_the_panels_keeps_the_amounts_already_typed(self):
        self.fill()
        self.price(CBC, "400")
        self.form.panel_boxes[LIPID].setChecked(True)
        self.assertEqual(self.amounts(), {CBC: "400", LIPID: ""})

    def test_removing_a_panel_leaves_the_other_amounts_alone(self):
        self.fill()
        self.price(CBC, "400")
        self.form.panel_boxes[LIPID].setChecked(True)
        self.price(LIPID, "600")
        self.form.panel_boxes[LIPID].setChecked(False)
        self.assertEqual(self.amounts(), {CBC: "400"})
        self.assertEqual(self.form.l_total.text(), "400.00")

    def test_a_hand_added_test_becomes_billable_once_it_is_named(self):
        self.fill()
        self.form._add_blank_row()
        self.assertEqual(self.services(), [CBC])
        last = self.form.table.rowCount() - 1
        self.form.table.item(last, 0).setText("Dengue NS1")
        self.assertEqual(self.services(), [CBC, "Investigations"])

    def test_the_service_name_cannot_be_edited_away_from_the_results(self):
        self.fill()
        self.assertFalse(self.form.bill_table.item(0, 0).flags() & Qt.ItemIsEditable)

    # AC-04 / AC-05 / AC-06 / AC-07 -----------------------------------------
    def test_totals_update_as_amounts_are_typed(self):
        self.fill()
        self.price(CBC, "400")
        self.form.panel_boxes[LIPID].setChecked(True)
        self.price(LIPID, "600")
        self.assertEqual(self.form.l_total.text(), "1,000.00")
        self.assertEqual(self.form.l_payable.text(), "1,000.00")

    def test_the_deposit_reduces_the_balance(self):
        self.fill()
        self.price(CBC, "400")
        self.form.f_deposit.setText("250")
        self.assertEqual(self.form.l_balance.text(), "150.00")

    def test_a_blank_deposit_leaves_the_whole_bill_outstanding(self):
        self.fill()
        self.price(CBC, "400")
        self.assertEqual(self.form.l_balance.text(), "400.00")

    def test_a_settled_bill_shows_a_cleared_balance(self):
        self.fill()
        self.price(CBC, "400")
        self.form.f_deposit.setText("400")
        self.assertEqual(self.form.l_balance.text(), "0.00")
        self.assertEqual(self.form.l_balance.objectName(), "BillBalanceClear")

    def test_an_outstanding_balance_is_shown_in_the_alarming_colour(self):
        self.fill()
        self.price(CBC, "400")
        self.assertEqual(self.form.l_balance.objectName(), "BillBalance")

    def test_an_unusable_amount_is_marked_and_left_out_of_the_total(self):
        self.fill()
        self.price(CBC, "abc")
        cell = self.form.bill_table.item(0, 1)
        self.assertEqual(cell.foreground().color().name().lower(), DANGER.lower())
        self.assertTrue(cell.toolTip())
        self.assertEqual(self.form.l_total.text(), "0.00")

    # validation ------------------------------------------------------------
    def test_an_unusable_amount_blocks_saving(self):
        self.fill()
        self.price(CBC, "abc")
        self.assertFalse(self.form.save())
        self.assertEqual(self.last_message()[1], "warning")
        self.assertIn("amount", self.last_message()[0])

    def test_a_deposit_larger_than_the_bill_blocks_saving(self):
        self.fill()
        self.price(CBC, "400")
        self.form.f_deposit.setText("500")
        self.assertFalse(self.form.save())
        self.assertEqual(self.last_message()[1], "warning")
        self.assertIn("net deposit", self.last_message()[0])

    def test_a_bad_bill_number_blocks_saving(self):
        self.fill()
        self.form.f_bill_no.setText("BILL#1")
        self.assertFalse(self.form.save())
        self.assertEqual(self.last_message()[1], "warning")

    def test_a_report_with_no_billing_at_all_still_saves(self):
        """Billing is an addition, not a new requirement: a lab that ignores it
        must be able to go on producing reports exactly as before."""
        self.fill()
        self.assertTrue(self.form.save())

    def test_typing_letters_into_the_deposit_is_blocked(self):
        self.form.f_deposit.setText("")
        QTest.keyClicks(self.form.f_deposit, "abc")
        self.assertEqual(self.form.f_deposit.text(), "")

    def test_typing_an_amount_into_the_deposit_works(self):
        self.form.f_deposit.setText("")
        QTest.keyClicks(self.form.f_deposit, "350.50")
        self.assertEqual(self.form.f_deposit.text(), "350.50")

    # AC-11 -----------------------------------------------------------------
    def test_a_saved_report_keeps_its_billing(self):
        self.fill()
        self.price(CBC, "400")
        self.form.f_deposit.setText("250")
        self.form.save()
        stored = self.storage.load_report(self.form.current_id).billing
        self.assertEqual(stored.net_deposit, "250")
        self.assertEqual([(i.service, i.amount) for i in stored.items],
                         [(CBC, "400")])

    def test_reopening_a_report_shows_the_billing_it_was_saved_with(self):
        self.fill()
        self.price(CBC, "400")
        self.form.f_deposit.setText("250")
        self.form.save()
        report = self.storage.load_report(self.form.current_id)

        self.form.new_report()
        self.form.load_report(report)
        self.assertEqual(self.form.f_bill_no.text(), report.billing.bill_no)
        self.assertEqual(self.amounts(), {CBC: "400"})
        self.assertEqual(self.form.f_deposit.text(), "250")
        self.assertEqual(self.form.l_balance.text(), "150.00")

    def test_a_saved_bill_is_read_only_until_it_is_unlocked(self):
        self.fill()
        self.price(CBC, "400")
        self.form.save()
        report = self.storage.load_report(self.form.current_id)
        self.form.load_report(report)

        self.assertTrue(self.form.f_bill_no.isReadOnly())
        self.assertTrue(self.form.f_deposit.isReadOnly())
        self.assertEqual(self.form.bill_table.editTriggers(),
                         QAbstractItemView.NoEditTriggers)

        self.allow_unlock(True)
        self.form.request_edit_access()
        self.assertFalse(self.form.f_deposit.isReadOnly())
        self.assertNotEqual(self.form.bill_table.editTriggers(),
                            QAbstractItemView.NoEditTriggers)

    def test_a_duplicate_starts_a_fresh_bill(self):
        """Duplicate as New is a repeat visit: it keeps the patient and the
        panels, so it must not carry the previous visit's payment across."""
        self.fill()
        self.price(CBC, "400")
        self.form.f_deposit.setText("250")
        self.form.save()
        report = self.storage.load_report(self.form.current_id)

        self.form.load_report(report, as_copy=True)
        self.assertNotEqual(self.form.f_bill_no.text(), report.billing.bill_no)
        self.assertEqual(self.form.f_deposit.text(), "")
        self.assertEqual(self.amounts(), {CBC: ""})

    def test_clearing_the_form_clears_the_bill(self):
        self.fill()
        self.price(CBC, "400")
        self.form.new_report()
        self.assertEqual(self.form.bill_table.rowCount(), 0)
        self.assertEqual(self.form.l_total.text(), "0.00")
        self.assertEqual(self.form.f_deposit.text(), "")

    # AC-08 / AC-09 ---------------------------------------------------------
    def test_the_bill_reaches_the_printable_output(self):
        self.fill()
        self.price(CBC, "400")
        self.form.f_deposit.setText("250")
        self.form.attach_bill.setChecked(True)
        html = self.form._html()
        self.assertIn("BILL SUMMARY", html)
        self.assertIn("400.00", html)
        self.assertIn("250.00", html)
        self.assertIn("150.00", html)

    def test_preview_print_and_pdf_all_render_the_same_bill(self):
        """One html builder feeds all three paths, so this asserts the property
        the change request asks for rather than three separate renderings."""
        self.fill()
        self.price(CBC, "400")
        self.form.save()
        report = self.storage.load_report(self.form.current_id)
        from app.report_html import build

        self.assertEqual(self.form._html(),
                         build(report, self.storage.load_profile(), with_bill=False))
        self.form.attach_bill.setChecked(True)
        self.assertEqual(self.form._html(),
                         build(report, self.storage.load_profile(), with_bill=True))

    def test_a_report_with_no_amounts_prints_no_bill_section(self):
        self.fill()
        self.assertNotIn("BILL SUMMARY", self.form._html())

    def test_the_exported_pdf_of_a_billed_report_is_a_real_pdf(self):
        import os

        from app import printing
        from app.report_html import build

        self.fill()
        self.price(CBC, "400")
        self.form.save()
        report = self.storage.load_report(self.form.current_id)
        path = os.path.join(self.sandbox, "bill.pdf")
        printing.export_pdf(build(report, self.storage.load_profile()), path)
        self.assertTrue(os.path.isfile(path))
        self.assertGreater(os.path.getsize(path), 1000)

    # AC-12 -----------------------------------------------------------------
    def test_the_existing_workflow_is_untouched(self):
        """Everything the form did before billing existed, in one pass."""
        self.fill()
        self.assertTrue(self.form.save())
        self.assertEqual(self.last_message()[1], "success")
        report = self.storage.load_report(self.form.current_id)
        self.assertEqual(report.patient_name, "Jane Doe")
        self.assertEqual(report.rows[0].result, "14.0")
        self.assertTrue(report.report_no.startswith("BR-"))
        self.assertTrue(report.patient_id.startswith("HFCD-"))

        self.history.reload()
        self.assertEqual(self.history.table.rowCount(), 1)

        html = self.form._html()
        self.assertIn("Jane Doe", html)
        self.assertIn("Haemoglobin (Hb)", html)
        self.assertIn("End of Report", html)


class PatientPhoneTests(UICase):
    def test_the_field_is_on_the_patient_card(self):
        self.assertIsNotNone(self.form.f_phone)
        self.assertIn("phone", FIELD_HELP)

    def test_typing_letters_is_blocked(self):
        QTest.keyClicks(self.form.f_phone, "abc")
        self.assertEqual(self.form.f_phone.text(), "")

    def test_a_real_number_is_typeable(self):
        QTest.keyClicks(self.form.f_phone, "+91 96200-55441")
        self.assertEqual(self.form.f_phone.text(), "+91 96200-55441")

    def test_it_is_optional(self):
        self.fill()
        self.assertTrue(self.form.save())

    def test_a_too_short_number_blocks_saving(self):
        self.fill()
        self.form.f_phone.setText("123")
        self.assertFalse(self.form.save())
        self.assertEqual(self.last_message()[1], "warning")

    def test_it_is_saved_and_reloaded_with_the_report(self):
        self.fill()
        self.form.f_phone.setText("9620055441")
        self.form.save()
        report = self.storage.load_report(self.form.current_id)
        self.assertEqual(report.phone, "+91 9620055441")

        self.form.new_report()
        self.form.load_report(report)
        self.assertEqual(self.form.f_phone.text(), "+91 9620055441")

    def test_it_locks_with_the_rest_of_a_saved_report(self):
        self.fill()
        self.form.save()
        self.form.load_report(self.storage.load_report(self.form.current_id))
        self.assertTrue(self.form.f_phone.isReadOnly())

    def test_it_reaches_the_bill(self):
        self.fill()
        self.form.f_phone.setText("9620055441")
        self.form.bill_table.item(0, 1).setText("400")
        self.assertIn("9620055441", self.form._bill_html())


class BillDocumentTests(UICase):
    """The standalone bill: a document in its own right, printed at the counter
    before any result exists."""

    def billed(self, amount="400", deposit=""):
        self.fill()
        self.form.bill_table.item(0, 1).setText(amount)
        if deposit:
            self.form.f_deposit.setText(deposit)

    def test_the_bill_actions_are_on_the_billing_card(self):
        self.assertEqual(len(self.form.bill_buttons), 3)
        for button in self.form.bill_buttons:
            self.assertIs(button.window(), self.window)

    def test_the_bill_is_a_different_document_from_the_report(self):
        self.billed()
        bill, report = self.form._bill_html(), self.form._html()
        self.assertNotEqual(bill, report)
        self.assertIn("Cash Bill", bill)
        self.assertNotIn("LABORATORY TEST REPORT", bill)
        self.assertNotIn("Haemoglobin (Hb)", bill)

    def test_the_bill_carries_the_patient_and_the_charges(self):
        self.billed(deposit="150")
        html = self.form._bill_html()
        for expected in ("Jane Doe", "Services", "Net Amount", "400.00",
                         "150.00", "250.00", "One Hundred Fifty Rupees Only"):
            self.assertIn(expected, html)

    def test_the_bill_uses_the_allocated_number(self):
        self.billed()
        self.form.save()
        self.assertIn(self.form.f_bill_no.text(), self.form._bill_html())

    def test_printing_a_bill_with_no_amounts_is_refused(self):
        self.fill()
        printed = []
        self.stub_print(printed)
        self.form.print_bill()
        self.assertEqual(printed, [])
        self.assertEqual(self.last_message()[1], "warning")
        self.assertIn("amount", self.last_message()[0])

    def test_an_invalid_report_blocks_the_bill(self):
        """The bill is printed off the same form, so it cannot escape the
        validation the report is held to."""
        self.billed()
        self.form.f_name.clear()
        printed = []
        self.stub_print(printed)
        self.form.print_bill()
        self.assertEqual(printed, [])
        self.assertEqual(self.last_message()[1], "warning")

    def test_printing_a_bill_saves_the_report_first(self):
        """Nothing leaves the counter unrecorded - the same rule the report's
        Save and Print follows."""
        self.billed()
        printed = []
        self.stub_print(printed)
        self.form.print_bill()
        self.assertEqual(len(printed), 1)
        self.assertTrue(self.form.current_id)
        self.assertEqual(len(self.storage.load_index()), 1)
        self.assertEqual(self.last_message()[1], "success")

    def test_a_saved_report_can_still_have_its_bill_reprinted(self):
        self.billed()
        self.form.save()
        self.form.load_report(self.storage.load_report(self.form.current_id))
        self.assertTrue(self.form.read_only)
        printed = []
        self.stub_print(printed)
        self.form.print_bill()
        self.assertEqual(len(printed), 1)
        self.assertEqual(len(self.storage.load_index()), 1)

    def test_preview_does_not_save(self):
        self.billed()
        previewed = []
        self.stub_preview(previewed)
        self.form.preview_bill()
        self.assertEqual(len(previewed), 1)
        self.assertEqual(self.storage.load_index(), [])

    def test_the_printer_dialog_says_which_document_it_is(self):
        self.billed()
        printed = []
        self.stub_print(printed)
        self.form.print_bill()
        self.assertEqual(printed[0][1], "Print Bill")

    def test_the_exported_bill_is_a_real_pdf(self):
        import os

        from app import printing

        self.billed(deposit="400")
        path = os.path.join(self.sandbox, "bill.pdf")
        printing.export_pdf(self.form._bill_html(), path)
        self.assertTrue(os.path.isfile(path))
        self.assertGreater(os.path.getsize(path), 1000)
        with open(path, "rb") as fh:
            self.assertTrue(fh.read(4).startswith(b"%PDF"))

    def test_the_report_prints_clean_unless_the_bill_is_attached(self):
        """The two documents are separate by default: the report prints without
        the bill summary, and the tickbox puts it back on the same sheet."""
        self.billed(deposit="150")
        self.assertFalse(self.form.attach_bill.isChecked())
        self.assertNotIn("BILL SUMMARY", self.form._html())
        self.form.attach_bill.setChecked(True)
        self.assertIn("BILL SUMMARY", self.form._html())


class BillFieldTests(UICase):
    """The fields added so the printed bill matches the lab's own slip."""

    def billed(self):
        self.fill()
        self.form.bill_table.item(0, 1).setText("400")
        self.form.f_deposit.setText("400")

    def test_a_new_bill_is_a_cash_bill_with_no_field_to_choose(self):
        """The type is not on the form any more; every bill is the default."""
        from app import billing

        self.assertFalse(hasattr(self.form, "f_bill_type"))
        self.billed()
        self.assertEqual(self.form._collect_billing().bill_type,
                         billing.DEFAULT_BILL_TYPE)
        self.assertIn("Cash Bill", self.form._bill_html())

    def test_a_bill_stored_with_another_type_keeps_it(self):
        self.billed()
        self.form.save()
        report = self.storage.load_report(self.form.current_id)
        report.billing.bill_type = "Credit Bill"
        self.storage.save_report(report)
        self.form.new_report()
        self.form.load_report(self.storage.load_report(report.id))
        self.assertEqual(self.form._collect_billing().bill_type, "Credit Bill")
        self.assertIn("Credit Bill", self.form._bill_html())

    def test_there_is_no_billed_by_field_but_the_bill_has_a_blank_for_it(self):
        self.assertFalse(hasattr(self.form, "f_billed_by"))
        self.billed()
        self.assertEqual(self.form._collect_billing().billed_by, "")
        self.assertIn("Billed By", self.form._bill_html())
        self.assertNotIn("Billed By", self.form._html())

    def test_a_stored_billed_by_name_survives_a_resave_and_prints(self):
        self.billed()
        self.form.save()
        report = self.storage.load_report(self.form.current_id)
        report.billing.billed_by = "Miss. Nethra H M"
        self.storage.save_report(report)
        self.form.new_report()
        self.form.load_report(self.storage.load_report(report.id))
        self.assertEqual(self.form._collect_billing().billed_by, "Miss. Nethra H M")
        self.assertIn("Miss. Nethra H M", self.form._bill_html())

    def test_the_bill_date_carries_a_time(self):
        self.billed()
        stored = self.form._collect_billing().bill_date
        self.assertRegex(stored, r"^\d{2}-\d{2}-\d{4} \d{2}:\d{2}:\d{2} [AP]M$")

    def test_the_new_fields_are_saved_and_reloaded(self):
        self.billed()
        self.form.save()
        report = self.storage.load_report(self.form.current_id)

        self.form.new_report()
        self.form.load_report(report)
        self.assertEqual(
            self.form.f_bill_date.dateTime().toString("dd-MM-yyyy hh:mm:ss AP"),
            report.billing.bill_date)

    def test_they_lock_with_the_rest_of_a_saved_report(self):
        self.billed()
        self.form.save()
        self.form.load_report(self.storage.load_report(self.form.current_id))
        self.assertTrue(self.form.f_bill_no.isReadOnly())
        self.assertFalse(self.form.f_title.isEnabled())

    def test_a_bill_written_by_the_first_build_reopens(self):
        """Those bills stored the day alone and had no type or clerk."""
        from app.models import BillItem, Billing

        self.billed()
        self.form.save()
        report = self.storage.load_report(self.form.current_id)
        report.billing = Billing(bill_no="BILL-000001", bill_date="30-08-2026",
                                 net_deposit="400",
                                 items=[BillItem("Complete Blood Count (CBC)", "400")])
        self.storage.save_report(report)

        self.form.new_report()
        self.form.load_report(self.storage.load_report(report.id))
        self.assertEqual(
            self.form.f_bill_date.dateTime().toString("dd-MM-yyyy"), "30-08-2026")
        self.assertEqual(self.form._collect_billing().bill_type, "Cash Bill")
        self.assertIn("30-Aug-2026", self.form._bill_html())

    def test_the_profile_notes_reach_the_bill(self):
        self.storage.save_profile(LabProfile(
            lab_name="Test Lab", mobile="9964725222",
            bill_notes="Please bring receipt while collecting the report\n"
                       "Working Hours : 7.00 am to 9.00 pm"))
        self.form.new_report()
        self.billed()
        html = self.form._bill_html()
        self.assertIn("Mob: 9964725222", html)
        self.assertIn("Note:", html)
        self.assertIn("Please bring receipt while collecting the report", html)
        self.assertIn("Working Hours : 7.00 am to 9.00 pm", html)


class LabProfileBillFieldTests(UICase):
    def test_the_settings_page_carries_the_new_fields(self):
        settings = self.window.settings
        self.assertIn("mobile", settings.edits)
        self.assertNotIn("billed_by", settings.edits)
        self.assertIsNotNone(settings.bill_notes)

    def test_they_save_and_reload(self):
        settings = self.window.settings
        settings.edits["lab_name"].setText("Mallige Diagnostic Center")
        settings.edits["mobile"].setText("9964725222")
        settings.bill_notes.setPlainText("First note\nSecond note")
        settings.save()

        profile = self.storage.load_profile()
        self.assertEqual(profile.mobile, "+91 9964725222")
        self.assertEqual(profile.bill_notes, "First note\nSecond note")

        settings.load()
        self.assertEqual(settings.bill_notes.toPlainText(), "First note\nSecond note")

    def test_a_brand_new_profile_opens_with_the_standing_terms(self):
        """Day one should not produce a bill with an empty footer."""
        from app.billing import DEFAULT_BILL_NOTES

        self.storage.save_profile(LabProfile())
        self.window.settings.load()
        self.assertEqual(self.window.settings.bill_notes.toPlainText(),
                         DEFAULT_BILL_NOTES)

    def test_an_established_profile_shows_exactly_what_it_stored(self):
        """Including blank. Prefilling every empty box would mean a lab could
        never keep the notes cleared - the defaults they deleted would reappear
        the next time they saved anything at all."""
        self.storage.save_profile(LabProfile(lab_name="Test Lab", bill_notes=""))
        self.window.settings.load()
        self.assertEqual(self.window.settings.bill_notes.toPlainText(), "")

    def test_clearing_the_notes_and_saving_really_means_none(self):
        settings = self.window.settings
        settings.edits["lab_name"].setText("Test Lab")
        settings.bill_notes.setPlainText("")
        settings.save()
        self.assertEqual(self.storage.load_profile().bill_notes, "")

        settings.load()          # reopening must not bring them back
        settings.save()
        self.assertEqual(self.storage.load_profile().bill_notes, "")

    def test_the_standard_terms_are_one_click_away(self):
        from app.billing import DEFAULT_BILL_NOTES

        settings = self.window.settings
        settings.bill_notes.setPlainText("")
        settings.use_standard_notes.click()
        self.assertEqual(settings.bill_notes.toPlainText(), DEFAULT_BILL_NOTES)

    def test_the_offered_terms_pass_their_own_validation(self):
        from app.billing import DEFAULT_BILL_NOTES

        self.assertIsNone(V.check_bill_notes(DEFAULT_BILL_NOTES))

    def test_too_many_notes_block_saving(self):
        settings = self.window.settings
        settings.edits["lab_name"].setText("Test Lab")
        settings.bill_notes.setPlainText("\n".join(f"note {i}" for i in range(9)))
        settings.save()
        self.assertEqual(self.last_message()[1], "warning")

    def test_a_bad_mobile_blocks_saving(self):
        settings = self.window.settings
        settings.edits["lab_name"].setText("Test Lab")
        settings.edits["mobile"].setText("12")
        settings.save()
        self.assertEqual(self.last_message()[1], "warning")


class BillPageSizeTests(UICase):
    """The bill is a counter slip, the report is a clinical record; they do not
    belong on the same sheet."""

    def test_the_two_documents_have_different_page_setups(self):
        from PySide6.QtGui import QPageLayout, QPageSize

        from app import printing

        self.assertEqual(printing.REPORT_PAGE.size, QPageSize.A4)
        self.assertEqual(printing.REPORT_PAGE.orientation, QPageLayout.Portrait)
        self.assertEqual(printing.BILL_PAGE.size, QPageSize.A5)
        self.assertEqual(printing.BILL_PAGE.orientation, QPageLayout.Landscape)

    def test_an_a5_page_is_half_an_a4_page(self):
        """Which is what lets a lab print two slips to a sheet and cut."""
        from PySide6.QtPrintSupport import QPrinter

        from app import printing

        sizes = {}
        for name, page in (("report", printing.REPORT_PAGE),
                           ("bill", printing.BILL_PAGE)):
            printer = QPrinter(QPrinter.HighResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printing._configure(printer, page)
            rect = printer.paperRect(QPrinter.Point)
            sizes[name] = (rect.width(), rect.height())
        # A4 portrait 210x297, A5 landscape 210x148: same width, half the height
        self.assertAlmostEqual(sizes["bill"][0], sizes["report"][0], delta=2)
        self.assertAlmostEqual(sizes["bill"][1], sizes["report"][1] / 2, delta=3)

    def billed(self):
        self.fill()
        self.form.bill_table.item(0, 1).setText("400")
        self.form.f_deposit.setText("400")

    def test_previewing_a_bill_asks_for_the_bill_page(self):
        from app import printing

        previewed = []
        self.stub_preview(previewed)
        self.billed()
        self.form.preview_bill()
        self.assertEqual(previewed[0][2], printing.BILL_PAGE)

    def test_printing_a_bill_asks_for_the_bill_page(self):
        from app import printing

        printed = []
        self.stub_print(printed)
        self.billed()
        self.form.print_bill()
        self.assertEqual(printed[0][2], printing.BILL_PAGE)

    def test_the_report_still_prints_on_a4(self):
        """Regression: giving the bill its own page must not move the report."""
        from app import printing

        printed = []
        self.stub_print(printed)
        self.billed()
        self.form.print_report()
        # the report passes no page at all, so it takes the A4 default
        self.assertIn(printed[0][2], (None, printing.REPORT_PAGE))


class BillLayoutTests(UICase):
    """The bill is laid out at the printer's resolution, not the screen's, so a
    label that fits on screen can still break in half on paper. These measure
    the real print layout rather than trusting the markup."""

    def print_document(self, report, profile=None):
        """The document exactly as printing.py hands it to the printer, on the
        bill's own page - A5 landscape, not the report's A4."""
        from PySide6.QtPrintSupport import QPrinter

        from app import printing
        from app.bill_html import build

        # A PDF printer: it honours any page size, where a physical default
        # printer that only knows Letter would quietly swap the A5 for it.
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printing._configure(printer, printing.BILL_PAGE)
        doc = printing._document(
            build(report, profile or self.storage.load_profile()), printer,
            printing.BILL_PAGE)
        return doc

    def full_profile(self):
        return LabProfile(
            lab_name="MALLIGE DIAGNOSTIC CENTER",
            address1="#M-17, 1st STAGE, NRUPATUNGA ROAD, NEAR SHANTHI SAGAR COMPLEX",
            address2="Opp. CORPORATION BANK KUVEMPUNAGAR, MYSURU-570023",
            phone="08212529999", mobile="9964725222",
            bill_notes="Please bring receipt while collecting the report\n"
                       "Working Hours : Weekdays : 7.00 am to 9.00 pm "
                       "Sundays /Holidays : 7.00 am to 1.00 pm")

    def bill_for(self, **kwargs):
        from app.models import BillItem, Billing, Report

        fields = dict(
            patient_id="147634", patient_name="Mr. PRASANNA C N",
            age="67", age_unit="Y", sex="M", phone="9620055441",
            referred_by="Dr. RAVIKUMAR KULKARNI",
            billing=Billing(bill_no="416385", bill_date="30-08-2026 10:43:30 AM",
                            bill_type="Cash Bill", billed_by="Miss. NETHRA H M",
                            net_deposit="1040",
                            items=[BillItem("USG-Abdomen & Pelvic Scan", "950"),
                                   BillItem("URINE ROUTINE", "90")]))
        fields.update(kwargs)
        return Report(**fields)

    def require_bill_font(self):
        """The bill asks for Arial and falls back to Segoe UI - both ship with
        Windows, which is what this app targets. The headless test platform can
        resolve neither and substitutes a face about a tenth taller, so a page
        measured there is not a page any operator will ever print. Skip rather
        than shrink the real bill to fit a font nobody has."""
        from PySide6.QtGui import QFontDatabase

        families = set(QFontDatabase.families())
        if not ({"Arial", "Segoe UI"} & families):
            self.skipTest("neither Arial nor Segoe UI available to measure with")

    def test_the_reference_bill_fits_on_one_page(self):
        self.require_bill_font()
        doc = self.print_document(self.bill_for(), self.full_profile())
        self.assertEqual(doc.pageCount(), 1)

    def measure(self, cell_style, text, width=90):
        """Height of one table cell squeezed into `width`, in document units."""
        from PySide6.QtGui import QTextDocument

        doc = QTextDocument()
        doc.setDocumentMargin(0)
        doc.setHtml(
            f'<table width="100%"><tr><td style="{cell_style}">{text}</td>'
            "</tr></table>")
        doc.setTextWidth(width)
        return doc.size().height()

    def test_nowrap_is_what_keeps_a_label_on_one_line(self):
        """The mechanism the whole bill layout rests on. Asserted directly rather
        than by measuring the finished bill: the real page is laid out in the
        printer's font at the printer's resolution, so a height measured here
        would only be describing this machine."""
        squeezed = self.measure("", "Net Payable Amt", width=50)
        held = self.measure("white-space:nowrap;", "Net Payable Amt", width=50)
        self.assertGreater(squeezed, held)
        self.assertLess(held, squeezed / 2)

    def test_every_fixed_format_cell_is_marked_nowrap(self):
        """Labels, amounts and values of fixed shape must never break in two.
        "Net Payable" over "Amt" is the difference between a bill and a mess."""
        from app.bill_html import CSS

        for rule in (".key", ".colon", ".money", ".boxlbl", ".th", ".totlbl",
                     ".tight", ".signname", ".signrole"):
            block = CSS.split(rule + " {", 1)[1].split("}", 1)[0]
            self.assertIn("nowrap", block, rule)

    def test_names_are_deliberately_left_breakable(self):
        """A name long enough to shove its column over its neighbour should give
        way instead. Only values of fixed, known shape are pinned."""
        from app.bill_html import CSS

        for rule in (".val", ".td", ".note"):
            block = CSS.split(rule + " {", 1)[1].split("}", 1)[0]
            self.assertNotIn("nowrap", block, rule)

    def test_the_two_identity_columns_cannot_squeeze_each_other(self):
        """Each half is its own table. In one six-column table a long doctor's
        name on the right would narrow the patient's name on the left."""
        from app.bill_html import build

        source = build(self.bill_for(), self.full_profile())
        identity = source.split("Patient Name")[0]
        self.assertIn('width="50%"', identity)

    def with_services(self, count):
        from app.models import BillItem, Billing

        return self.bill_for(billing=Billing(
            bill_no="416385", bill_date="30-08-2026 10:43:30 AM",
            bill_type="Cash Bill", billed_by="Miss. NETHRA H M",
            net_deposit="1040",
            items=[BillItem(f"Service {i}", "950") for i in range(count)]))

    def test_a_typical_bill_fits_one_a5_slip(self):
        """An A5 slip is half an A4 and the bill's furniture - letterhead,
        identity, closing figures, signatures, standing terms - takes most of it.
        A one-service bill leaving no headroom would mean every real bill spilled
        onto a second sheet."""
        self.require_bill_font()
        for count in (1, 2, 3):
            doc = self.print_document(self.with_services(count),
                                      self.full_profile())
            self.assertEqual(doc.pageCount(), 1, f"{count} services")

    def test_the_bill_is_sized_for_its_page(self):
        """Runs whatever font is available, so it always guards the design.

        The exact page-count tests skip on a machine without Arial or Segoe UI,
        which would leave nothing watching the one property that matters: that
        the bill is still cut for half a sheet. Before the A5 change it stood at
        a hundred and sixty per cent of this page; the allowance here is loose
        enough for a substituted font and nowhere near loose enough for that.
        """
        from PySide6.QtGui import QFont, QTextDocument
        from PySide6.QtCore import QSizeF
        from PySide6.QtPrintSupport import QPrinter

        from app import printing
        from app.bill_html import build

        printer = QPrinter(QPrinter.HighResolution)
        printing._configure(printer, printing.BILL_PAGE)
        rect = printer.pageRect(QPrinter.Point)

        doc = QTextDocument()
        doc.setDefaultFont(QFont("Segoe UI", 10))
        doc.setDocumentMargin(0)
        doc.setHtml(build(self.with_services(2), self.full_profile()))
        # an unbounded page, so this is content height and not page-break padding
        doc.setPageSize(QSizeF(rect.width(), 100000))
        self.assertLess(doc.size().height(), rect.height() * 1.15)

    def test_a_long_bill_flows_onto_a_second_slip(self):
        """Rather than truncating. There is only so much room on half a sheet."""
        doc = self.print_document(self.with_services(12), self.full_profile())
        self.assertGreater(doc.pageCount(), 1)
        self.assertIn("Service 11", doc.toPlainText())

    def test_a_very_long_name_still_renders(self):
        """It may push onto a second sheet, which is correct - the bill flows
        rather than truncating - but it must not fail to lay out."""
        long_name = "Mr. " + "Venkatasubramanian " * 4
        doc = self.print_document(self.bill_for(patient_name=long_name),
                                  self.full_profile())
        self.assertGreater(doc.pageCount(), 0)
        self.assertIn("Venkatasubramanian", doc.toPlainText())


if __name__ == "__main__":
    unittest.main()


class DrivePromptTests(UICase):
    """Save offers Google Drive once, then copies there without asking."""

    def _fill_and_save(self):
        self.fill()
        return self.form.save()

    def test_the_first_save_asks(self):
        self._fill_and_save()
        self.assertEqual(self.drive_prompts, 1)

    def test_not_now_asks_again_next_time(self):
        self._fill_and_save()
        self.form.new_report()
        self._fill_and_save()
        self.assertEqual(self.drive_prompts, 2)

    def test_dont_ask_again_is_remembered(self):
        from app.ui.drive_prompt import Answer
        self.drive_answers = [Answer("", True)]
        self._fill_and_save()
        self.form.new_report()
        self._fill_and_save()
        self.assertEqual(self.drive_prompts, 1)
        self.assertEqual(self.storage.load_profile().backup_declined, "1")

    def test_choosing_a_folder_backs_up_that_save_and_every_later_one(self):
        import os
        from app.ui.drive_prompt import Answer
        folder = os.path.join(self.sandbox, "My Drive", "Lably")
        self.drive_answers = [Answer(folder, False)]
        self._fill_and_save()
        self.assertEqual(self.storage.load_profile().backup_dir, folder)
        report = self.storage.load_report(self.form.current_id)
        month = self.storage.backup_month_dir(folder, report)
        self.assertEqual(len(os.listdir(os.path.join(month, "data"))), 1)
        self.assertEqual([f for f in os.listdir(month) if f.endswith(".pdf")],
                         [self.storage.backup_name(report) + ".pdf"])
        self.form.new_report()
        self._fill_and_save()
        self.assertEqual(self.drive_prompts, 1)
        self.assertEqual(len(os.listdir(os.path.join(month, "data"))), 2)
        self.assertIn("Copied to the backup folder", self.messages[-1][0])

    def test_an_unusable_folder_is_refused_and_asked_again(self):
        from app.ui.drive_prompt import Answer
        self.drive_answers = [Answer("Lably", False)]
        self._fill_and_save()
        self.assertEqual(self.storage.load_profile().backup_dir, "")
        self.assertEqual(self.messages[-2][1], "warning")


class TitleFieldTests(UICase):
    def test_a_new_report_defaults_to_mr(self):
        self.assertEqual(self.form.f_title.currentText(), "Mr.")

    def test_choosing_female_moves_the_title_to_mrs(self):
        self.form.f_sex.setCurrentText("F")
        self.assertEqual(self.form.f_title.currentText(), "Mrs.")
        self.form.f_sex.setCurrentText("M")
        self.assertEqual(self.form.f_title.currentText(), "Mr.")

    def test_a_hand_picked_title_that_fits_is_kept(self):
        self.form.f_sex.setCurrentText("F")
        self.form.f_title.setCurrentText("Miss")
        self.form.f_sex.setCurrentText("F")
        self.assertEqual(self.form.f_title.currentText(), "Miss")

    def test_the_title_is_saved_reloaded_and_printed(self):
        self.fill(name="Hemavathi")
        self.form.f_sex.setCurrentText("F")
        self.form.f_title.setCurrentText("Mrs.")
        self.form.save()
        report = self.storage.load_report(self.form.current_id)
        self.assertEqual(report.title, "Mrs.")
        self.assertIn("<b>Mrs. Hemavathi</b>", self.form._html())
        self.form.new_report()
        self.form.load_report(report)
        self.assertEqual(self.form.f_title.currentText(), "Mrs.")

    def test_the_label_reads_ref_by(self):
        from PySide6.QtWidgets import QLabel
        labels = [w.text() for w in self.form.findChildren(QLabel)]
        self.assertIn("Ref. By:", labels)
        self.assertNotIn("Referred By:", labels)


class PanelPriceTests(UICase):
    def test_a_priced_panel_fills_its_amount_when_ticked(self):
        from app import templates
        templates.set_price(CBC, "450")
        self.fill()
        self.assertEqual(self.form.bill_table.item(0, 1).text(), "450")
        self.assertEqual(self.form.l_total.text(), "450.00")

    def test_an_unpriced_panel_still_starts_blank(self):
        self.fill()
        self.assertEqual(self.form.bill_table.item(0, 1).text(), "")

    def test_a_typed_amount_wins_over_the_standing_price(self):
        from app import templates
        templates.set_price(CBC, "450")
        self.fill()
        self.form.bill_table.item(0, 1).setText("400")
        self.form.panel_boxes["Lipid Profile"].setChecked(True)
        self.assertEqual(self.form.bill_table.item(0, 1).text(), "400")

    def test_the_templates_page_edits_the_price(self):
        from app import templates
        view = self.window.templates
        view.reload(select=CBC)
        view.price.setText("325.50")
        view.save_panel()
        self.assertEqual(templates.price_for(CBC), "325.50")
        view.reload(select="Lipid Profile")
        self.assertEqual(view.price.text(), "")
        view.reload(select=CBC)
        self.assertEqual(view.price.text(), "325.50")

    def test_a_bad_price_blocks_the_panel_save(self):
        view = self.window.templates
        view.reload(select=CBC)
        view.price.setText("99999999")
        view.save_panel()
        self.assertEqual(self.messages[-1][1], "warning")


class HistoryLayoutTests(UICase):
    def test_the_search_box_sits_above_the_stat_tiles(self):
        self.history.resize(1000, 700)
        self.history.show()
        self.assertLess(self.history.search.geometry().top(),
                        self.history.stat_total.geometry().top())


class ReportPageFitTests(UICase):
    """A single panel, with its bill and the signatures, fits one A4 sheet."""

    def _profile(self):
        return LabProfile(
            lab_name="HEMAVATHI", lab_subtitle="Family Clinic", address1="#12, MG Road",
            phone="080 2555 1234", mobile="9845012345", email="a@b.com",
            reg_no="KA/1", timings="Mon-Sat 7-8", holidays="Sundays",
            pathologist="Dr. A. Rao", pathologist_degrees="MD", technician="S. Kumar",
            billed_by="Miss. Nethra", footer_note="Computer generated report.")

    def _pages(self, panels):
        from PySide6.QtPrintSupport import QPrinter
        from app import printing, templates
        from app.models import BillItem, Billing, Report, TestRow
        from app.report_html import build
        rows = [TestRow(p, r["name"], "5.0", r["unit"], templates.ref_for(r, "F"),
                        r.get("kind", "test"))
                for p in panels for r in templates.rows_for(p)]
        report = Report(report_no="BR-1", patient_id="HFCD-1", title="Mrs.",
                        patient_name="Hemavathi", age="42", sex="F", rows=rows,
                        remarks="Kindly correlate clinically.",
                        billing=Billing(bill_no="B-1", bill_date="12-09-2026 08:05:00 AM",
                                        billed_by="Miss. Nethra", net_deposit="450",
                                        items=[BillItem(p, "450") for p in panels]))
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printing._configure(printer, printing.REPORT_PAGE)
        return printing._document(build(report, self._profile()), printer,
                                  printing.REPORT_PAGE).pageCount()

    def test_a_full_cbc_fits_one_page(self):
        self.assertEqual(self._pages([CBC]), 1)

    def test_a_short_panel_fits_one_page(self):
        self.assertEqual(self._pages(["Blood Sugar"]), 1)
