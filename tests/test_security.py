"""The edit password: hashing, verification, and the properties that matter."""
import json
import os
import unittest

from tests.base import SandboxCase

from app import security


class RecordFile:
    """Read/write helpers for security.json, shared by both suites."""

    def record_path(self):
        return os.path.join(self.storage.app_dir(), security.FILENAME)

    def read_raw(self) -> str:
        with open(self.record_path(), encoding="utf-8") as fh:
            return fh.read()

    def read_record(self) -> dict:
        return json.loads(self.read_raw())

    def write(self, payload):
        with open(self.record_path(), "w", encoding="utf-8") as fh:
            fh.write(payload if isinstance(payload, str) else json.dumps(payload))


class PasswordTests(RecordFile, SandboxCase):

    def test_no_password_to_begin_with(self):
        self.assertFalse(security.is_set())
        self.assertFalse(security.verify("anything"))

    def test_setting_then_verifying(self):
        self.assertIsNone(security.set_password("lab1234"))
        self.assertTrue(security.is_set())
        self.assertTrue(security.verify("lab1234"))

    def test_wrong_password_is_rejected(self):
        security.set_password("lab1234")
        for wrong in ("Lab1234", "lab123", "lab12345", "", " lab1234"):
            self.assertFalse(security.verify(wrong), wrong)

    def test_password_is_never_stored_in_the_clear(self):
        security.set_password("hunter2secret")
        self.assertNotIn("hunter2secret", self.read_raw())

    def test_record_shape(self):
        security.set_password("lab1234")
        record = self.read_record()
        self.assertEqual(record["algorithm"], "pbkdf2_sha256")
        self.assertGreaterEqual(record["iterations"], 100_000)
        self.assertEqual(len(record["salt"]), security.SALT_BYTES * 2)
        self.assertEqual(len(record["hash"]), 64)          # sha256, hex

    def test_the_salt_is_random_per_password(self):
        security.set_password("same")
        first = self.read_record()
        security.set_password("same")
        second = self.read_record()

        self.assertNotEqual(first["salt"], second["salt"])
        self.assertNotEqual(first["hash"], second["hash"],
                            "same password must not produce the same hash twice")

    def test_short_passwords_are_refused(self):
        self.assertIsNotNone(security.set_password("ab"))
        self.assertIsNotNone(security.set_password(""))
        self.assertFalse(security.is_set())

    def test_minimum_length_is_enforced_at_the_boundary(self):
        self.assertIsNone(security.set_password("a" * security.MIN_LENGTH))

    def test_unicode_passwords_work(self):
        security.set_password("पासवर्ड123")
        self.assertTrue(security.verify("पासवर्ड123"))
        self.assertFalse(security.verify("पासवर्ड124"))

    def test_changing_requires_the_current_password(self):
        security.set_password("first123")
        self.assertIsNotNone(security.change_password("wrong", "second123"))
        self.assertTrue(security.verify("first123"))

        self.assertIsNone(security.change_password("first123", "second123"))
        self.assertTrue(security.verify("second123"))
        self.assertFalse(security.verify("first123"))

    def test_changing_rejects_a_weak_new_password(self):
        security.set_password("first123")
        self.assertIsNotNone(security.change_password("first123", "ab"))
        self.assertTrue(security.verify("first123"), "the old password must survive")

    def test_clearing_removes_protection(self):
        security.set_password("lab1234")
        security.clear_password()
        self.assertFalse(security.is_set())
        self.assertFalse(security.verify("lab1234"))

    def test_clearing_when_none_is_set_is_harmless(self):
        security.clear_password()
        self.assertFalse(security.is_set())


class CorruptRecordTests(RecordFile, SandboxCase):
    """A damaged file must fail closed - never let anyone in."""

    def test_unparseable_file(self):
        self.write("not json at all")
        self.assertFalse(security.verify("anything"))
        self.assertFalse(security.is_set())

    def test_missing_salt(self):
        self.write({"hash": "a" * 64, "iterations": 1000})
        self.assertFalse(security.verify("anything"))

    def test_non_hex_salt(self):
        self.write({"hash": "a" * 64, "salt": "zzzz", "iterations": 1000})
        self.assertFalse(security.verify("anything"))

    def test_nonsense_iteration_count(self):
        self.write({"hash": "a" * 64, "salt": "abcd", "iterations": 0})
        self.assertFalse(security.verify("anything"))
        self.write({"hash": "a" * 64, "salt": "abcd", "iterations": "many"})
        self.assertFalse(security.verify("anything"))

    def test_empty_hash_is_not_a_password(self):
        self.write({"hash": "", "salt": "abcd", "iterations": 1000})
        self.assertFalse(security.is_set())
        self.assertFalse(security.verify(""))

    def test_a_record_keeps_its_own_iteration_count(self):
        """Raising the app's cost later must not lock anyone out."""
        security.set_password("lab1234")
        recorded = self.read_record()["iterations"]
        original = security.ITERATIONS
        try:
            security.ITERATIONS = original * 2
            self.assertTrue(security.verify("lab1234"))
            self.assertEqual(self.read_record()["iterations"], recorded)
        finally:
            security.ITERATIONS = original


if __name__ == "__main__":
    unittest.main()
