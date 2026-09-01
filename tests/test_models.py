"""Dataclass serialisation. These structures are the on-disk format, so a
regression here silently corrupts every stored report."""
import unittest

from app.models import BillItem, Billing, LabProfile, Report, TestRow


class TestRowTests(unittest.TestCase):
    def test_round_trip(self):
        row = TestRow("CBC", "Hb", "14.0", "g/dL", "13 - 17")
        self.assertEqual(TestRow.from_dict(row.to_dict()), row)

    def test_missing_keys_default_to_empty(self):
        row = TestRow.from_dict({})
        self.assertEqual(row.name, "")
        self.assertEqual(row.result, "")

    def test_numeric_values_are_coerced_to_text(self):
        row = TestRow.from_dict({"name": "Hb", "result": 14.0})
        self.assertEqual(row.result, "14.0")
        self.assertIsInstance(row.result, str)


class ReportTests(unittest.TestCase):
    def make(self):
        return Report(
            id="20260101-100000-abcd", report_no="BR-000001",
            patient_name="Jane", age="34", sex="F", patient_id="PID-000001",
            panels=["Complete Blood Count (CBC)"],
            rows=[TestRow("Complete Blood Count (CBC)", "Hb", "9.2", "g/dL", "12 - 15")],
            created_at="2026-01-01T10:00:00",
        )

    def test_round_trip_preserves_everything(self):
        original = self.make()
        restored = Report.from_dict(original.to_dict())
        self.assertEqual(restored.to_dict(), original.to_dict())

    def test_rows_become_testrow_objects_not_dicts(self):
        restored = Report.from_dict(self.make().to_dict())
        self.assertIsInstance(restored.rows[0], TestRow)
        self.assertEqual(restored.rows[0].result, "9.2")

    def test_empty_dict_gives_a_usable_blank_report(self):
        report = Report.from_dict({})
        self.assertEqual(report.rows, [])
        self.assertEqual(report.panels, [])
        self.assertEqual(report.patient_name, "")

    def test_unknown_keys_are_ignored(self):
        data = self.make().to_dict()
        data["some_future_field"] = "value"
        report = Report.from_dict(data)
        self.assertFalse(hasattr(report, "some_future_field"))
        self.assertEqual(report.patient_name, "Jane")

    def test_reports_do_not_share_mutable_defaults(self):
        """A classic dataclass trap: a shared list would leak rows between reports."""
        a, b = Report(), Report()
        a.rows.append(TestRow(name="Hb"))
        a.panels.append("CBC")
        self.assertEqual(b.rows, [])
        self.assertEqual(b.panels, [])

    def test_index_entry_shape(self):
        entry = self.make().index_entry()
        self.assertEqual(entry["report_no"], "BR-000001")
        self.assertEqual(entry["patient_id"], "PID-000001")
        self.assertEqual(entry["age"], "34Y")
        self.assertEqual(entry["panels"], ["Complete Blood Count (CBC)"])

    def test_index_entry_age_is_blank_when_age_is_blank(self):
        report = self.make()
        report.age = ""
        self.assertEqual(report.index_entry()["age"], "")

    def test_index_entry_panels_is_a_copy(self):
        report = self.make()
        entry = report.index_entry()
        entry["panels"].append("Injected")
        self.assertEqual(report.panels, ["Complete Blood Count (CBC)"])


class BillFieldTests(unittest.TestCase):
    """The fields the lab's own slip needs. Each has to survive the round trip
    and each has to be absent-tolerant, because reports written before it
    existed still have to open."""

    def test_the_new_billing_fields_round_trip(self):
        original = Billing(bill_type="Credit Bill", billed_by="Miss. Nethra H M",
                           bill_date="30-08-2026 10:43:30 AM")
        restored = Billing.from_dict(original.to_dict())
        self.assertEqual(restored.bill_type, "Credit Bill")
        self.assertEqual(restored.billed_by, "Miss. Nethra H M")
        self.assertEqual(restored.bill_date, "30-08-2026 10:43:30 AM")

    def test_a_bill_from_the_first_build_opens_with_them_blank(self):
        restored = Billing.from_dict({"bill_no": "BILL-000001",
                                      "bill_date": "30-08-2026"})
        self.assertEqual(restored.bill_type, "")
        self.assertEqual(restored.billed_by, "")
        self.assertEqual(restored.bill_date, "30-08-2026")

    def test_the_new_profile_fields_round_trip(self):
        original = LabProfile(mobile="9964725222", billed_by="Miss. Nethra H M",
                              bill_notes="One\nTwo")
        restored = LabProfile.from_dict(original.to_dict())
        self.assertEqual(restored.mobile, "9964725222")
        self.assertEqual(restored.billed_by, "Miss. Nethra H M")
        self.assertEqual(restored.bill_notes, "One\nTwo")

    def test_a_profile_from_the_first_build_opens_with_them_blank(self):
        restored = LabProfile.from_dict({"lab_name": "X"})
        self.assertEqual(restored.mobile, "")
        self.assertEqual(restored.bill_notes, "")
        self.assertEqual(restored.billed_by, "")


