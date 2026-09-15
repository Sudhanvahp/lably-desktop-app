"""The standalone bill. This is the slip handed to the patient at the counter,
so what it says about money has to be exactly right, and it has to keep saying
it after someone pastes a script tag into a service name."""
import unittest

from app.bill_html import build
from app.models import BillItem, Billing, LabProfile, Report


def sample_bill(**kwargs):
    fields = dict(bill_no="416385", bill_date="30-08-2026 10:43:30 AM",
                  bill_type="Cash Bill", billed_by="Miss. NETHRA H M",
                  net_deposit="1040",
                  items=[BillItem("USG-Abdomen & Pelvic Scan", "950"),
                         BillItem("Urine Routine", "90")])
    fields.update(kwargs)
    return Billing(**fields)


def sample_report(**kwargs):
    fields = dict(patient_name="Mr. Prasanna C N", patient_id="147634",
                  age="67", age_unit="Y", sex="M", phone="9620055441",
                  referred_by="Dr. Ravikumar Kulkarni", billing=sample_bill())
    fields.update(kwargs)
    return Report(**fields)


def sample_profile(**kwargs):
    fields = dict(lab_name="Mallige Diagnostic Center",
                  address1="#M-17, 1st Stage, Nrupatunga Road",
                  address2="Opp. Corporation Bank, Mysuru-570023",
                  phone="08212529999", mobile="9964725222", reg_no="KA/DC/77",
                  bill_notes="Please bring receipt while collecting the report\n"
                             "Working Hours : 7.00 am to 9.00 pm")
    fields.update(kwargs)
    return LabProfile(**fields)


class HeaderTests(unittest.TestCase):
    def setUp(self):
        self.html = build(sample_report(), sample_profile())

    def test_the_lab_letterhead_is_on_the_bill(self):
        for expected in ("Mallige Diagnostic Center", "Nrupatunga Road",
                         "Opp. Corporation Bank"):
            self.assertIn(expected, self.html)

    def test_both_contact_numbers_are_on_one_line(self):
        self.assertIn("Ph: 08212529999 &middot; Mob: 9964725222", self.html)

    def test_the_letterhead_is_name_and_sub_heading_only(self):
        """Contact details print in the footer, as on the report."""
        html = build(sample_report(), sample_profile(lab_subtitle="Family Clinic"))
        head = html[:html.index("Cash Bill")]
        self.assertIn("Family Clinic", head)
        for text in ("08212529999", "9964725222", "Nrupatunga"):
            self.assertNotIn(text, head)
            self.assertIn(text, html)
        self.assertLess(html.index("Note:"), html.index("Nrupatunga"))

    def test_the_bill_type_is_the_documents_heading(self):
        self.assertIn('class="heading" align="center">Cash Bill<', self.html)

    def test_a_different_bill_type_retitles_the_document(self):
        html = build(sample_report(billing=sample_bill(bill_type="Credit Bill")),
                     sample_profile())
        self.assertIn('class="heading" align="center">Credit Bill<', html)
        self.assertNotIn("Cash Bill", html)

    def test_the_bill_type_no_longer_has_its_own_row(self):
        self.assertNotIn("Bill Type", self.html)

    def test_the_patient_identity_block(self):
        for expected in ("Patient Name", "Mr. Prasanna C N",
                         "Patient ID", "147634",
                         "Phone No", "9620055441"):
            self.assertIn(expected, self.html)

    def test_age_and_gender_read_the_way_the_slip_does(self):
        self.assertIn("67 Yrs / Male", self.html)

    def test_the_bill_identity_block(self):
        for expected in ("Bill No", "416385", "Bill Date",
                         "Ref. By", "Dr. Ravikumar Kulkarni"):
            self.assertIn(expected, self.html)

    def test_the_date_carries_the_time_and_spells_out_the_month(self):
        """The slip prints the minute the bill was raised, and '30-Aug' cannot be
        misread as the 8th of a month the way '30-08' can."""
        self.assertIn("30-Aug-2026 10.43.30 AM", self.html)

    def test_a_blank_field_keeps_its_row(self):
        """The two columns are read across. Collapsing one side alone would slide
        every row below it out of step with its neighbour."""
        html = build(sample_report(phone="", referred_by=""), sample_profile())
        self.assertIn("Phone No", html)
        self.assertIn("Ref. By", html)

    def test_female_and_infant_patients_read_correctly(self):
        html = build(sample_report(sex="F", age="8", age_unit="M"), sample_profile())
        self.assertIn("8 Mths / Female", html)


