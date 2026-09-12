r"""Local-storage layer: JSON files under %APPDATA%\BloodReportApp plus an in-memory cache.

Deliberately no database. Every write is atomic (write .tmp then os.replace) so an
interrupted save can never leave a half-written report behind.
"""
import json
import os
import shutil
import uuid
import re
import string
from datetime import datetime
from typing import Any, Dict, List, Optional

from .billing import BILL_DATE_FMT
from .branding import DATA_FOLDER, PATIENT_ID_PREFIX
from .models import LabProfile, Report


def app_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, DATA_FOLDER)


def reports_dir() -> str:
    return os.path.join(app_dir(), "reports")


def assets_dir() -> str:
    return os.path.join(app_dir(), "assets")


def _p(name: str) -> str:
    return os.path.join(app_dir(), name)


def ensure_dirs() -> None:
    for d in (app_dir(), reports_dir(), assets_dir()):
        os.makedirs(d, exist_ok=True)


def _read_json(path: str, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _write_json(path: str, data: Any) -> None:
    ensure_dirs()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


# --------------------------------------------------------------------------
# cache
# --------------------------------------------------------------------------
_cache: Dict[str, Any] = {"profile": None, "index": None}


def clear_cache() -> None:
    _cache["profile"] = None
    _cache["index"] = None


# --------------------------------------------------------------------------
# lab profile
# --------------------------------------------------------------------------
def load_profile() -> LabProfile:
    if _cache["profile"] is None:
        _cache["profile"] = LabProfile.from_dict(_read_json(_p("lab_profile.json"), {}))
    return _cache["profile"]


def save_profile(profile: LabProfile) -> None:
    _write_json(_p("lab_profile.json"), profile.to_dict())
    _cache["profile"] = profile


def import_asset(src_path: str, kind: str) -> str:
    """Copy a chosen logo/signature into assets/ so the report survives the
    original file being moved or deleted. Returns the stored path."""
    ensure_dirs()
    ext = os.path.splitext(src_path)[1].lower() or ".png"
    dest = os.path.join(assets_dir(), f"{kind}{ext}")
    for old in os.listdir(assets_dir()):
        if os.path.splitext(old)[0] == kind and os.path.join(assets_dir(), old) != dest:
            try:
                os.remove(os.path.join(assets_dir(), old))
            except OSError:
                pass
    if os.path.abspath(src_path) != os.path.abspath(dest):
        shutil.copyfile(src_path, dest)
    return dest


# --------------------------------------------------------------------------
# report numbering
# --------------------------------------------------------------------------
def _serial(value: str, prefix: str) -> int:
    """'BR-000042' -> 42; anything unrecognised -> 0."""
    text = str(value or "")
    if not text.startswith(prefix):
        return 0
    try:
        return int(text[len(prefix):])
    except ValueError:
        return 0


def _counters() -> Dict[str, int]:
    """Counter file values, raised to at least the highest serial already stored.

    counter.json is only a fast path. If it is lost or restored from a stale
    backup, falling back to it alone would hand out serials that are already in
    use, so the index is treated as the floor."""
    data = _read_json(_p("counter.json"), {})
    if not isinstance(data, dict):
        data = {}
    try:
        last = int(data.get("last", 0))
    except (TypeError, ValueError):
        last = 0
    try:
        last_patient = int(data.get("last_patient", 0))
    except (TypeError, ValueError):
        last_patient = 0
    try:
        last_bill = int(data.get("last_bill", 0))
    except (TypeError, ValueError):
        last_bill = 0

    index = load_index()
    for entry in index:
        last = max(last, _serial(entry.get("report_no"), "BR-"))
        # Both prefixes are floored: IDs handed out as PID- before the rename
        # still occupy their numbers, so the sequence carries on rather than
        # restarting at 1 under the new prefix.
        for prefix in (PATIENT_ID_PREFIX, "PID-"):
            last_patient = max(last_patient, _serial(entry.get("patient_id"), prefix))
        last_bill = max(last_bill, _serial(entry.get("bill_no"), "BILL-"))
    return {"last": last, "last_patient": last_patient, "last_bill": last_bill}


def next_report_no() -> str:
    c = _counters()
    c["last"] += 1
    _write_json(_p("counter.json"), c)
    return f"BR-{c['last']:06d}"


def peek_report_no() -> str:
    return f"BR-{_counters()['last'] + 1:06d}"


def next_bill_no() -> str:
    """Reserve the next bill number. Floored by the index like the others, so a
    hand-typed bill number that happens to match the generated form can never be
    handed out twice."""
    c = _counters()
    c["last_bill"] += 1
    _write_json(_p("counter.json"), c)
    return f"BILL-{c['last_bill']:06d}"


def peek_bill_no() -> str:
    return f"BILL-{_counters()['last_bill'] + 1:06d}"


def _known_patient_ids() -> set:
    return {str(e.get("patient_id", "")) for e in load_index() if e.get("patient_id")}


def peek_patient_id() -> str:
    """The ID a new patient would get, shown in the form before it is committed."""
    used = _known_patient_ids()
    n = _counters()["last_patient"]
    while True:
        n += 1
        candidate = f"{PATIENT_ID_PREFIX}{n:06d}"
        if candidate not in used:
            return candidate


def next_patient_id() -> str:
    """Reserve and return a patient ID that is not already used by any stored report.
    The counter is the fast path; the index is checked so a restored backup or a
    hand-edited report can never cause a collision."""
    used = _known_patient_ids()
    c = _counters()
    while True:
        c["last_patient"] += 1
        candidate = f"{PATIENT_ID_PREFIX}{c['last_patient']:06d}"
        if candidate not in used:
            _write_json(_p("counter.json"), c)
            return candidate


def new_report_id() -> str:
    """A fresh id: a timestamp (so the files sort by day) and enough random
    hex that two reports saved in the same second cannot share one - and a
    check on disk, so even a repeat is caught rather than overwriting."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-")
    while True:
        candidate = stamp + uuid.uuid4().hex[:8]
        if not os.path.exists(os.path.join(reports_dir(), candidate + ".json")):
            return candidate


# --------------------------------------------------------------------------
# index + reports
# --------------------------------------------------------------------------
def load_index() -> List[Dict[str, Any]]:
    if _cache["index"] is None:
        idx = _read_json(_p("index.json"), None)
        if not isinstance(idx, list):
            idx = rebuild_index()
        _cache["index"] = idx
    return _cache["index"]


def _save_index(idx: List[Dict[str, Any]]) -> None:
    idx.sort(key=lambda e: e.get("created_at", ""), reverse=True)
    _write_json(_p("index.json"), idx)
    _cache["index"] = idx


def rebuild_index() -> List[Dict[str, Any]]:
    """Recover the history list by reading every stored report. Used when
    index.json is missing or corrupt."""
    ensure_dirs()
    entries: List[Dict[str, Any]] = []
    for fn in os.listdir(reports_dir()):
        if not fn.endswith(".json"):
            continue
        data = _read_json(os.path.join(reports_dir(), fn), None)
        if isinstance(data, dict):
            entries.append(Report.from_dict(data).index_entry())
    entries.sort(key=lambda e: e.get("created_at", ""), reverse=True)
    _write_json(_p("index.json"), entries)
    _cache["index"] = entries
    return entries


def save_report(report: Report) -> Report:
    ensure_dirs()
    if not report.id:
        report.id = new_report_id()
    if not report.created_at:
        report.created_at = datetime.now().isoformat(timespec="seconds")
    if not report.report_no:
        report.report_no = next_report_no()
    if not report.patient_id:
        report.patient_id = next_patient_id()
    # Every report gets a bill reference, whether or not it carries amounts:
    # it is the number the lab quotes when the patient asks about the bill, and
    # allocating it on save keeps it in step with the report number.
    if not report.billing.bill_no:
        report.billing.bill_no = next_bill_no()
    if not report.billing.bill_date:
        report.billing.bill_date = datetime.now().strftime(BILL_DATE_FMT)
    _write_json(os.path.join(reports_dir(), report.id + ".json"), report.to_dict())

    idx = [e for e in load_index() if e.get("id") != report.id]
    idx.append(report.index_entry())
    _save_index(idx)
    return report


# --------------------------------------------------------------------------
# backup to a synced folder (Google Drive for desktop, OneDrive, ...)
# --------------------------------------------------------------------------
# Google Drive for desktop mounts the account as a drive letter holding
# "My Drive", or (older installs / mirror mode) as a folder under the profile.
_DRIVE_ROOT_NAMES = ("My Drive", "Google Drive")


def find_google_drive() -> str:
    """The local folder Google Drive for desktop syncs, or "" if there is none.

    Looked for rather than asked about: the operator at a lab counter does not
    know where Drive keeps its folder, but they do know whether it is installed."""
    candidates: List[str] = []
    home = os.path.expanduser("~")
    for letter in string.ascii_uppercase:
        candidates.append(f"{letter}:\\My Drive")
    for name in _DRIVE_ROOT_NAMES:
        candidates.append(os.path.join(home, name))
    for path in candidates:
        if os.path.isdir(path):
            return path
    return ""


def is_google_drive_path(path: str) -> bool:
    parts = [part.lower() for part in re.split(r"[\\/]+", path or "")]
    return any(name.lower() in parts for name in _DRIVE_ROOT_NAMES)


def check_backup_dir(path: str) -> Optional[str]:
    """Why this folder cannot be used for backup, or None if it can.

    A blank means 'no backup' and is always fine. Otherwise the folder must
    exist (or be creatable) and be writable now, so a typo is caught at Save
    Profile rather than silently losing every backup afterwards."""
    path = (path or "").strip()
    if not path:
        return None
    # A relative path would land somewhere different depending on how the app
    # was started (run.bat vs the exe), so only a full path is accepted.
    if not os.path.isabs(path):
        return "Give the full path of the backup folder, e.g. G:\\My Drive\\Lably."
    own = os.path.normcase(os.path.abspath(app_dir()))
    given = os.path.normcase(os.path.abspath(path))
    if given == own or given.startswith(own + os.sep):
        return "The backup folder must be outside the app's own data folder."
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".lably-write-test")
        with open(probe, "w", encoding="utf-8") as fh:
            fh.write("ok")
        os.remove(probe)
    except (OSError, ValueError) as exc:
        return f"Cannot write to the backup folder: {getattr(exc, 'strerror', None) or exc}"
    return None


def backup_dir() -> str:
    return (load_profile().backup_dir or "").strip()


def should_ask_for_backup() -> bool:
    """Whether Save should offer Google Drive: no folder chosen yet, and the
    operator has not told the app to stop asking."""
    profile = load_profile()
    return not (profile.backup_dir or "").strip() and profile.backup_declined != "1"


def set_backup_dir(path: str) -> None:
    profile = load_profile()
    profile.backup_dir = path.strip()
    profile.backup_declined = ""
    save_profile(profile)


def decline_backup_prompt() -> None:
    profile = load_profile()
    profile.backup_declined = "1"
    save_profile(profile)


DRIVE_DOWNLOAD_URL = "https://www.google.com/drive/download/"
DRIVE_WEB_URL = "https://drive.google.com/"


def open_backup_folder() -> bool:
    """Show the backup folder in Explorer, creating it if it is not there yet.
    Returns False when backup is off or the folder cannot be reached."""
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices

    folder = backup_dir()
    if not folder:
        return False
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError:
        return False
    return QDesktopServices.openUrl(QUrl.fromLocalFile(folder))


def backup_month_dir(folder: str, report: Report) -> str:
    """Where this report's copies live: <folder>\\2026\\09-September.

    One folder per year, one per month inside it, so a year of reports in
    Drive is a dozen folders rather than a few thousand files - and the month
    is what a lab remembers when a patient comes back asking for a copy. The
    month is the one the report was made in, so a report never moves once
    filed, even if it is edited later."""
    when = None
    try:
        when = datetime.fromisoformat(report.created_at)
    except (TypeError, ValueError):
        pass
    if when is None:
        when = datetime.now()
    return os.path.join(folder, f"{when:%Y}", f"{when:%m-%B}")


def backup_name(report: Report) -> str:
    """A file name a person can find in Drive: report number and patient name,
    reduced to characters every filesystem and sync client accepts."""
    name = re.sub(r"[^A-Za-z0-9]+", "-", report.patient_name).strip("-")
    stem = "-".join(part for part in (report.report_no, name) if part)
    return stem or report.id


def _stale_backup_stems(folder: str, report: Report) -> List[str]:
    """Names (without extension) of earlier copies of *this* report in the
    backup folder that no longer match its current name.

    The file is named after the patient, so correcting a misspelt name and
    saving again would otherwise leave both spellings in Drive - and the wrong
    one is the one somebody will eventually send out. A candidate has to start
    with the report number *and* carry this report's own id inside, so a copy
    from another PC that happens to reuse the number is never touched."""
    keep = backup_name(report)
    prefix = report.report_no + "-"
    if not report.report_no:
        return []
    stale = []
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    for name in names:
        stem, ext = os.path.splitext(name)
        if ext != ".json" or stem == keep or not stem.startswith(prefix):
            continue
        data = _read_json(os.path.join(folder, name), None)
        if isinstance(data, dict) and data.get("id") == report.id:
            stale.append(stem)
    return stale


def _remove_quietly(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def backup_copy(report: Report) -> Optional[str]:
    """Copy the report's data file into its month folder under the backup
    folder, retiring any copy of the same report saved under an earlier name
    (and its PDF twin).

    The PDF sits directly in the month folder - that is what the lab browses
    in Drive - and the data file, which only the app reads, in `data` under
    it. Returns the month folder written to, or None when backup is off or
    unwritable. Never raises: a missing USB stick or a paused Drive must not
    stop the report saving on this PC - the local file is the record, the
    copy is a convenience."""
    folder = backup_dir()
    if not folder:
        return None
    try:
        month = backup_month_dir(folder, report)
        dest = os.path.join(month, "data")
        os.makedirs(dest, exist_ok=True)
        for stem in _stale_backup_stems(dest, report):
            _remove_quietly(os.path.join(dest, stem + ".json"))
            _remove_quietly(os.path.join(month, stem + ".pdf"))
        shutil.copyfile(os.path.join(reports_dir(), report.id + ".json"),
                        os.path.join(dest, backup_name(report) + ".json"))
        return month
    except OSError:
        return None


def load_report(report_id: str) -> Optional[Report]:
    data = _read_json(os.path.join(reports_dir(), report_id + ".json"), None)
    return Report.from_dict(data) if isinstance(data, dict) else None


def delete_reports(report_ids: List[str]) -> int:
    """Delete several reports in one pass, rewriting the index only once.
    Returns how many report files were actually removed."""
    targets = set(report_ids)
    removed = 0
    for report_id in targets:
        try:
            os.remove(os.path.join(reports_dir(), report_id + ".json"))
            removed += 1
        except OSError:
            pass
    _save_index([e for e in load_index() if e.get("id") not in targets])
    return removed


def delete_report(report_id: str) -> None:
    delete_reports([report_id])
