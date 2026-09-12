"""Renders a Report's bill as a standalone printable Cash Bill.

This is a separate document from the lab report, not a section of it. A bill is
raised at the counter, before any result exists; the report is printed later.
Laying it out here rather than in `report_html` keeps that separation honest -
neither document can quietly acquire the other's furniture.

The layout reproduces the slip the lab already issues, field for field and rule
for rule: centred letterhead, the bill type as the heading, a two-column block of
patient and bill identity, a fully ruled services table with Amount and Net
Amount, the paid amount in words beside the closing figures, the Printed By /
Billed By pair, and the numbered notes.

It is deliberately monochrome. The report is a clinical document and carries the
lab's colours; a bill is an accounting document that gets photocopied, faxed and
filed, and every rule on it has to survive that.

Qt's rich-text subset is the constraint throughout: layout is nested tables, and
rules are real table borders with an explicit colour, because Qt paints an
unstyled border in its own grey.
"""
from html import escape
from typing import List, Tuple

from .billing import (DEFAULT_BILL_TYPE, amount_in_words, deposit,
                      format_amount, format_bill_date, net_payable,
                      parse_amount, summary, total_billed)
from .models import LabProfile, Report

INK = "#000000"
PAPER = "#ffffff"

# Column widths, shared by the services table and the block beneath it so the
# closing figures line up under the money columns instead of merely near them.
W_SERIAL, W_SERVICE, W_AMOUNT, W_NET = "5%", "55%", "20%", "20%"

AGE_WORDS = {"Y": "Yrs", "M": "Mths", "D": "Days"}
SEX_WORDS = {"M": "Male", "F": "Female"}


def _box(content: str, border: int = 1, padding: int = 2) -> str:
    """A ruled table. The colour is set explicitly - an unstyled Qt border is
    grey, and a grey rule disappears on the second photocopy."""
    return (
        f'<table width="100%" border="{border}" cellspacing="0"'
        f' cellpadding="{padding}" style="border-color:{INK};'
        f' border-style:solid;">{content}</table>'
    )


def _plain(content: str, padding: int = 0) -> str:
    """An unruled table, used purely to place things side by side."""
    return (
        f'<table width="100%" border="0" cellspacing="0"'
        f' cellpadding="{padding}">{content}</table>'
    )


def _hrule() -> str:
    """A full-width line. Qt ignores most border shorthands on <hr>, so a filled
    one-pixel cell is the only separator that renders in every output path."""
    return (
        '<table width="100%" cellspacing="0" cellpadding="0">'
        f'<tr><td bgcolor="{INK}" height="1" '
        'style="font-size:1px; line-height:1px;">&nbsp;</td></tr></table>'
    )


# --------------------------------------------------------------------------
# the parts
# --------------------------------------------------------------------------
def letterhead(lab: LabProfile) -> str:
    """Centred, black, no logo: the name and its sub-heading, nothing else -
    the same top as the report. Contact details print in the footer."""
    lines = [
        f'<div class="labname">{escape(lab.lab_name or "LABORATORY NAME")}</div>'
    ]
    if lab.lab_subtitle:
        lines.append(f'<div class="labsub">{escape(lab.lab_subtitle)}</div>')
    return f'<div align="center">{"".join(lines)}</div>'


def footer(lab: LabProfile) -> str:
    """Address, numbers, email, registration, hours - the lines the report
    carries in its footer, set the same way here so the two documents agree."""
    lines = []
    address = ", ".join(part for part in (lab.address1, lab.address2) if part)
    if address:
        lines.append(escape(address))
    contact = [f"{label}: {escape(value)}" for label, value in
               (("Ph", lab.phone), ("Mob", lab.mobile), ("Email", lab.email),
                ("Reg. No", lab.reg_no)) if value]
    if contact:
        lines.append(" &middot; ".join(contact))
    hours = [f"{label}: {escape(value)}" for label, value in
             (("Timings", lab.timings), ("Holidays", lab.holidays)) if value]
    if hours:
        lines.append(" &middot; ".join(hours))
    if not lines:
        return ""
    return '<div align="center">' + "".join(
        f'<div class="labline">{line}</div>' for line in lines) + "</div>"


