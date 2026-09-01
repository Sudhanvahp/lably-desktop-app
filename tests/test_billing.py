"""Bill arithmetic. Every figure a patient is asked to pay comes through here,
so parsing, rounding and the blank-versus-zero distinction are the whole point."""
import unittest
from decimal import Decimal

from app import billing
from app.models import BillItem, Billing, TestRow


def bill(*amounts, deposit=""):
    return Billing(net_deposit=deposit,
                   items=[BillItem(f"Panel {i}", a) for i, a in enumerate(amounts)])


class ParsingTests(unittest.TestCase):
    def test_plain_numbers(self):
        self.assertEqual(billing.parse_amount("350"), Decimal("350.00"))
        self.assertEqual(billing.parse_amount("350.5"), Decimal("350.50"))
        self.assertEqual(billing.parse_amount("0"), Decimal("0.00"))

    def test_blank_is_not_an_amount(self):
        for value in ("", "   ", None):
            self.assertIsNone(billing.parse_amount(value))

    def test_junk_is_not_an_amount(self):
        for value in ("abc", "3.4.5", "--1", "1/2", "NaN", "Infinity"):
            self.assertIsNone(billing.parse_amount(value), value)

    def test_a_typed_currency_sign_or_separator_is_tolerated(self):
        """Nothing in the app produces these, but a hand-edited report file or a
        pasted value can carry them, and refusing to read a stored bill is worse
        than accepting the two harmless decorations."""
        self.assertEqual(billing.parse_amount("₹ 1,250.00"), Decimal("1250.00"))

    def test_rounding_is_half_up_to_two_places(self):
        self.assertEqual(billing.parse_amount("10.005"), Decimal("10.01"))
        self.assertEqual(billing.parse_amount("10.004"), Decimal("10.00"))

    def test_blank_counts_as_zero_when_adding_up(self):
        self.assertEqual(billing.amount_or_zero(""), Decimal("0.00"))
        self.assertEqual(billing.amount_or_zero("nonsense"), Decimal("0.00"))


class FormattingTests(unittest.TestCase):
    def test_two_decimals_always(self):
        self.assertEqual(billing.format_amount("40"), "40.00")
        self.assertEqual(billing.format_amount("40.5"), "40.50")

    def test_thousands_are_grouped(self):
        self.assertEqual(billing.format_amount("1234567"), "1,234,567.00")

    def test_money_carries_the_currency(self):
        self.assertTrue(billing.format_money("40").startswith(billing.CURRENCY))
        self.assertIn("40.00", billing.format_money("40"))


class TotalsTests(unittest.TestCase):
    def test_total_is_the_sum_of_the_lines(self):
        self.assertEqual(billing.total_billed(bill("400", "600")), Decimal("1000.00"))

    def test_unpriced_lines_add_nothing(self):
        self.assertEqual(billing.total_billed(bill("400", "", "  ")),
                         Decimal("400.00"))

    def test_an_empty_bill_totals_zero(self):
        self.assertEqual(billing.total_billed(Billing()), Decimal("0.00"))

    def test_net_payable_equals_the_total_while_no_adjustment_is_configured(self):
        b = bill("400", "600")
        self.assertEqual(billing.net_payable(b), billing.total_billed(b))

    def test_balance_is_payable_less_deposit(self):
        self.assertEqual(billing.balance(bill("400", "600", deposit="250")),
                         Decimal("750.00"))

    def test_a_blank_deposit_leaves_the_whole_bill_outstanding(self):
        self.assertEqual(billing.balance(bill("400")), Decimal("400.00"))

    def test_a_fully_paid_bill_has_no_balance(self):
        self.assertEqual(billing.balance(bill("400", deposit="400")),
                         Decimal("0.00"))

    def test_decimal_amounts_do_not_drift(self):
        """The reason money is Decimal: as floats this sums to 0.30000000000000004."""
        self.assertEqual(billing.total_billed(bill("0.1", "0.2")), Decimal("0.30"))

    def test_summary_agrees_with_the_individual_figures(self):
        b = bill("400", "600", deposit="250")
        figures = billing.summary(b)
        self.assertEqual(figures["total_billed"], billing.total_billed(b))
        self.assertEqual(figures["net_payable"], billing.net_payable(b))
        self.assertEqual(figures["net_deposit"], billing.deposit(b))
        self.assertEqual(figures["balance"], billing.balance(b))


class BillableServiceTests(unittest.TestCase):
    def rows(self, *panels):
        return [TestRow(panel=p, name=f"t{i}") for i, p in enumerate(panels)]

    def test_one_line_per_panel_not_per_test(self):
        rows = self.rows("CBC", "CBC", "CBC", "Lipid Profile")
        self.assertEqual(billing.billable_services(rows), ["CBC", "Lipid Profile"])

    def test_panel_order_is_the_order_they_print_in(self):
        self.assertEqual(billing.billable_services(self.rows("Lipid Profile", "CBC")),
                         ["Lipid Profile", "CBC"])

    def test_rows_with_no_panel_bill_under_investigations(self):
        self.assertEqual(billing.billable_services(self.rows("")),
                         [billing.DEFAULT_SERVICE])

    def test_no_rows_means_nothing_to_bill(self):
        self.assertEqual(billing.billable_services([]), [])


