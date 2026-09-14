"""The printable HTML. This is what actually reaches the patient, so escaping
and data completeness matter more here than anywhere else."""
import unittest

from app.billing import CURRENCY
from app.models import BillItem, Billing, LabProfile, Report, TestRow
from app.report_html import build, letterhead


def sample_report(**kwargs):
    fields = dict(
        report_no="BR-000001", patient_id="PID-000001", patient_name="Jane Doe",
        age="34", age_unit="Y", sex="F", referred_by="Dr. Mehta",
        sample_type="Blood", collected_on="01-01-2026 10:00 AM",
        reported_on="01-01-2026 11:00 AM",
        rows=[
            TestRow("Complete Blood Count (CBC)", "Haemoglobin (Hb)", "9.2",
                    "g/dL", "12.0 - 15.0"),
            TestRow("Complete Blood Count (CBC)", "Platelet Count", "2.5",
                    "lakhs/cmm", "1.5 - 4.5"),
            TestRow("Lipid Profile", "Total Cholesterol", "260", "mg/dL", "< 200"),
        ],
    )
    fields.update(kwargs)
    return Report(**fields)


def sample_profile(**kwargs):
    fields = dict(lab_name="Sunrise Diagnostics", address1="MG Road",
                  phone="080-1234", technician="S. Kumar",
                  reg_no="KA/1", footer_note="Computer generated")
    fields.update(kwargs)
    return LabProfile(**fields)


class ContentTests(unittest.TestCase):
    def setUp(self):
        self.html = build(sample_report(), sample_profile())

    def test_patient_details_are_present(self):
        for expected in ("Jane Doe", "BR-000001", "PID-000001", "Dr. Mehta",
                         "34 Years", "Blood"):
            self.assertIn(expected, self.html)

    def test_lab_details_are_present(self):
        for expected in ("Sunrise Diagnostics", "MG Road", "080-1234",
                         "KA/1", "Computer generated"):
            self.assertIn(expected, self.html)

    def test_every_result_row_appears(self):
        for expected in ("Haemoglobin (Hb)", "9.2", "g/dL", "12.0 - 15.0",
                         "Platelet Count", "Total Cholesterol", "260"):
            self.assertIn(expected, self.html)

    def test_panels_get_their_own_section_in_order(self):
        cbc = self.html.index("Complete Blood Count (CBC)")
        lipid = self.html.index("Lipid Profile")
        self.assertLess(cbc, lipid)

    def test_out_of_range_values_are_flagged(self):
        self.assertIn("abn", self.html)
        self.assertIn("<b>L</b>", self.html)   # low haemoglobin
        self.assertIn("<b>H</b>", self.html)   # high cholesterol

    def test_in_range_values_are_not_flagged(self):
        html = build(sample_report(rows=[
            TestRow("CBC", "Haemoglobin (Hb)", "14.0", "g/dL", "13.0 - 17.0")]),
            sample_profile())
        self.assertNotIn("<b>H</b>", html)
        self.assertNotIn("<b>L</b>", html)

    def test_end_of_report_marker(self):
        self.assertIn("End of Report", self.html)

    def test_remarks_appear_only_when_set(self):
        self.assertNotIn("Remarks:", self.html)
        with_remarks = build(sample_report(remarks="Repeat after 2 weeks"),
                             sample_profile())
        self.assertIn("Repeat after 2 weeks", with_remarks)

    def test_age_units_are_spelled_out(self):
        for unit, word in (("Y", "Years"), ("M", "Months"), ("D", "Days")):
            html = build(sample_report(age="3", age_unit=unit), sample_profile())
            self.assertIn(f"3 {word}", html)


def sample_bill(**kwargs):
    fields = dict(bill_no="BILL-000001", bill_date="01-01-2026 09:15:00 AM",
                  bill_type="Cash Bill", billed_by="Miss. Nethra H M",
                  net_deposit="250",
                  items=[BillItem("Complete Blood Count (CBC)", "400"),
                         BillItem("Lipid Profile", "600")])
    fields.update(kwargs)
    return Billing(**fields)


