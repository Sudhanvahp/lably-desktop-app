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


def _spacer(pt: int = 4) -> str:
    return f'<div style="font-size:{pt}pt;">&nbsp;</div>'


def _keyed(pairs) -> str:
    """One line of `Label: value` pairs set apart by dots; blanks are skipped."""
    parts = [f'{label}: {escape(value)}' for label, value in pairs if value]
    return "&nbsp;&nbsp;&middot;&nbsp;&nbsp;".join(parts)


# --------------------------------------------------------------------------
# letterhead and footer
# --------------------------------------------------------------------------
def letterhead(lab: LabProfile) -> str:
    """The identity block at the top: name over sub-heading, centred, with
    the logo off to the left. Contact details live in the footer."""
    logo = _data_uri(lab.logo_path)
    logo_cell = (
        f'<td width="80" valign="middle" style="padding-right:10px;">'
        f'<img src="{logo}" width="70"></td>'
        if logo
        else ""
    )
    lines: List[str] = [
        f'<div class="labname" align="center">'
        f'{escape(lab.lab_name or "LABORATORY NAME")}</div>'
    ]
    if lab.lab_subtitle:
        lines.append(f'<div class="labsub" align="center">{escape(lab.lab_subtitle)}</div>')
    # The logo sits in a column of its own and an empty column of the same
    # width balances it on the right, so the text block is centred on the page
    # rather than on whatever room the logo leaves over.
    balance = '<td width="80">&nbsp;</td>' if logo else ""
    return (
        '<table width="100%" cellpadding="0" cellspacing="0"><tr>'
        + logo_cell
        + '<td valign="middle" align="center">' + "".join(lines) + "</td>"
        + balance
        + "</tr></table>"
    )


def footer(lab: LabProfile) -> str:
    """Address, contact details, hours and the footer note, under a rule at the
    foot of the page - where a patient looks for how to reach the lab."""
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
        _rule(RULE_SOFT, 1)
        + '<div class="footer" align="center" style="padding-top:3px;">'
        + "<br>".join(lines)
        + "</div>"
    )


# --------------------------------------------------------------------------
# the report
# --------------------------------------------------------------------------
def _title_bar(r: Report) -> str:
    """The document's name, ruled above and below, report number opposite."""
    meta = f"Report No: {escape(r.report_no)}" if r.report_no else "&nbsp;"
    return (
        _rule(RULE, 1)
        + '<table width="100%" cellspacing="0" cellpadding="2"><tr>'
        '<td class="doctitle">LABORATORY TEST REPORT</td>'
        f'<td align="right" class="docmeta">{meta}</td>'
        "</tr></table>"
        + _rule(RULE, 1)
    )


def _patient_block(r: Report) -> str:
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

    def col(items):
        out = []
        for k, v in items:
            if not v:
                continue
            # The patient's name is the one thing on the page set in bold.
            shown = f"<b>{escape(v)}</b>" if k == "Patient Name" else escape(v)
            out.append(
                f'<tr><td class="lbl" valign="top">{escape(k)}</td>'
                f'<td class="cln" valign="top">:</td>'
                f'<td class="val" valign="top">{shown}</td></tr>')
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


def _panel_header(title: str) -> str:
    """Panel title, ruled underneath."""
    return (
        '<table width="100%" cellspacing="0" cellpadding="2">'
        f'<tr><td class="panel">{escape(title)}</td></tr></table>'
        + _rule(RULE, 1)
    )


