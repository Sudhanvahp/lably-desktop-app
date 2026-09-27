"""User-set appearance for every piece of text on the printed report.

A lab that has used a letterhead for twenty years wants its own letterhead, not
this app's taste: the name ranged left or centred, the footer in grey italics,
the pathologist's name underlined. So every text region of the report is a named
*slot*, and a slot can carry an alignment, a font, a size, a
colour and bold / italic / underline - exactly the handful of controls a
spreadsheet offers, and for the same reason.

This covers the **report** only. The bill is deliberately left alone: it is an
accounting document that gets photocopied, faxed and filed, its layout is a
ruled form the lab already issues, and giving one set of controls two documents
to answer for meant the operator could never be sure which one a change would
land on. The bill prints the way it always has.

One rule keeps this from becoming a second, competing stylesheet: a slot stores
only what the operator actually changed. Everything else stays blank and the
report's own CSS decides it, so an untouched profile prints exactly what it
printed before this feature existed, and a restyled footer does not silently
freeze the rest of the page at today's sizes.

Everything read back from disk is validated here rather than trusted: these
values are interpolated into a stylesheet, so a hand-edited lab_profile.json
must not be able to smuggle declarations of its own into it.
"""
from dataclasses import dataclass
from typing import Dict, List, Tuple

ALIGNMENTS = ("left", "center", "right")

# Offered in the picker, and the only families accepted from disk. All of them
# ship with Windows, so a report styled on the counter PC prints the same on the
# one in the back room - a font named here but missing would silently fall back
# to something else and change the layout.
FONTS: Tuple[str, ...] = (
    "Segoe UI", "Calibri", "Arial", "Tahoma", "Verdana", "Trebuchet MS",
    "Times New Roman", "Georgia", "Cambria", "Garamond", "Book Antiqua",
    "Courier New", "Consolas",
)

# What each family falls back to if it is ever missing, so a substitution stays
# in the same class of face rather than turning a serif letterhead sans.
_FALLBACK = {
    "Times New Roman": "Georgia, serif",
    "Georgia": "'Times New Roman', serif",
    "Cambria": "Georgia, serif",
    "Garamond": "Georgia, serif",
    "Book Antiqua": "Georgia, serif",
    "Courier New": "Consolas, monospace",
    "Consolas": "'Courier New', monospace",
}
_SANS_FALLBACK = "Arial, sans-serif"

# Print sizes. Below 5pt nothing is legible on paper; above 48pt a single line
# fills the letterhead and pushes the signatures off the sheet.
MIN_SIZE, MAX_SIZE = 5.0, 48.0

# The tri-state each of bold / italic / underline is stored in: blank leaves the
# document's own rule alone, which is not the same as switching the effect off.
ON, OFF, INHERIT = "1", "0", ""

TOGGLES = ("bold", "italic", "underline")


def _clean_align(value) -> str:
    text = str(value or "").strip().lower()
    if text == "centre":            # the spelling half the world types
        text = "center"
    return text if text in ALIGNMENTS else ""


def _clean_font(value) -> str:
    text = str(value or "").strip()
    for known in FONTS:
        if known.lower() == text.lower():
            return known
    return ""


def _clean_size(value) -> str:
    """A size as a plain string, or blank. Kept as text like every other stored
    field, so a profile stays one flat JSON object of strings."""
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        size = float(text)
    except ValueError:
        return ""
    if not MIN_SIZE <= size <= MAX_SIZE:
        return ""
    # 9.0 stores as "9", 8.5 stays "8.5": no trailing zeroes in the CSS.
    return f"{size:g}"


def _clean_color(value) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if not text.startswith("#"):
        text = "#" + text
    body = text[1:]
    if len(body) == 3:                      # #abc is a real CSS colour
        body = "".join(ch * 2 for ch in body)
    if len(body) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in body):
        return ""
    return "#" + body.lower()


def _clean_toggle(value) -> str:
    if isinstance(value, bool):
        return ON if value else OFF
    text = str(value if value is not None else "").strip().lower()
    if text in ("1", "true", "yes", "on"):
        return ON
    if text in ("0", "false", "no", "off"):
        return OFF
    return INHERIT


