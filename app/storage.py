"""Local-storage layer: JSON files under %APPDATA%\BloodReportApp plus an in-memory cache.

Deliberately no database. Every write is atomic (write .tmp then os.replace) so an
interrupted save can never leave a half-written report behind.
"""
import json
import os
import shutil
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from .billing import BILL_DATE_FMT
from .branding import DATA_FOLDER
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
        last_patient = max(last_patient, _serial(entry.get("patient_id"), "PID-"))
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
        candidate = f"PID-{n:06d}"
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
        candidate = f"PID-{c['last_patient']:06d}"
        if candidate not in used:
            _write_json(_p("counter.json"), c)
            return candidate


def new_report_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]


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
