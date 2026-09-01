"""Input rules for the form fields.

Two layers, deliberately:

* Qt validators stop the wrong *characters* from ever being typed or pasted -
  a letter in the age box, a digit in a patient's name.
* check_* functions run at save time for the rules a character filter cannot
  express: "is this age plausible for its unit", "is this actually an email".

Result values are deliberately NOT restricted to numbers. Pathology results are
routinely qualitative - "Nil", "Absent", "Trace", "Positive", "<0.01" - and a
numbers-only rule there would make the app unable to report a normal urine
deposit or a negative serology.
"""
import re
from typing import Optional, Tuple

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator

from .billing import MAX_AMOUNT, parse_amount

# --------------------------------------------------------------------------
# character-level patterns
# --------------------------------------------------------------------------
# Letters, spaces and the punctuation real names use: "M. K. Sharma",
# "D'Souza", "Baby of Sunita", "Rao-Naidu". No digits.
NAME_PATTERN = r"[A-Za-z][A-Za-z .'\-]*"

# Same, but allowed to start with the honorific dot people type: ".Dr" is odd
# but harmless, and blocking the first keystroke is worse.
DOCTOR_PATTERN = r"[A-Za-z][A-Za-z .'\-]*"

DIGITS_PATTERN = r"\d{0,3}"

# Indian numbers only: exactly ten national digits, written with the +91 country
# code. Landlines fit the same rule once the trunk 0 is dropped - 0821 2529999
# is the ten digits 8212529999 - so one rule covers both.
#
# The typing filter stays loose (a plus, digits, spaces, hyphens) because people
# paste numbers in every shape there is. The count is enforced on save, where the
# message can explain itself, and `normalise_phone` puts whatever was typed into
# one form so the stored and printed number never varies.
PHONE_PATTERN = r"\+?[0-9][0-9 \-]*"
PHONE_DIGITS = 10
PHONE_CC = "91"
MAX_PHONE = 18
EMAIL_PATTERN = r"[^@\s]+@?[^@\s]*"
REG_NO_PATTERN = r"[A-Za-z0-9][A-Za-z0-9 /\-.]*"
SAMPLE_PATTERN = r"[A-Za-z][A-Za-z /\-]*"

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+\.[^@\s]+$")

# Plausible upper bound per age unit. Generous on purpose - these exist to catch
# a slipped keystroke ("340" years), not to argue with the operator.
AGE_LIMITS = {"Y": 130, "M": 36, "D": 400}
AGE_UNIT_NAMES = {"Y": "years", "M": "months", "D": "days"}


def validator(pattern: str, parent=None) -> QRegularExpressionValidator:
    """A Qt validator that accepts the whole string against `pattern`."""
    return QRegularExpressionValidator(QRegularExpression(f"^(?:{pattern})$"), parent)


# --------------------------------------------------------------------------
# save-time checks: each returns None when fine, or an error message
# --------------------------------------------------------------------------
def check_person_name(value: str, label: str = "patient name") -> Optional[str]:
    text = (value or "").strip()
    if not text:
        return f"Enter the {label}."
    if len(re.sub(r"[^A-Za-z]", "", text)) < 2:
        return f"The {label} needs at least two letters."
    if re.search(r"\d", text):
        return f"The {label} cannot contain numbers."
    return None


def check_age(value: str, unit: str) -> Optional[str]:
    text = (value or "").strip()
    if not text:
        return "Enter the patient's age."
    if not text.isdigit():
        return "Age must be a whole number."
    limit = AGE_LIMITS.get(unit, AGE_LIMITS["Y"])
    if int(text) > limit:
        return (f"Age looks wrong: {text} {AGE_UNIT_NAMES.get(unit, 'years')} "
                f"(maximum {limit}). Check the unit next to the age.")
    return None


def check_optional_name(value: str, label: str) -> Optional[str]:
    """For fields that may be left blank, such as the referring doctor."""
    text = (value or "").strip()
    if not text:
        return None
    return check_person_name(text, label)


def check_email(value: str) -> Optional[str]:
    text = (value or "").strip()
    if not text:
        return None
    if not _EMAIL_RE.match(text):
        return "That email address does not look valid."
    return None


# Longest first: 0091... has to be recognised before 91... or 0...
_PHONE_PREFIXES = ("00" + PHONE_CC, "0" + PHONE_CC, PHONE_CC, "0")


