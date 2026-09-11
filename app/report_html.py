"""Renders a Report into self-contained printable HTML.

Images are inlined as data: URIs so QTextDocument resolves them with no base URL,
which keeps preview, printer output and exported PDF byte-identical.

The markup deliberately stays inside Qt's rich-text subset: layout is done with
nested tables and cell attributes (width/align/bgcolor) rather than flexbox or
positioning, and every colour that matters is also set as an attribute so it
survives even where the stylesheet cascade does not. Two Qt quirks shape the
markup throughout - see _rule() and _end_marker().
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

# Print palette. Navy and teal carry the structure; crimson is reserved for the
# lab identity and for values that fall outside the reference range.
INK = "#12202e"
INK_SOFT = "#41525f"
MUTED = "#6a7b8a"
RULE = "#dde4ec"
BAND = "#0b2a3a"
BAND_SOFT = "#14425a"
ACCENT = "#0d7d8f"
ACCENT_TINT = "#eef7f8"
ACCENT_LINE = "#bfdfe4"
CRIMSON = "#b3202c"
CRIMSON_TINT = "#fdf4f4"
CRIMSON_LINE = "#f0cdcf"
GREEN = "#17734d"
GREEN_TINT = "#eef7f2"
ZEBRA = "#f7f9fb"
HEAD_BG = "#e9eff5"
PAPER = "#ffffff"


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
    """Inline style for a cell that exists only to be a coloured bar.

    Qt lays a table cell out around its text, ignoring the height attribute, so
    the bar's thickness is really the font size of the &nbsp; inside it."""
    return f"font-size:{px}px; line-height:{px}px;"


def _rule(color: str = RULE, height: int = 1) -> str:
    """A hairline. Qt ignores most border shorthands on <hr>, so a filled 1px-tall
    table cell is the one separator that renders identically in every output path."""
    return (
        '<table width="100%" cellspacing="0" cellpadding="0">'
        f'<tr><td bgcolor="{color}" height="{height}" style="{_bar(height)}">'
        "&nbsp;</td></tr></table>"
    )


def _ribbon() -> str:
    """The brand bar across the very top of the page - three colour segments,
    which is as close to a gradient as Qt's rich text will go."""
    return (
        '<table width="100%" cellspacing="0" cellpadding="0"><tr>'
        f'<td width="46%" bgcolor="{CRIMSON}" style="{_bar(6)}">&nbsp;</td>'
        f'<td width="18%" bgcolor="{BAND}" style="{_bar(6)}">&nbsp;</td>'
        f'<td width="36%" bgcolor="{ACCENT}" style="{_bar(6)}">&nbsp;</td>' 
        "</tr></table>"
    )


def _spacer(pt: int = 6) -> str:
    return f'<div style="font-size:{pt}pt;">&nbsp;</div>'


def letterhead(lab: LabProfile) -> str:
    """The identity block, centred on the page with the logo off to the left.

    Everything the lab wants a patient to be able to read off the top of the
    report is here: name, address, the numbers to ring, the hours it is open
    and who to call when it is shut. A blank field prints nothing - no stray
    label, no empty line."""
    logo = _data_uri(lab.logo_path)
    logo_cell = (
        f'<td width="96" valign="middle" style="padding-right:14px;">'
        f'<img src="{logo}" width="84"></td>'
        if logo
        else ""
    )
    name = escape(lab.lab_name or "LABORATORY NAME")

    lines: List[str] = [f'<div class="labname" align="center">{name}</div>']
    for txt in (lab.address1, lab.address2):
        if txt:
            lines.append(f'<div class="sub" align="center">{escape(txt)}</div>')

    def keyed(pairs) -> str:
        """One centred line of `Label  value` pairs, set apart by dots."""
        parts = [
            f'<span class="subkey">{label}</span>&nbsp;&nbsp;{escape(value)}'
            for label, value in pairs if value
        ]
        return "&nbsp;&nbsp;&middot;&nbsp;&nbsp;".join(parts)

    contact = keyed((("Tel", lab.phone), ("Mob", lab.mobile),
                     ("Email", lab.email), ("Reg. No", lab.reg_no)))
    if contact:
        lines.append(f'<div class="sub" align="center">{contact}</div>')

    hours = keyed((("Timings", lab.timings), ("Holidays", lab.holidays)))
    if hours:
        lines.append(f'<div class="hours" align="center">{hours}</div>')

    # The logo sits in a column of its own and an empty column of the same
    # width balances it on the right, so the text block is centred on the page
    # rather than on whatever room the logo leaves over.
    balance = '<td width="96">&nbsp;</td>' if logo else ""
    return (
        '<table width="100%" cellpadding="0" cellspacing="0"><tr>'
        + logo_cell
        + '<td valign="middle" align="center">' + "".join(lines) + "</td>"
        + balance
        + "</tr></table>"
    )


