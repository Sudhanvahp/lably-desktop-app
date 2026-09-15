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
        self.assertEqual(ids[0], "HFCD-000001")

    def test_ids_handed_out_as_pid_still_occupy_their_numbers(self):
        """Reports made before the HFCD prefix keep their PID and the new
        sequence carries on after them rather than restarting at 1."""
        old = self.make_report("Old")
        old.patient_id = "PID-000041"
        self.storage.save_report(old)
        self.assertEqual(self.storage.peek_patient_id(), "HFCD-000042")

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


class BackupTests(SandboxCase):
    """Copying saved reports to a synced (Google Drive) folder."""

    def _enable(self):
        folder = os.path.join(self.sandbox, "My Drive", "Lably")
        self.storage.save_profile(LabProfile(lab_name="Sunrise", backup_dir=folder))
        return folder

    def _month(self, folder, report):
        return self.storage.backup_month_dir(folder, report)

    def test_backup_is_off_by_default(self):
        report = self.storage.save_report(self.make_report())
        self.assertIsNone(self.storage.backup_copy(report))

    def test_saved_report_is_copied_under_a_readable_name(self):
        folder = self._enable()
        report = self.storage.save_report(self.make_report(name="Jane Doe"))
        month = self._month(folder, report)
        self.assertEqual(self.storage.backup_copy(report), month)
        expected = os.path.join(month, "data", f"{report.report_no}-Jane-Doe.json")
        self.assertTrue(os.path.isfile(expected))
        with open(expected, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["patient_name"], "Jane Doe")

    def test_backup_name_strips_unsafe_characters(self):
        report = self.make_report(name='A/B: "C"?')
        report.report_no = "BR-000007"
        self.assertEqual(self.storage.backup_name(report), "BR-000007-A-B-C")

    def test_an_unwritable_backup_folder_does_not_stop_the_save(self):
        bad = os.path.join(self.sandbox, "not-a-folder.txt")
        with open(bad, "w") as fh:
            fh.write("x")
        self.storage.save_profile(LabProfile(lab_name="S", backup_dir=bad))
        report = self.storage.save_report(self.make_report())
        self.assertIsNone(self.storage.backup_copy(report))
        self.assertIsNotNone(self.storage.load_report(report.id))

    def test_check_backup_dir(self):
        self.assertIsNone(self.storage.check_backup_dir(""))
        self.assertIsNone(self.storage.check_backup_dir(
            os.path.join(self.sandbox, "new", "deep")))
        self.assertIn("outside", self.storage.check_backup_dir(self.storage.app_dir()))
        with open(os.path.join(self.sandbox, "file.txt"), "w") as fh:
            fh.write("x")
        self.assertIn("Cannot write", self.storage.check_backup_dir(
            os.path.join(self.sandbox, "file.txt")))
        self.assertIn("Cannot write", self.storage.check_backup_dir(
            os.path.join(self.sandbox, "bad" + chr(0) + "name")))

    def test_google_drive_paths_are_recognised(self):
        self.assertTrue(self.storage.is_google_drive_path(r"G:\My Drive\Lably"))
        self.assertTrue(self.storage.is_google_drive_path("/home/x/Google Drive/Lably"))
        self.assertFalse(self.storage.is_google_drive_path(r"D:\Backups"))
        self.assertFalse(self.storage.is_google_drive_path(""))

    def test_profile_round_trips_the_new_letterhead_fields(self):
        self.storage.save_profile(LabProfile(
            lab_name="S", timings="Mon-Sat 7-8", holidays="Sundays",
            backup_dir=r"G:\My Drive\Lably"))
        self.storage.clear_cache()
        loaded = self.storage.load_profile()
        self.assertEqual(loaded.timings, "Mon-Sat 7-8")
        self.assertEqual(loaded.holidays, "Sundays")
        self.assertEqual(loaded.backup_dir, r"G:\My Drive\Lably")

    def test_a_relative_backup_path_is_refused(self):
        self.assertIn("full path", self.storage.check_backup_dir("Lably"))

    def test_the_app_folder_check_ignores_case(self):
        self.assertIn("outside", self.storage.check_backup_dir(
            self.storage.app_dir().upper()))

    def test_renaming_the_patient_replaces_the_old_backup_copy(self):
        folder = self._enable()
        report = self.storage.save_report(self.make_report(name="Jane Do"))
        self.storage.backup_copy(report)
        report.patient_name = "Jane Doe"
        self.storage.save_report(report)
        self.storage.backup_copy(report)
        names = sorted(os.listdir(os.path.join(self._month(folder, report), "data")))
        self.assertEqual(names, [f"{report.report_no}-Jane-Doe.json"])

    def test_purging_never_touches_other_reports(self):
        folder = self._enable()
        first = self.storage.save_report(self.make_report(name="A"))
        second = self.storage.save_report(self.make_report(name="B"))
        self.storage.backup_copy(first)
        self.storage.backup_copy(second)
        self.storage.backup_copy(first)
        self.assertEqual(len(os.listdir(os.path.join(self._month(folder, first), "data"))), 2)

    def test_purging_spares_another_pcs_report_with_the_same_number(self):
        """Two machines sharing one Drive folder can both hand out BR-000001."""
        folder = self._enable()
        report = self.storage.save_report(self.make_report(name="Mine"))
        dest = os.path.join(self._month(folder, report), "data")
        os.makedirs(dest)
        foreign = os.path.join(dest, f"{report.report_no}-Theirs.json")
        with open(foreign, "w", encoding="utf-8") as fh:
            json.dump({"id": "some-other-id", "patient_name": "Theirs"}, fh)
        self.storage.backup_copy(report)
        self.assertTrue(os.path.isfile(foreign))

    def test_the_pdf_twin_of_a_stale_copy_is_retired_too(self):
        folder = self._enable()
        report = self.storage.save_report(self.make_report(name="Jane Do"))
        self.storage.backup_copy(report)
        pdf_dir = self._month(folder, report)
        old_pdf = os.path.join(pdf_dir, f"{report.report_no}-Jane-Do.pdf")
        with open(old_pdf, "wb") as fh:
            fh.write(b"%PDF-1.4")
        report.patient_name = "Jane Doe"
        self.storage.save_report(report)
        self.storage.backup_copy(report)
        self.assertFalse(os.path.exists(old_pdf))

    def test_copies_are_filed_by_year_and_month(self):
        folder = self._enable()
        report = self.make_report(name="Jane")
        report.created_at = "2026-03-15T10:00:00"
        report = self.storage.save_report(report)
        month = self.storage.backup_copy(report)
        self.assertEqual(month, os.path.join(folder, "2026", "03-March"))
        self.assertTrue(os.path.isfile(os.path.join(
            month, "data", f"{report.report_no}-Jane.json")))

    def test_an_unreadable_created_at_files_under_today(self):
        from datetime import datetime
        folder = self._enable()
        report = self.make_report(name="Jane")
        report.created_at = "garbage"
        self.assertEqual(self.storage.backup_month_dir(folder, report),
                         os.path.join(folder, f"{datetime.now():%Y}",
                                      f"{datetime.now():%m-%B}"))


class ReportIdTests(SandboxCase):
    def test_a_burst_of_saves_in_one_second_never_collides(self):
        ids = {self.storage.new_report_id() for _ in range(500)}
        self.assertEqual(len(ids), 500)

    def test_an_id_already_on_disk_is_never_handed_out_again(self):
        import uuid
        fixed = "deadbeef"
        original = uuid.uuid4
        calls = {"n": 0}

        class Fake:
            hex = fixed * 4

        def fake_uuid4():
            calls["n"] += 1
            return Fake() if calls["n"] == 1 else original()
        report = self.storage.save_report(self.make_report())
        report.id = ""   # force a fresh id next time
        uuid.uuid4 = fake_uuid4
        try:
            taken = self.storage.new_report_id()
            self.assertTrue(taken.endswith(fixed))
            with open(os.path.join(self.storage.reports_dir(), taken + ".json"), "w") as fh:
                fh.write("{}")
            calls["n"] = 0
            fresh = self.storage.new_report_id()
        finally:
            uuid.uuid4 = original
        self.assertNotEqual(fresh, taken)
