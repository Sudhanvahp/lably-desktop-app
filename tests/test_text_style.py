"""The lab's own text styling: what is stored, what is printed, what is ignored.

The rule under most of these: a profile nobody has restyled must print exactly
what it printed before the feature existed, and a restyled region must change
that one region and nothing else.
"""
import unittest

from app import bill_html, report_html
from app import text_style as TS
from app.models import LabProfile, Report, TestRow


def profile(**styles) -> LabProfile:
    return LabProfile(lab_name="Sunrise Diagnostics", lab_subtitle="Family Clinic",
                      address1="MG Road", phone="+918012345678",
                      pathologist="Dr. A. Rao", footer_note="Computer generated",
                      text_styles=styles)


def report() -> Report:
    return Report(report_no="BR-1", patient_name="Jane Doe", age="34", sex="F",
                  remarks="See attached",
                  rows=[TestRow("CBC", "Haemoglobin (Hb)", "9.2", "g/dL",
                                "12.0 - 15.0")])


class CleaningTests(unittest.TestCase):
    """Everything read back off disk is validated: these values end up inside a
    stylesheet, and a hand-edited profile must not be able to write CSS."""

    def test_an_unknown_alignment_is_dropped(self):
        self.assertEqual(TS.TextStyle.from_dict({"align": "justify"}).align, "")

    def test_british_spelling_is_accepted(self):
        self.assertEqual(TS.TextStyle.from_dict({"align": "centre"}).align, "center")

    def test_a_font_outside_the_list_is_dropped(self):
        self.assertEqual(TS.TextStyle.from_dict({"font": "Comic Sans MS"}).font, "")

    def test_a_known_font_is_kept_however_it_is_cased(self):
        self.assertEqual(TS.TextStyle.from_dict({"font": "georgia"}).font, "Georgia")

    def test_a_size_outside_the_printable_range_is_dropped(self):
        for size in ("0", "4", "72", "-10", "nonsense"):
            self.assertEqual(TS.TextStyle.from_dict({"size": size}).size, "",
                             f"{size} should not be stored")

    def test_a_size_keeps_its_half_point_but_loses_trailing_zeroes(self):
        self.assertEqual(TS.TextStyle.from_dict({"size": "8.50"}).size, "8.5")
        self.assertEqual(TS.TextStyle.from_dict({"size": "9.0"}).size, "9")

    def test_a_colour_is_normalised(self):
        self.assertEqual(TS.TextStyle.from_dict({"color": "1A4FA3"}).color, "#1a4fa3")
        self.assertEqual(TS.TextStyle.from_dict({"color": "#ABC"}).color, "#aabbcc")

    def test_a_colour_that_is_not_one_is_dropped(self):
        for value in ("red; }", "#12345", "rgb(1,2,3)", "javascript:x"):
            self.assertEqual(TS.TextStyle.from_dict({"color": value}).color, "",
                             f"{value} should not be stored")

    def test_no_stored_value_can_close_a_css_rule(self):
        """The whole point of the cleaning: nothing reaches the sheet verbatim."""
        nasty = {"font": "X; } body { display:none", "color": "#000; } *{",
                 "size": "8pt; color:red", "align": "left; }"}
        self.assertEqual(TS.TextStyle.from_dict(nasty).declarations(), "")

    def test_an_unknown_region_is_dropped_entirely(self):
        self.assertEqual(TS.load({"made_up": {"align": "left"}}), {})

    def test_a_region_with_nothing_set_is_not_stored(self):
        self.assertEqual(TS.load({"footer": {}}), {})

    def test_junk_in_place_of_the_whole_table_is_survived(self):
        for junk in (None, "", [], "footer"):
            self.assertEqual(TS.load(junk), {})


class StoringTests(unittest.TestCase):
    """Only departures from the printed default are kept, so the documents stay
    free to change their own minds later."""

    def test_the_documents_own_alignment_is_not_stored(self):
        self.assertEqual(TS.trimmed("footer", TS.TextStyle(align="center")), {})

    def test_a_chosen_alignment_is_stored(self):
        self.assertEqual(TS.trimmed("footer", TS.TextStyle(align="left")),
                         {"align": "left"})

    def test_leaving_a_bold_region_bold_stores_nothing(self):
        self.assertEqual(TS.trimmed("lab_name", TS.TextStyle(bold=TS.ON)), {})

    def test_un_bolding_a_bold_region_is_stored(self):
        self.assertEqual(TS.trimmed("lab_name", TS.TextStyle(bold=TS.OFF)),
                         {"bold": "0"})

    def test_bolding_a_plain_region_is_stored(self):
        self.assertEqual(TS.trimmed("footer", TS.TextStyle(bold=TS.ON)),
                         {"bold": "1"})

    def test_leaving_a_plain_region_plain_stores_nothing(self):
        self.assertEqual(TS.trimmed("footer", TS.TextStyle(bold=TS.OFF)), {})

    def test_the_editor_opens_showing_what_the_document_does(self):
        style = TS.effective(LabProfile(), "lab_name")
        self.assertEqual(style.bold, TS.ON)      # the letterhead is bold
        self.assertEqual(style.align, "left")
        style = TS.effective(LabProfile(), "footer")
        self.assertEqual(style.bold, TS.OFF)
        self.assertEqual(style.align, "center")

    def test_a_stored_choice_beats_the_document(self):
        lab = profile(footer={"align": "right", "bold": "1"})
        style = TS.effective(lab, "footer")
        self.assertEqual((style.align, style.bold), ("right", TS.ON))