@dataclass
class TextStyle:
    """One slot's overrides. Every field blank means "leave it as it prints"."""
    align: str = ""
    font: str = ""
    size: str = ""
    color: str = ""
    bold: str = ""          # "1" on, "0" off, "" leave the document's own rule
    italic: str = ""
    underline: str = ""

    @staticmethod
    def from_dict(d) -> "TextStyle":
        if not isinstance(d, dict):
            return TextStyle()
        return TextStyle(
            align=_clean_align(d.get("align", "")),
            font=_clean_font(d.get("font", "")),
            size=_clean_size(d.get("size", "")),
            color=_clean_color(d.get("color", "")),
            bold=_clean_toggle(d.get("bold")),
            italic=_clean_toggle(d.get("italic")),
            underline=_clean_toggle(d.get("underline")),
        )

    def to_dict(self) -> Dict[str, str]:
        """Only what was set. A slot the operator never touched round-trips as
        an empty dict, and one they reset disappears from the profile."""
        return {k: v for k, v in self.__dict__.items() if v}

    def is_plain(self) -> bool:
        return not self.to_dict()

    def declarations(self) -> str:
        """The slot as CSS declarations, in the order a stylesheet reads best."""
        out: List[str] = []
        if self.align:
            out.append(f"text-align: {self.align}")
        if self.font:
            fallback = _FALLBACK.get(self.font, _SANS_FALLBACK)
            out.append(f"font-family: '{self.font}', {fallback}")
        if self.size:
            out.append(f"font-size: {self.size}pt")
        if self.color:
            out.append(f"color: {self.color}")
        # These three are written out even when switched *off*: a slot the
        # document prints bold can only be un-bolded by saying so.
        if self.bold:
            out.append(f"font-weight: {'bold' if self.bold == ON else 'normal'}")
        if self.italic:
            out.append(f"font-style: {'italic' if self.italic == ON else 'normal'}")
        if self.underline:
            out.append("text-decoration: "
                       + ("underline" if self.underline == ON else "none"))
        return "; ".join(out) + (";" if out else "")


@dataclass(frozen=True)
class Slot:
    """One stylable region of the report.

    `selector` is what the region is set by in the report's stylesheet.

    `align`, `bold`, `italic` and `underline` are what the report already does.
    They are here so the editor can open showing the truth rather than a guess,
    and so a control put back where it started stores nothing at all - which is
    the difference between "print it plain, as always" and "freeze this slot as
    plain forever".
    """
    key: str
    label: str
    hint: str
    selector: str = ""
    align: str = "left"
    bold: bool = False
    italic: bool = False
    underline: bool = False

    def default_toggle(self, name: str) -> bool:
        return bool(getattr(self, name, False))


# Ordered the way the eye goes down a printed sheet, because that is the order
# an operator will look for the line they want to change.
SLOTS: Tuple[Slot, ...] = (
    Slot("lab_name", "Laboratory name",
         "the big line at the very top of every report",
         ".labname", "left", bold=True),
    Slot("lab_subtitle", "Sub-heading",
         "the line under the laboratory name",
         ".labsub", "left", bold=True),
    Slot("doc_title", "Document title",
         "LABORATORY TEST REPORT",
         ".doctitle", "left"),
    Slot("doc_meta", "Report number",
         "the number printed opposite the title",
         ".docmeta", "right"),
    Slot("patient_label", "Patient labels",
         "Patient Name, Age / Sex, Ref. By - the words, not the values",
         ".lbl, .cln", "left"),
    Slot("patient_value", "Patient details",
         "the patient's own name, age, sample type and dates",
         ".val", "left"),
    Slot("panel_title", "Panel titles",
         "the name of each panel, e.g. COMPLETE BLOOD COUNT",
         ".panel", "left"),
    Slot("section_head", "Sub-headings inside a panel",
         "the grouping lines within a panel, e.g. Differential Count",
         "td.subhead", "left"),
    Slot("table_head", "Column headings",
         "Test, Result, Unit, Reference Range",
         "table.results th", "left"),
    Slot("table_body", "Results",
         "every test name, result, unit and reference range",
         ".tname, .res, .unit, .ref", "left"),
    Slot("legend", "H / L legend",
         "the line explaining the out-of-range marks",
         ".legend", "left"),
    Slot("remarks", "Remarks",
         "the remarks paragraph under the results",
         ".remarks, .remarks-h", "left"),
    Slot("money", "Amounts and totals",
         "the figures and their labels in the bill summary on the report",
         ".money, .billlbl", "right"),
    Slot("sign_name", "Signatory names",
         "the technician's and the pathologist's names",
         ".signname", "center", bold=True),
    Slot("sign_role", "Signatory roles",
         "Lab Technician, Consultant Pathologist and the degrees",
         ".signrole", "center", bold=True),
    Slot("end_marker", "End of Report",
         "the closing line between two rules",
         ".end", "center"),
    Slot("footer", "Footer",
         "address, phone, email, timings and the footer note",
         ".footer", "center"),
)


BY_KEY: Dict[str, Slot] = {slot.key: slot for slot in SLOTS}