def _title_bar(r: Report) -> str:
    """The dark band naming the document, carrying the report number opposite."""
    meta = (
        f'<span class="bandlbl">REPORT NO</span>&nbsp;&nbsp;'
        f"<b>{escape(r.report_no)}</b>"
        if r.report_no
        else "&nbsp;"
    )
    return (
        f'<table width="100%" cellspacing="0" cellpadding="7" bgcolor="{BAND}">'
        f'<tr><td bgcolor="{BAND}" class="bandtext">LABORATORY TEST REPORT</td>'
        f'<td bgcolor="{BAND}" align="right" class="bandmeta">{meta}</td>'
        "</tr></table>"
    )


def _patient_block(r: Report) -> str:
    age = f"{r.age} {dict(Y='Years', M='Months', D='Days').get(r.age_unit, '')}".strip()
    left = [
        ("Patient Name", r.patient_name),
        ("Age / Sex", " / ".join(x for x in (age, r.sex) if x)),
        ("Patient ID", r.patient_id),
        ("Referred By", r.referred_by),
    ]
    right = [
        ("Sample Type", r.sample_type),
        ("Collected On", r.collected_on),
        ("Reported On", r.reported_on),
    ]

    def col(items):
        # Every value is set heavy with an explicit <b>: Qt honours the tag
        # where a class-only font-weight is sometimes dropped on the printer
        # path. The name is set a size larger again - it is the one field the
        # patient checks first.
        out = []
        for k, v in items:
            if not v:
                continue
            shown = f"<b>{escape(v)}</b>"
            label = escape(k)
            if k == "Patient Name":
                shown = f'<span class="pname">{shown}</span>'
                label = f'<span class="pname-lbl"><b>{label}</b></span>'
            out.append(
                f'<tr><td class="lbl" valign="top">{label}</td>'
                f'<td class="cln" valign="top">:</td>'
                f'<td class="val" valign="top">{shown}</td></tr>')
        return "".join(out)

    return (
        f'<table width="100%" class="patient" cellspacing="0" cellpadding="8"'
        f' bgcolor="{ACCENT_TINT}"><tr>'
        f'<td width="3" bgcolor="{ACCENT}" style="font-size:1px;">&nbsp;</td>'
        f'<td width="52%" valign="top" bgcolor="{ACCENT_TINT}">'
        f'<table cellspacing="0" cellpadding="2" width="100%">{col(left)}</table></td>'
        f'<td width="48%" valign="top" bgcolor="{ACCENT_TINT}">'
        f'<table cellspacing="0" cellpadding="2" width="100%">{col(right)}</table></td>'
        "</tr></table>"
    )


def _tally(rows: List[TestRow]) -> Tuple[int, int]:
    """(tests measured, tests outside their reference range)."""
    tests = [r for r in rows if not r.is_heading() and r.result.strip()]
    flagged = [r for r in tests if flag_for(r.result, r.ref)]
    return len(tests), len(flagged)