class DeclarationTests(unittest.TestCase):
    def test_an_untouched_region_declares_nothing(self):
        self.assertEqual(TS.TextStyle().declarations(), "")

    def test_switching_an_effect_off_is_declared_rather_than_omitted(self):
        """A region the document prints bold can only be un-bolded by saying so."""
        self.assertIn("font-weight: normal",
                      TS.TextStyle(bold=TS.OFF).declarations())

    def test_a_font_carries_a_fallback_of_the_same_kind(self):
        self.assertIn("serif", TS.TextStyle(font="Georgia").declarations())
        self.assertIn("sans-serif", TS.TextStyle(font="Calibri").declarations())
        self.assertIn("monospace", TS.TextStyle(font="Consolas").declarations())


class RenderingTests(unittest.TestCase):
    def test_an_unstyled_profile_prints_what_it_always_printed(self):
        plain = report_html.build(report(), profile())
        self.assertNotIn("laboratory's own text styling", plain)
        self.assertEqual(report_html.stylesheet(profile()), report_html.CSS)

    def test_the_override_lands_after_the_documents_own_rule(self):
        """Later in the sheet is all it takes to win, so the order is the point."""
        sheet = report_html.stylesheet(profile(footer={"size": "10"}))
        self.assertLess(sheet.index(".footer { font-size: 7.5pt"),
                        sheet.index(".footer { font-size: 10pt;"))

    def test_the_bill_is_left_alone(self):
        """One set of controls, one document. The bill is a ruled accounting
        form and prints the way it always has, whatever the report is told."""
        lab = profile(footer={"italic": "1"}, lab_name={"font": "Georgia"})
        bill = bill_html.build(report(), lab)
        self.assertNotIn("font-style: italic", bill)
        self.assertNotIn("Georgia", bill)
        self.assertEqual(bill, bill_html.build(report(), profile()))

    def test_alignment_reaches_the_markup_not_only_the_stylesheet(self):
        """Qt honours a cell's align attribute over CSS, so a choice that stops
        at the stylesheet is a choice that never prints."""
        head = report_html.letterhead(profile(lab_name={"align": "center"}))
        self.assertIn('<div class="labname" align="center">', head)
        # The sub-heading is a region of its own and stays where it was: one
        # control moves one line, which is the whole contract of the screen.
        self.assertIn('<div class="labsub" align="left">', head)

    def test_the_footer_can_be_ranged_left(self):
        foot = report_html.footer(profile(footer={"align": "left"}))
        self.assertIn('<div class="footer" align="left"', foot)

    def test_every_region_the_editor_offers_can_be_printed(self):
        """A region with a control but no selector would be a setting that
        silently does nothing."""
        for slot in TS.SLOTS:
            self.assertTrue(slot.selector, f"{slot.key} is styled nowhere")

    def test_every_selector_matches_something_in_the_report(self):
        for slot in TS.SLOTS:
            for one in (part.strip() for part in slot.selector.split(",")):
                self.assertIn(one, report_html.CSS,
                              f"{slot.key}: {one} is in no report rule")


class ProfileTests(unittest.TestCase):
    def test_styles_round_trip_through_the_profile_dict(self):
        lab = profile(lab_name={"align": "center", "size": "20"})
        back = LabProfile.from_dict(lab.to_dict())
        self.assertEqual(back.text_styles, lab.text_styles)

    def test_a_profile_saved_before_this_feature_loads_unstyled(self):
        back = LabProfile.from_dict({"lab_name": "Sunrise"})
        self.assertEqual(back.text_styles, {})

    def test_a_ruined_styles_table_does_not_stop_the_profile_loading(self):
        back = LabProfile.from_dict({"lab_name": "Sunrise", "text_styles": "oops"})
        self.assertEqual(back.lab_name, "Sunrise")
        self.assertEqual(back.text_styles, {})

    def test_the_summary_says_what_a_region_carries(self):
        lab = profile(footer={"align": "right", "size": "9", "italic": "1"})
        self.assertEqual(TS.summary(lab, "footer"), "right, 9pt, I")
        self.assertEqual(TS.summary(lab, "lab_name"), "default")

    def test_the_styled_regions_are_listed_in_printing_order(self):
        lab = profile(footer={"bold": "1"}, lab_name={"align": "center"})
        self.assertEqual(TS.styled_slots(lab), ["lab_name", "footer"])


if __name__ == "__main__":
    unittest.main()


def _point_size(html: str, text: str) -> float:
    from PySide6.QtGui import QTextDocument
    from PySide6.QtWidgets import QApplication
    # A full QApplication, not a QGuiApplication: the UI tests run later in
    # the same process reuse whatever instance exists, and widgets need this one.
    QApplication.instance() or QApplication([])
    doc = QTextDocument()
    doc.setHtml(html)
    return doc.find(text).charFormat().fontPointSize()


