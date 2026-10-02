"""Small helpers shared across the app."""
import re

# Characters Windows forbids in a filename, plus the control range.
_UNSAFE_CHARS = set('<>:"/|?*' + chr(92)) | {chr(c) for c in range(32)}

# Device names Windows reserves, with or without an extension.
_RESERVED_NAMES = ({"CON", "PRN", "AUX", "NUL"}
                   | {f"COM{i}" for i in range(1, 10)}
                   | {f"LPT{i}" for i in range(1, 10)})


def safe_filename(name: str, fallback: str = "report") -> str:
    """Make a string usable as a Windows filename.

    Patient names and report numbers end up in suggested PDF filenames, and a
    name like 'Baby of A/B Sharma' would otherwise be read as a folder path.
    Done with a character set rather than a regex class, because escaping a
    backslash inside a class is exactly the kind of thing that silently fails.
    """
    cleaned = "".join("-" if ch in _UNSAFE_CHARS else ch for ch in str(name or ""))
    cleaned = cleaned.replace(" ", "_")
    cleaned = re.sub(r"[-_]{2,}", lambda m: m.group(0)[0], cleaned).strip(" ._-")
    if not cleaned:
        return fallback
    # CON, PRN, NUL, COM1... are device names on Windows whatever extension
    # follows them: "NUL.pdf" silently writes nowhere. Prefixing the fallback
    # keeps the name recognisable while making it an ordinary file.
    if cleaned.split(".")[0].upper() in _RESERVED_NAMES:
        cleaned = f"{fallback}_{cleaned}"
    return cleaned