def _summary(rows: List[TestRow]) -> str:
    """Three stat tiles: what was measured, and how much of it needs attention.
    The first thing a clinician looks for, so it goes above the tables."""
    total, flagged = _tally(rows)
    if not total:
        return ""
    tiles = [
        ("TESTS PERFORMED", str(total), INK, HEAD_BG, "#c9d6e2"),
        ("WITHIN RANGE", str(total - flagged), GREEN, GREEN_TINT, "#c5e2d4"),
        ("OUT OF RANGE", str(flagged), CRIMSON, CRIMSON_TINT, CRIMSON_LINE),
    ]
    cells = []
    for i, (label, value, fg, bg, line) in enumerate(tiles):
        if i:
            cells.append('<td width="10">&nbsp;</td>')
        cells.append(
            f'<td width="32%" bgcolor="{bg}" valign="top">'
            f'<table width="100%" cellspacing="0" cellpadding="6"><tr>'
            f'<td width="3" bgcolor="{line}" style="font-size:1px;">&nbsp;</td>'
            f'<td bgcolor="{bg}">'
            f'<div class="tilelbl">{label}</div>'
            f'<div class="tileval" style="color:{fg};">{value}</div>'
            "</td></tr></table></td>"
        )
    return (
        '<table width="100%" cellspacing="0" cellpadding="0"><tr>'
        + "".join(cells)
        + "</tr></table>"
    )


def _panel_header(title: str) -> str:
    """Panel title in a filled band, so sections are scannable at a glance."""
    return (
        f'<table width="100%" cellspacing="0" cellpadding="5" bgcolor="{BAND_SOFT}">'
        f'<tr><td width="4" bgcolor="{CRIMSON}" style="font-size:1px;">&nbsp;</td>'
        f'<td bgcolor="{BAND_SOFT}" class="panel">{escape(title)}</td>'
        "</tr></table>"
    )


def _rows_table(rows: List[TestRow]) -> str:
    out = [
        '<table width="100%" class="results" cellspacing="0" cellpadding="5">',
        f'<tr><th bgcolor="{HEAD_BG}" align="left" width="40%">TEST</th>'
        f'<th bgcolor="{HEAD_BG}" align="left" width="17%">RESULT</th>'
        f'<th bgcolor="{HEAD_BG}" align="left" width="15%">UNIT</th>'
        f'<th bgcolor="{HEAD_BG}" align="left" width="28%">REFERENCE RANGE</th></tr>',
    ]
    striped = 0
    for row in rows:
        if row.is_heading():
            out.append(
                f'<tr><td colspan="4" bgcolor="#dfe7ef" class="subhead">'
                f"{escape(row.name)}</td></tr>"
            )
            striped = 0
            continue
        striped += 1
        flag = flag_for(row.result, row.ref)
        value = escape(row.result)
        if flag:
            # An out-of-range row is tinted end to end, not just its number, so
            # it can be found by flipping through a printed report.
            bg = CRIMSON_TINT
            value = f'<span class="abn"><b>{value}</b>&nbsp;&nbsp;<b>{flag}</b></span>'
            name_cls, ref_cls = "tname abnname", "ref abnref"
        else:
            bg = ZEBRA if striped % 2 == 0 else PAPER
            value = f'<span class="ok"><b>{value}</b></span>'
            name_cls, ref_cls = "tname", "ref"
        out.append(
            "<tr>"
            f'<td bgcolor="{bg}" class="{name_cls}"><b>{escape(row.name)}</b></td>'
            f'<td bgcolor="{bg}">{value}</td>'
            f'<td bgcolor="{bg}" class="unit">{escape(row.unit)}</td>'
            f'<td bgcolor="{bg}" class="{ref_cls}">{escape(row.ref)}</td></tr>'
        )
    out.append("</table>")
    return "".join(out)


def _legend(rows: List[TestRow]) -> str:
    """Explains the H/L marks, but only on reports that actually carry one."""
    if not _tally(rows)[1]:
        return ""
    return (
        '<div class="legend"><span class="abn"><b>H</b></span>&nbsp; above '
        'reference range &nbsp;&nbsp;&middot;&nbsp;&nbsp; '
        '<span class="abn"><b>L</b></span>&nbsp; below reference range '
        '&nbsp;&nbsp;&middot;&nbsp;&nbsp; shaded rows need clinical '
        "correlation</div>"
    )


def _remarks(text: str) -> str:
    return (
        '<table width="100%" cellspacing="0" cellpadding="8"><tr>'
        f'<td width="4" bgcolor="{ACCENT}" style="font-size:1px;">&nbsp;</td>'
        f'<td bgcolor="{ACCENT_TINT}" class="remarks">'
        f'<span class="remarks-h">REMARKS</span><br>{escape(text)}</td>'
        "</tr></table>"
    )