def _heading(r: Report) -> str:
    """The bill type doubles as the document's title, as on the slip."""
    return (f'<div class="heading" align="center">'
            f'{escape(r.billing.bill_type or DEFAULT_BILL_TYPE)}</div>')


def _age_sex(r: Report) -> str:
    age = f"{r.age} {AGE_WORDS.get(r.age_unit, 'Yrs')}".strip() if r.age else ""
    sex = SEX_WORDS.get(r.sex, r.sex)
    return " / ".join(part for part in (age, sex) if part)


def _identity(r: Report) -> str:
    """Patient on the left, bill on the right, four rows each.

    Blank rows are kept rather than dropped: the two columns are read across, and
    collapsing one side alone slides every row below it out of step with its
    neighbour.
    """
    # Per row: (label, value, bold?, must-not-break?).
    #
    # Bold is how the slip sets it - who the patient is prints heavy, while the
    # reference numbers that identify the paperwork print light, so the eye lands
    # on the person rather than on the filing.
    #
    # Must-not-break is for values of fixed shape. A timestamp broken after
    # "10.43.30" reads as a different field on the next line. A name is left
    # breakable, because an unusually long one should wrap rather than shove the
    # column it lives in over the top of its neighbour.
    left: List[Tuple[str, str, bool, bool]] = [
        ("Patient Name", r.display_name(), True, False),
        ("Patient No", r.patient_id, False, True),
        ("Age/Gender", _age_sex(r), True, True),
        ("Phone No", r.phone, True, True),
    ]
    right: List[Tuple[str, str, bool, bool]] = [
        ("Bill No", r.billing.bill_no, False, True),
        ("Bill Date", format_bill_date(r.billing.bill_date), False, True),
        ("Ref. By", r.referred_by, True, False),
        ("", "", False, False),
    ]

    def row(key: str, value: str, heavy: bool, tight: bool) -> str:
        if not key:
            # A filler row keeps the two columns four rows tall each, so the
            # bill's shape does not change from one to the next.
            return '<tr><td colspan="3">&nbsp;</td></tr>'
        shown = escape(value)
        if heavy and shown:
            shown = f"<b>{shown}</b>"
        return (
            "<tr>"
            f'<td class="key">{escape(key)}</td>'
            f'<td class="colon">:</td>'
            f'<td width="100%" class="{"val tight" if tight else "val"}">'
            f"{shown}</td></tr>"
        )

    def half(items) -> str:
        return _plain("".join(row(*item) for item in items), padding=1)

    # Each half is its own table inside a two-cell shell, rather than one
    # six-column table. In a single table the widest cell on either side sets
    # the column width for both, so a long doctor's name on the right would
    # squeeze the patient's name on the left until it wrapped. Two tables cannot
    # reach across, and the midpoint stays put from one bill to the next.
    return _plain(
        '<tr>'
        f'<td width="50%" valign="top">{half(left)}</td>'
        f'<td width="50%" valign="top">{half(right)}</td>'
        "</tr>",
        padding=0,
    )


