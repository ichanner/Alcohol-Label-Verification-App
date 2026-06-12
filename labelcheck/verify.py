"""Compares what's on the application against what's printed on the label.

The model only transcribes (see extract.py); every pass/fail decision lives
here in plain code, so an agent or an auditor can trace exactly why a label
was flagged. Each check lands on one of four outcomes:

  match    — agrees with the application
  review   — probably fine, but a human should glance at it
             (e.g. "STONE'S THROW" on the label, "Stone's Throw" on the form)
  mismatch — disagrees with the application
  missing  — couldn't find the field on the label at all

Any mismatch/missing fails the label; any review flags it; otherwise it passes.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from . import govwarning

MATCH = "match"
REVIEW = "review"
MISMATCH = "mismatch"
MISSING = "missing"

# Labels love decorative type — fold curly quotes into plain ones before comparing.
_QUOTES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "`": "'"})


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.translate(_QUOTES)).strip()


def _result(field, label, status, expected, found, notes=None):
    return {
        "field": field,
        "label": label,
        "status": status,
        "expected": expected,
        "found": found,
        "notes": notes or [],
    }


def check_text(field, label, expected, found, fuzzy=0.85):
    if not expected or not expected.strip():
        return _result(field, label, REVIEW, expected, found,
                       ["Application left this blank — nothing to compare against."])
    if not found or not found.strip():
        return _result(field, label, MISSING, expected, found,
                       ["Not found on the label."])
    e, f = _clean(expected), _clean(found)
    if e == f:
        return _result(field, label, MATCH, expected, found)
    if e.casefold() == f.casefold():
        # Same words, different case. Agents treat these as the same thing,
        # so we do too — but say so, rather than silently passing it.
        return _result(field, label, MATCH, expected, found,
                       ["Matches apart from capitalization."])
    ratio = SequenceMatcher(None, e.casefold(), f.casefold()).ratio()
    if ratio >= fuzzy:
        return _result(field, label, REVIEW, expected, found,
                       [f"Close but not identical ({ratio:.0%} similar) — "
                        "worth a human look."])
    return _result(field, label, MISMATCH, expected, found,
                   ["Doesn't match the application."])


# --- alcohol content ---------------------------------------------------------

_PCT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_PROOF = re.compile(r"(\d+(?:\.\d+)?)\s*proof", re.IGNORECASE)
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def parse_abv(text: str | None) -> float | None:
    """Pull an ABV percentage out of a string like '45% Alc./Vol. (90 Proof)'."""
    if not text:
        return None
    if m := _PCT.search(text):
        return float(m.group(1))
    if m := _PROOF.search(text):
        return float(m.group(1)) / 2  # proof is exactly twice the ABV
    if m := _NUMBER.search(text):
        return float(m.group(0))
    return None


def check_abv(expected, found):
    field, label = "alcohol_content", "Alcohol content"
    if not found or not found.strip():
        return _result(field, label, MISSING, expected, found,
                       ["Not found on the label."])
    want, got = parse_abv(expected), parse_abv(found)
    if want is None:
        return _result(field, label, REVIEW, expected, found,
                       ["Couldn't read an ABV number off the application — check manually."])
    if got is None:
        return _result(field, label, REVIEW, expected, found,
                       ["Couldn't read an ABV number off the label — check manually."])
    if abs(want - got) > 0.001:
        return _result(field, label, MISMATCH, expected, found,
                       [f"Application says {want:g}% but the label shows {got:g}%."])

    notes, status = [], MATCH
    if m := _PROOF.search(found):
        proof = float(m.group(1))
        if abs(proof - got * 2) > 0.001:
            # The label disagrees with itself — that's worth a look even
            # though the ABV matches the application.
            status = REVIEW
            notes.append(f"Label's proof ({proof:g}) doesn't agree with its own ABV "
                         f"({got:g}% would be {got * 2:g} proof).")
    return _result(field, label, status, expected, found, notes)


# --- net contents -------------------------------------------------------------

_VOLUME = re.compile(
    r"(\d+(?:\.\d+)?)\s*"
    r"(fl\.?\s*oz\.?|milliliters?|millilitres?|centiliters?|centilitres?"
    r"|liters?|litres?|m\s?l|cl|oz\.?|l\b)",
    re.IGNORECASE,
)

_TO_ML = {
    "ml": 1.0, "milliliter": 1.0, "millilitre": 1.0,
    "cl": 10.0, "centiliter": 10.0, "centilitre": 10.0,
    "l": 1000.0, "liter": 1000.0, "litre": 1000.0,
    "floz": 29.5735, "oz": 29.5735,
}


def parse_volume_ml(text: str | None) -> float | None:
    if not text:
        return None
    m = _VOLUME.search(text)
    if not m:
        return None
    qty = float(m.group(1))
    unit = re.sub(r"[\s.]", "", m.group(2)).lower().rstrip("s")
    factor = _TO_ML.get(unit)
    return qty * factor if factor else None


def check_net_contents(expected, found):
    field, label = "net_contents", "Net contents"
    if not found or not found.strip():
        return _result(field, label, MISSING, expected, found,
                       ["Not found on the label."])
    want, got = parse_volume_ml(expected), parse_volume_ml(found)
    if want is None or got is None:
        # Couldn't make sense of one side as a volume — fall back to text.
        return check_text(field, label, expected, found)
    if abs(want - got) <= 1:  # fl oz <-> mL conversions round a little
        notes = []
        if _clean(expected).casefold() != _clean(found).casefold():
            notes.append(f'Same volume, written differently '
                         f'("{found.strip()}" vs "{expected.strip()}").')
        return _result(field, label, MATCH, expected, found, notes)
    return _result(field, label, MISMATCH, expected, found,
                   [f"Application says {expected.strip()} but the label "
                    f"shows {found.strip()}."])


# --- putting it together -------------------------------------------------------

def verify_label(application: dict, extracted: dict) -> dict:
    checks = [
        check_text("brand_name", "Brand name",
                   application.get("brand_name", ""), extracted.get("brand_name")),
        check_text("class_type", "Class / type",
                   application.get("class_type", ""), extracted.get("class_type"),
                   fuzzy=0.8),
        check_abv(application.get("alcohol_content", ""),
                  extracted.get("alcohol_content")),
        check_net_contents(application.get("net_contents", ""),
                           extracted.get("net_contents")),
        govwarning.check(extracted.get("government_warning"),
                         extracted.get("warning_prefix_bold")),
    ]

    statuses = {c["status"] for c in checks}
    if MISMATCH in statuses or MISSING in statuses:
        overall = "fail"
    elif REVIEW in statuses:
        overall = "review"
    else:
        overall = "pass"

    notes = []
    if extracted.get("legibility") == "poor":
        if overall == "pass":
            overall = "review"
        detail = extracted.get("legibility_notes")
        notes.append("Image quality is poor — don't trust a clean result without "
                     "a second look." + (f" ({detail})" if detail else ""))

    return {"overall": overall, "checks": checks, "notes": notes}
