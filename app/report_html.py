"""Renders a Report into self-contained printable HTML.

Images are inlined as data: URIs so QTextDocument resolves them with no base URL,
which keeps preview, printer output and exported PDF byte-identical.

The markup deliberately stays inside Qt's rich-text subset: layout is done with
nested tables and cell attributes (width/align) rather than flexbox or
positioning. Two Qt quirks shape the markup throughout - see _rule() and
_end_marker().

The look is deliberately plain. It is a medical record: white paper, black
type, thin rules, one weight of ink. The lab's name is the only thing in
colour (and, with the patient's name, the only thing in bold). Everything is sized so a
single panel fits one A4 sheet with room for the signatures.
"""
import base64
import mimetypes
import os
from html import escape
from typing import List, Tuple

from .billing import (CURRENCY, format_amount, format_bill_date,
                      has_content, parse_amount, summary)
from .models import LabProfile, Report, TestRow
from .panels import flag_for
from . import text_style

INK = "#000000"
INK_SOFT = "#333333"
MUTED = "#555555"
RULE = "#000000"
RULE_SOFT = "#999999"
BRAND = "#1a4fa3"          # the one colour on the page: the lab's own name
FLAG = "#b00020"           # H / L marks only


def _data_uri(path: str) -> str:
    if not path or not os.path.isfile(path):
        return ""
    mime = mimetypes.guess_type(path)[0] or "image/png"
    try:
        with open(path, "rb") as fh:
            return f"data:{mime};base64," + base64.b64encode(fh.read()).decode("ascii")
    except OSError:
        return ""


def _bar(px: int) -> str:
    """Inline style for a cell that exists only to be a rule.

    Qt lays a table cell out around its text, ignoring the height attribute, so
    the rule's thickness is really the font size of the &nbsp; inside it."""
    return f"font-size:{px}px; line-height:{px}px;"


def _rule(color: str = RULE, height: int = 1) -> str:
    """A hairline. Qt ignores most border shorthands on <hr>, so a filled 1px-tall
    table cell is the one separator that renders identically in every output path."""
    return (
        '<table width="100%" cellspacing="0" cellpadding="0">'
        f'<tr><td bgcolor="{color}" height="{height}" style="{_bar(height)}">'
        "&nbsp;</td></tr></table>"
    )


def _spacer(pt: float = 4) -> str:
    return f'<div style="font-size:{pt}pt;">&nbsp;</div>'


# Qt's rich text has no `position: fixed`, so the footer cannot be pinned in
# CSS. The document leaves this marker where the slack belongs and printing
# measures the laid-out page and swaps in a spacer of exactly that height.
FOOTER_PAD = "<!--footer-pad-->"


def _keyed(pairs) -> str:
    """One line of `Label: value` pairs set apart by dots; blanks are skipped."""
    parts = [f'{label}: {escape(value)}' for label, value in pairs if value]
    return "&nbsp;&nbsp;&middot;&nbsp;&nbsp;".join(parts)


# --------------------------------------------------------------------------
# letterhead and footer
# --------------------------------------------------------------------------
def letterhead(lab: LabProfile) -> str:
    """The identity block at the top: name over sub-heading, both bold and in
    capitals, ranged left beside the logo. Contact details live in the footer.

    The capitals are applied here rather than in the stylesheet because Qt's
    rich text has no `text-transform`."""
    name_align = text_style.align_for(lab, "lab_name")
    sub_align = text_style.align_for(lab, "lab_subtitle")
    logo = _data_uri(lab.logo_path)
    logo_cell = (
        f'<td width="80" valign="middle" style="padding-right:10px;">'
        f'<img src="{logo}" width="70"></td>'
        if logo
        else ""
    )
    lines: List[str] = [
        f'<div class="labname" align="{name_align}">'
        f'{escape((lab.lab_name or "Laboratory Name").upper())}</div>'
    ]
    if lab.lab_subtitle:
        lines.append(
            f'<div class="labsub" align="{sub_align}">'
            f'{escape(lab.lab_subtitle.upper())}</div>'
        )
    # Left-ranged, so the text takes whatever room the logo leaves over and no
    # balancing column is needed on the right.
    return (
        '<table width="100%" cellpadding="0" cellspacing="0"><tr>'
        + logo_cell
        + f'<td valign="middle" align="{name_align}">'
        + "".join(lines) + "</td>"
        + "</tr></table>"
    )