def _rows_table(rows: List[TestRow], start: int = 1) -> Tuple[str, int]:
    """Renders the rows; returns (html, next serial). Serial numbers run on
    across panels so the last one is the count of tests on the report."""
    out = [
        '<table width="100%" class="results" cellspacing="0" cellpadding="1">',
        '<tr><th align="left" width="8%" style="white-space:nowrap;">Sl. No.</th>'
        '<th align="left" width="36%">Test</th>'
        '<th align="left" width="16%">Result</th>'
        '<th align="left" width="14%">Unit</th>'
        '<th align="left" width="26%">Reference Range</th></tr>',
    ]
    serial = start
    for row in rows:
        if row.is_heading():
            out.append(f'<tr><td></td><td colspan="4" class="subhead">'
                       f"{escape(row.name)}</td></tr>")
            continue
        flag = flag_for(row.result, row.ref)
        value = escape(row.result)
        if flag:
            value = f'{value}&nbsp;&nbsp;<span class="flag">{flag}</span>'
        out.append(
            "<tr>"
            f'<td class="slno">{serial}</td>'
            f'<td class="tname">{escape(row.name)}</td>'
            f'<td>{value}</td>'
            f'<td class="unit">{escape(row.unit)}</td>'
            f'<td class="ref">{escape(row.ref)}</td></tr>'
        )
        serial += 1
    out.append("</table>")
    return "".join(out), serial


def _legend(rows: List[TestRow]) -> str:
    """Explains the H/L marks, but only on reports that actually carry one."""
    if not _tally(rows)[1]:
        return ""
    return (
        '<div class="legend"><span class="flag">H</span> above reference range'
        '&nbsp;&nbsp;&middot;&nbsp;&nbsp;<span class="flag">L</span> below '
        "reference range</div>"
    )


def _remarks(text: str) -> str:
    return (
        '<table width="100%" cellspacing="0" cellpadding="2"><tr>'
        f'<td class="remarks"><span class="remarks-h">Remarks:</span> '
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


def _bill_header(r: Report) -> str:
    bill = r.billing
    meta = []
    if bill.bill_no:
        meta.append(f"Bill No: {escape(bill.bill_no)}")
    if bill.bill_date:
        meta.append(f"Date: {escape(format_bill_date(bill.bill_date))}")
    return (
        '<table width="100%" cellspacing="0" cellpadding="2"><tr>'
        '<td class="panel">BILL SUMMARY</td>'
        f'<td align="right" class="docmeta">'
        f'{"&nbsp;&nbsp;&middot;&nbsp;&nbsp;".join(meta) or "&nbsp;"}</td>'
        "</tr></table>"
        + _rule(RULE, 1)
    )


def _bill_items(r: Report) -> str:
    """One numbered row per billed service. An unpriced line prints a dash
    rather than 0.00, so 'not charged for' and 'charged nothing' stay
    distinguishable."""
    out = [
        '<table width="100%" class="results" cellspacing="0" cellpadding="1">',
        '<tr><th align="left" width="8%" style="white-space:nowrap;">Sl. No.</th>'
        '<th align="left" width="64%">Service / Test</th>'
        f'<th align="right" width="28%">Amount ({CURRENCY})</th></tr>',
    ]
    for i, item in enumerate(r.billing.items, 1):
        amount = parse_amount(item.amount)
        text = format_amount(amount) if amount is not None else "&ndash;"
        out.append(
            "<tr>"
            f'<td class="slno">{i}</td>'
            f'<td class="tname">{escape(item.service)}</td>'
            f'<td align="right" class="money">{text}</td></tr>'
        )
    out.append("</table>")
    return "".join(out)


def _bill_totals(r: Report) -> str:
    figures = summary(r.billing)
    rows = [
        f'<tr><td class="billlbl" align="right">{label}</td>'
        f'<td class="money" align="right" width="34%">'
        f"{format_amount(figures[key])}</td></tr>"
        for label, key in BILL_TOTALS
    ]
    rows.append(
        f'<tr><td align="right" class="billlbl">Balance</td>'
        f'<td align="right" class="money">{format_amount(figures["balance"])}</td></tr>'
    )
    return (
        '<table width="100%" cellspacing="0" cellpadding="0"><tr>'
        '<td width="52%" valign="top">&nbsp;</td>'
        f'<td width="48%" valign="top">'
        f'<table width="100%" cellspacing="0" cellpadding="1">'
        + "".join(rows) + "</table></td></tr></table>"
    )


def _bill_summary(r: Report) -> str:
    """The whole billing block, or nothing at all - rendered only when the bill
    carries figures, and placed after the results and remarks."""
    if not has_content(r.billing):
        return ""
    return _bill_header(r) + _bill_items(r) + _rule(RULE_SOFT, 1) + _bill_totals(r)


# --------------------------------------------------------------------------
# closing
# --------------------------------------------------------------------------
def _end_marker() -> str:
    """'End of Report' set between two rules, so nothing after it can be passed
    off as part of the report."""
    side = f'<td width="40%" valign="middle">{_rule(RULE_SOFT, 1)}</td>'
    return (
        '<table width="100%" cellspacing="0" cellpadding="0"><tr>'
        + side
        + '<td align="center" valign="middle" class="end">'
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
SIGN_SPACE_PT = 34


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
                   "Pathologist"),
    ]

    def cell(content: str, cls: str = "") -> str:
        return f'<td align="center" width="50%" class="{cls}">{content}</td>'

    def row(cells: List[str]) -> str:
        return "<tr>" + "".join(cells) + "</tr>"

    blank = "&nbsp;"
    space = row([cell(f'<img src="{p.image}" height="{SIGN_SPACE_PT}">' if p.image
                      else _spacer(SIGN_SPACE_PT))
                 for p in people])
    names = row([cell(escape(p.name) if p.name else blank, "signname") for p in people])
    # Role and qualification share a line ("Pathologist, MD") so the block is
    # one row shorter - that row is what keeps a full panel on one sheet.
    roles = row([cell(", ".join(x for x in (p.role, escape(p.degrees)) if x),
                      "signrole") for p in people])
    return (
        '<table width="100%" cellspacing="0" cellpadding="0">'
        + space + names + roles
        + "</table>"
    )


