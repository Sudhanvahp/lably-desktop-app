"""The printable HTML. This is what actually reaches the patient, so escaping
and data completeness matter more here than anywhere else."""
import re
import unittest

from app.billing import CURRENCY
from app.models import BillItem, Billing, LabProfile, Report, TestRow
from app.report_html import CSS, build, footer, letterhead


def sample_report(**kwargs):
    fields = dict(
        report_no="BR-000001", patient_id="HFCD-000001", patient_name="Jane Doe",
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
                  phone="080-1234", pathologist="Dr. A. Rao",
                  pathologist_degrees="MD", reg_no="KA/1", footer_note="Computer generated")
    fields.update(kwargs)
    return LabProfile(**fields)


class ContentTests(unittest.TestCase):
    def setUp(self):
        self.html = build(sample_report(), sample_profile())

    def test_patient_details_are_present(self):
        for expected in ("Jane Doe", "BR-000001", "HFCD-000001", "Dr. Mehta",
                         "34 Years", "Blood"):
            self.assertIn(expected, self.html)

    def test_lab_details_are_present(self):
        for expected in ("Sunrise Diagnostics", "MG Road", "080-1234",
                         "Dr. A. Rao", "KA/1", "Computer generated"):
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
        self.assertIn('<span class="flag">L</span>', self.html)   # low haemoglobin
        self.assertIn('<span class="flag">H</span>', self.html)   # high cholesterol

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


class BillSummaryTests(unittest.TestCase):
    """The bill is printed on the same sheet as the results, so it has to be
    unmistakably its own section and it has to add up in front of the patient."""

    def setUp(self):
        self.html = build(sample_report(billing=sample_bill()), sample_profile())

    def test_the_section_is_clearly_identified(self):
        self.assertIn("BILL SUMMARY", self.html)

    def test_the_bill_number_and_date_are_printed(self):
        self.assertIn("BILL-000001", self.html)
        self.assertIn("01-Jan-2026 09.15.00 AM", self.html)

    def test_the_date_reads_the_same_here_as_on_the_standalone_bill(self):
        """One bill quoted by two documents. They must not disagree about when it
        was raised, nor write the same instant two different ways."""
        from app.bill_html import build as build_bill

        report = sample_report(billing=sample_bill())
        for html in (self.html, build_bill(report, sample_profile())):
            self.assertIn("01-Jan-2026 09.15.00 AM", html)
            self.assertNotIn("01-01-2026 09:15:00 AM", html)

    def test_every_billed_service_is_listed_with_its_amount(self):
        for expected in ("Complete Blood Count (CBC)", "400.00",
                         "Lipid Profile", "600.00"):
            self.assertIn(expected, self.html)

    def test_the_totals_are_all_present(self):
        for label in ("Total Billed", "Net Payable", "Net Deposit", "Balance"):
            self.assertIn(label, self.html)

    def test_the_arithmetic_is_printed_correctly(self):
        self.assertIn("1,000.00", self.html)   # total billed and net payable
        self.assertIn("250.00", self.html)     # deposit
        self.assertIn("750.00", self.html)     # balance

    def test_the_currency_is_named_on_the_amount_column(self):
        self.assertIn(f"Amount ({CURRENCY})", self.html)

    def test_the_bill_comes_after_the_results_and_before_the_end_marker(self):
        """Section 6: the bill must not overlap or hide laboratory results."""
        self.assertLess(self.html.index("Haemoglobin (Hb)"),
                        self.html.index("BILL SUMMARY"))
        self.assertLess(self.html.index("BILL SUMMARY"),
                        self.html.index("End of Report"))

    def test_the_bill_comes_after_the_remarks(self):
        html = build(sample_report(billing=sample_bill(),
                                   remarks="Repeat after 2 weeks"), sample_profile())
        self.assertLess(html.index("Repeat after 2 weeks"), html.index("BILL SUMMARY"))

    def test_a_settled_bill_prints_a_zero_balance_rather_than_nothing(self):
        html = build(sample_report(billing=sample_bill(net_deposit="1000")),
                     sample_profile())
        self.assertIn("Balance", html)
        self.assertIn("0.00", html)

    def test_an_unpriced_service_prints_a_dash_not_a_zero_charge(self):
        html = build(sample_report(billing=sample_bill(
            items=[BillItem("Complete Blood Count (CBC)", "400"),
                   BillItem("Lipid Profile", "")])), sample_profile())
        self.assertIn("&ndash;", html)

    def test_amounts_are_always_two_decimal_places(self):
        html = build(sample_report(billing=sample_bill(
            items=[BillItem("CBC", "400.5")], net_deposit="")), sample_profile())
        self.assertIn("400.50", html)

    def test_a_report_with_no_billing_prints_no_bill_section(self):
        self.assertNotIn("BILL SUMMARY", build(sample_report(), sample_profile()))

    def test_a_bill_number_alone_is_not_a_bill(self):
        """A lab that never enters an amount should not find a bill block on
        every report it prints."""
        html = build(sample_report(billing=Billing(
            bill_no="BILL-000001", bill_date="01-01-2026",
            items=[BillItem("Complete Blood Count (CBC)", "")])), sample_profile())
        self.assertNotIn("BILL SUMMARY", html)

    def test_an_unreadable_amount_is_not_smuggled_into_the_total(self):
        html = build(sample_report(billing=sample_bill(
            items=[BillItem("CBC", "400"), BillItem("Lipid Profile", "nonsense")],
            net_deposit="")), sample_profile())
        self.assertIn("BILL SUMMARY", html)
        self.assertNotIn("nonsense", html)

    def test_service_names_are_escaped(self):
        html = build(sample_report(billing=sample_bill(
            items=[BillItem("<script>alert(1)</script>", "400")])), sample_profile())
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_the_bill_number_is_escaped(self):
        html = build(sample_report(billing=sample_bill(bill_no="A & B")),
                     sample_profile())
        self.assertIn("A &amp; B", html)


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
                                    signature_path="C:/nope/sig.png"))
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