class NoBillOnTheReportTests(unittest.TestCase):
    """The report is the clinical document and carries no charges.

    The bill is a separate document with its own page size, rendered by
    `bill_html`. A report is filed with a patient's history and photocopied for
    a consultant, and what the visit cost has no business travelling with it.
    """

    def setUp(self):
        self.html = build(sample_report(billing=sample_bill()), sample_profile())

    def test_there_is_no_bill_section(self):
        self.assertNotIn("BILL SUMMARY", self.html)

    def test_no_amount_from_the_bill_is_printed(self):
        for figure in ("400.00", "600.00", "1,000.00", "250.00", "750.00"):
            self.assertNotIn(figure, self.html)

    def test_none_of_the_bill_totals_are_named(self):
        for label in ("Total Billed", "Net Payable", "Net Deposit", "BALANCE"):
            self.assertNotIn(label, self.html)

    def test_the_bill_number_is_not_printed(self):
        self.assertNotIn("BILL-000001", self.html)

    def test_the_currency_column_is_not_printed(self):
        self.assertNotIn(f"AMOUNT ({CURRENCY})", self.html)

    def test_the_results_still_are(self):
        """Removing the bill must not have taken anything else with it."""
        self.assertIn("Haemoglobin (Hb)", self.html)
        self.assertIn("End of Report", self.html)

    def test_the_standalone_bill_still_carries_all_of_it(self):
        """What left the report has to exist somewhere, or this is data loss
        rather than a separation of documents."""
        from app.bill_html import build as build_bill

        bill = build_bill(sample_report(billing=sample_bill()), sample_profile())
        for expected in ("BILL-000001", "01-Jan-2026 09.15.00 AM",
                         "Complete Blood Count (CBC)", "400.00",
                         "Lipid Profile", "600.00", "1,000.00", "750.00"):
            self.assertIn(expected, bill)


class EscapingTests(unittest.TestCase):
    def test_patient_name_is_escaped(self):
        html = build(sample_report(patient_name='<script>alert(1)</script>'),
                     sample_profile())
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_test_names_and_results_are_escaped(self):
        html = build(sample_report(rows=[
            TestRow("P", "A & B <test>", "<b>5</b>", "mg", "1 - 2")]), sample_profile())
        self.assertIn("A &amp; B &lt;test&gt;", html)
        self.assertNotIn("<b>5</b>", html)

    def test_lab_fields_are_escaped(self):
        html = build(sample_report(), sample_profile(lab_name="A & B <Lab>"))
        self.assertIn("A &amp; B &lt;Lab&gt;", html)

    def test_remarks_are_escaped(self):
        html = build(sample_report(remarks="<img src=x>"), sample_profile())
        self.assertNotIn("<img src=x>", html)


class RobustnessTests(unittest.TestCase):
    def test_empty_report_still_renders(self):
        html = build(Report(), LabProfile())
        self.assertIn("<html>", html)
        self.assertIn("End of Report", html)

    def test_missing_lab_profile_uses_a_placeholder(self):
        self.assertIn("LABORATORY NAME", build(sample_report(), LabProfile()))

    def test_missing_image_files_are_skipped_silently(self):
        html = build(sample_report(),
                     sample_profile(logo_path="C:/nope/missing.png",
                                    technician_signature_path="C:/nope/sig.png"))
        self.assertIn("Sunrise Diagnostics", html)
        self.assertNotIn("missing.png", html)

    def test_rows_without_a_panel_are_grouped_under_investigations(self):
        html = build(sample_report(rows=[TestRow("", "Custom Test", "1", "u", "0 - 2")]),
                     sample_profile())
        self.assertIn("Investigations", html)
        self.assertIn("Custom Test", html)

    def test_letterhead_alone_renders(self):
        self.assertIn("Sunrise Diagnostics", letterhead(sample_profile()))

    def test_unicode_names_render(self):
        html = build(sample_report(patient_name="रमेश"), sample_profile())
        self.assertIn("रमेश", html)


if __name__ == "__main__":
    unittest.main()