# The order the bill reads in: what it came to, what is payable, what was paid,
# what is left. Balance last, because that is the line the patient looks for.
BILL_TOTALS = (
    ("Total Billed", "total_billed"),
    ("Net Payable", "net_payable"),
    ("Net Deposit", "net_deposit"),
)


def _bill_header(r: Report) -> str:
    """The band that names the section, carrying the bill number and date opposite -
    deliberately the same shape as the report's own title bar, so the bill reads
    as part of the document rather than as something stapled to it."""
    bill = r.billing
    meta = []
    if bill.bill_no:
        meta.append(f'<span class="bandlbl">BILL NO</span>&nbsp;&nbsp;'
                    f"<b>{escape(bill.bill_no)}</b>")
    if bill.bill_date:
        # Formatted the same way the standalone bill prints it, so the two
        # documents never quote the same bill with two different dates.
        meta.append(f'<span class="bandlbl">DATE</span>&nbsp;&nbsp;'
                    f"<b>{escape(format_bill_date(bill.bill_date))}</b>")
    return (
        f'<table width="100%" cellspacing="0" cellpadding="7" bgcolor="{BAND}">'
        f'<tr><td bgcolor="{BAND}" class="bandtext">BILL SUMMARY</td>'
        f'<td bgcolor="{BAND}" align="right" class="bandmeta">'
        f'{"&nbsp;&nbsp;&middot;&nbsp;&nbsp;".join(meta) or "&nbsp;"}</td>'
        "</tr></table>"
    )


def _bill_items(r: Report) -> str:
    """One row per billed service. An unpriced line prints a dash rather than
    0.00, so 'not charged for' and 'charged nothing' stay distinguishable."""
    out = [
        '<table width="100%" class="results" cellspacing="0" cellpadding="5">',
        f'<tr><th bgcolor="{HEAD_BG}" align="left" width="72%">SERVICE / TEST</th>'
        f'<th bgcolor="{HEAD_BG}" align="right" width="28%">AMOUNT ({CURRENCY})</th>'
        "</tr>",
    ]
    for i, item in enumerate(r.billing.items):
        bg = ZEBRA if i % 2 else PAPER
        amount = parse_amount(item.amount)
        text = format_amount(amount) if amount is not None else "&ndash;"
        out.append(
            "<tr>"
            f'<td bgcolor="{bg}" class="tname">{escape(item.service)}</td>'
            f'<td bgcolor="{bg}" align="right" class="money">{text}</td></tr>'
        )
    out.append("</table>")
    return "".join(out)


def _bill_totals(r: Report) -> str:
    """The totals, right-aligned under the amount column, with the balance set
    apart on its own tinted line."""
    figures = summary(r.billing)
    rows = [
        f'<tr><td class="billlbl" align="right">{label}</td>'
        f'<td class="money" align="right" width="34%">'
        f"{format_amount(figures[key])}</td></tr>"
        for label, key in BILL_TOTALS
    ]
    due = figures["balance"]
    # A balance that is owed is the one number on the page that has to be
    # noticed; a cleared bill says so in the same slot rather than going blank.
    if due > 0:
        fg, bg, line = CRIMSON, CRIMSON_TINT, CRIMSON_LINE
    else:
        fg, bg, line = GREEN, GREEN_TINT, "#c5e2d4"
    rows.append(
        f'<tr><td bgcolor="{bg}" align="right" class="billlbl"'
        f' style="color:{fg};"><b>BALANCE</b></td>'
        f'<td bgcolor="{bg}" align="right" class="money"'
        f' style="color:{fg}; font-size:11pt;"><b>{format_amount(due)}</b></td></tr>'
    )
    # cellpadding is 0 on the wrapper so the accent stripe stays a stripe: any
    # padding is added to the 3px cell on both sides and turns it into a slab.
    inner = (
        f'<table width="100%" cellspacing="0" cellpadding="0">'
        f'<tr><td width="3" bgcolor="{line}" style="font-size:1px;">&nbsp;</td>'
        f'<td style="padding-left:10px;">'
        f'<table width="100%" cellspacing="0" cellpadding="4">'
        + "".join(rows) + "</table></td></tr></table>"
    )
    return (
        '<table width="100%" cellspacing="0" cellpadding="0"><tr>'
        '<td width="52%" valign="top">&nbsp;</td>'
        f'<td width="48%" valign="top">{inner}</td>'
        "</tr></table>"
    )