class ServiceTableTests(unittest.TestCase):
    def setUp(self):
        self.html = build(sample_report(), sample_profile())

    def test_the_columns_match_the_slip(self):
        for header in ("Sl. No.", "Services", "Amount", "Net Amount"):
            self.assertIn(header, self.html)

    def test_the_table_is_fully_ruled_in_black(self):
        """A grey rule - Qt's unstyled default - vanishes on the photocopy that
        goes in the file."""
        self.assertIn('border="1"', self.html)
        self.assertIn("border-color:#000000", self.html)

    def test_every_service_is_listed(self):
        self.assertIn("USG-Abdomen &amp; Pelvic Scan", self.html)
        self.assertIn("Urine Routine", self.html)

    def test_services_are_numbered_from_one(self):
        self.assertIn(">1</td>", self.html)
        self.assertIn(">2</td>", self.html)

    def test_amounts_are_printed_to_two_places(self):
        self.assertIn("950.00", self.html)
        self.assertIn("90.00", self.html)

    def test_the_total_billed_row_closes_the_table(self):
        self.assertIn("Total Billed", self.html)
        self.assertIn("1,040.00", self.html)
        self.assertLess(self.html.index("Urine Routine"),
                        self.html.index("Total Billed"))

    def test_an_unpriced_service_prints_a_dash(self):
        html = build(sample_report(billing=sample_bill(
            items=[BillItem("USG", "950"), BillItem("Urine Routine", "")])),
            sample_profile())
        self.assertIn("&ndash;", html)

    def test_a_bill_with_one_service_still_renders(self):
        html = build(sample_report(billing=sample_bill(
            items=[BillItem("CBC", "400")], net_deposit="")), sample_profile())
        self.assertIn("CBC", html)
        self.assertIn("400.00", html)


class ClosingFigureTests(unittest.TestCase):
    def test_the_three_closing_figures_are_labelled_as_on_the_slip(self):
        html = build(sample_report(), sample_profile())
        for label in ("Net Payable Amt", "Net Deposit Amt", "Balance"):
            self.assertIn(label, html)

    def test_a_fully_paid_bill_closes_at_zero(self):
        html = build(sample_report(), sample_profile())
        self.assertIn("0.00", html)

    def test_a_part_paid_bill_shows_what_is_left(self):
        html = build(sample_report(billing=sample_bill(net_deposit="700")),
                     sample_profile())
        self.assertIn("340.00", html)

    def test_the_paid_amount_is_spelled_out(self):
        html = build(sample_report(), sample_profile())
        self.assertIn("Paid Amount", html)
        self.assertIn("One Thousand Forty Rupees Only", html)

    def test_the_bill_amount_is_spelled_out_whether_or_not_it_is_paid(self):
        """Regression: the only figure in words used to be the *paid* amount, so
        a bill with nothing paid yet carried no amount in words at all - an
        8,900 bill whose sole sentence read "Zero Rupees Only"."""
        for deposit in ("", "0", "250", "1000"):
            html = build(sample_report(billing=sample_bill(net_deposit=deposit)),
                         sample_profile())
            self.assertIn("Amount in Words", html)
            self.assertIn("One Thousand Forty Rupees Only", html, deposit)

    def test_an_unpaid_bill_carries_no_paid_amount_line(self):
        """With the bill's own amount now stated above, "Paid Amount : Zero
        Rupees Only" adds nothing the Balance has not already said."""
        html = build(sample_report(billing=sample_bill(net_deposit="")),
                     sample_profile())
        self.assertNotIn("Paid Amount", html)
        self.assertIn("Amount in Words", html)

    def test_the_words_follow_the_services_table(self):
        html = build(sample_report(), sample_profile())
        self.assertLess(html.index("Total Billed"), html.index("Amount in Words"))
        self.assertLess(html.index("Amount in Words"), html.index("Net Payable Amt"))

    def test_the_words_state_the_payable_not_the_deposit(self):
        html = build(sample_report(billing=sample_bill(net_deposit="250")),
                     sample_profile())
        words = html.index("Amount in Words")
        self.assertIn("One Thousand Forty Rupees Only", html[words:words + 200])

    def test_the_bill_carries_a_billed_by_line(self):
        """The counter fills the name in by hand, so with nothing on record the
        line is a ruled blank rather than absent."""
        html = build(sample_report(billing=sample_bill(billed_by="")),
                     sample_profile(billed_by=""))
        self.assertIn("Billed By", html)
        self.assertNotIn("Printed By", html)
        self.assertNotIn("Miss. NETHRA H M", html)

    def test_a_name_on_record_prints_on_the_billed_by_line(self):
        html = build(sample_report(), sample_profile())
        self.assertIn("Billed By", html)
        self.assertIn("Miss. NETHRA H M", html)

    def test_the_profile_default_fills_billed_by_when_the_bill_has_none(self):
        html = build(sample_report(billing=sample_bill(billed_by="")),
                     sample_profile(billed_by="R. Shetty"))
        self.assertIn("R. Shetty", html)