def _services(r: Report) -> str:
    """The ruled services table, closed by the Total Billed row.

    Amount and Net Amount carry the same figure. Per-line adjustments are out of
    scope, so nothing can currently separate them - but the lab's slip has both
    columns, and dropping one would mean re-cutting the table the day a discount
    is specified.
    """
    rows = [
        "<tr>"
        f'<td width="{W_SERIAL}" align="center" class="th">#</td>'
        f'<td width="{W_SERVICE}" class="th">Services</td>'
        f'<td width="{W_AMOUNT}" align="center" class="th">Amount</td>'
        f'<td width="{W_NET}" align="center" class="th">Net Amount</td>'
        "</tr>"
    ]
    for i, item in enumerate(r.billing.items, start=1):
        amount = parse_amount(item.amount)
        # An unpriced service prints a dash: "not charged for" and "charged
        # nothing" are different things, and the patient can see which is which.
        text = format_amount(amount) if amount is not None else "&ndash;"
        rows.append(
            "<tr>"
            f'<td align="center" class="td">{i}</td>'
            f'<td class="td"><b>{escape(item.service)}</b></td>'
            f'<td align="right" class="money">{text}</td>'
            f'<td align="right" class="money">{text}</td>'
            "</tr>"
        )

    total = format_amount(total_billed(r.billing))
    rows.append(
        '<tr><td colspan="2" align="center" class="totlbl"><b>Total Billed</b></td>'
        f'<td align="right" class="money"><b>{total}</b></td>'
        f'<td align="right" class="money"><b>{total}</b></td></tr>'
    )
    return _box("".join(rows))


def _closing(r: Report) -> str:
    """Paid-in-words on the left, the three closing figures ruled on the right.

    The block is sized to its own labels rather than to a fixed percentage: the
    printer decides the real page width, and a label that has to fit is a
    stronger constraint than a column boundary that merely looks tidy.
    """
    figures = summary(r.billing)
    rows = "".join(
        f'<tr><td class="boxlbl"><b>{label}</b></td>'
        f'<td align="right" class="money"><b>'
        f"{format_amount(figures[key])}</b></td></tr>"
        for label, key in (("Net Payable Amt", "net_payable"),
                           ("Net Deposit Amt", "net_deposit"),
                           ("Balance", "balance"))
    )

    # What the bill comes to, in words, always. This is the figure the words are
    # there to protect - a total can be altered after the fact with one pen
    # stroke and a sentence cannot - so it is stated whether or not anything has
    # been paid yet.
    # What was handed over, in words, but only when something was. On an
    # unsettled bill "Paid Amount : Zero Rupees Only" says nothing the Balance
    # has not already said.
    paid = deposit(r.billing)
    words = (
        f'<span class="key">Paid Amount</span>&nbsp;: '
        f'<b>{escape(amount_in_words(paid))}</b>'
        if paid else "&nbsp;"
    )

    return _plain(
        '<tr>'
        f'<td width="62%" valign="middle" class="td">{words}</td>'
        f'<td width="38%" valign="top">{_box(rows)}</td>'
        "</tr>",
        padding=2,
    )


def _amount_words(r: Report) -> str:
    """What the bill comes to, spelled out, on a line of its own.

    Always printed, whether or not anything has been paid: a total can be altered
    after the fact with one pen stroke and a sentence cannot, so the figure the
    words exist to protect is the one being charged.

    It gets the full width rather than sharing the row with the closing figures.
    Those are all nowrap and claim their natural width whatever percentage the
    cell is given, which left the sentence squeezed into what remained and broken
    across two lines on any bill over a few thousand rupees.
    """
    return (
        f'<div class="words"><span class="key">Amount in Words</span>&nbsp;: '
        f'<b>{escape(amount_in_words(net_payable(r.billing)))}</b></div>'
    )


def _signatories(r: Report) -> str:
    """The slip no longer names who printed or billed it: the lab asked for the
    field to go. Bills stored with a name keep it in the data file; nothing
    prints. Kept as a function so the page assembly below stays readable."""
    return ""


def _notes(lab: LabProfile) -> str:
    """The lab's standing terms, numbered as they are typed - one per line."""
    lines = [line.strip() for line in (lab.bill_notes or "").splitlines()
             if line.strip()]
    if not lines:
        return ""
    items = "".join(
        f'<div class="note">{i}.&nbsp;&nbsp;{escape(line)}</div>'
        for i, line in enumerate(lines, start=1)
    )
    return f'<div class="notehead">Note:</div>{items}'