def footer(lab: LabProfile) -> str:
    """Address, contact details, hours and the footer note, in black under a
    black rule at the foot of the page - where a patient looks for how to reach
    the lab."""
    lines: List[str] = []
    address = ", ".join(part for part in (lab.address1, lab.address2) if part)
    if address:
        lines.append(escape(address))
    contact = _keyed((("Tel", lab.phone), ("Mob", lab.mobile), ("Email", lab.email),
                      ("Reg. No", lab.reg_no)))
    if contact:
        lines.append(contact)
    hours = _keyed((("Timings", lab.timings), ("Holidays", lab.holidays)))
    if hours:
        lines.append(hours)
    if lab.footer_note:
        lines.append(escape(lab.footer_note))
    if not lines:
        return ""
    return (
        _rule(RULE, 1)
        + f'<div class="footer" align="{text_style.align_for(lab, "footer")}"'
        + ' style="padding-top:3px;">'
        + "<br>".join(lines)
        + "</div>"
    )


# --------------------------------------------------------------------------
# the report
# --------------------------------------------------------------------------
def _title_bar(r: Report, lab: LabProfile) -> str:
    """The document's name, ruled above and below, report number opposite."""
    meta = f"Report No: {escape(r.report_no)}" if r.report_no else "&nbsp;"
    return (
        _rule(RULE, 1)
        + '<table width="100%" cellspacing="0" cellpadding="2"><tr>'
        f'<td class="doctitle" align="{text_style.align_for(lab, "doc_title")}">'
        "LABORATORY TEST REPORT</td>"
        f'<td align="{text_style.align_for(lab, "doc_meta")}" class="docmeta">'
        f"{meta}</td>"
        "</tr></table>"
        + _rule(RULE, 1)
    )


def _patient_block(r: Report, lab: LabProfile) -> str:
    age = f"{r.age} {dict(Y='Years', M='Months', D='Days').get(r.age_unit, '')}".strip()
    left = [
        ("Patient Name", r.display_name()),
        ("Age / Sex", " / ".join(x for x in (age, r.sex) if x)),
        ("Patient ID", r.patient_id),
        ("Ref. By", r.referred_by),
    ]
    right = [
        ("Sample Type", r.sample_type),
        ("Collected On", r.collected_on),
        ("Reported On", r.reported_on),
    ]

    label_align = text_style.align_for(lab, "patient_label")
    value_align = text_style.align_for(lab, "patient_value")

    def col(items):
        out = []
        for k, v in items:
            if not v:
                continue
            # The patient's name is the one thing on the page set in bold.
            shown = f"<b>{escape(v)}</b>" if k == "Patient Name" else escape(v)
            out.append(
                f'<tr><td class="lbl" align="{label_align}" valign="top">'
                f'{escape(k)}</td>'
                f'<td class="cln" valign="top">:</td>'
                f'<td class="val" align="{value_align}" valign="top">'
                f'{shown}</td></tr>')
        return "".join(out)

    return (
        '<table width="100%" class="patient" cellspacing="0" cellpadding="0"><tr>'
        f'<td width="52%" valign="top">'
        f'<table cellspacing="0" cellpadding="0" width="100%">{col(left)}</table></td>'
        f'<td width="48%" valign="top">'
        f'<table cellspacing="0" cellpadding="0" width="100%">{col(right)}</table></td>'
        "</tr></table>"
        + _rule(RULE_SOFT, 1)
    )


