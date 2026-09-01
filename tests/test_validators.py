"""Field rules: what may be typed, and what is caught at save time."""
import unittest

from tests.base import SandboxCase  # noqa: F401  (sets the offscreen Qt platform)

from PySide6.QtGui import QValidator
from PySide6.QtWidgets import QApplication

from app import validators as V


def app():
    return QApplication.instance() or QApplication([])


class ValidatorPatternTests(unittest.TestCase):
    """The character filter that runs while the operator types."""

    def setUp(self):
        self.app = app()

    def accepts(self, pattern, text):
        state, _, _ = V.validator(pattern).validate(text, len(text))
        return state == QValidator.Acceptable

    def rejects(self, pattern, text):
        state, _, _ = V.validator(pattern).validate(text, len(text))
        return state == QValidator.Invalid

    # names ----------------------------------------------------------------
    def test_names_accept_real_world_forms(self):
        for name in ("Jane Doe", "M. K. Sharma", "D'Souza", "Rao-Naidu",
                     "Baby of Sunita", "A"):
            self.assertTrue(self.accepts(V.NAME_PATTERN, name), name)

    def test_names_reject_digits(self):
        for name in ("Patient 1", "P0", "Jane2", "123"):
            self.assertTrue(self.rejects(V.NAME_PATTERN, name), name)

    def test_names_reject_symbols(self):
        for name in ("Jane@Doe", "Jane#", "Jane/Doe", "<script>"):
            self.assertTrue(self.rejects(V.NAME_PATTERN, name), name)

    # age ------------------------------------------------------------------
    def test_age_accepts_digits_only(self):
        for value in ("", "0", "34", "130"):
            self.assertTrue(self.accepts(V.DIGITS_PATTERN, value), value)

    def test_age_rejects_letters_and_symbols(self):
        for value in ("34y", "abc", "3.4", "-5", "34 "):
            self.assertTrue(self.rejects(V.DIGITS_PATTERN, value), value)

    def test_age_is_capped_at_three_digits(self):
        self.assertTrue(self.rejects(V.DIGITS_PATTERN, "1234"))

    # phone ----------------------------------------------------------------
    def test_phone_accepts_the_shapes_people_type(self):
        for value in ("9845012345", "98450 12345", "+91 9845012345",
                      "+919845012345", "98450-12345", "0821 2529999"):
            self.assertTrue(self.accepts(V.PHONE_PATTERN, value), value)

    def test_phone_refuses_brackets(self):
        """Indian numbers are not written with them, and every character the
        filter lets through is one the save-time check has to reason about."""
        for value in ("(080) 2555-1234", "080 (2555) 1234"):
            self.assertFalse(self.accepts(V.PHONE_PATTERN, value), value)

    def test_phone_rejects_letters(self):
        self.assertTrue(self.rejects(V.PHONE_PATTERN, "call me"))


class AgeCheckTests(unittest.TestCase):
    def test_blank_age_is_rejected(self):
        self.assertIsNotNone(V.check_age("", "Y"))

    def test_normal_ages_pass(self):
        for value, unit in (("34", "Y"), ("0", "Y"), ("6", "M"), ("10", "D")):
            self.assertIsNone(V.check_age(value, unit), f"{value}{unit}")

    def test_non_numeric_age_is_rejected(self):
        self.assertIsNotNone(V.check_age("thirty", "Y"))

    def test_implausible_age_is_rejected_per_unit(self):
        self.assertIsNotNone(V.check_age("340", "Y"))
        self.assertIsNotNone(V.check_age("99", "M"))
        self.assertIsNotNone(V.check_age("900", "D"))

    def test_boundaries_are_allowed(self):
        self.assertIsNone(V.check_age("130", "Y"))
        self.assertIsNone(V.check_age("36", "M"))
        self.assertIsNone(V.check_age("400", "D"))

    def test_message_mentions_the_unit(self):
        message = V.check_age("500", "D")
        self.assertIn("days", message)


