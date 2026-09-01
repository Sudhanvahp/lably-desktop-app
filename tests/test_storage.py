"""The local-storage layer: serials, atomic writes, index integrity, recovery."""
import json
import os
import unittest

from tests.base import SandboxCase

from app.models import LabProfile


class SerialNumberTests(SandboxCase):
    def test_report_numbers_increment(self):
        a = self.storage.save_report(self.make_report("A"))
        b = self.storage.save_report(self.make_report("B"))
        self.assertEqual(a.report_no, "BR-000001")
        self.assertEqual(b.report_no, "BR-000002")

    def test_patient_ids_increment_and_are_unique(self):
        ids = [self.storage.save_report(self.make_report(f"P{i}")).patient_id
               for i in range(5)]
        self.assertEqual(len(set(ids)), 5)
        self.assertEqual(ids[0], "PID-000001")

    def test_peek_does_not_consume_a_number(self):
        first = self.storage.peek_report_no()
        self.assertEqual(self.storage.peek_report_no(), first)
        self.assertEqual(self.storage.peek_patient_id(),
                         self.storage.peek_patient_id())
        saved = self.storage.save_report(self.make_report())
        self.assertEqual(saved.report_no, first)

    def test_serials_survive_losing_the_counter_file(self):
        """Regression: a lost counter.json used to restart numbering at 1 and
        hand out a report number that was already in use."""
        a = self.storage.save_report(self.make_report("A"))
        b = self.storage.save_report(self.make_report("B"))
        os.remove(os.path.join(self.storage.app_dir(), "counter.json"))
        self.storage.clear_cache()

        c = self.storage.save_report(self.make_report("C"))
        self.assertNotIn(c.report_no, {a.report_no, b.report_no})
        self.assertNotIn(c.patient_id, {a.patient_id, b.patient_id})
        self.assertEqual(c.report_no, "BR-000003")

    def test_serials_survive_a_corrupt_counter_file(self):
        self.storage.save_report(self.make_report("A"))
        with open(os.path.join(self.storage.app_dir(), "counter.json"), "w") as fh:
            fh.write("{ not json at all")
        self.storage.clear_cache()
        b = self.storage.save_report(self.make_report("B"))
        self.assertEqual(b.report_no, "BR-000002")

    def test_counter_file_holding_wrong_types_does_not_crash(self):
        self.storage.save_report(self.make_report("A"))
        with open(os.path.join(self.storage.app_dir(), "counter.json"), "w") as fh:
            json.dump({"last": "abc", "last_patient": None}, fh)
        self.storage.clear_cache()
        b = self.storage.save_report(self.make_report("B"))
        self.assertEqual(b.report_no, "BR-000002")

    def test_existing_patient_id_is_kept_on_resave(self):
        report = self.storage.save_report(self.make_report("A"))
        original = report.patient_id
        report.patient_name = "A Edited"
        again = self.storage.save_report(report)
        self.assertEqual(again.patient_id, original)
        self.assertEqual(again.report_no, report.report_no)

    def test_serial_parser_ignores_junk(self):
        self.assertEqual(self.storage._serial("BR-000042", "BR-"), 42)
        self.assertEqual(self.storage._serial("PID-000007", "PID-"), 7)
        self.assertEqual(self.storage._serial("nonsense", "BR-"), 0)
        self.assertEqual(self.storage._serial("BR-abc", "BR-"), 0)
        self.assertEqual(self.storage._serial(None, "BR-"), 0)
        self.assertEqual(self.storage._serial("", "BR-"), 0)


class BillNumberTests(SandboxCase):
    def test_bill_numbers_increment(self):
        a = self.storage.save_report(self.make_report("A"))
        b = self.storage.save_report(self.make_report("B"))
        self.assertEqual(a.billing.bill_no, "BILL-000001")
        self.assertEqual(b.billing.bill_no, "BILL-000002")

    def test_every_saved_report_gets_a_bill_reference_and_date(self):
        saved = self.storage.save_report(self.make_report())
        self.assertTrue(saved.billing.bill_no)
        self.assertTrue(saved.billing.bill_date)

    def test_peek_does_not_consume_a_bill_number(self):
        first = self.storage.peek_bill_no()
        self.assertEqual(self.storage.peek_bill_no(), first)
        self.assertEqual(
            self.storage.save_report(self.make_report()).billing.bill_no, first)

    def test_a_bill_number_the_lab_typed_is_kept(self):
        from app.models import Billing

        report = self.make_report(billing=Billing(bill_no="CASH-42"))
        self.assertEqual(self.storage.save_report(report).billing.bill_no, "CASH-42")

    def test_a_typed_number_does_not_consume_a_generated_one(self):
        from app.models import Billing

        self.storage.save_report(
            self.make_report("A", billing=Billing(bill_no="CASH-42")))
        b = self.storage.save_report(self.make_report("B"))
        self.assertEqual(b.billing.bill_no, "BILL-000001")

    def test_bill_serials_survive_losing_the_counter_file(self):
        """Same failure mode as the report serials: without the index as a floor,
        a lost counter.json would re-issue a bill number already in use."""
        import os

        self.storage.save_report(self.make_report("A"))
        self.storage.save_report(self.make_report("B"))
        os.remove(os.path.join(self.storage.app_dir(), "counter.json"))
        self.storage.clear_cache()

        c = self.storage.save_report(self.make_report("C"))
        self.assertEqual(c.billing.bill_no, "BILL-000003")

    def test_a_reopened_report_keeps_its_bill_number(self):
        saved = self.storage.save_report(self.make_report())
        reloaded = self.storage.load_report(saved.id)
        again = self.storage.save_report(reloaded)
        self.assertEqual(again.billing.bill_no, saved.billing.bill_no)


