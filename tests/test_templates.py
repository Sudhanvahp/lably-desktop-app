"""Editable test panels: overrides, custom panels, sub-headings, reset."""
import unittest

from tests.base import SandboxCase

from app import templates
from app.panels import PANELS

CBC = "Complete Blood Count (CBC)"


class DefaultsTests(SandboxCase):
    def test_untouched_install_offers_the_built_ins(self):
        self.assertEqual(templates.panel_names(), list(PANELS))

    def test_rows_match_the_shipped_panel(self):
        rows = templates.rows_for(CBC)
        self.assertEqual(len(rows), len(PANELS[CBC]))
        self.assertEqual(rows[0]["name"], "Haemoglobin (Hb)")
        self.assertEqual(rows[0]["unit"], "g/dL")

    def test_sex_specific_ranges_are_split_into_two_columns(self):
        haemoglobin = templates.rows_for(CBC)[0]
        self.assertEqual(haemoglobin["ref_m"], "13.0 - 17.0")
        self.assertEqual(haemoglobin["ref_f"], "12.0 - 15.0")

    def test_ref_for_picks_by_sex(self):
        row = templates.rows_for(CBC)[0]
        self.assertEqual(templates.ref_for(row, "M"), "13.0 - 17.0")
        self.assertEqual(templates.ref_for(row, "F"), "12.0 - 15.0")
        self.assertEqual(templates.ref_for(row, "Other"), "13.0 - 17.0")

    def test_a_shared_range_is_used_for_both_sexes(self):
        row = templates.make_test("WBC", "/cmm", "4000 - 11000")
        self.assertEqual(templates.ref_for(row, "M"), "4000 - 11000")
        self.assertEqual(templates.ref_for(row, "F"), "4000 - 11000")

    def test_headings_have_no_range(self):
        self.assertEqual(templates.ref_for(templates.make_heading("X"), "M"), "")

    def test_unknown_panel_is_empty(self):
        self.assertEqual(templates.rows_for("Nothing"), [])


class EditingBuiltInsTests(SandboxCase):
    def test_editing_a_built_in_persists(self):
        rows = templates.rows_for(CBC)
        rows[0]["ref_m"] = "14.0 - 18.0"
        templates.save_panel(CBC, rows)
        self.storage.clear_cache()

        self.assertEqual(templates.rows_for(CBC)[0]["ref_m"], "14.0 - 18.0")
        self.assertTrue(templates.is_modified(CBC))

    def test_only_the_difference_is_stored(self):
        """An untouched panel must keep tracking the shipped defaults."""
        templates.save_panel(CBC, templates.rows_for(CBC))
        self.assertFalse(templates.is_modified(CBC))
        self.assertEqual(templates.load_overlay()["overrides"], {})

    def test_reset_restores_the_shipped_rows(self):
        rows = templates.rows_for(CBC)
        rows[0]["name"] = "Hb (edited)"
        templates.save_panel(CBC, rows)

        self.assertTrue(templates.reset_panel(CBC))
        self.assertEqual(templates.rows_for(CBC)[0]["name"], "Haemoglobin (Hb)")
        self.assertFalse(templates.is_modified(CBC))

    def test_reset_refuses_for_a_custom_panel(self):
        templates.create_panel("Mine", [templates.make_test("A")])
        self.assertFalse(templates.reset_panel("Mine"))

    def test_removing_a_built_in_hides_it(self):
        templates.delete_panel(CBC)
        self.assertNotIn(CBC, templates.panel_names())

    def test_restore_all_brings_built_ins_back(self):
        templates.delete_panel(CBC)
        rows = templates.rows_for("Lipid Profile")
        rows[0]["unit"] = "changed"
        templates.save_panel("Lipid Profile", rows)

        templates.restore_all_builtins()
        self.assertIn(CBC, templates.panel_names())
        self.assertFalse(templates.is_modified("Lipid Profile"))