class SyncTests(unittest.TestCase):
    def rows(self, *panels):
        return [TestRow(panel=p, name="t") for p in panels]

    def test_adding_a_panel_adds_an_unpriced_line(self):
        items = billing.sync_items(bill(), self.rows("CBC"))
        self.assertEqual([(i.service, i.amount) for i in items], [("CBC", "")])

    def test_an_amount_already_typed_survives_another_panel_being_added(self):
        current = Billing(items=[BillItem("CBC", "400")])
        items = billing.sync_items(current, self.rows("CBC", "Lipid Profile"))
        self.assertEqual([(i.service, i.amount) for i in items],
                         [("CBC", "400"), ("Lipid Profile", "")])

    def test_removing_a_panel_removes_its_line_and_leaves_the_rest(self):
        current = Billing(items=[BillItem("CBC", "400"),
                                 BillItem("Lipid Profile", "600")])
        items = billing.sync_items(current, self.rows("CBC"))
        self.assertEqual([(i.service, i.amount) for i in items], [("CBC", "400")])

    def test_re_adding_a_panel_comes_back_unpriced(self):
        """The amount left with the panel; it does not come back from the dead."""
        current = Billing(items=[BillItem("CBC", "400")])
        dropped = Billing(items=billing.sync_items(current, []))
        items = billing.sync_items(dropped, self.rows("CBC"))
        self.assertEqual(items[0].amount, "")

    def test_syncing_an_unchanged_bill_changes_nothing(self):
        current = Billing(items=[BillItem("CBC", "400")])
        items = billing.sync_items(current, self.rows("CBC"))
        self.assertEqual([(i.service, i.amount) for i in items], [("CBC", "400")])


class AmountInWordsTests(unittest.TestCase):
    """A bill states the paid amount in words as well as figures, because a
    figure can be altered after the fact with one pen stroke and a sentence
    cannot. Indian grouping - crore, lakh, thousand."""

    def words(self, value):
        return billing.amount_in_words(value)

    def test_the_slip_this_was_modelled_on(self):
        self.assertEqual(self.words("1040"), "One Thousand Forty Rupees Only")

    def test_units_and_teens(self):
        self.assertEqual(self.words("7"), "Seven Rupees Only")
        self.assertEqual(self.words("13"), "Thirteen Rupees Only")
        self.assertEqual(self.words("20"), "Twenty Rupees Only")
        self.assertEqual(self.words("21"), "Twenty One Rupees Only")

    def test_hundreds(self):
        self.assertEqual(self.words("100"), "One Hundred Rupees Only")
        self.assertEqual(self.words("105"), "One Hundred Five Rupees Only")
        self.assertEqual(self.words("999"), "Nine Hundred Ninety Nine Rupees Only")

    def test_indian_grouping_not_western(self):
        self.assertEqual(self.words("100000"), "One Lakh Rupees Only")
        self.assertIn("Lakh", self.words("1234567"))
        self.assertNotIn("Million", self.words("1234567"))

    def test_the_largest_amount_the_app_allows(self):
        self.assertEqual(
            self.words("9999999.99"),
            "Ninety Nine Lakh Ninety Nine Thousand Nine Hundred Ninety Nine "
            "Rupees and Ninety Nine Paise Only")

    def test_paise(self):
        self.assertEqual(self.words("40.50"), "Forty Rupees and Fifty Paise Only")
        self.assertEqual(self.words("0.50"), "Fifty Paise Only")

    def test_singular_forms(self):
        """'One Rupees Only' on a printed bill looks machine-made."""
        self.assertEqual(self.words("1"), "One Rupee Only")
        self.assertEqual(self.words("1.01"), "One Rupee and One Paisa Only")
        self.assertEqual(self.words("2.01"), "Two Rupees and One Paisa Only")

    def test_zero_and_blank(self):
        self.assertEqual(self.words("0"), "Zero Rupees Only")
        self.assertEqual(self.words(""), "Zero Rupees Only")

    def test_every_amount_the_app_accepts_produces_words(self):
        """No gaps: a bill must never print a blank where the words should be."""
        for n in list(range(0, 130)) + [999, 1000, 1001, 10_000, 99_999,
                                        100_000, 1_000_000, 9_999_999]:
            text = self.words(str(n))
            self.assertTrue(text.endswith("Only"), n)
            self.assertNotIn("  ", text)


class BillDateTests(unittest.TestCase):
    def test_the_stored_day_is_printed_with_the_month_spelled_out(self):
        self.assertEqual(billing.format_bill_date("30-08-2026"), "30-Aug-2026")

    def test_an_unreadable_date_is_passed_through_rather_than_blanked(self):
        self.assertEqual(billing.format_bill_date("whenever"), "whenever")
        self.assertEqual(billing.format_bill_date(""), "")


class HasContentTests(unittest.TestCase):
    def test_an_untouched_bill_has_nothing_to_print(self):
        self.assertFalse(billing.has_content(Billing(
            bill_no="BILL-000001", bill_date="01-01-2026",
            items=[BillItem("CBC", "")])))

    def test_a_priced_line_counts(self):
        self.assertTrue(billing.has_content(bill("400")))

    def test_a_zero_charge_still_counts_as_a_bill(self):
        """Zero is a decision - 'no charge for this' - and blank is not."""
        self.assertTrue(billing.has_content(bill("0")))

    def test_a_deposit_alone_counts(self):
        self.assertTrue(billing.has_content(bill(deposit="500")))

    def test_no_billing_at_all(self):
        self.assertFalse(billing.has_content(Billing()))
        self.assertFalse(billing.has_content(None))


if __name__ == "__main__":
    unittest.main()