class PlainDesignTests(unittest.TestCase):
    """It is a medical record: no bands, no tints, one bold word."""

    def setUp(self):
        self.html = build(sample_report(patient_name="Jane Doe"), sample_profile())

    def test_the_patient_name_is_the_only_bold_text_in_the_body(self):
        """Besides the lab's own name in the letterhead, which is styled bold."""
        self.assertIn("<b>Jane Doe</b>", self.html)
        self.assertEqual(self.html.count("<b>"), 1)

    def test_no_coloured_bands_or_tints(self):
        body = self.html.split("</style>")[1]
        colours = set(re.findall(r'bgcolor="(#[0-9a-fA-F]{6})"', body))
        # only the rules themselves are painted, in black and grey
        self.assertTrue(colours <= {"#000000", "#999999"}, colours)

    def test_headings_are_plain_black(self):
        self.assertIn("LABORATORY TEST REPORT", self.html)
        self.assertNotIn("color: #ffffff", self.html)

    def test_out_of_range_values_carry_a_plain_flag(self):
        self.assertIn('<span class="flag">L</span>', self.html)
        self.assertIn('<span class="flag">H</span>', self.html)

    def test_body_type_is_sized_for_a4(self):
        self.assertIn("font-size: 8pt", self.html)


class SerialNumberTests(unittest.TestCase):
    def test_tests_are_numbered_across_panels(self):
        html = build(sample_report(), sample_profile())
        for n in (1, 2, 3):
            self.assertIn(f'<td class="slno">{n}</td>', html)
        self.assertNotIn('<td class="slno">4</td>', html)
        self.assertIn("Sl. No.", html)

    def test_headings_take_no_number(self):
        report = sample_report(rows=[
            TestRow("CBC", "DIFFERENTIAL", kind="heading"),
            TestRow("CBC", "Neutrophils", "60", "%", "40 - 75"),
        ])
        html = build(report, sample_profile())
        self.assertIn('<td class="slno">1</td>', html)
        self.assertNotIn('<td class="slno">2</td>', html)

    def test_bill_lines_are_numbered(self):
        report = sample_report(billing=Billing(items=[
            BillItem("CBC", "400"), BillItem("Lipid Profile", "600")]))
        html = build(report, sample_profile())
        self.assertIn('<td class="slno">2</td><td class="tname">Lipid Profile</td>', html)