class CustomPanelTests(SandboxCase):
    def test_creating_a_panel(self):
        templates.create_panel("Urine Routine", [
            templates.make_heading("PHYSICAL"),
            templates.make_test("Colour", "", "Pale yellow"),
            templates.make_test("pH", "", "5.0 - 7.5"),
        ])
        self.storage.clear_cache()

        self.assertIn("Urine Routine", templates.panel_names())
        rows = templates.rows_for("Urine Routine")
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["kind"], templates.HEADING)
        self.assertEqual(rows[1]["name"], "Colour")

    def test_custom_panels_come_after_the_built_ins(self):
        templates.create_panel("Mine", [templates.make_test("A")])
        names = templates.panel_names()
        self.assertEqual(names[-1], "Mine")
        self.assertEqual(names[:len(PANELS)], list(PANELS),
                         "creating a panel must not reshuffle the built-ins")

    def test_editing_a_custom_panel(self):
        templates.create_panel("Mine", [templates.make_test("A")])
        templates.save_panel("Mine", [templates.make_test("A"), templates.make_test("B")])
        self.assertEqual(len(templates.rows_for("Mine")), 2)

    def test_deleting_a_custom_panel(self):
        templates.create_panel("Mine", [templates.make_test("A")])
        templates.delete_panel("Mine")
        self.assertNotIn("Mine", templates.panel_names())

    def test_renaming_a_custom_panel_keeps_its_rows(self):
        templates.create_panel("Old", [templates.make_test("A", "u", "1 - 2")])
        templates.rename_panel("Old", "New")

        self.assertNotIn("Old", templates.panel_names())
        self.assertIn("New", templates.panel_names())
        self.assertEqual(templates.rows_for("New")[0]["name"], "A")

    def test_renaming_a_built_in_makes_it_yours(self):
        templates.rename_panel(CBC, "CBC (our version)")
        names = templates.panel_names()

        self.assertNotIn(CBC, names)
        self.assertIn("CBC (our version)", names)
        self.assertFalse(templates.is_builtin("CBC (our version)"))
        self.assertEqual(len(templates.rows_for("CBC (our version)")), len(PANELS[CBC]))


class HeadingTests(SandboxCase):
    def test_a_heading_carries_no_measurement_fields(self):
        heading = templates.make_heading("DIFFERENTIAL COUNT")
        self.assertEqual(heading["kind"], templates.HEADING)
        self.assertEqual(heading["unit"], "")
        self.assertEqual(heading["ref_m"], "")

    def test_headings_survive_a_save_and_reload(self):
        templates.create_panel("P", [
            templates.make_heading("SECTION ONE"),
            templates.make_test("Test A", "u", "1 - 2"),
        ])
        self.storage.clear_cache()
        rows = templates.rows_for("P")
        self.assertEqual([r["kind"] for r in rows],
                         [templates.HEADING, templates.TEST])


class RobustnessTests(SandboxCase):
    def test_a_corrupt_file_falls_back_to_the_defaults(self):
        with open(templates._path(), "w", encoding="utf-8") as fh:
            fh.write("not json")
        self.assertEqual(templates.panel_names(), list(PANELS))

    def test_garbage_rows_are_coerced(self):
        templates.save_overlay({
            "overrides": {}, "custom": {"P": ["nonsense", {"name": "Real"}, 42]},
            "deleted": [], "order": [],
        })
        rows = templates.rows_for("P")
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1]["name"], "Real")
        self.assertTrue(all("kind" in r for r in rows))

    def test_wrongly_typed_sections_are_ignored(self):
        templates.save_overlay({"overrides": "nope", "custom": None,
                                "deleted": "no", "order": 5})
        self.assertEqual(templates.panel_names(), list(PANELS))

    def test_clean_row_defaults_to_a_test(self):
        row = templates.clean_row({"name": "X"})
        self.assertEqual(row["kind"], templates.TEST)


if __name__ == "__main__":
    unittest.main()
