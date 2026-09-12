"""Plain data structures for the app. Everything round-trips to/from JSON dicts."""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any


@dataclass
class LabProfile:
    lab_name: str = ""
    lab_subtitle: str = ""      # the line under the name, e.g. "Family Clinic"
    address1: str = ""
    address2: str = ""
    phone: str = ""
    mobile: str = ""
    email: str = ""
    reg_no: str = ""
    timings: str = ""           # e.g. "Mon-Sat 7:00 AM - 8:00 PM"; printed in the letterhead
    holidays: str = ""          # when the lab is shut, e.g. "Sundays & public holidays"
    backup_dir: str = ""        # a synced folder (Google Drive, OneDrive) copied to on save
    backup_declined: str = ""   # "1" once the operator has said not to ask about Drive again
    pathologist: str = ""
    pathologist_degrees: str = ""
    technician: str = ""                # lab technician who ran the tests
    technician_signature_path: str = ""
    footer_note: str = ""
    bill_notes: str = ""        # one note per line; the bill numbers them
    billed_by: str = ""         # default staff name on a new bill
    logo_path: str = ""
    signature_path: str = ""

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "LabProfile":
        p = LabProfile()
        for k in p.__dict__:
            if k in d and d[k] is not None:
                setattr(p, k, str(d[k]))
        return p

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TestRow:
    panel: str = ""
    name: str = ""
    result: str = ""
    unit: str = ""
    ref: str = ""
    kind: str = "test"     # "test" or "heading" (a section title inside a panel)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "TestRow":
        return TestRow(
            panel=str(d.get("panel", "")),
            name=str(d.get("name", "")),
            result=str(d.get("result", "")),
            unit=str(d.get("unit", "")),
            ref=str(d.get("ref", "")),
            kind="heading" if str(d.get("kind", "test")) == "heading" else "test",
        )

    def is_heading(self) -> bool:
        return self.kind == "heading"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BillItem:
    """One priced line on the bill: a panel (or 'Investigations') and its charge.

    The amount is a string like every other stored field. Blank is meaningful -
    it means 'not priced yet', which is not the same as a charge of zero."""
    service: str = ""
    amount: str = ""

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "BillItem":
        if not isinstance(d, dict):
            return BillItem()
        return BillItem(service=str(d.get("service", "")),
                        amount=str(d.get("amount", "")))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Billing:
    """The billing side of a report. Totals are never stored - they are derived
    in `app.billing` from these values, so a stored bill can never disagree with
    its own arithmetic."""
    bill_no: str = ""
    bill_date: str = ""
    bill_type: str = ""
    billed_by: str = ""
    net_deposit: str = ""
    items: List[BillItem] = field(default_factory=list)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Billing":
        b = Billing()
        if not isinstance(d, dict):
            return b
        for k in ("bill_no", "bill_date", "bill_type", "billed_by", "net_deposit"):
            if d.get(k) is not None:
                setattr(b, k, str(d[k]))
        raw = d.get("items")
        b.items = [BillItem.from_dict(x) for x in raw] if isinstance(raw, list) else []
        return b

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["items"] = [i.to_dict() for i in self.items]
        return d


@dataclass
class Report:
    id: str = ""
    report_no: str = ""
    title: str = ""             # Mr / Mrs / Miss ... printed before the name
    patient_name: str = ""
    age: str = ""
    age_unit: str = "Y"
    sex: str = "M"
    patient_id: str = ""
    phone: str = ""
    referred_by: str = ""
    sample_type: str = "Blood"
    collected_on: str = ""
    reported_on: str = ""
    remarks: str = ""
    panels: List[str] = field(default_factory=list)
    rows: List[TestRow] = field(default_factory=list)
    billing: Billing = field(default_factory=Billing)
    created_at: str = ""

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Report":
        r = Report()
        for k, v in d.items():
            if k in ("rows", "panels", "billing"):
                continue
            if hasattr(r, k) and v is not None:
                setattr(r, k, str(v))
        r.panels = [str(p) for p in d.get("panels", [])]
        r.rows = [TestRow.from_dict(x) for x in d.get("rows", [])]
        r.billing = Billing.from_dict(d.get("billing") or {})
        return r

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["rows"] = [r.to_dict() for r in self.rows]
        d["billing"] = self.billing.to_dict()
        return d

    def display_name(self) -> str:
        """The name as it prints: 'Mrs. Hemavathi', or just the name."""
        return " ".join(part for part in (self.title, self.patient_name) if part)

    def index_entry(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "report_no": self.report_no,
            "bill_no": self.billing.bill_no,
            "patient_name": self.patient_name,
            "title": self.title,
            "patient_id": self.patient_id,
            "age": f"{self.age}{self.age_unit}" if self.age else "",
            "sex": self.sex,
            "referred_by": self.referred_by,
            "panels": list(self.panels),
            "reported_on": self.reported_on,
            "created_at": self.created_at,
        }