def phone_digits(value: str) -> Optional[str]:
    """The ten national digits behind whatever was typed, or None if there is no
    valid Indian number in it.

    A prefix is only stripped when the length says it is one. That matters:
    `9198765432` is a perfectly good ten-digit mobile that happens to start with
    the country code, and it must not be read as `+91 98765432`.
    """
    digits = re.sub(r"\D", "", str(value or ""))
    for prefix in _PHONE_PREFIXES:
        if len(digits) == PHONE_DIGITS + len(prefix) and digits.startswith(prefix):
            digits = digits[len(prefix):]
            break
    return digits if len(digits) == PHONE_DIGITS else None


def normalise_phone(value: str) -> str:
    """One stored and printed form: `+91 9845012345`.

    Anything unrecognised is handed back untouched rather than mangled - saving
    is blocked separately, and a number the app cannot read should still be
    visible in the box so the operator can see what to fix.
    """
    digits = phone_digits(value)
    return f"+{PHONE_CC} {digits}" if digits else (value or "").strip()


def check_phone(value: str, label: str = "phone number") -> Optional[str]:
    """Blank is allowed - every phone field in the app is optional. Anything
    else has to be a full Indian number: ten digits, no more and no fewer."""
    text = (value or "").strip()
    if not text:
        return None
    if phone_digits(text) is None:
        count = len(re.sub(r"\D", "", text))
        return (f"That {label} is not a valid Indian number: it has {count} "
                f"digit{'s' if count != 1 else ''}, and it needs exactly "
                f"{PHONE_DIGITS}. Enter it as +91 9845012345, or as "
                "9845012345 - a landline drops its leading 0.")
    return None


def check_result_value(value: str) -> Optional[str]:
    """Results may be numeric or qualitative; only obvious junk is rejected."""
    text = (value or "").strip()
    if not text:
        return None
    if len(text) > 40:
        return "Result is too long to fit the report."
    return None


def first_error(*checks: Optional[str]) -> Optional[str]:
    """Return the first failing check, so the operator fixes one thing at a time."""
    for message in checks:
        if message:
            return message
    return None


def is_number(value: str) -> Tuple[bool, float]:
    try:
        return True, float(str(value).strip())
    except (TypeError, ValueError):
        return False, 0.0


# --------------------------------------------------------------------------
# results grid and templates
# --------------------------------------------------------------------------
# Units are symbols, not prose: "g/dL", "%", "/cmm", "mm/1st hr", "uIU/mL".
# Digits are allowed because of forms like "mm/1st hr" and "10^3/uL".
UNIT_PATTERN = r"[A-Za-z0-9%/^][A-Za-z0-9%/^.,\-() ]*"

# A test or panel name: words, numbers and the punctuation lab names use -
# "SGOT / AST", "Vitamin B-12", "T3 (Total)", "25-OH Vitamin D".
TEST_NAME_PATTERN = r"[A-Za-z0-9][A-Za-z0-9 .,'()/+%\-]*"

# A line of prose: an address, a qualification, a footer note.
TEXT_LINE_PATTERN = r"[A-Za-z0-9][A-Za-z0-9 .,'()/&:;+#\-]*"

_NUM_RANGE = re.compile(
    r"^\s*-?\d+(?:\.\d+)?\s*(?:-|to|–|—)\s*-?\d+(?:\.\d+)?\s*$", re.I)
_NUM_BOUND = re.compile(r"^\s*(?:<|<=|>|>=|≤|≥)\s*-?\d+(?:\.\d+)?\s*$")
_WORDS_ONLY = re.compile(r"^[A-Za-z][A-Za-z \-]*$")

MAX_UNIT = 20
MAX_TEST_NAME = 60
MAX_REFERENCE = 30
MAX_TEXT_LINE = 120
MAX_REMARKS = 300


def check_unit(value: str) -> Optional[str]:
    """Units are optional (a ratio has none) but must look like a unit."""
    text = (value or "").strip()
    if not text:
        return None
    if len(text) > MAX_UNIT:
        return f"Unit is too long (limit {MAX_UNIT} characters)."
    if not re.match(f"^(?:{UNIT_PATTERN})$", text):
        return f"'{text}' is not a valid unit. Use forms like g/dL, %, /cmm or U/L."
    # Digits may start a unit ("10^3/uL"), but a bare number is not one.
    if not re.search(r"[A-Za-z%/]", text):
        return f"'{text}' is not a unit - it is just a number."
    return None