class BillPersistenceTests(SandboxCase):
    def test_amounts_and_deposit_are_stored_with_the_report(self):
        from app.models import BillItem, Billing

        saved = self.storage.save_report(self.make_report(billing=Billing(
            net_deposit="250", items=[BillItem("CBC", "400")])))
        reloaded = self.storage.load_report(saved.id)
        self.assertEqual(reloaded.billing.net_deposit, "250")
        self.assertEqual(reloaded.billing.items[0].service, "CBC")
        self.assertEqual(reloaded.billing.items[0].amount, "400")

    def test_totals_are_never_written_to_disk(self):
        """They are derived, so a corrected amount always re-totals correctly
        instead of disagreeing with a stale sum stored beside it."""
        import json
        import os

        saved = self.storage.save_report(self.make_report())
        path = os.path.join(self.storage.reports_dir(), saved.id + ".json")
        with open(path, encoding="utf-8") as fh:
            stored = json.load(fh)
        for key in ("total_billed", "net_payable", "balance"):
            self.assertNotIn(key, stored["billing"])

    def test_a_rebuilt_index_still_carries_bill_numbers(self):
        saved = self.storage.save_report(self.make_report())
        entries = self.storage.rebuild_index()
        self.assertEqual(entries[0]["bill_no"], saved.billing.bill_no)


class ReportPersistenceTests(SandboxCase):
    def test_save_then_load_round_trips_every_field(self):
        report = self.make_report(
            "Round Trip", age="9", age_unit="M", sex="F", referred_by="Dr. X",
            sample_type="Serum", collected_on="01-01-2026 10:00 AM",
            reported_on="01-01-2026 11:00 AM", remarks="Repeat sample",
        )
        saved = self.storage.save_report(report)
        loaded = self.storage.load_report(saved.id)

        self.assertEqual(loaded.to_dict(), saved.to_dict())
        self.assertEqual(loaded.rows[0].name, "Haemoglobin (Hb)")
        self.assertEqual(loaded.age_unit, "M")
        self.assertEqual(loaded.remarks, "Repeat sample")

    def test_unicode_survives_the_round_trip(self):
        name = "Ramesh Iyer – रमेश"
        saved = self.storage.save_report(self.make_report(name))
        loaded = self.storage.load_report(saved.id)
        self.assertEqual(loaded.patient_name, name)

    def test_loading_a_missing_report_returns_none(self):
        self.assertIsNone(self.storage.load_report("does-not-exist"))

    def test_loading_a_corrupt_report_returns_none(self):
        saved = self.storage.save_report(self.make_report())
        path = os.path.join(self.storage.reports_dir(), saved.id + ".json")
        with open(path, "w") as fh:
            fh.write("broken json here")
        self.assertIsNone(self.storage.load_report(saved.id))

    def test_report_ids_are_unique(self):
        ids = {self.storage.save_report(self.make_report(f"P{i}")).id for i in range(20)}
        self.assertEqual(len(ids), 20)

    def test_no_temp_files_are_left_behind(self):
        self.storage.save_report(self.make_report())
        leftovers = [f for f in os.listdir(self.storage.reports_dir())
                     if f.endswith(".tmp")]
        self.assertEqual(leftovers, [])

    def test_editing_does_not_create_a_second_file(self):
        report = self.storage.save_report(self.make_report("A"))
        report.patient_name = "A Edited"
        self.storage.save_report(report)
        files = [f for f in os.listdir(self.storage.reports_dir()) if f.endswith(".json")]
        self.assertEqual(len(files), 1)
        self.assertEqual(len(self.storage.load_index()), 1)


