"""Editable test panels.

The six panels in `panels.py` are the shipped defaults. This module layers the
lab's own edits on top of them and adds any panels the lab creates, so the Test
Panels list in the form is whatever the lab last saved.

Only the differences are stored, never a full copy of the defaults. That way a
panel the lab has not touched still picks up any correction shipped in a later
version of the app, and "reset to default" is simply dropping the override.

A row is either a test or a sub-heading:

    {"kind": "test",    "name": "Haemoglobin (Hb)", "unit": "g/dL",
     "ref_m": "13.0 - 17.0", "ref_f": "12.0 - 15.0"}
    {"kind": "heading", "name": "DIFFERENTIAL COUNT"}

A heading carries no unit, range or result; it prints as a bold section title
inside the panel's table.
"""
import os
from typing import Any, Dict, List

from . import storage
from .panels import PANELS, resolve_ref

TEST, HEADING = "test", "heading"
FILENAME = "panels.json"


# --------------------------------------------------------------------------
# row helpers
# --------------------------------------------------------------------------
def make_test(name: str, unit: str = "", ref_m: str = "", ref_f: str = "") -> Dict[str, str]:
    return {"kind": TEST, "name": name, "unit": unit,
            "ref_m": ref_m, "ref_f": ref_f or ref_m}


def make_heading(name: str) -> Dict[str, str]:
    return {"kind": HEADING, "name": name, "unit": "", "ref_m": "", "ref_f": ""}


def clean_row(raw: Any) -> Dict[str, str]:
    """Coerce anything read off disk into a well-formed row."""
    if not isinstance(raw, dict):
        return make_heading("")
    kind = HEADING if str(raw.get("kind", TEST)) == HEADING else TEST
    name = str(raw.get("name", "")).strip()
    if kind == HEADING:
        return make_heading(name)
    return make_test(name, str(raw.get("unit", "")).strip(),
                     str(raw.get("ref_m", "")).strip(), str(raw.get("ref_f", "")).strip())


def ref_for(row: Dict[str, str], sex: str) -> str:
    """The reference range to use for a patient of this sex."""
    if row.get("kind") == HEADING:
        return ""
    female = (sex or "M").upper().startswith("F")
    return (row.get("ref_f") or row.get("ref_m") or "") if female else \
           (row.get("ref_m") or row.get("ref_f") or "")


# --------------------------------------------------------------------------
# defaults
# --------------------------------------------------------------------------
def default_rows(panel: str) -> List[Dict[str, str]]:
    return [make_test(name, unit, resolve_ref(ref, "M"), resolve_ref(ref, "F"))
            for name, unit, ref in PANELS.get(panel, [])]


def default_panel_names() -> List[str]:
    return list(PANELS)


# --------------------------------------------------------------------------
# the stored overlay
# --------------------------------------------------------------------------
def _path() -> str:
    return os.path.join(storage.app_dir(), FILENAME)


def _blank() -> Dict[str, Any]:
    return {"overrides": {}, "custom": {}, "deleted": [], "order": [], "prices": {}}


def load_overlay() -> Dict[str, Any]:
    data = storage._read_json(_path(), None)
    if not isinstance(data, dict):
        return _blank()
    overlay = _blank()
    if isinstance(data.get("overrides"), dict):
        overlay["overrides"] = {
            str(k): [clean_row(r) for r in v]
            for k, v in data["overrides"].items() if isinstance(v, list)
        }
    if isinstance(data.get("custom"), dict):
        overlay["custom"] = {
            str(k): [clean_row(r) for r in v]
            for k, v in data["custom"].items() if isinstance(v, list)
        }
    if isinstance(data.get("deleted"), list):
        overlay["deleted"] = [str(x) for x in data["deleted"]]
    if isinstance(data.get("order"), list):
        overlay["order"] = [str(x) for x in data["order"]]
    if isinstance(data.get("prices"), dict):
        overlay["prices"] = {str(k): str(v).strip() for k, v in data["prices"].items()
                             if str(v).strip()}
    return overlay


def save_overlay(overlay: Dict[str, Any]) -> None:
    storage._write_json(_path(), overlay)


# --------------------------------------------------------------------------
# the merged view - what the rest of the app uses
# --------------------------------------------------------------------------
def panel_names() -> List[str]:
    overlay = load_overlay()
    names = [n for n in default_panel_names() if n not in overlay["deleted"]]
    names += [n for n in overlay["custom"] if n not in names]

    order = overlay.get("order") or []
    ranked = {name: i for i, name in enumerate(order)}
    return sorted(names, key=lambda n: (ranked.get(n, len(order)), names.index(n)))