def check_reference(value: str) -> Optional[str]:
    """A reference range must be a real range, a bound, or a qualitative term.

    Numeric ranges are the point of the field - they drive the H/L flagging -
    so anything numeric has to parse. Purely qualitative ranges are allowed
    because tests like 'Protein: Absent' or 'Colour: Pale yellow' have no
    numbers at all. What is rejected is the mixture in between: '13 abc',
    '12 -', 'about 200' - text that looks numeric but cannot be checked, and
    would silently never flag an abnormal result.
    """
    text = (value or "").strip()
    if not text:
        return None
    if len(text) > MAX_REFERENCE:
        return f"Reference range is too long (limit {MAX_REFERENCE} characters)."
    if _NUM_RANGE.match(text) or _NUM_BOUND.match(text):
        return None
    if _WORDS_ONLY.match(text):
        return None
    return (f"'{text}' is not a usable reference range. Use a range like "
            "'13.0 - 17.0', a limit like '< 200', or a word like 'Absent'.")


def check_test_name(value: str, label: str = "test name") -> Optional[str]:
    text = (value or "").strip()
    if not text:
        return f"Enter the {label}."
    if len(text) > MAX_TEST_NAME:
        return f"The {label} is too long (limit {MAX_TEST_NAME} characters)."
    if not re.match(f"^(?:{TEST_NAME_PATTERN})$", text):
        return f"'{text}' is not a valid {label}."
    return None


def check_text_line(value: str, label: str, limit: int = MAX_TEXT_LINE) -> Optional[str]:
    """For optional prose: address lines, qualifications, footer notes."""
    text = (value or "").strip()
    if not text:
        return None
    if len(text) > limit:
        return f"{label} is too long (limit {limit} characters)."
    if any(ord(ch) < 32 for ch in text):
        return f"{label} contains characters that cannot be printed."
    return None


def is_numeric_reference(value: str) -> bool:
    """True when a range will actually drive H / L flagging."""
    text = (value or "").strip()
    return bool(_NUM_RANGE.match(text) or _NUM_BOUND.match(text))


# --------------------------------------------------------------------------
# billing
# --------------------------------------------------------------------------
# Amounts are typed, not calculated, so the character filter does the heavy
# lifting: digits and at most one decimal point with at most two places after
# it. No currency sign, no thousands separator, no minus - a negative charge is
# a refund, and refunds are out of scope.
AMOUNT_PATTERN = r"\d{0,7}(?:\.\d{0,2})?"

# A bill number the lab types itself: "C-1042", "2026/0117", "CASH 88".
BILL_NO_PATTERN = r"[A-Za-z0-9][A-Za-z0-9 /\-]*"
MAX_BILL_NO = 24


def check_amount(value: str, label: str = "amount") -> Optional[str]:
    """Blank is allowed: it means the service has not been priced, not that it
    is free. Anything else has to be a number the bill can add up."""
    text = (value or "").strip()
    if not text:
        return None
    amount = parse_amount(text)
    if amount is None:
        return (f"'{text}' is not a valid {label}. "
                "Enter a number such as 350 or 350.00.")
    if amount < 0:
        return f"The {label} cannot be negative."
    if amount > MAX_AMOUNT:
        return f"The {label} is too large (maximum {MAX_AMOUNT:,.2f})."
    return None


def check_bill_no(value: str) -> Optional[str]:
    """Blank is allowed - the app generates one on save."""
    text = (value or "").strip()
    if not text:
        return None
    if len(text) > MAX_BILL_NO:
        return f"The bill number is too long (limit {MAX_BILL_NO} characters)."
    if not re.match(f"^(?:{BILL_NO_PATTERN})$", text):
        return (f"'{text}' is not a valid bill number. Use letters, digits, "
                "spaces and / or -.")
    return None


MAX_BILL_NOTES = 6
MAX_BILL_NOTE = 150


def check_bill_notes(value: str) -> Optional[str]:
    """The standing terms at the foot of the bill: one per line, and few enough
    that they still fit under the figures rather than pushing them onto page 2."""
    lines = [line.strip() for line in (value or "").splitlines() if line.strip()]
    if len(lines) > MAX_BILL_NOTES:
        return (f"That is {len(lines)} bill notes; the bill has room for "
                f"{MAX_BILL_NOTES}.")
    for i, line in enumerate(lines, start=1):
        problem = check_text_line(line, f"Bill note {i}", MAX_BILL_NOTE)
        if problem:
            return problem
    return None