class NameCheckTests(unittest.TestCase):
    def test_blank_name_is_rejected(self):
        self.assertIsNotNone(V.check_person_name(""))
        self.assertIsNotNone(V.check_person_name("   "))

    def test_single_letter_is_rejected(self):
        self.assertIsNotNone(V.check_person_name("A"))

    def test_punctuation_only_is_rejected(self):
        self.assertIsNotNone(V.check_person_name("..."))

    def test_real_names_pass(self):
        for name in ("Jane Doe", "M. K. Sharma", "D'Souza"):
            self.assertIsNone(V.check_person_name(name), name)

    def test_digits_are_rejected(self):
        self.assertIsNotNone(V.check_person_name("Patient 1"))

    def test_label_appears_in_the_message(self):
        self.assertIn("referring doctor", V.check_person_name("", "referring doctor"))

    def test_optional_name_allows_blank_but_still_checks_content(self):
        self.assertIsNone(V.check_optional_name("", "doctor"))
        self.assertIsNone(V.check_optional_name("Dr. Mehta", "doctor"))
        self.assertIsNotNone(V.check_optional_name("Dr 99", "doctor"))


class ContactCheckTests(unittest.TestCase):
    def test_email_optional_but_validated(self):
        self.assertIsNone(V.check_email(""))
        self.assertIsNone(V.check_email("lab@example.com"))
        for bad in ("lab", "lab@", "@example.com", "lab@example", "a b@c.com"):
            self.assertIsNotNone(V.check_email(bad), bad)

    def test_phone_is_optional_but_must_be_a_full_indian_number(self):
        self.assertIsNone(V.check_phone(""))
        self.assertIsNone(V.check_phone("+91 9845012345"))
        self.assertIsNotNone(V.check_phone("123"))


class ResultValueTests(unittest.TestCase):
    def test_numeric_results_pass(self):
        for value in ("14.0", "0", "12800", "-1.5"):
            self.assertIsNone(V.check_result_value(value), value)

    def test_qualitative_results_pass(self):
        """Pathology results are often words - a numbers-only rule would make
        the app unable to report a negative or a trace finding."""
        for value in ("Nil", "Absent", "Trace", "Positive", "Not Detected", "<0.01"):
            self.assertIsNone(V.check_result_value(value), value)

    def test_blank_result_is_allowed(self):
        self.assertIsNone(V.check_result_value(""))

    def test_absurdly_long_result_is_rejected(self):
        self.assertIsNotNone(V.check_result_value("x" * 60))


class HelperTests(unittest.TestCase):
    def test_first_error_returns_the_first_problem(self):
        self.assertEqual(V.first_error(None, "second", "third"), "second")
        self.assertIsNone(V.first_error(None, None))

    def test_is_number(self):
        self.assertEqual(V.is_number("14.5"), (True, 14.5))
        self.assertEqual(V.is_number("Nil")[0], False)
        self.assertEqual(V.is_number(None)[0], False)



class UnitTests(unittest.TestCase):
    def test_real_units_pass(self):
        for unit in ("g/dL", "mg/dL", "%", "/cmm", "million/cmm", "lakhs/cmm",
                     "U/L", "mmol/L", "uIU/mL", "fL", "pg", "ng/dL", "ug/dL",
                     "mm/1st hr", "10^3/uL", ""):
            self.assertIsNone(V.check_unit(unit), unit)

    def test_junk_is_rejected(self):
        for unit in ("!!!", "@#$", "<b>", "g/dL;DROP"):
            self.assertIsNotNone(V.check_unit(unit), unit)

    def test_a_bare_number_is_not_a_unit(self):
        self.assertIsNotNone(V.check_unit("123"))
        self.assertIsNotNone(V.check_unit("1.5"))

    def test_over_length_is_rejected(self):
        self.assertIsNotNone(V.check_unit("x" * (V.MAX_UNIT + 1)))


