"""Shared test scaffolding.

Every test runs against a throwaway APPDATA directory, so the suite never reads
or writes the real %APPDATA%\BloodReportApp data.
"""
import os
import shutil
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class SandboxCase(unittest.TestCase):
    """Base case that isolates app storage into a temp folder."""

    def setUp(self):
        from app import storage

        self._old_appdata = os.environ.get("APPDATA")
        self.sandbox = tempfile.mkdtemp(prefix="brm-test-")
        os.environ["APPDATA"] = self.sandbox
        storage.clear_cache()
        storage.ensure_dirs()
        self.storage = storage

    def tearDown(self):
        from app import storage

        storage.clear_cache()
        if self._old_appdata is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = self._old_appdata
        shutil.rmtree(self.sandbox, ignore_errors=True)

    # convenience ----------------------------------------------------------
    def make_report(self, name="Test Patient", **kwargs):
        from app.models import Report, TestRow

        fields = dict(
            patient_name=name,
            age="30",
            sex="M",
            rows=[TestRow("Complete Blood Count (CBC)", "Haemoglobin (Hb)",
                          "14.0", "g/dL", "13.0 - 17.0")],
            panels=["Complete Blood Count (CBC)"],
        )
        fields.update(kwargs)
        return Report(**fields)
