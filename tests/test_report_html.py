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
                  phone="080-1234", pathologist="Dr. A. Rao",
                  pathologist_degrees="MD", reg_no="KA/1", footer_note="Computer generated")
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
        for label in ("Total Billed", "Net Payable", "Net Deposit", "BALANCE"):
            self.assertIn(label, self.html)

    def test_the_arithmetic_is_printed_correctly(self):
        self.assertIn("1,000.00", self.html)   # total billed and net payable
        self.assertIn("250.00", self.html)     # deposit
        self.assertIn("750.00", self.html)     # balance

    def test_the_currency_is_named_on_the_amount_column(self):
        self.assertIn(f"AMOUNT ({CURRENCY})", self.html)

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
        self.assertIn("BALANCE", html)
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