def _tally(rows: List[TestRow]) -> Tuple[int, int]:
    """(tests measured, tests outside their reference range)."""
    tests = [r for r in rows if not r.is_heading() and r.result.strip()]
    flagged = [r for r in tests if flag_for(r.result, r.ref)]
    return len(tests), len(flagged)


# The opening tag of a panel's results table, kept in one place because
# printing rewrites it to move a panel onto a page of its own. The bill summary
# is ruled the same way and so opens identically; `data-panel` is what tells
# the two apart when printing counts them. Qt ignores the attribute.
PANEL_TABLE_OPEN = ('<table width="100%" class="results" cellspacing="0" '
                    'cellpadding="1" data-panel="yes"')

# Qt honours page-break-before on a table.
PAGE_BREAK = ' style="page-break-before:always"'


def panel_count(html: str) -> int:
    """How many panel tables the report has."""
    return html.count(PANEL_TABLE_OPEN)


def with_page_breaks(html: str, indexes) -> str:
    """The same report with the panels at `indexes` (0-based, in the order
    they print) started on a fresh page.

    Printing decides which those are - it is the only layer that knows where
    the page boundaries fall - but the rewriting belongs here with the rest of
    the HTML."""
    if not indexes:
        return html
    parts = html.split(PANEL_TABLE_OPEN)
    out = [parts[0]]
    for i, part in enumerate(parts[1:]):
        out.append(PANEL_TABLE_OPEN + (PAGE_BREAK if i in indexes else "") + part)
    return "".join(out)


def _rows_table(rows: List[TestRow], lab: LabProfile, title: str = "") -> str:
    """One panel: its title and column headings over its rows, as a single
    table. Each panel numbers its own tests from 1, the way a lab reads a
    panel - the number is the test's place within its panel, not a running
    count of the whole report.

    The title and the column headings sit in a `<thead>` rather than in a block
    of their own above the table. Qt repeats a table's header rows on every
    page the table runs onto, so a panel that does not fit one sheet carries
    its name and its column headings over to the next - and the title can never
    be left stranded at the foot of a page with its rows overleaf, because it
    is part of the table that breaks."""
    head_align = text_style.align_for(lab, "table_head")
    body_align = text_style.align_for(lab, "table_body")
    out = [
        PANEL_TABLE_OPEN + ">",
        "<thead>",
        (f'<tr><td colspan="4" class="panel" '
         f'align="{text_style.align_for(lab, "panel_title")}">'
         f"{escape(title)}</td></tr>"
         if title else ""),
        f'<tr><th align="{head_align}" width="40%">Test</th>'
        f'<th align="{head_align}" width="18%">Result</th>'
        f'<th align="{head_align}" width="14%">Unit</th>'
        f'<th align="{head_align}" width="28%">Reference Range</th></tr>',
        "</thead>",
    ]
    for row in rows:
        if row.is_heading():
            out.append(f'<tr><td colspan="4" class="subhead" '
                       f'align="{text_style.align_for(lab, "section_head")}">'
                       f"{escape(row.name)}</td></tr>")
            continue
        flag = flag_for(row.result, row.ref)
        value = escape(row.result)
        if flag:
            value = f'{value}&nbsp;&nbsp;<span class="flag">{flag}</span>'
        out.append(
            "<tr>"
            f'<td class="tname" align="{body_align}">{escape(row.name)}</td>'
            f'<td class="res" align="{body_align}">{value}</td>'
            f'<td class="unit" align="{body_align}">{escape(row.unit)}</td>'
            f'<td class="ref" align="{body_align}">{escape(row.ref)}</td></tr>'
        )
    out.append("</table>")
    return "".join(out)


def _legend(rows: List[TestRow], lab: LabProfile) -> str:
    """Explains the H/L marks, but only on reports that actually carry one."""
    if not _tally(rows)[1]:
        return ""
    return (
        f'<div class="legend" align="{text_style.align_for(lab, "legend")}">'
        '<span class="flag">H</span> above reference range'
        '&nbsp;&nbsp;&middot;&nbsp;&nbsp;<span class="flag">L</span> below '
        "reference range</div>"
    )