class NoteTests(unittest.TestCase):
    def test_the_notes_come_from_the_laboratory_profile_and_are_numbered(self):
        html = build(sample_report(), sample_profile())
        self.assertIn("Note:", html)
        self.assertIn("1.", html)
        self.assertIn("Please bring receipt while collecting the report", html)
        self.assertIn("2.", html)
        self.assertIn("Working Hours : 7.00 am to 9.00 pm", html)

    def test_the_standing_terms_are_offered_ready_made(self):
        """A lab should not have to invent them, and a bill printed on day one
        should not have an empty footer."""
        from app.billing import DEFAULT_BILL_NOTES

        self.assertEqual(len(DEFAULT_BILL_NOTES.splitlines()), 2)
        html = build(sample_report(),
                     sample_profile(bill_notes=DEFAULT_BILL_NOTES))
        self.assertIn("Please bring receipt while collecting the report", html)
        self.assertIn("2.", html)
        for gone in ("Beyond 01 month", "culture reports"):
            self.assertNotIn(gone, html)

    def test_a_profile_with_no_notes_prints_none(self):
        html = build(sample_report(), sample_profile(bill_notes=""))
        self.assertIn("416385", html)
        self.assertNotIn("Note:", html)

    def test_blank_lines_between_notes_do_not_break_the_numbering(self):
        html = build(sample_report(),
                     sample_profile(bill_notes="First\n\n   \nSecond"))
        self.assertIn("1.&nbsp;&nbsp;First", html)
        self.assertIn("2.&nbsp;&nbsp;Second", html)

    def test_notes_are_escaped(self):
        html = build(sample_report(), sample_profile(bill_notes="<b>shout</b>"))
        self.assertNotIn("<b>shout</b>", html)


class RobustnessTests(unittest.TestCase):
    def test_an_empty_report_still_renders_a_page(self):
        html = build(Report(), LabProfile())
        self.assertIn("<html>", html)
        self.assertIn("Cash Bill", html)
        self.assertIn("LABORATORY NAME", html)

    def test_service_names_are_escaped(self):
        html = build(sample_report(billing=sample_bill(
            items=[BillItem("<script>alert(1)</script>", "1")])), sample_profile())
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_the_patient_name_is_escaped(self):
        html = build(sample_report(patient_name="<b>Jane</b>"), sample_profile())
        self.assertNotIn("<b>Jane</b>", html)

    def test_the_bill_number_is_escaped(self):
        html = build(sample_report(billing=sample_bill(bill_no="A & B")),
                     sample_profile())
        self.assertIn("A &amp; B", html)

    def test_an_unreadable_amount_is_not_smuggled_onto_the_bill(self):
        html = build(sample_report(billing=sample_bill(
            items=[BillItem("CBC", "nonsense")], net_deposit="")), sample_profile())
        self.assertNotIn("nonsense", html)

    def test_an_unreadable_bill_date_is_printed_as_stored(self):
        """Better a date that looks odd than a bill that refuses to print, or one
        that quietly claims to have been raised today."""
        html = build(sample_report(billing=sample_bill(bill_date="whenever")),
                     sample_profile())
        self.assertIn("whenever", html)

    def test_a_bill_written_by_the_first_build_still_prints(self):
        """Those bills stored the day alone, with no time on it."""
        html = build(sample_report(billing=sample_bill(bill_date="30-08-2026")),
                     sample_profile())
        self.assertIn("30-Aug-2026", html)
        self.assertNotIn("12.00.00 AM", html)

    def test_a_bill_with_no_type_falls_back_rather_than_printing_blank(self):
        html = build(sample_report(billing=sample_bill(bill_type="")),
                     sample_profile())
        self.assertIn("Cash Bill", html)

    def test_unicode_names_render(self):
        html = build(sample_report(patient_name="रमेश"), sample_profile())
        self.assertIn("रमेश", html)

    def test_the_bill_is_self_contained_with_no_external_references(self):
        """Same rule as the report: QTextDocument resolves nothing over the
        network, so anything not inlined simply does not print."""
        html = build(sample_report(), sample_profile())
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)


if __name__ == "__main__":
    unittest.main()