class LetterheadTests(unittest.TestCase):
    def test_letterhead_is_centred(self):
        html = letterhead(sample_profile())
        self.assertIn('<td valign="middle" align="center">', html)
        self.assertIn('class="labname" align="center"', html)

    def test_logo_is_balanced_by_an_empty_column(self):
        """So the text block is centred on the page, not on the space left over."""
        import tempfile, os
        with tempfile.NamedTemporaryFile("wb", suffix=".png", delete=False) as fh:
            fh.write(b"\x89PNG\r\n\x1a\n")
        try:
            html = letterhead(sample_profile(logo_path=fh.name))
        finally:
            os.remove(fh.name)
        self.assertEqual(html.count('width="96"'), 2)

    def test_timings_and_holidays_print_in_the_letterhead(self):
        html = letterhead(sample_profile(timings="Mon-Sat 7 AM - 8 PM",
                                         holidays="Sundays and public holidays"))
        self.assertIn("Timings", html)
        self.assertIn("Mon-Sat 7 AM - 8 PM", html)
        self.assertIn("Holidays", html)
        self.assertIn("Sundays and public holidays", html)

    def test_blank_timings_print_no_label(self):
        html = letterhead(sample_profile())
        self.assertNotIn("Timings", html)
        self.assertNotIn("Holidays", html)

    def test_timings_are_escaped(self):
        html = letterhead(sample_profile(timings="<b>7-8</b>"))
        self.assertNotIn("<b>7-8</b>", html)
        self.assertIn("&lt;b&gt;7-8&lt;/b&gt;", html)


class EmphasisTests(unittest.TestCase):
    def test_patient_name_is_bold_and_larger(self):
        html = build(sample_report(patient_name="Jane Doe"), sample_profile())
        self.assertIn('<span class="pname"><b>Jane Doe</b></span>', html)

    def test_results_are_bold(self):
        html = build(sample_report(), sample_profile())
        self.assertIn('<span class="ok"><b>2.5</b></span>', html)
        self.assertIn('<span class="abn"><b>9.2</b>&nbsp;&nbsp;<b>L</b></span>', html)


class SignatoryTests(unittest.TestCase):
    """One signatory on the report: the technician who ran the tests."""

    def report_html(self):
        return build(sample_report(), sample_profile(technician="S. Kumar"))

    def test_the_technician_signs_at_the_bottom_left(self):
        html = build(sample_report(), sample_profile(technician="S. Kumar"))
        self.assertIn("S. Kumar", html)
        self.assertIn("Lab Technician", html)
        # Left of the page, and after the results rather than above them.
        self.assertLess(html.index("End of Report"), html.index("S. Kumar"))
        block = html[html.index("End of Report"):]
        self.assertIn('align="left"', block)

    def test_the_pathologist_is_not_printed(self):
        """They were dropped from the lab profile too, so there is nothing left
        to print - this holds the door shut."""
        self.assertNotIn("Authorised Signatory", self.report_html())
        self.assertFalse(hasattr(LabProfile(), "pathologist"))
        self.assertFalse(hasattr(LabProfile(), "pathologist_degrees"))

    def test_the_billing_clerk_is_not_printed(self):
        """They sign the bill. The report is not an accounting document."""
        report = sample_report(billing=Billing(billed_by="Miss. Nethra"))
        html = build(report, sample_profile(billed_by="Miss. Nethra",
                                            technician="S. Kumar"))
        self.assertNotIn("Miss. Nethra", html)
        self.assertNotIn("Billed By", html)

    def test_no_technician_means_no_signature_block(self):
        html = build(sample_report(), sample_profile(technician=""))
        self.assertNotIn("Lab Technician", html)

    def test_technician_name_is_escaped(self):
        html = build(sample_report(), sample_profile(technician="<i>x</i>"))
        self.assertNotIn("<i>x</i>", html)
        self.assertIn("&lt;i&gt;x&lt;/i&gt;", html)


class LabelEmphasisTests(unittest.TestCase):
    def test_patient_name_label_and_test_names_are_bold(self):
        html = build(sample_report(), sample_profile())
        self.assertIn('<span class="pname-lbl"><b>Patient Name</b></span>', html)
        self.assertIn("<b>Haemoglobin (Hb)</b>", html)
