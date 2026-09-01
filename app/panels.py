"""Built-in test panels.

Each row is (test name, unit, reference). Reference is either a plain string, or a
dict keyed "M"/"F" when the normal range depends on the patient's sex.
"""
from typing import Dict, List, Tuple, Union

Ref = Union[str, Dict[str, str]]
Row = Tuple[str, str, Ref]

PANELS: Dict[str, List[Row]] = {
    "Complete Blood Count (CBC)": [
        ("Haemoglobin (Hb)", "g/dL", {"M": "13.0 - 17.0", "F": "12.0 - 15.0"}),
        ("Total RBC Count", "million/cmm", {"M": "4.5 - 5.5", "F": "3.8 - 4.8"}),
        ("Total WBC Count (TLC)", "/cmm", "4000 - 11000"),
        ("Neutrophils", "%", "40 - 75"),
        ("Lymphocytes", "%", "20 - 45"),
        ("Eosinophils", "%", "1 - 6"),
        ("Monocytes", "%", "2 - 10"),
        ("Basophils", "%", "0 - 1"),
        ("Platelet Count", "lakhs/cmm", "1.5 - 4.5"),
        ("PCV / Haematocrit", "%", {"M": "40 - 50", "F": "36 - 46"}),
        ("MCV", "fL", "83 - 101"),
        ("MCH", "pg", "27 - 32"),
        ("MCHC", "g/dL", "31.5 - 34.5"),
        ("RDW-CV", "%", "11.6 - 14.0"),
        ("ESR", "mm/1st hr", {"M": "0 - 15", "F": "0 - 20"}),
    ],
    "Lipid Profile": [
        ("Total Cholesterol", "mg/dL", "< 200"),
        ("Triglycerides", "mg/dL", "< 150"),
        ("HDL Cholesterol", "mg/dL", {"M": "40 - 60", "F": "50 - 60"}),
        ("LDL Cholesterol", "mg/dL", "< 100"),
        ("VLDL Cholesterol", "mg/dL", "6 - 38"),
        ("Total Chol / HDL Ratio", "", "< 4.5"),
    ],
    "Liver Function Test (LFT)": [
        ("Bilirubin - Total", "mg/dL", "0.3 - 1.2"),
        ("Bilirubin - Direct", "mg/dL", "0.0 - 0.3"),
        ("Bilirubin - Indirect", "mg/dL", "0.1 - 0.9"),
        ("SGOT / AST", "U/L", "5 - 40"),
        ("SGPT / ALT", "U/L", "5 - 45"),
        ("Alkaline Phosphatase", "U/L", "40 - 130"),
        ("Total Protein", "g/dL", "6.0 - 8.3"),
        ("Albumin", "g/dL", "3.5 - 5.2"),
        ("Globulin", "g/dL", "2.3 - 3.5"),
        ("A / G Ratio", "", "1.0 - 2.1"),
    ],
    "Kidney Function Test (KFT)": [
        ("Blood Urea", "mg/dL", "15 - 45"),
        ("Blood Urea Nitrogen (BUN)", "mg/dL", "7 - 20"),
        ("Serum Creatinine", "mg/dL", {"M": "0.7 - 1.3", "F": "0.6 - 1.1"}),
        ("Uric Acid", "mg/dL", {"M": "3.5 - 7.2", "F": "2.6 - 6.0"}),
        ("Sodium", "mmol/L", "135 - 145"),
        ("Potassium", "mmol/L", "3.5 - 5.1"),
        ("Chloride", "mmol/L", "98 - 107"),
        ("Calcium", "mg/dL", "8.6 - 10.2"),
    ],
    "Blood Sugar": [
        ("Glucose - Fasting (FBS)", "mg/dL", "70 - 100"),
        ("Glucose - Post Prandial (PPBS)", "mg/dL", "70 - 140"),
        ("Glucose - Random (RBS)", "mg/dL", "70 - 140"),
        ("HbA1c", "%", "4.0 - 5.6"),
    ],
    "Thyroid Profile": [
        ("Total T3", "ng/dL", "80 - 200"),
        ("Total T4", "ug/dL", "5.1 - 14.1"),
        ("TSH (Ultrasensitive)", "uIU/mL", "0.27 - 4.20"),
    ],
}

PANEL_NAMES: List[str] = list(PANELS.keys())


def resolve_ref(ref: Ref, sex: str) -> str:
    """Pick the sex-appropriate reference range, defaulting to the male range."""
    if isinstance(ref, dict):
        return ref.get((sex or "M").upper()[:1], ref.get("M", ""))
    return ref


def panel_rows(panel: str, sex: str) -> List[Tuple[str, str, str]]:
    return [(n, u, resolve_ref(r, sex)) for n, u, r in PANELS.get(panel, [])]


import re

_RANGE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*(?:-|to|–)\s*(-?\d+(?:\.\d+)?)\s*$", re.I)
_UPPER = re.compile(r"^\s*<=?\s*(-?\d+(?:\.\d+)?)\s*$")
_LOWER = re.compile(r"^\s*>=?\s*(-?\d+(?:\.\d+)?)\s*$")
_NUM = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*$")


def flag_for(result: str, ref: str) -> str:
    """Return 'H', 'L' or '' by comparing a numeric result against a reference range.
    Non-numeric results and unparseable ranges are never flagged."""
    m = _NUM.match(result or "")
    if not m:
        return ""
    val = float(m.group(1))
    ref = (ref or "").strip()

    m = _RANGE.match(ref)
    if m:
        lo, hi = float(m.group(1)), float(m.group(2))
        return "L" if val < lo else ("H" if val > hi else "")
    m = _UPPER.match(ref)
    if m:
        return "H" if val > float(m.group(1)) else ""
    m = _LOWER.match(ref)
    if m:
        return "L" if val < float(m.group(1)) else ""
    return ""