# --------------------------------------------------------------------------
# reading and writing a whole profile's worth of styles
# --------------------------------------------------------------------------
def load(raw) -> Dict[str, Dict[str, str]]:
    """Validate whatever was on disk into styles this module will print.

    Unknown slot names are dropped rather than kept: a slot that no longer
    exists cannot be edited or reset from the screen, so keeping it would leave
    styling in the profile that nobody could ever get rid of."""
    out: Dict[str, Dict[str, str]] = {}
    if not isinstance(raw, dict):
        return out
    for key, value in raw.items():
        if key not in BY_KEY:
            continue
        cleaned = TextStyle.from_dict(value).to_dict()
        if cleaned:
            out[key] = cleaned
    return out


def style_of(styles, key: str) -> TextStyle:
    """One slot's style out of a styles dict, set or not."""
    if isinstance(styles, dict):
        return TextStyle.from_dict(styles.get(key))
    return TextStyle()


def _styles_of(lab) -> Dict[str, Dict[str, str]]:
    return getattr(lab, "text_styles", None) or {}


def style_for(lab, key: str) -> TextStyle:
    return style_of(_styles_of(lab), key)


def align_for(lab, key: str) -> str:
    """The alignment attribute a block should carry.

    Qt's rich text honours a cell's or a div's `align` attribute over the
    stylesheet, so the alignment has to be written into the markup as well; the
    slot's own default is what the document did before this existed."""
    slot = BY_KEY.get(key)
    default = slot.align if slot else "left"
    return style_for(lab, key).align or default


def effective(lab, key: str) -> TextStyle:
    """A slot's style with the document's own defaults filled in.

    What the editor opens showing: the alignment and the three effects are never
    blank here, because the document always has an answer for them.
    """
    slot = BY_KEY.get(key)
    style = style_for(lab, key)
    if slot is None:
        return style
    return TextStyle(
        align=style.align or slot.align,
        font=style.font,
        size=style.size,
        color=style.color,
        bold=style.bold or (ON if slot.bold else OFF),
        italic=style.italic or (ON if slot.italic else OFF),
        underline=style.underline or (ON if slot.underline else OFF),
    )


def trimmed(key: str, style: TextStyle) -> Dict[str, str]:
    """What is worth storing for a slot: only what differs from the document.

    A control put back where it started drops out entirely, so a slot the
    operator fiddled with and undid is indistinguishable from one they never
    touched - and the document stays free to change its own defaults later.
    """
    slot = BY_KEY.get(key)
    if slot is None:
        return {}
    kept = TextStyle(
        align="" if style.align == slot.align else _clean_align(style.align),
        font=_clean_font(style.font),
        size=_clean_size(style.size),
        color=_clean_color(style.color),
    )
    for name in TOGGLES:
        value = _clean_toggle(getattr(style, name))
        wanted = ON if slot.default_toggle(name) else OFF
        setattr(kept, name, "" if value in ("", wanted) else value)
    return kept.to_dict()


def overrides(lab) -> str:
    """The lab's styling as a CSS block, to append after the report's own.

    Appended rather than merged: each rule then sits later in the sheet than the
    one it overrides, which is all it needs to win, and the report's own
    stylesheet stays readable as the thing it is - the default."""
    styles = _styles_of(lab)
    if not styles:
        return ""
    rules: List[str] = []
    for slot in SLOTS:
        declarations = style_of(styles, slot.key).declarations()
        if declarations:
            rules.append(f"{slot.selector} {{ {declarations} }}")
    if not rules:
        return ""
    return "\n/* the laboratory's own text styling */\n" + "\n".join(rules) + "\n"


def stylesheet(base: str, lab) -> str:
    """The report's stylesheet with the lab's own text styling applied."""
    return base + overrides(lab)


def summary(lab, key: str) -> str:
    """A one-line description of a slot's styling, for the editor's list."""
    style = style_for(lab, key)
    if style.is_plain():
        return "default"
    parts: List[str] = []
    if style.align:
        parts.append(style.align)
    if style.font:
        parts.append(style.font)
    if style.size:
        parts.append(f"{style.size}pt")
    marks = "".join(mark for mark, field in (("B", "bold"), ("I", "italic"),
                                             ("U", "underline"))
                    if getattr(style, field) == ON)
    if marks:
        parts.append(marks)
    if any(getattr(style, field) == OFF for field in TOGGLES):
        parts.append("plain")
    if style.color:
        parts.append(style.color)
    return ", ".join(parts)


def styled_slots(lab) -> List[str]:
    """Which slots carry styling, in printing order."""
    styles = _styles_of(lab)
    return [slot.key for slot in SLOTS if styles.get(slot.key)]