def _remarks(text: str, lab: LabProfile) -> str:
    return (
        '<table width="100%" cellspacing="0" cellpadding="2"><tr>'
        f'<td class="remarks" align="{text_style.align_for(lab, "remarks")}">'
        f'<span class="remarks-h">Remarks:</span> '
        f'{escape(text)}</td></tr></table>'
    )


# --------------------------------------------------------------------------
# the bill summary inside the report
# --------------------------------------------------------------------------
# The order the bill reads in: what it came to, what was paid, what is left.
BILL_TOTALS = (
    ("Total Billed", "total_billed"),
    ("Net Payable", "net_payable"),
    ("Net Deposit", "net_deposit"),
)


def _bill_header(r: Report, lab: LabProfile) -> str:
    bill = r.billing
    meta = []
    if bill.bill_no:
        meta.append(f"Bill No: {escape(bill.bill_no)}")
    if bill.bill_date:
        meta.append(f"Date: {escape(format_bill_date(bill.bill_date))}")
    return (
        '<table width="100%" cellspacing="0" cellpadding="2"><tr>'
        f'<td class="panel" align="{text_style.align_for(lab, "panel_title")}">'
        "BILL SUMMARY</td>"
        f'<td align="{text_style.align_for(lab, "doc_meta")}" class="docmeta">'
        f'{"&nbsp;&nbsp;&middot;&nbsp;&nbsp;".join(meta) or "&nbsp;"}</td>'
        "</tr></table>"
        + _rule(RULE, 1)
    )


def _bill_items(r: Report, lab: LabProfile) -> str:
    """One numbered row per billed service. An unpriced line prints a dash
    rather than 0.00, so 'not charged for' and 'charged nothing' stay
    distinguishable."""
    head_align = text_style.align_for(lab, "table_head")
    body_align = text_style.align_for(lab, "table_body")
    money_align = text_style.align_for(lab, "money")
    out = [
        '<table width="100%" class="results" cellspacing="0" cellpadding="1">',
        f'<tr><th align="{head_align}" width="8%" '
        'style="white-space:nowrap;">Sl. No.</th>'
        f'<th align="{head_align}" width="64%">Service / Test</th>'
        f'<th align="{money_align}" width="28%">Amount ({CURRENCY})</th></tr>',
    ]
    for i, item in enumerate(r.billing.items, 1):
        amount = parse_amount(item.amount)
        text = format_amount(amount) if amount is not None else "&ndash;"
        out.append(
            "<tr>"
            f'<td class="slno">{i}</td>'
            f'<td class="tname" align="{body_align}">{escape(item.service)}</td>'
            f'<td align="{money_align}" class="money">{text}</td></tr>'
        )
    out.append("</table>")
    return "".join(out)


def _bill_totals(r: Report, lab: LabProfile) -> str:
    figures = summary(r.billing)
    money_align = text_style.align_for(lab, "money")
    rows = [
        f'<tr><td class="billlbl" align="{money_align}">{label}</td>'
        f'<td class="money" align="{money_align}" width="34%">'
        f"{format_amount(figures[key])}</td></tr>"
        for label, key in BILL_TOTALS
    ]
    rows.append(
        f'<tr><td align="{money_align}" class="billlbl">Balance</td>'
        f'<td align="{money_align}" class="money">'
        f'{format_amount(figures["balance"])}</td></tr>'
    )
    return (
        '<table width="100%" cellspacing="0" cellpadding="0"><tr>'
        '<td width="52%" valign="top">&nbsp;</td>'
        f'<td width="48%" valign="top">'
        f'<table width="100%" cellspacing="0" cellpadding="1">'
        + "".join(rows) + "</table></td></tr></table>"
    )


def _bill_summary(r: Report, lab: LabProfile) -> str:
    """The whole billing block, or nothing at all - rendered only when the bill
    carries figures, and placed after the results and remarks."""
    if not has_content(r.billing):
        return ""
    return (_bill_header(r, lab) + _bill_items(r, lab) + _rule(RULE_SOFT, 1)
            + _bill_totals(r, lab))


