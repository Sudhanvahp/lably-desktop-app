"""Panel catalogue and the H/L reference-range check."""
import unittest

from app.panels import PANELS, PANEL_NAMES, flag_for, panel_rows, resolve_ref


class PanelCatalogueTests(unittest.TestCase):
    def test_all_panels_are_listed(self):
        self.assertEqual(set(PANEL_NAMES), set(PANELS))
        self.assertEqual(len(PANEL_NAMES), 6)

    def test_every_row_is_a_name_unit_reference_triple(self):
        for panel, rows in PANELS.items():
            self.assertTrue(rows, f"{panel} has no tests")
            for row in rows:
                self.assertEqual(len(row), 3, f"malformed row in {panel}: {row}")
                name, unit, ref = row
                self.assertTrue(name.strip(), f"unnamed test in {panel}")
                self.assertIsInstance(unit, str)
                self.assertIsInstance(ref, (str, dict))

    def test_test_names_are_unique_within_a_panel(self):
        for panel, rows in PANELS.items():
            names = [r[0] for r in rows]
            self.assertEqual(len(names), len(set(names)), f"duplicate test in {panel}")

    def test_sex_specific_ranges_cover_both_sexes(self):
        for panel, rows in PANELS.items():
            for name, _unit, ref in rows:
                if isinstance(ref, dict):
                    self.assertIn("M", ref, f"{panel}/{name} missing male range")
                    self.assertIn("F", ref, f"{panel}/{name} missing female range")

    def test_every_reference_range_is_parseable(self):
        """A range the flagger cannot read would silently never flag anything."""
        for panel, rows in PANELS.items():
            for name, _unit, ref in rows:
                for sex in ("M", "F"):
                    text = resolve_ref(ref, sex)
                    if not text:
                        continue
                    low_hit = flag_for("-99999", text)
                    high_hit = flag_for("99999", text)
                    self.assertTrue(
                        low_hit or high_hit,
                        f"unparseable reference '{text}' for {panel}/{name}")


class ResolveRefTests(unittest.TestCase):
    def test_plain_string_is_returned_as_is(self):
        self.assertEqual(resolve_ref("4000 - 11000", "F"), "4000 - 11000")

    def test_sex_specific_picks_the_right_branch(self):
        ref = {"M": "13.0 - 17.0", "F": "12.0 - 15.0"}
        self.assertEqual(resolve_ref(ref, "M"), "13.0 - 17.0")
        self.assertEqual(resolve_ref(ref, "F"), "12.0 - 15.0")

    def test_unknown_sex_falls_back_to_male_range(self):
        ref = {"M": "13.0 - 17.0", "F": "12.0 - 15.0"}
        self.assertEqual(resolve_ref(ref, "Other"), "13.0 - 17.0")
        self.assertEqual(resolve_ref(ref, ""), "13.0 - 17.0")

    def test_panel_rows_resolves_and_keeps_order(self):
        rows = panel_rows("Complete Blood Count (CBC)", "F")
        self.assertEqual(rows[0][0], "Haemoglobin (Hb)")
        self.assertEqual(rows[0][2], "12.0 - 15.0")
        self.assertEqual(len(rows), len(PANELS["Complete Blood Count (CBC)"]))

    def test_unknown_panel_is_empty_not_an_error(self):
        self.assertEqual(panel_rows("No Such Panel", "M"), [])


class FlagTests(unittest.TestCase):
    def test_within_range_is_not_flagged(self):
        self.assertEqual(flag_for("15", "13.0 - 17.0"), "")

    def test_below_and_above_range(self):
        self.assertEqual(flag_for("9.2", "13.0 - 17.0"), "L")
        self.assertEqual(flag_for("18", "13.0 - 17.0"), "H")

    def test_boundaries_are_inclusive(self):
        self.assertEqual(flag_for("13.0", "13.0 - 17.0"), "")
        self.assertEqual(flag_for("17.0", "13.0 - 17.0"), "")

    def test_upper_bound_only(self):
        self.assertEqual(flag_for("250", "< 200"), "H")
        self.assertEqual(flag_for("150", "< 200"), "")

    def test_lower_bound_only(self):
        self.assertEqual(flag_for("30", "> 40"), "L")
        self.assertEqual(flag_for("50", "> 40"), "")

    def test_non_numeric_results_are_never_flagged(self):
        for value in ("Nil", "Absent", "Trace", "positive", ""):
            self.assertEqual(flag_for(value, "0 - 1"), "", value)

    def test_unparseable_reference_is_never_flagged(self):
        self.assertEqual(flag_for("5", "see note"), "")
        self.assertEqual(flag_for("5", ""), "")

    def test_negative_values(self):
        self.assertEqual(flag_for("-3", "0 - 10"), "L")

    def test_whitespace_is_tolerated(self):
        self.assertEqual(flag_for("  9.2  ", "  13.0 - 17.0  "), "L")

    def test_none_inputs_do_not_raise(self):
        self.assertEqual(flag_for(None, None), "")


if __name__ == "__main__":
    unittest.main()