def _bill_summary(r: Report) -> str:
    """The whole billing block, or nothing at all.

    Rendered only when the bill actually carries figures - see
    `billing.has_content` - and placed after the results and remarks, so it can
    never sit on top of a laboratory value.
    """
    if not has_content(r.billing):
        return ""
    return (
        _bill_header(r)
        + _bill_items(r)
        + _spacer(4)
        + _bill_totals(r)
    )


def _end_marker() -> str:
    """'End of Report' set between two rules, so nothing after it can be passed
    off as part of the report."""
    # The side rules are nested single-cell tables: a bgcolor on the outer cell
    # would be painted over the cell's full text height and read as a thick bar.
    side = f'<td width="38%" valign="middle">{_rule(ACCENT_LINE, 1)}</td>'
    return (
        '<table width="100%" cellspacing="0" cellpadding="0"><tr>'
        + side
        + '<td align="center" valign="middle" class="end">'
        "&nbsp;&nbsp;End of Report&nbsp;&nbsp;</td>"
        + side
        + "</tr></table>"
    )


def _signatory(image_path: str, name: str, degrees: str, role: str) -> str:
    """One signing block: image (or a blank line to sign on), rule, name,
    qualification, role. Empty when there is nobody to name."""
    sig = _data_uri(image_path)
    if not (sig or name or degrees):
        return ""
    # Signing line drawn as a filled cell rather than a border, for the same
    # reason as the end-of-report rules.
    signline = (
        '<table width="150" cellspacing="0" cellpadding="0" align="center">'
        f'<tr><td bgcolor="{MUTED}" height="1" style="{_bar(1)}">'
        "&nbsp;</td></tr></table>"
    )
    parts = [
        f'<img src="{sig}" width="120"><br>' if sig else _spacer(14),
        signline,
        _spacer(3),
    ]
    if name:
        parts.append(f'<b class="signname">{escape(name)}</b><br>')
    # The qualification line is always emitted, blank if need be, so the two
    # signatories' rules and names sit level across the page - Qt ignores
    # valign="bottom" on cells, so the blocks have to be the same height.
    parts.append(f'<span class="sub">{escape(degrees) or "&nbsp;"}</span><br>')
    parts.append(f'<span class="signrole">{role}</span>')
    return "".join(parts)


def _signature(lab: LabProfile, r: Report) -> str:
    """Three signatories across the foot of the page, left to right in the
    order the work passed through their hands: the person who raised the bill
    (a space to sign by hand, and their name), the technician who ran the
    tests, and the pathologist who vouches for the result."""
    billed = _signatory("", r.billing.billed_by or lab.billed_by, "", "Billed By")
    technician = _signatory(lab.technician_signature_path, lab.technician, "",
                            "Lab Technician")
    pathologist = _signatory(lab.signature_path, lab.pathologist,
                             lab.pathologist_degrees,
                             "Verified &amp; Authorised Signatory")
    if not (billed or technician or pathologist):
        return ""
    cells = "".join(
        f'<td align="center" valign="bottom" width="32%">{block or "&nbsp;"}</td>'
        + ('<td width="2%">&nbsp;</td>' if i < 2 else "")
        for i, block in enumerate((billed, technician, pathologist))
    )
    return (
        '<table width="100%" cellspacing="0" cellpadding="0"><tr>'
        + cells + "</tr></table>"
    )