class SpecificityTests(unittest.TestCase):
    """Qt ranks CSS by specificity, so an override that is merely later in the
    sheet loses to a more specific base rule. Checked in a real QTextDocument."""

    def test_a_size_set_for_the_results_reaches_the_results_table(self):
        html = report_html.build(report(), profile(table_body={"size": "14"}))
        self.assertEqual(_point_size(html, "Haemoglobin"), 14.0)

    def test_a_size_set_for_panel_titles_reaches_them(self):
        html = report_html.build(report(), profile(panel_title={"size": "15"}))
        self.assertEqual(_point_size(html, "CBC"), 15.0)


def bill_profile(**styles) -> LabProfile:
    lab = profile()
    lab.bill_text_styles = styles
    return lab


class BillSlotTests(unittest.TestCase):
    def test_doc_picks_the_bill_list(self):
        self.assertIs(TS.slots_for(TS.BILL), TS.BILL_SLOTS)
        self.assertIs(TS.slots_for(), TS.SLOTS)
        self.assertIn("services", TS.by_key(TS.BILL))
        self.assertNotIn("services", TS.by_key())

    def test_bill_keys_are_unique(self):
        keys = [slot.key for slot in TS.BILL_SLOTS]
        self.assertEqual(len(keys), len(set(keys)))

    def test_load_keeps_bill_slots_only_for_the_bill(self):
        raw = {"services": {"bold": "1"}, "doc_title": {"bold": "1"}}
        self.assertEqual(TS.load(raw, TS.BILL), {"services": {"bold": "1"}})
        self.assertEqual(TS.load(raw), {"doc_title": {"bold": "1"}})

    def test_bill_styles_do_not_reach_the_report_and_vice_versa(self):
        lab = bill_profile(footer={"italic": "1"})
        self.assertIn(".labline", TS.overrides(lab, TS.BILL))
        self.assertEqual(TS.overrides(lab), "")
        lab = profile(footer={"italic": "1"})
        self.assertEqual(TS.overrides(lab, TS.BILL), "")

    def test_bill_defaults_come_from_the_bill_slot(self):
        lab = bill_profile()
        self.assertEqual(TS.align_for(lab, "lab_name", TS.BILL), "center")
        self.assertEqual(TS.align_for(lab, "lab_name"), "left")
        self.assertEqual(TS.effective(lab, "heading", TS.BILL).bold, TS.ON)

    def test_trimmed_against_the_bill_defaults(self):
        same = TS.TextStyle(align="center", bold="1")
        self.assertEqual(TS.trimmed("lab_name", same, TS.BILL), {})
        self.assertEqual(TS.trimmed("lab_name", same),
                         {"align": "center"})

    def test_summary_and_styled_slots_for_the_bill(self):
        lab = bill_profile(money={"size": "9"}, lab_name={"align": "left"})
        self.assertEqual(TS.summary(lab, "money", TS.BILL), "9pt")
        self.assertEqual(TS.styled_slots(lab, TS.BILL), ["lab_name", "money"])

    def test_every_bill_selector_names_a_class_the_bill_prints(self):
        from app.models import BillItem
        r = report()
        r.billing.items = [BillItem("CBC", "300")]
        # A class the stylesheet styles, or one the markup carries.
        html = bill_html.build(r, profile())
        for slot in TS.BILL_SLOTS:
            for one in (part.strip() for part in slot.selector.split(",")):
                cls = one.lstrip(".")
                self.assertRegex(html, rf'(class="[^"]*\b{cls}\b|\.{cls} )',
                                 f"{slot.key}: {one}")

    def test_injection_through_bill_styles_is_cleaned(self):
        lab = bill_profile(footer={"color": "red;} body{display:none",
                                   "font": "x'; }"})
        self.assertEqual(TS.overrides(lab, TS.BILL), "")


class BillAlignmentReachesMarkupTests(unittest.TestCase):
    """Qt ignores CSS text-align in table cells; the attribute must be set."""

    def test_unstyled_bill_has_no_extra_align_and_centred_headings(self):
        html = bill_html.build(report(), bill_profile())
        self.assertIn('<td class="key">Patient Name</td>', html)
        self.assertIn('<td class="key billedby">Billed By</td>', html)
        self.assertIn('align="center" class="th">Sl. No.', html)
        self.assertIn('align="center" class="th">Net Amount', html)

    def test_label_value_and_billed_by_alignment_reach_the_cells(self):
        html = bill_html.build(report(), bill_profile(
            label={"align": "right"}, value={"align": "center"},
            billed_by={"align": "right"}))
        self.assertIn('<td class="key" align="right">Patient Name</td>', html)
        self.assertIn('<td width="100%" align="center" class="val', html)
        self.assertIn('<td class="key billedby" align="right">Billed By</td>', html)

    def test_heading_alignment_reaches_every_heading(self):
        html = bill_html.build(report(), bill_profile(table_head={"align": "right"}))
        for text in ("Sl. No.", "Services", "Amount", "Net Amount"):
            self.assertIn(f'align="right" class="th">{text}<', html)
