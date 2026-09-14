"""Bill arithmetic: what the services cost, what was paid, what is still owed.

Money is Decimal, never float. A bill is a handful of two-decimal amounts added
together, and `0.1 + 0.2 = 0.30000000000000004` is not a number a patient should
ever read on a printed total.

Nothing here is stored. The report file keeps only what the operator typed - the
service lines, their amounts and the deposit - and every total is recomputed from
those, so a stored bill can never disagree with its own arithmetic. It also means
an amount corrected in a saved report re-totals correctly rather than keeping a
stale sum that was written next to it.

Blank is not zero. A service with no amount yet is *unpriced*: it contributes
nothing to the total instead of quietly billing zero, and it prints as a dash
rather than as a free test.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

from .models import BillItem, Billing

# The rupee sign; Segoe UI carries it, and the print path uses Segoe UI.
CURRENCY = "₹"

ZERO = Decimal("0.00")
_CENTS = Decimal("0.01")

# A lab bill that reaches eight digits is a typo, not a bill.
MAX_AMOUNT = Decimal("9999999.99")

# A bill carries the minute it was raised, not just the day: two bills for one
# patient on one morning have to be tellable apart at the counter.
BILL_DATE_FMT = "%d-%m-%Y %I:%M:%S %p"
BILL_QT_DATE_FMT = "dd-MM-yyyy hh:mm:ss AP"

# How it reads on the printed bill: "30-Aug-2026 10.43.30 AM". The month is
# spelled out because "30-08" and "08-30" are the same six characters, and the
# time is dotted the way the lab's own slip prints it.
BILL_PRINT_DATE_FMT = "%d-%b-%Y %I.%M.%S %p"

# The first build stored the day alone. Those bills still have to open.
_LEGACY_DATE_FMTS = ("%d-%m-%Y",)

# What kind of bill this is. Printed as the document's title and as its own row,
# exactly as on the lab's slip.
BILL_TYPES = ("Cash Bill", "Credit Bill", "Insurance Bill")
DEFAULT_BILL_TYPE = BILL_TYPES[0]

# The standing terms every lab receipt carries. Offered as the starting value on
# the Laboratory Profile so a bill is never printed with an empty footer; the lab
# edits them to suit, and clearing the box and saving prints no notes at all.
DEFAULT_BILL_NOTES = "\n".join((
    "Please bring receipt while collecting the report",
    "Beyond 01 month reports will not be preserved",
    "All culture reports after 3-4 days",
    "Working Hours : Weekdays : 7.00 am to 9.00 pm  Sundays / Holidays : "
    "7.00 am to 1.00 pm",
))


def format_bill_date(stored: str) -> str:
    """The stored timestamp rendered for print.

    Anything unparseable - a hand-edited file, a format from some later build -
    is passed through as it stands. A bill that prints an odd-looking date is
    better than a bill that refuses to print, or one that quietly shows today.
    """
    from datetime import datetime

    text = (stored or "").strip()
    for fmt in (BILL_DATE_FMT,) + _LEGACY_DATE_FMTS:
        try:
            when = datetime.strptime(text, fmt)
        except ValueError:
            continue
        printed = when.strftime(BILL_PRINT_DATE_FMT)
        if fmt in _LEGACY_DATE_FMTS:
            # A day-only bill has no time; the midnight is an artefact of
            # parsing it, so it is dropped rather than printed as fact.
            printed = printed.replace(" 12.00.00 AM", "")
        return printed
    return text

# Rows typed by hand rather than loaded from a panel bill under one heading,
# the same one report_html groups them under.
DEFAULT_SERVICE = "Investigations"


# --------------------------------------------------------------------------
# amounts
# --------------------------------------------------------------------------
def parse_amount(value: Any) -> Optional[Decimal]:
    """A typed amount as a Decimal, or None when it is not one.

    Blank returns None too: the caller decides whether an empty box means zero
    (adding up a total) or means nothing at all (validating what was typed).
    """
    text = str(value if value is not None else "").strip()
    if text.startswith(CURRENCY):
        text = text[len(CURRENCY):].strip()
    text = text.replace(",", "").replace(" ", "")
    if not text:
        return None
    try:
        amount = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    if not amount.is_finite():
        return None
    return amount.quantize(_CENTS, rounding=ROUND_HALF_UP)


def amount_or_zero(value: Any) -> Decimal:
    """The amount, treating blank or unusable input as nothing owed."""
    parsed = parse_amount(value)
    return ZERO if parsed is None else parsed


def format_amount(value: Any) -> str:
    """`1234.5` -> `1,234.50`. Always two decimals, so a column of them lines up."""
    if not isinstance(value, Decimal):
        value = amount_or_zero(value)
    return f"{value:,.2f}"


def format_money(value: Any) -> str:
    """The same, carrying the currency sign, for anywhere a figure stands alone."""
    return f"{CURRENCY} {format_amount(value)}"


# --------------------------------------------------------------------------
# what is billable
# --------------------------------------------------------------------------
def billable_services(rows: List[Any]) -> List[str]:
    """The service lines a bill is made of, in the order they print.

    One line per panel, not one per test: a lab bills for "CBC", not for each of
    its fifteen components. Derived from the result rows rather than from the
    ticked-panel list, and grouped exactly the way `report_html` groups its
    tables, so the bill and the results always describe the same work.
    """
    services: List[str] = []
    for row in rows:
        name = (getattr(row, "panel", "") or DEFAULT_SERVICE)
        if name not in services:
            services.append(name)
    return services


def sync_items(billing: Billing, rows: List[Any]) -> List[BillItem]:
    """Rebuild the bill lines from the current results, keeping every amount
    already typed against a service that is still there.

    This is what makes ticking and unticking a panel safe: the new line arrives
    unpriced, the removed line takes its amount with it, and nothing else on the
    bill moves.
    """
    priced = {item.service: item.amount for item in billing.items}
    return [BillItem(service=name, amount=priced.get(name, ""))
            for name in billable_services(rows)]


# --------------------------------------------------------------------------
# the totals
# --------------------------------------------------------------------------
def total_billed(billing: Billing) -> Decimal:
    """Sum of the priced service lines."""
    return sum((amount_or_zero(item.amount) for item in billing.items), ZERO)


def net_payable(billing: Billing) -> Decimal:
    """What the patient owes before anything they have already paid.

    Equal to the total billed: discounts, tax and insurance are out of scope for
    this build, so there is nothing configured to adjust it. The function exists
    anyway so that when an adjustment is specified there is exactly one place it
    has to be applied, rather than a dozen call sites summing their own totals.
    """
    return total_billed(billing)


def deposit(billing: Billing) -> Decimal:
    """What has been paid against the bill. Blank means nothing has."""
    return amount_or_zero(billing.net_deposit)


def balance(billing: Billing) -> Decimal:
    """Still outstanding: net payable less what was deposited."""
    return net_payable(billing) - deposit(billing)


def summary(billing: Billing) -> Dict[str, Decimal]:
    """All four figures in one pass, so the screen and the printout cannot drift."""
    payable = net_payable(billing)
    paid = deposit(billing)
    return {
        "total_billed": total_billed(billing),
        "net_payable": payable,
        "net_deposit": paid,
        "balance": payable - paid,
    }


def has_content(billing: Billing) -> bool:
    """True when the bill has something worth printing.

    An untouched bill - a generated number and date, no amounts, no deposit -
    is not a bill. Checked before every bill action so a lab that does not use
    billing is told there is nothing to print, rather than handed a blank slip
    with a letterhead on it.
    """
    if billing is None:
        return False
    if parse_amount(billing.net_deposit) is not None:
        return True
    return any(parse_amount(item.amount) is not None for item in billing.items)


# --------------------------------------------------------------------------
# amounts in words
# --------------------------------------------------------------------------
# Indian grouping - crore, lakh, thousand - because that is how a bill is read
# aloud here. "1040" is "One Thousand Forty", never "One Zero Four Zero".
_ONES = ("", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight",
         "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen",
         "Sixteen", "Seventeen", "Eighteen", "Nineteen")
_TENS = ("", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy",
         "Eighty", "Ninety")

# Largest unit first; each is written only when its slice is non-zero.
_SCALE = ((10_000_000, "Crore"), (100_000, "Lakh"), (1_000, "Thousand"))


def _under_hundred(n: int) -> str:
    if n < 20:
        return _ONES[n]
    return " ".join(part for part in (_TENS[n // 10], _ONES[n % 10]) if part)


def _under_thousand(n: int) -> str:
    if n < 100:
        return _under_hundred(n)
    rest = _under_hundred(n % 100)
    return f"{_ONES[n // 100]} Hundred" + (f" {rest}" if rest else "")


def _whole_in_words(n: int) -> str:
    parts = []
    for size, name in _SCALE:
        slice_, n = divmod(n, size)
        if slice_:
            parts.append(f"{_under_thousand(slice_)} {name}")
    if n:
        parts.append(_under_thousand(n))
    return " ".join(parts)


def amount_in_words(value: Any) -> str:
    """`1040` -> `One Thousand Forty Rupees Only`.

    A bill states the paid amount in words as well as figures, because a figure
    can be altered after the fact with one pen stroke and a sentence cannot.
    """
    amount = amount_or_zero(value)
    sign = "Minus " if amount < 0 else ""
    amount = abs(amount)
    rupees = int(amount)
    paise = int((amount - rupees) * 100)

    words = []
    if rupees or not paise:
        # Singular matters: a bill that reads "One Rupees Only" looks machine-made.
        words.append(f"{_whole_in_words(rupees) or 'Zero'} "
                     f"{'Rupee' if rupees == 1 else 'Rupees'}")
    if paise:
        words.append(f"{'and ' if rupees else ''}{_whole_in_words(paise)} "
                     f"{'Paisa' if paise == 1 else 'Paise'}")
    return sign + " ".join(words) + " Only"
