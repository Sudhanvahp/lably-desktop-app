"""safe_filename: patient names must never escape into a path."""
import os
import unittest

from tests.base import SandboxCase  # noqa: F401  (sets QT platform)

from app.util import safe_filename


class SafeFilenameTests(unittest.TestCase):
    def test_spaces_become_underscores(self):
        self.assertEqual(safe_filename("Jane Doe"), "Jane_Doe")

    def test_path_separators_are_removed(self):
        result = safe_filename("Baby of A/B" + os.sep + "Sharma")
        self.assertNotIn("/", result)
        self.assertNotIn(os.sep, result)

    def test_windows_reserved_characters_are_removed(self):
        result = safe_filename('a<b>c:d"e|f?g*h')
        for ch in '<>:"|?*':
            self.assertNotIn(ch, result)

    def test_control_characters_are_removed(self):
        self.assertNotIn("\t", safe_filename("R\tX"))
        self.assertNotIn("\n", safe_filename("R\nX"))

    def test_empty_and_junk_fall_back(self):
        self.assertEqual(safe_filename(""), "report")
        self.assertEqual(safe_filename("   "), "report")
        self.assertEqual(safe_filename("..."), "report")
        self.assertEqual(safe_filename(None), "report")

    def test_runs_are_collapsed(self):
        self.assertEqual(safe_filename("a///b"), "a-b")

    def test_normal_name_is_untouched(self):
        self.assertEqual(safe_filename("BR-000001_Ravi"), "BR-000001_Ravi")


if __name__ == "__main__":
    unittest.main()