class LetterheadTests(unittest.TestCase):
    def test_name_and_sub_heading_are_centred_and_blue(self):
        html = letterhead(sample_profile(lab_name="Hemavathi",
                                         lab_subtitle="Family Clinic"))
        self.assertIn('<div class="labname" align="center">Hemavathi</div>', html)
        self.assertIn('<div class="labsub" align="center">Family Clinic</div>', html)
        self.assertLess(html.index("Hemavathi"), html.index("Family Clinic"))
        self.assertIn(".labname { font-size: 14pt; font-weight: bold; color: #1a4fa3", CSS)
        self.assertIn(".labsub { font-size: 9.5pt; color: #1a4fa3", CSS)

    def test_no_sub_heading_prints_no_empty_line(self):
        self.assertNotIn("labsub", letterhead(sample_profile()))

    def test_sub_heading_is_escaped(self):
        html = letterhead(sample_profile(lab_subtitle="<i>x</i>"))
        self.assertNotIn("<i>x</i>", html)

    def test_logo_is_balanced_by_an_empty_column(self):
        import tempfile, os
        with tempfile.NamedTemporaryFile("wb", suffix=".png", delete=False) as fh:
            fh.write(b"\x89PNG\r\n\x1a\n")
        try:
            html = letterhead(sample_profile(logo_path=fh.name))
        finally:
            os.remove(fh.name)
        self.assertEqual(html.count('width="80"'), 2)

    def test_contact_details_moved_to_the_footer(self):
        profile = sample_profile(address1="MG Road", phone="080-1234",
                                 email="a@b.com", timings="7-8",
                                 holidays="Sundays")
        head = letterhead(profile)
        foot = footer(profile)
        for text in ("MG Road", "080-1234", "a@b.com", "Timings", "Holidays"):
            self.assertNotIn(text, head)
            self.assertIn(text, foot)
        self.assertLess(build(sample_report(), profile).index("End of Report"),
                        build(sample_report(), profile).index("MG Road"))

    def test_footer_is_escaped(self):
        self.assertIn("&lt;b&gt;", footer(sample_profile(timings="<b>")))
        self.assertNotIn("<b>", footer(sample_profile(timings="<b>")))


class TitleTests(unittest.TestCase):
    def test_the_title_prints_before_the_name(self):
        html = build(sample_report(title="Mrs.", patient_name="Hemavathi"),
                     sample_profile())
        self.assertIn("<b>Mrs. Hemavathi</b>", html)

    def test_no_title_prints_just_the_name(self):
        html = build(sample_report(title="", patient_name="Hemavathi"), sample_profile())
        self.assertIn("<b>Hemavathi</b>", html)

    def test_referred_by_is_labelled_ref_by(self):
        html = build(sample_report(), sample_profile())
        self.assertIn("Ref. By", html)
        self.assertNotIn("Referred By", html)


class SignatoryTests(unittest.TestCase):
    def test_technician_left_pathologist_right(self):
        html = build(sample_report(), sample_profile(technician="S. Kumar"))
        names = html[html.index('class="signname"'):]
        self.assertLess(names.index("S. Kumar"), names.index("Dr. A. Rao"))

    def test_nobody_is_named_as_billed_by(self):
        report = sample_report(billing=Billing(billed_by="Miss. Nethra"))
        html = build(report, sample_profile(technician="S. Kumar"))
        self.assertNotIn("Billed By", html)
        self.assertNotIn("Miss. Nethra", html)

    def test_all_three_names_sit_in_one_table_row(self):
        """One row holds all the names, so they are level by construction."""
        html = build(sample_report(), sample_profile(technician="S. Kumar"))
        row = re.search(r"<tr>((?:(?!</tr>).)*S\. Kumar(?:(?!</tr>).)*)</tr>", html).group(1)
        self.assertIn("Dr. A. Rao", row)

    def test_roles_are_named(self):
        html = build(sample_report(), sample_profile(technician="S. Kumar"))
        for role in ("Lab Technician", "Pathologist"):
            self.assertIn(role, html)

    def test_missing_people_leave_blank_slots(self):
        html = build(sample_report(), sample_profile())
        self.assertNotIn("Lab Technician", html)
        self.assertIn("Dr. A. Rao", html)

    def test_names_are_escaped(self):
        html = build(sample_report(), sample_profile(technician="<i>x</i>"))
        self.assertNotIn("<i>x</i>", html)