class IndexTests(SandboxCase):
    def test_index_entry_has_the_fields_history_shows(self):
        self.storage.save_report(self.make_report("Jane"))
        entry = self.storage.load_index()[0]
        for key in ("id", "report_no", "patient_id", "patient_name", "age",
                    "sex", "referred_by", "panels", "created_at"):
            self.assertIn(key, entry)

    def test_index_is_newest_first(self):
        for i in range(3):
            report = self.make_report(f"P{i}")
            report.created_at = f"2026-01-0{i + 1}T10:00:00"
            self.storage.save_report(report)
        names = [e["patient_name"] for e in self.storage.load_index()]
        self.assertEqual(names, ["P2", "P1", "P0"])

    def test_rebuild_recovers_a_deleted_index(self):
        for i in range(3):
            self.storage.save_report(self.make_report(f"P{i}"))
        os.remove(os.path.join(self.storage.app_dir(), "index.json"))
        self.storage.clear_cache()
        self.assertEqual(len(self.storage.load_index()), 3)

    def test_rebuild_recovers_a_corrupt_index(self):
        self.storage.save_report(self.make_report("A"))
        with open(os.path.join(self.storage.app_dir(), "index.json"), "w") as fh:
            fh.write("not a list")
        self.storage.clear_cache()
        self.assertEqual(len(self.storage.load_index()), 1)

    def test_rebuild_skips_corrupt_report_files(self):
        good = self.storage.save_report(self.make_report("Good"))
        with open(os.path.join(self.storage.reports_dir(), "junk.json"), "w") as fh:
            fh.write("definitely not json")
        entries = self.storage.rebuild_index()
        self.assertEqual([e["id"] for e in entries], [good.id])

    def test_cache_is_consistent_with_disk(self):
        self.storage.save_report(self.make_report("A"))
        cached = list(self.storage.load_index())
        self.storage.clear_cache()
        self.assertEqual(cached, self.storage.load_index())


class DeletionTests(SandboxCase):
    def test_delete_removes_file_and_index_entry(self):
        report = self.storage.save_report(self.make_report())
        self.storage.delete_report(report.id)
        self.assertEqual(self.storage.load_index(), [])
        self.assertFalse(os.path.exists(
            os.path.join(self.storage.reports_dir(), report.id + ".json")))

    def test_bulk_delete_removes_only_the_named_reports(self):
        reports = [self.storage.save_report(self.make_report(f"P{i}")) for i in range(5)]
        doomed = [reports[0].id, reports[3].id]
        removed = self.storage.delete_reports(doomed)

        self.assertEqual(removed, 2)
        remaining = {e["id"] for e in self.storage.load_index()}
        self.assertEqual(remaining, {reports[1].id, reports[2].id, reports[4].id})

    def test_bulk_delete_of_everything_empties_the_index(self):
        reports = [self.storage.save_report(self.make_report(f"P{i}")) for i in range(4)]
        self.storage.delete_reports([r.id for r in reports])
        self.assertEqual(self.storage.load_index(), [])

    def test_deleting_an_unknown_id_is_harmless(self):
        self.storage.save_report(self.make_report())
        self.assertEqual(self.storage.delete_reports(["nope"]), 0)
        self.assertEqual(len(self.storage.load_index()), 1)

    def test_deleting_nothing_is_harmless(self):
        self.storage.save_report(self.make_report())
        self.assertEqual(self.storage.delete_reports([]), 0)
        self.assertEqual(len(self.storage.load_index()), 1)

    def test_serials_do_not_rewind_after_deleting_everything(self):
        """Deleting history must not cause the next report to reuse an old number."""
        reports = [self.storage.save_report(self.make_report(f"P{i}")) for i in range(3)]
        used = {r.report_no for r in reports}
        self.storage.delete_reports([r.id for r in reports])
        fresh = self.storage.save_report(self.make_report("New"))
        self.assertNotIn(fresh.report_no, used)


class ProfileTests(SandboxCase):
    def test_profile_round_trips(self):
        profile = LabProfile(lab_name="Sunrise", address1="MG Road", phone="080",
                             pathologist="Dr. Rao", footer_note="note")
        self.storage.save_profile(profile)
        self.storage.clear_cache()
        loaded = self.storage.load_profile()
        self.assertEqual(loaded.lab_name, "Sunrise")
        self.assertEqual(loaded.footer_note, "note")

    def test_missing_profile_is_empty_not_an_error(self):
        self.assertEqual(self.storage.load_profile().lab_name, "")

    def test_corrupt_profile_falls_back_to_empty(self):
        with open(os.path.join(self.storage.app_dir(), "lab_profile.json"), "w") as fh:
            fh.write("not valid json")
        self.storage.clear_cache()
        self.assertEqual(self.storage.load_profile().lab_name, "")

    def test_import_asset_copies_into_the_app_folder(self):
        source = os.path.join(self.sandbox, "logo.png")
        with open(source, "wb") as fh:
            fh.write(b"\x89PNG\r\n\x1a\n")
        stored = self.storage.import_asset(source, "logo")

        self.assertTrue(os.path.isfile(stored))
        self.assertTrue(os.path.abspath(stored).startswith(
            os.path.abspath(self.storage.assets_dir())))
        os.remove(source)
        self.assertTrue(os.path.isfile(stored), "asset must survive losing the original")

    def test_import_asset_replaces_the_previous_one(self):
        for ext in (".png", ".jpg"):
            source = os.path.join(self.sandbox, "pic" + ext)
            with open(source, "wb") as fh:
                fh.write(b"data")
            self.storage.import_asset(source, "logo")
        logos = [f for f in os.listdir(self.storage.assets_dir())
                 if f.startswith("logo")]
        self.assertEqual(len(logos), 1)


if __name__ == "__main__":
    unittest.main()