# --------------------------------------------------------------------------
# closing
# --------------------------------------------------------------------------
def _end_marker(lab: LabProfile) -> str:
    """'End of Report' set between two rules, so nothing after it can be passed
    off as part of the report."""
    side = f'<td width="40%" valign="middle">{_rule(RULE_SOFT, 1)}</td>'
    return (
        '<table width="100%" cellspacing="0" cellpadding="0"><tr>'
        + side
        + f'<td align="{text_style.align_for(lab, "end_marker")}"'
        ' valign="middle" class="end">'
        "&nbsp;&nbsp;End of Report&nbsp;&nbsp;</td>"
        + side
        + "</tr></table>"
    )


class _Signatory:
    """One person who signs the report."""

    def __init__(self, image_path: str, name: str, degrees: str, role: str):
        self.image = _data_uri(image_path)
        self.name = name
        self.degrees = degrees
        self.role = role

    def present(self) -> bool:
        return bool(self.image or self.name)


# Height of the blank left above each name for a handwritten signature, in
# points. A signature image, when one is set, prints at the same height so the
# block is the same size either way.
#
# Trimmed from 34pt (~12mm) to buy the room the full-size sub-heading needs;
# 30pt is still about 10.6mm, comfortable for a signature. The sheet is full,
# so anything added to the letterhead has to be paid for here or in the page
# margins - see REPORT_PAGE in printing.py.
SIGN_SPACE_PT = 30


def _signature(lab: LabProfile, r: Report) -> str:
    """Two signatories across the foot of the page: the lab technician who ran
    the tests on the left, the pathologist who vouches for the result on the
    right. Each is a clear space to sign in, then the name, then the role.

    Both slots always print, role and all, even with no name in the profile:
    the space and the title are the placeholder the person signs against by
    hand. There is no rule above the names - the lab signs by hand and asked
    for the line to go. Laid out as one table with a row per element (space,
    name, role) rather than two stacked blocks: Qt ignores valign, so this is
    the one way to guarantee both names sit on the same line."""
    people = [
        _Signatory(lab.technician_signature_path, lab.technician, "", "Lab Technician"),
        _Signatory(lab.signature_path, lab.pathologist, lab.pathologist_degrees,
                   "Consultant Pathologist"),
    ]

    def cell(content: str, cls: str = "", key: str = "sign_name") -> str:
        align = text_style.align_for(lab, key)
        return (f'<td align="{align}" width="50%" class="{cls}">'
                f"{content}</td>")

    def row(cells: List[str]) -> str:
        return "<tr>" + "".join(cells) + "</tr>"

    blank = "&nbsp;"
    space = row([cell(f'<img src="{p.image}" height="{SIGN_SPACE_PT}">' if p.image
                      else _spacer(SIGN_SPACE_PT), "", "sign_name")
                 for p in people])
    names = row([cell(escape(p.name) if p.name else blank, "signname",
                      "sign_name") for p in people])
    # Role and qualification share a line ("Consultant Pathologist, MD") so it is
    # one row shorter - that row is what keeps a full panel on one sheet.
    roles = row([cell(", ".join(x for x in (p.role, escape(p.degrees)) if x),
                      "signrole", "sign_role") for p in people])
    return (
        '<table width="100%" cellspacing="0" cellpadding="0">'
        + space + names + roles
        + "</table>"
    )