CSS = f"""
body {{ font-family: 'Segoe UI', Calibri, Arial, sans-serif; font-size: 10pt;
        color: {INK}; }}
.labname {{ font-size: 18pt; font-weight: bold; color: {CRIMSON};
            letter-spacing: 0.5px; }}
.sub {{ font-size: 8.5pt; color: {MUTED}; }}
.subkey {{ font-weight: bold; color: {INK_SOFT}; }}
.hours {{ font-size: 8.5pt; color: {ACCENT}; font-weight: bold; }}
.pname {{ font-size: 11pt; font-weight: bold; color: {INK}; }}
.pname-lbl {{ font-weight: bold; color: {INK_SOFT}; }}
.bandtext {{ color: #ffffff; font-size: 10.5pt; font-weight: bold;
             letter-spacing: 2.5px; }}
.bandmeta {{ color: #ffffff; font-size: 9.5pt; letter-spacing: 0.5px; }}
.bandlbl {{ color: {ACCENT_LINE}; font-size: 8.5pt; letter-spacing: 1px; }}
.patient {{ font-size: 9.5pt; }}
.lbl {{ color: {MUTED}; font-size: 9pt; }}
.cln {{ color: {ACCENT_LINE}; padding-left: 4px; padding-right: 8px; }}
.val {{ font-weight: bold; color: {INK}; font-size: 9.5pt; }}
.tilelbl {{ font-size: 7.5pt; font-weight: bold; color: {MUTED};
            letter-spacing: 1.5px; }}
.tileval {{ font-size: 17pt; font-weight: bold; }}
.panel {{ color: #ffffff; font-size: 10.5pt; font-weight: bold;
          letter-spacing: 1.5px; }}
table.results th {{ font-size: 8pt; color: {INK_SOFT}; letter-spacing: 1.5px;
                    border-bottom: 1px solid #b0c0cf; }}
table.results td {{ border-bottom: 1px solid {RULE}; font-size: 9.5pt; }}
.tname {{ color: {INK}; }}
.abnname {{ font-weight: bold; }}
.unit {{ color: {INK_SOFT}; font-size: 9pt; }}
.ref {{ color: {MUTED}; font-size: 9pt; }}
.abnref {{ color: {CRIMSON}; font-size: 9pt; }}
.ok {{ font-weight: bold; color: {INK}; font-size: 10pt; }}
.abn {{ color: {CRIMSON}; font-weight: bold; }}
td.subhead {{ font-weight: bold; font-size: 8pt; color: {BAND};
              letter-spacing: 1.5px; }}
.legend {{ font-size: 8pt; color: {MUTED}; }}
.money {{ font-family: 'Consolas', 'Courier New', monospace; font-size: 9.5pt;
          color: {INK}; }}
.billlbl {{ font-size: 8.5pt; color: {MUTED}; letter-spacing: 1.2px; }}
.remarks {{ font-size: 9.5pt; color: {INK_SOFT}; }}
.remarks-h {{ font-size: 8pt; font-weight: bold; color: {ACCENT};
              letter-spacing: 1.5px; }}
.end {{ font-size: 8pt; color: {ACCENT}; font-weight: bold;
        letter-spacing: 2.5px; white-space: nowrap; }}
.signname {{ font-size: 10.5pt; color: {INK}; }}
.signrole {{ font-size: 8pt; color: {MUTED}; letter-spacing: 1px; }}
.footer {{ font-size: 8pt; color: {MUTED}; }}
"""


def build(report: Report, lab: LabProfile) -> str:
    body = [
        _ribbon(),
        _spacer(5),
        letterhead(lab),
        _spacer(4),
        _rule(CRIMSON, 3),
        _rule(ACCENT_LINE, 1),
        _spacer(5),
        _title_bar(report),
        _patient_block(report),
    ]

    summary = _summary(report.rows)
    if summary:
        body.append(_spacer(6))
        body.append(summary)

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
        body.append(_spacer(6))
        body.append(_panel_header(key))
        body.append(_rows_table(grouped[key]))

    legend = _legend(report.rows)
    if legend:
        body.append(_spacer(4))
        body.append(legend)

    if report.remarks:
        body.append(_spacer(6))
        body.append(_remarks(report.remarks))

    bill = _bill_summary(report)
    if bill:
        body.append(_spacer(8))
        body.append(bill)

    body.append(_spacer(6))
    body.append(_end_marker())
    body.append(_spacer(4))
    body.append(_signature(lab, report))

    if lab.footer_note:
        body.append(_spacer(6))
        body.append(_rule(RULE, 1))
        body.append(
            f'<div class="footer" align="center" style="padding-top:6px;">'
            f"{escape(lab.footer_note)}</div>"
        )

    return f"<html><head><style>{CSS}</style></head><body>{''.join(body)}</body></html>"