CSS = f"""
body {{ font-family: Arial, 'Helvetica Neue', 'Segoe UI', sans-serif;
        font-size: 7pt; color: {INK}; }}
.labname {{ font-size: 12pt; font-weight: bold; }}
.labsub {{ font-size: 8pt; }}
.labline {{ font-size: 6.5pt; }}
.heading {{ font-size: 8.5pt; font-weight: bold; }}
/* Every fixed-format cell is nowrap. A printer page is laid out at the
   printer's own resolution, not the screen's, so the exact width a label gets
   is not knowable here - and "Net Payable" / "Amt" broken over two lines is the
   difference between a bill and a mess. A nowrap cell claims its natural width
   and the table gives the slack to the columns that can take it. */
.key {{ font-weight: bold; font-size: 7pt; white-space: nowrap; }}
.colon {{ font-size: 7pt; white-space: nowrap;
          padding-left: 4px; padding-right: 4px; }}
.val {{ font-size: 7pt; }}
.tight {{ white-space: nowrap; }}
.th {{ font-weight: bold; font-size: 7pt; white-space: nowrap; }}
.td {{ font-size: 7pt; }}
.money {{ font-size: 7pt; white-space: nowrap; }}
.totlbl {{ font-size: 7pt; font-weight: bold; white-space: nowrap; }}
.boxlbl {{ font-size: 7pt; white-space: nowrap; }}
.signname {{ font-size: 7pt; font-weight: bold; white-space: nowrap; }}
.signrole {{ font-size: 7pt; font-weight: bold; white-space: nowrap; }}
.notehead {{ font-size: 6pt; font-weight: bold; }}
/* A shade smaller than the body: the standing terms are the longest lines on
   the bill and the least important, and one of them wrapping to a single
   orphaned word is the first thing the eye finds. */
.words {{ font-size: 7pt; }}
.note {{ font-size: 6pt; }}
"""


def _band(html: str, top: int = 0, bottom: int = 0) -> str:
    """One block of the bill, as a row of the page table.

    The space above and below is cell padding rather than a spacer element. Qt
    puts a minimum line box around any block it lays out, so every `<div>` or
    stray table used purely as a gap costs about five points whatever size it is
    asked for - and a dozen of those was eighty points, a fifth of an A5 slip.
    Padding on a cell has no such floor and is exact.
    """
    return (f'<tr><td style="padding-top:{top}px; padding-bottom:{bottom}px;">'
            f"{html}</td></tr>")


def build(report: Report, lab: LabProfile) -> str:
    """The whole bill as self-contained HTML, ready for preview, printer or PDF.

    A bill is read in blocks - who it is for, what was done, what it came to,
    what was paid - and the space between them is what tells the eye where one
    block ends. On an A5 slip that space has to be bought carefully, so it is
    spent where a block genuinely changes subject and nowhere else.
    """
    bands = [
        _band(letterhead(lab), bottom=2),
        _band(_hrule()),
        _band(_heading(report), top=2, bottom=2),
        _band(_hrule()),
        _band(_identity(report), top=2, bottom=2),
        _band(_hrule()),
        _band(_services(report), top=4),
        _band(_amount_words(report), top=3),
        _band(_closing(report), top=3),
    ]

    signatories = _signatories(report)
    if signatories:
        bands.append(_band(signatories, top=6))

    notes = _notes(lab)
    if notes:
        bands.append(_band(notes, top=5))

    foot = footer(lab)
    if foot:
        bands.append(_band(_hrule(), top=4))
        bands.append(_band(foot, top=2))

    # Everything sits inside one ruled rectangle - the slip is a form, and a form
    # has an edge. It also makes a short bill read as finished rather than as a
    # page that was cut off.
    page = _box(f'<tr><td>{_plain("".join(bands))}</td></tr>', border=1, padding=6)
    return f"<html><head><style>{CSS}</style></head><body>{page}</body></html>"