CSS = f"""
body {{ font-family: 'Segoe UI', Calibri, Arial, sans-serif; font-size: 8pt;
        color: {INK}; }}
.labname {{ font-size: 18pt; font-weight: bold; color: {BRAND}; letter-spacing: 0.8px; }}
.labsub {{ font-size: 18pt; font-weight: bold; color: {BRAND}; letter-spacing: 0.8px; }}
.sub {{ font-size: 7.5pt; color: {MUTED}; }}
.doctitle {{ font-size: 9.5pt; color: {INK}; letter-spacing: 2px; }}
.docmeta {{ font-size: 8.5pt; color: {INK}; }}
.patient {{ font-size: 8.5pt; }}
.lbl {{ color: {MUTED}; font-size: 8pt; }}
.cln {{ color: {MUTED}; padding-left: 4px; padding-right: 6px; }}
.val {{ color: {INK}; font-size: 8.5pt; }}
.panel {{ color: {INK}; font-size: 9pt; letter-spacing: 1px; }}
table.results th {{ font-size: 7.5pt; font-weight: normal; color: {INK_SOFT};
                    border-bottom: 1px solid {RULE_SOFT}; }}
table.results td.panel {{ border-bottom: 1px solid {RULE}; }}
table.results td {{ font-size: 8pt; }}
.slno {{ color: {MUTED}; }}
.tname {{ color: {INK}; }}
/* The result cell. It has a class purely so the lab can restyle results
   without the rule also catching the panel titles in the same table. */
.res {{ color: {INK}; }}
.unit {{ color: {INK_SOFT}; font-size: 8pt; }}
.ref {{ color: {INK_SOFT}; font-size: 8pt; }}
.flag {{ color: {FLAG}; }}
td.subhead {{ font-size: 7.5pt; color: {INK_SOFT}; letter-spacing: 1px; }}
.legend {{ font-size: 7.5pt; color: {MUTED}; }}
.money {{ font-family: 'Consolas', 'Courier New', monospace; font-size: 8.5pt;
          color: {INK}; }}
.billlbl {{ font-size: 8pt; color: {MUTED}; }}
.remarks {{ font-size: 8.5pt; color: {INK}; }}
.remarks-h {{ color: {MUTED}; }}
.end {{ font-size: 7.5pt; color: {MUTED}; letter-spacing: 2px; white-space: nowrap; }}
.signname {{ font-size: 8.5pt; font-weight: bold; color: {INK}; }}
.signrole {{ font-size: 7.5pt; font-weight: bold; color: {INK}; }}
.footer {{ font-size: 7.5pt; color: {INK}; }}
"""


def stylesheet(lab: LabProfile) -> str:
    """The report's stylesheet with the lab's own text styling appended.

    `CSS` stays the default it always was; anything rendering a report asks for
    this instead, so preview, printer and PDF cannot drift apart."""
    return text_style.stylesheet(CSS, lab)


def build(report: Report, lab: LabProfile, with_bill: bool = True) -> str:
    """The whole report as printable HTML.

    `with_bill` decides whether the bill summary is attached under the results.
    The bill is also a document of its own (see bill_html), so the lab can
    hand out the report clean and the cash bill separately, or one sheet that
    carries both."""
    body = [
        letterhead(lab),
        _spacer(6),
        _title_bar(report, lab),
        _spacer(2),
        _patient_block(report, lab),
    ]

    # Group rows by panel, preserving the order they appear in the report.
    order: List[str] = []
    grouped = {}
    for row in report.rows:
        key = row.panel or "Investigations"
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(row)

    for key in order:
        body.append(_spacer(3))
        body.append(_rows_table(grouped[key], lab, key))

    legend = _legend(report.rows, lab)
    if legend:
        body.append(_spacer(1))
        body.append(legend)

    if report.remarks:
        body.append(_spacer(2))
        body.append(_remarks(report.remarks, lab))

    bill = _bill_summary(report, lab) if with_bill else ""
    if bill:
        body.append(_spacer(2))
        body.append(bill)

    body.append(_spacer(1))
    body.append(_end_marker(lab))

    foot = footer(lab)
    if foot:
        # Everything above is set solid; the slack goes here, so the signatures
        # and the footer under them land at the foot of the page rather than
        # floating halfway up it.
        body.append(FOOTER_PAD)
    body.append(_signature(lab, report))
    if foot:
        body.append(_spacer(2))
        body.append(foot)

    return (f"<html><head><style>{stylesheet(lab)}</style></head>"
            f"<body>{''.join(body)}</body></html>")