class PatientPhoneTests(unittest.TestCase):
    def test_the_phone_round_trips(self):
        restored = Report.from_dict(Report(phone="9620055441").to_dict())
        self.assertEqual(restored.phone, "9620055441")

    def test_a_report_saved_before_the_field_existed_opens_with_a_blank_phone(self):
        self.assertEqual(Report.from_dict({"patient_name": "Jane"}).phone, "")

    def test_a_numeric_phone_is_coerced_to_text(self):
        restored = Report.from_dict({"phone": 9620055441})
        self.assertEqual(restored.phone, "9620055441")
        self.assertIsInstance(restored.phone, str)


class BillingTests(unittest.TestCase):
    def make(self):
        return Billing(bill_no="BILL-000001", bill_date="01-01-2026",
                       net_deposit="250",
                       items=[BillItem("CBC", "400"), BillItem("Lipid Profile", "")])

    def test_round_trip(self):
        self.assertEqual(Billing.from_dict(self.make().to_dict()).to_dict(),
                         self.make().to_dict())

    def test_items_become_billitem_objects_not_dicts(self):
        restored = Billing.from_dict(self.make().to_dict())
        self.assertIsInstance(restored.items[0], BillItem)
        self.assertEqual(restored.items[0].amount, "400")

    def test_numeric_amounts_are_coerced_to_text(self):
        restored = Billing.from_dict({"items": [{"service": "CBC", "amount": 400}]})
        self.assertEqual(restored.items[0].amount, "400")
        self.assertIsInstance(restored.items[0].amount, str)

    def test_missing_or_malformed_items_give_an_empty_bill(self):
        for raw in ({}, {"items": None}, {"items": "nonsense"}):
            self.assertEqual(Billing.from_dict(raw).items, [])

    def test_bills_do_not_share_mutable_defaults(self):
        a, b = Billing(), Billing()
        a.items.append(BillItem("CBC", "1"))
        self.assertEqual(b.items, [])


class ReportBillingTests(unittest.TestCase):
    """A report written before billing existed has to keep opening cleanly, and
    a report written with it has to survive the round trip to disk."""

    def test_a_report_without_billing_gets_an_empty_bill(self):
        report = Report.from_dict({"patient_name": "Jane"})
        self.assertIsInstance(report.billing, Billing)
        self.assertEqual(report.billing.items, [])
        self.assertEqual(report.billing.bill_no, "")

    def test_billing_survives_the_round_trip(self):
        original = Report(patient_name="Jane",
                          billing=Billing(bill_no="BILL-000007", net_deposit="100",
                                          items=[BillItem("CBC", "400")]))
        restored = Report.from_dict(original.to_dict())
        self.assertEqual(restored.billing.bill_no, "BILL-000007")
        self.assertEqual(restored.billing.items[0].service, "CBC")
        self.assertEqual(restored.to_dict(), original.to_dict())

    def test_billing_is_not_flattened_into_a_string(self):
        """The generic from_dict loop stringifies every field it does not know
        about; billing has to be excluded from it or it arrives as text."""
        restored = Report.from_dict(Report(billing=Billing(bill_no="B")).to_dict())
        self.assertIsInstance(restored.billing, Billing)

    def test_a_junk_billing_value_does_not_break_loading(self):
        report = Report.from_dict({"patient_name": "Jane", "billing": "corrupt"})
        self.assertEqual(report.patient_name, "Jane")
        self.assertEqual(report.billing.items, [])

    def test_reports_do_not_share_one_bill(self):
        a, b = Report(), Report()
        a.billing.items.append(BillItem("CBC", "1"))
        self.assertEqual(b.billing.items, [])

    def test_the_index_carries_the_bill_number(self):
        report = Report(billing=Billing(bill_no="BILL-000009"))
        self.assertEqual(report.index_entry()["bill_no"], "BILL-000009")


class LabProfileTests(unittest.TestCase):
    def test_round_trip(self):
        profile = LabProfile(lab_name="Sunrise", phone="080", reg_no="KA/1")
        self.assertEqual(LabProfile.from_dict(profile.to_dict()).to_dict(),
                         profile.to_dict())

    def test_missing_and_null_values_default_to_empty(self):
        profile = LabProfile.from_dict({"lab_name": "X", "phone": None})
        self.assertEqual(profile.lab_name, "X")
        self.assertEqual(profile.phone, "")
        self.assertEqual(profile.address1, "")

    def test_unknown_keys_are_ignored(self):
        profile = LabProfile.from_dict({"lab_name": "X", "nonsense": 1})
        self.assertFalse(hasattr(profile, "nonsense"))


if __name__ == "__main__":
    unittest.main()
