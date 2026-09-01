"""The edit password that guards saved reports.

How the password is validated
-----------------------------
The password itself is never stored. On set-up the app generates 16 random
bytes of salt and runs the password through PBKDF2-HMAC-SHA256 for 260,000
iterations; the salt, the iteration count and the resulting hash go into
security.json. Checking a password repeats that computation with the stored
salt and compares the two hashes with `hmac.compare_digest`, which takes the
same time whether the first byte differs or the last - an ordinary `==` leaks
how much of the guess was right.

Storing the iteration count alongside the hash means the cost can be raised
later without locking anyone out: an old record simply verifies at its own
recorded cost.

What this does and does not protect
-----------------------------------
It stops someone at the counter quietly altering or deleting a finished report -
which is the real risk in a lab, where a printed report is a medical record.

It is NOT protection against someone with real access to the machine: the
reports are plain JSON in %APPDATA% and anyone who can read that folder can edit
them with Notepad. Encrypting them would mean a forgotten password destroys
every report, which is far worse for a small lab than the risk it removes. Use
a Windows account password if you need protection at that level.
"""
import hashlib
import hmac
import os
from typing import Optional

from . import storage

FILENAME = "security.json"
ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 260_000
SALT_BYTES = 16
MIN_LENGTH = 4


def _path() -> str:
    return os.path.join(storage.app_dir(), FILENAME)


def _derive(password: str, salt: bytes, iterations: int) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations).hex()


# --------------------------------------------------------------------------
def is_set() -> bool:
    record = storage._read_json(_path(), None)
    return isinstance(record, dict) and bool(record.get("hash"))


def set_password(password: str) -> Optional[str]:
    """Store a new password. Returns an error message, or None on success."""
    problem = check_strength(password)
    if problem:
        return problem
    salt = os.urandom(SALT_BYTES)
    storage._write_json(_path(), {
        "algorithm": ALGORITHM,
        "iterations": ITERATIONS,
        "salt": salt.hex(),
        "hash": _derive(password, salt, ITERATIONS),
    })
    return None


def check_strength(password: str) -> Optional[str]:
    if not password:
        return "Enter a password."
    if len(password) < MIN_LENGTH:
        return f"The password must be at least {MIN_LENGTH} characters."
    return None


def verify(password: str) -> bool:
    """True when `password` matches the stored one. False if none is set."""
    record = storage._read_json(_path(), None)
    if not isinstance(record, dict) or not record.get("hash"):
        return False
    try:
        salt = bytes.fromhex(str(record.get("salt", "")))
        iterations = int(record.get("iterations", ITERATIONS))
    except (ValueError, TypeError):
        return False
    if not salt or iterations < 1:
        return False

    candidate = _derive(password, salt, iterations)
    return hmac.compare_digest(candidate, str(record.get("hash", "")))


def change_password(current: str, new: str) -> Optional[str]:
    """Change the password, proving knowledge of the current one first."""
    if is_set() and not verify(current):
        return "The current password is not correct."
    return set_password(new)


def clear_password() -> None:
    """Remove the password entirely, leaving reports unprotected."""
    try:
        os.remove(_path())
    except OSError:
        pass