class ReferenceRangeTests(unittest.TestCase):
    def test_numeric_ranges_pass(self):
        for ref in ("13.0 - 17.0", "13-17", "0.5 - 2", "-3 - 3", "70 to 100"):
            self.assertIsNone(V.check_reference(ref), ref)

    def test_bounds_pass(self):
        for ref in ("< 200", "<200", "<= 200", "> 40", ">= 40"):
            self.assertIsNone(V.check_reference(ref), ref)

    def test_qualitative_ranges_pass(self):
        """Tests like 'Protein: Absent' have no numbers at all."""
        for ref in ("Absent", "Nil", "Negative", "Pale yellow", "Clear",
                    "Not Detected"):
            self.assertIsNone(V.check_reference(ref), ref)

    def test_blank_is_allowed(self):
        self.assertIsNone(V.check_reference(""))

    def test_the_dangerous_middle_ground_is_rejected(self):
        """Text that looks numeric but cannot be parsed would silently never
        flag an abnormal result - that is the case worth catching."""
        for ref in ("13 abc", "12 -", "- 17", "about 200", "13.0 -- 17",
                    "1 - 2 - 3", "!!!", "13,17"):
            self.assertIsNotNone(V.check_reference(ref), ref)

    def test_over_length_is_rejected(self):
        self.assertIsNotNone(V.check_reference("a " * 40))

    def test_accepted_numeric_ranges_actually_drive_flagging(self):
        """Every range the validator accepts as numeric must be one the
        flagger can use - otherwise validation and flagging disagree."""
        from app.panels import flag_for

        for ref in ("13.0 - 17.0", "13-17", "< 200", "> 40", ">= 40", "70 to 100"):
            self.assertTrue(V.is_numeric_reference(ref), ref)
            self.assertTrue(flag_for("-99999", ref) or flag_for("99999", ref),
                            f"{ref} accepted but never flags")

    def test_qualitative_ranges_are_not_treated_as_numeric(self):
        self.assertFalse(V.is_numeric_reference("Absent"))
        self.assertFalse(V.is_numeric_reference(""))


class TestNameTests(unittest.TestCase):
    def test_real_test_names_pass(self):
        for name in ("Haemoglobin (Hb)", "SGOT / AST", "Vitamin B-12",
                     "25-OH Vitamin D", "T3 (Total)", "A / G Ratio",
                     "Neutrophils", "HbA1c"):
            self.assertIsNone(V.check_test_name(name), name)

    def test_blank_is_rejected(self):
        self.assertIsNotNone(V.check_test_name(""))

    def test_markup_is_rejected(self):
        self.assertIsNotNone(V.check_test_name("<script>alert(1)</script>"))

    def test_over_length_is_rejected(self):
        self.assertIsNotNone(V.check_test_name("x" * (V.MAX_TEST_NAME + 1)))

    def test_label_appears_in_the_message(self):
        self.assertIn("panel name", V.check_test_name("", "panel name"))


class TextLineTests(unittest.TestCase):
    def test_addresses_and_qualifications_pass(self):
        for text in ("#42, MG Road, Bengaluru 560001", "MD (Pathology)",
                     "This is a computer generated report.", "Ph: 080-2555 1234", ""):
            self.assertIsNone(V.check_text_line(text, "Field"), text)

    def test_control_characters_are_rejected(self):
        self.assertIsNotNone(V.check_text_line("line\x00break", "Field"))

    def test_over_length_is_rejected(self):
        self.assertIsNotNone(V.check_text_line("x" * 200, "Field"))

    def test_label_appears_in_the_message(self):
        self.assertIn("Address", V.check_text_line("x" * 200, "Address"))


class BuiltInPanelConsistencyTests(unittest.TestCase):
    """The panels the app ships with must satisfy the rules it enforces.

    Without this, the app could reject its own defaults the moment someone
    opened a built-in panel in the template editor and pressed Save."""

    def test_every_built_in_row_passes_validation(self):
        from app import templates
        from app.panels import PANELS

        for panel in PANELS:
            self.assertIsNone(V.check_test_name(panel, "panel name"), panel)
            for row in templates.default_rows(panel):
                where = f"{panel} / {row['name']}"
                self.assertIsNone(V.check_test_name(row["name"]), where)
                self.assertIsNone(V.check_unit(row["unit"]), where)
                self.assertIsNone(V.check_reference(row["ref_m"]), where)
                self.assertIsNone(V.check_reference(row["ref_f"]), where)