def rows_for(panel: str) -> List[Dict[str, str]]:
    """The rows for one panel: the lab's version if it has one, else the default."""
    overlay = load_overlay()
    if panel in overlay["overrides"]:
        return [dict(r) for r in overlay["overrides"][panel]]
    if panel in overlay["custom"]:
        return [dict(r) for r in overlay["custom"][panel]]
    return default_rows(panel)


def price_for(panel: str) -> str:
    """The standing charge for a panel, as typed on Test Templates, or "".

    Kept beside the panel rather than on the bill so it is typed once and
    every report that ticks the panel starts with it filled in - the lab can
    still overwrite the amount on any one bill."""
    return load_overlay()["prices"].get(panel, "")


def set_price(panel: str, price: str) -> None:
    overlay = load_overlay()
    price = (price or "").strip()
    if price:
        overlay["prices"][panel] = price
    else:
        overlay["prices"].pop(panel, None)
    save_overlay(overlay)


def is_builtin(panel: str) -> bool:
    return panel in PANELS


def is_modified(panel: str) -> bool:
    """True when a built-in panel has been edited away from its shipped form."""
    return is_builtin(panel) and panel in load_overlay()["overrides"]


# --------------------------------------------------------------------------
# editing
# --------------------------------------------------------------------------
def save_panel(panel: str, rows: List[Dict[str, str]]) -> None:
    overlay = load_overlay()
    cleaned = [clean_row(r) for r in rows]
    if is_builtin(panel):
        if cleaned == default_rows(panel):
            overlay["overrides"].pop(panel, None)   # back to shipped: drop the override
        else:
            overlay["overrides"][panel] = cleaned
        if panel in overlay["deleted"]:
            overlay["deleted"].remove(panel)
    else:
        overlay["custom"][panel] = cleaned
    _remember_order(overlay, panel)
    save_overlay(overlay)


def create_panel(panel: str, rows: List[Dict[str, str]] = None) -> None:
    overlay = load_overlay()
    overlay["custom"][panel] = [clean_row(r) for r in (rows or [])]
    _remember_order(overlay, panel)
    save_overlay(overlay)


def rename_panel(old: str, new: str) -> None:
    """Built-ins keep their identity; renaming one produces a custom copy."""
    overlay = load_overlay()
    rows = rows_for(old)
    if is_builtin(old):
        if old not in overlay["deleted"]:
            overlay["deleted"].append(old)
        overlay["overrides"].pop(old, None)
    else:
        overlay["custom"].pop(old, None)
    overlay["custom"][new] = rows
    if old in overlay["prices"]:
        overlay["prices"][new] = overlay["prices"].pop(old)
    overlay["order"] = [new if n == old else n for n in overlay["order"]]
    _remember_order(overlay, new)
    save_overlay(overlay)


def delete_panel(panel: str) -> None:
    overlay = load_overlay()
    if is_builtin(panel):
        if panel not in overlay["deleted"]:
            overlay["deleted"].append(panel)
        overlay["overrides"].pop(panel, None)
    else:
        overlay["custom"].pop(panel, None)
    overlay["order"] = [n for n in overlay["order"] if n != panel]
    overlay["prices"].pop(panel, None)
    save_overlay(overlay)


def reset_panel(panel: str) -> bool:
    """Restore a built-in to its shipped rows. Returns False for custom panels,
    which have no default to fall back to."""
    if not is_builtin(panel):
        return False
    overlay = load_overlay()
    overlay["overrides"].pop(panel, None)
    if panel in overlay["deleted"]:
        overlay["deleted"].remove(panel)
    save_overlay(overlay)
    return True


def restore_all_builtins() -> None:
    overlay = load_overlay()
    overlay["overrides"] = {}
    overlay["deleted"] = []
    save_overlay(overlay)


def _remember_order(overlay: Dict[str, Any], panel: str) -> None:
    """Keep `order` a complete list of known panels, newest last.

    It has to hold every panel, not just the new one: panel_names() ranks by
    position in this list, so a single-entry list would jump that panel to the
    front and shuffle everything else behind it."""
    if not overlay["order"]:
        overlay["order"] = [n for n in default_panel_names()
                            if n not in overlay["deleted"]]
    if panel not in overlay["order"]:
        overlay["order"].append(panel)