CSS = f"""
body {{ font-family: 'Segoe UI', Calibri, Arial, sans-serif; font-size: 8pt;
        color: {INK}; }}
.labname {{ font-size: 18pt; font-weight: bold; color: {BRAND}; letter-spacing: 0.8px; }}
.labsub {{ font-size: 11.5pt; color: {BRAND}; }}
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
table.results td {{ border-bottom: 1px solid #e6e6e6; font-size: 8pt; }}
.slno {{ color: {MUTED}; }}
.tname {{ color: {INK}; }}
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
.signname {{ font-size: 8.5pt; color: {INK}; }}
.signrole {{ font-size: 7.5pt; color: {MUTED}; }}
.footer {{ font-size: 7.5pt; color: {MUTED}; }}
"""


def build(report: Report, lab: LabProfile, with_bill: bool = True) -> str:
    """The whole report as printable HTML.

    `with_bill` decides whether the bill summary is attached under the results.
    The bill is also a document of its own (see bill_html), so the lab can
    hand out the report clean and the cash bill separately, or one sheet that
    carries both."""
    body = [
        letterhead(lab),
        _spacer(2),
        _title_bar(report),
        _spacer(1),
        _patient_block(report),
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

    serial = 1
    for key in order:
        body.append(_spacer(3))
        body.append(_panel_header(key))
        table, serial = _rows_table(grouped[key], serial)
        body.append(table)

    legend = _legend(report.rows)
    if legend:
        body.append(_spacer(1))
        body.append(legend)

    if report.remarks:
        body.append(_spacer(3))
        body.append(_remarks(report.remarks))

    bill = _bill_summary(report) if with_bill else ""
    if bill:
        body.append(_spacer(4))
        body.append(bill)

    body.append(_spacer(2))
    body.append(_end_marker())
    body.append(_signature(lab, report))

    foot = footer(lab)
    if foot:
        body.append(_spacer(2))
        body.append(foot)

    return f"<html><head><style>{CSS}</style></head><body>{''.join(body)}</body></html>"