class IndianPhoneTests(unittest.TestCase):
    """Ten national digits, no more and no fewer, however they were typed."""

    def test_the_shapes_an_operator_might_type_all_read_the_same(self):
        for value in ("9845012345", "98450 12345", "98450-12345",
                      "+91 9845012345", "+919845012345", "+91 98450 12345",
                      "09845012345", "0091 9845012345", "0091-98450-12345"):
            self.assertEqual(V.phone_digits(value), "9845012345", value)
            self.assertEqual(V.normalise_phone(value), "+91 9845012345", value)

    def test_a_landline_fits_the_same_rule_once_the_trunk_zero_goes(self):
        for value in ("0821 2529999", "08212529999", "+91 8212529999"):
            self.assertEqual(V.phone_digits(value), "8212529999", value)

    def test_a_mobile_that_begins_with_the_country_code_is_left_alone(self):
        """9198765432 is ten digits and starts with 91. Stripping that as a
        country code would silently turn it into an eight-digit number."""
        self.assertEqual(V.phone_digits("9198765432"), "9198765432")
        self.assertEqual(V.normalise_phone("9198765432"), "+91 9198765432")

    def test_too_few_digits_is_refused(self):
        for value in ("123", "984501234", "+91 98450"):
            self.assertIsNone(V.phone_digits(value), value)
            self.assertIsNotNone(V.check_phone(value), value)

    def test_too_many_digits_is_refused(self):
        for value in ("98450123456", "+91 98450123456", "9845012345678"):
            self.assertIsNone(V.phone_digits(value), value)
            self.assertIsNotNone(V.check_phone(value), value)

    def test_the_message_says_how_many_digits_were_given(self):
        message = V.check_phone("98450123456")
        self.assertIn("11", message)
        self.assertIn("10", message)

    def test_the_message_names_the_field(self):
        self.assertIn("mobile number", V.check_phone("123", "mobile number"))

    def test_blank_is_allowed_because_every_phone_field_is_optional(self):
        for value in ("", "   ", None):
            self.assertIsNone(V.check_phone(value))
            self.assertEqual(V.normalise_phone(value), "")

    def test_an_unreadable_number_is_handed_back_untouched(self):
        """Saving is blocked separately; mangling it would hide what to fix."""
        self.assertEqual(V.normalise_phone("12345"), "12345")


class AmountTests(unittest.TestCase):
    """Billing values are typed, so the only defence against a wrong total is
    refusing anything that is not a number."""

    def test_blank_is_allowed(self):
        """Blank means the service has not been priced, not that it is free."""
        self.assertIsNone(V.check_amount(""))
        self.assertIsNone(V.check_amount("   "))

    def test_plain_amounts_pass(self):
        for value in ("0", "350", "350.5", "350.00", "9999999.99"):
            self.assertIsNone(V.check_amount(value), value)

    def test_non_numeric_amounts_are_refused(self):
        for value in ("abc", "3.4.5", "350/-", "three hundred"):
            self.assertIsNotNone(V.check_amount(value), value)

    def test_an_absurd_amount_is_refused(self):
        self.assertIsNotNone(V.check_amount("99999999"))

    def test_a_negative_amount_is_refused(self):
        self.assertIsNotNone(V.check_amount("-50"))

    def test_the_message_names_the_field(self):
        self.assertIn("net deposit", V.check_amount("abc", "net deposit"))


class AmountTypingTests(unittest.TestCase):
    """The character filter on the amount and deposit boxes."""

    def setUp(self):
        self.app = app()

    def accepts(self, text):
        state = V.validator(V.AMOUNT_PATTERN).validate(text, 0)[0]
        return state != QValidator.State.Invalid

    def test_digits_and_one_decimal_point_are_typeable(self):
        for text in ("", "3", "350", "350.", "350.5", "350.50"):
            self.assertTrue(self.accepts(text), text)

    def test_letters_signs_and_extra_decimals_are_blocked(self):
        for text in ("a", "-1", "3.456", "3.4.5", "\u20b95"):
            self.assertFalse(self.accepts(text), text)


class BillNumberTests(unittest.TestCase):
    def test_blank_is_allowed_because_the_app_generates_one(self):
        self.assertIsNone(V.check_bill_no(""))

    def test_generated_and_hand_typed_forms_both_pass(self):
        for value in ("BILL-000001", "CASH-42", "2026/0117", "C 88"):
            self.assertIsNone(V.check_bill_no(value), value)

    def test_punctuation_that_does_not_belong_is_refused(self):
        for value in ("<b>1</b>", "BILL#1", "bill@lab"):
            self.assertIsNotNone(V.check_bill_no(value), value)

    def test_an_over_long_bill_number_is_refused(self):
        self.assertIsNotNone(V.check_bill_no("B" * (V.MAX_BILL_NO + 1)))


if __name__ == "__main__":
    unittest.main()
