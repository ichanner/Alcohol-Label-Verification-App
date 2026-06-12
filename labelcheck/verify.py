"""Compares the application fields against what was read off the label.

The model only transcribes (extract.py). Everything that decides pass/fail
is plain code in here, so you can always trace why a label got flagged.

Four outcomes per field:
  match    - agrees with the application
  review   - probably fine but a human should look, e.g. STONE'S THROW on
             the label vs Stone's Throw on the form
  mismatch - the tool positively saw a conflict
  missing  - couldn't find the field in this image

A label fails on a mismatch (the tool saw a real conflict) or when the
mandatory government warning is missing — the warning is required on every
alcohol label, so its absence is always a problem to resolve. A non-warning
field that's merely not found goes to review, not fail: "not in this one
image" isn't "absent from the product" — brand or net contents can sit on
another panel. Any review flags it for a human; otherwise it passes.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

from . import govwarning

MATCH = "match"
REVIEW = "review"
MISMATCH = "mismatch"
MISSING = "missing"

# labels love decorative type, fold curly quotes into plain ones first
_QUOTES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "`": "'"})
# separators that don't change the words: hyphen, slash, the en/em dashes
_SEPARATORS = str.maketrans({"-": " ", "/": " ", "–": " ", "—": " "})


def _clean(text: str) -> str:
    """Normalize for comparison only — the original is still shown to the agent.

    This is deliberately limited to differences that don't change the words:
    curly quotes, accents (Château = Chateau, Añejo = Anejo), "&" vs "and",
    the whisky/whiskey spelling, separating punctuation (Single-Barrel =
    Single Barrel, Co. = Co, Booker's = Bookers), and whitespace. It does NOT
    try to resolve synonyms, abbreviations (Co. vs Company), or word order —
    those need judgment and are left to the review tier on purpose.
    """
    text = text.translate(_QUOTES)
    # strip diacritics: decompose, drop the combining marks
    text = "".join(c for c in unicodedata.normalize("NFKD", text)
                   if not unicodedata.combining(c))
    text = re.sub(r"\s*&\s*", " and ", text)
    text = re.sub(r"\bwhisk(?:e)?y\b", "whiskey", text, flags=re.IGNORECASE)
    text = text.replace("'", "")          # Booker's -> Bookers
    text = text.translate(_SEPARATORS)    # Single-Barrel -> Single Barrel
    text = re.sub(r"[.,]", "", text)      # Co. -> Co
    return re.sub(r"\s+", " ", text).strip()


def _result(field: str, label: str, status: str, expected, found,
            notes: list[str] | None = None) -> dict:
    return {
        "field": field,
        "label": label,
        "status": status,
        "expected": expected,
        "found": found,
        "notes": notes or [],
    }


def check_text(field: str, label: str, expected: str | None,
               found: str | None, fuzzy: float = 0.85) -> dict:
    if not expected or not expected.strip():
        return _result(field, label, REVIEW, expected, found,
                       ["Application left this blank — nothing to compare against."])
    if not found or not found.strip():
        return _result(field, label, MISSING, expected, found,
                       ["Not found in this image — check the other panels of the label."])
    e, f = _clean(expected), _clean(found)
    if e == f:
        return _result(field, label, MATCH, expected, found)
    if e.casefold() == f.casefold():
        # Same words, different case. Agents treat these as the same thing,
        # so we do too but say so, rather than silently passing it
        return _result(field, label, MATCH, expected, found,
                       ["Matches apart from capitalization."])
    ce, cf = e.casefold(), f.casefold()
    if f" {ce} " in f" {cf} " or f" {cf} " in f" {ce} ":
        # One fully contains the other as whole words: the label states the
        # same thing with an added qualifier ("Malt & Hop" vs "Malt & Hop
        # Brewery", "Ale" vs "Ale with Honey..."). That's a judgment call for
        # an agent, not a hard mismatch. (Padding with spaces keeps it to
        # whole words, so "Ale" doesn't match inside "Pale".)
        return _result(field, label, REVIEW, expected, found,
                       ["The label and application agree but one adds extra "
                        "words — confirm they refer to the same thing."])
    ratio = SequenceMatcher(None, ce, cf).ratio()
    if ratio >= fuzzy:
        return _result(field, label, REVIEW, expected, found,
                       [f"Close but not identical ({ratio:.0%} similar) — "
                        "worth a human look."])
    return _result(field, label, MISMATCH, expected, found,
                   ["Doesn't match the application."])


# alcohol content

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


def check_abv(expected: str | None, found: str | None) -> dict:
    field, label = "alcohol_content", "Alcohol content"
    if not found or not found.strip():
        return _result(field, label, MISSING, expected, found,
                       ["Not found in this image — check the other panels of the label."])
    want, got = parse_abv(expected), parse_abv(found)
    if not (expected or "").strip():
        # ABV is optional in the application — some wine and beer are exempt
        # from stating it. Left blank on purpose, so review against the label
        # rather than treating it as an error.
        return _result(field, label, REVIEW, expected, found,
                       ["No alcohol content in the application (optional for some "
                        f"wine and beer). The label shows: {found.strip()}."])
    if want is None:
        return _result(field, label, REVIEW, expected, found,
                       ["Couldn't read an ABV number off the application — check manually."])
    if got is None:
        return _result(field, label, REVIEW, expected, found,
                       ["Couldn't read an ABV number off the label — check manually."])

    # Labels usually print proof too, and proof is exactly 2x ABV. That makes
    # it a free second reading of the same number — useful because a misread
    # digit in tiny print is the model's most common error on hard images.
    proof_raw = float(m.group(1)) if (m := _PROOF.search(found)) else None
    proof_abv = proof_raw / 2 if proof_raw is not None else None

    if abs(want - got) > 0.001:
        if proof_abv is not None and abs(proof_abv - want) <= 0.001:
            # The stated % disagrees with the application, but the label's own
            # proof implies the application's value. Both can't be right —
            # most likely the % was misread. Flag for a human, don't fail.
            return _result(field, label, REVIEW, expected, found,
                           [f"The label's stated ABV ({got:g}%) doesn't match the "
                            f"application ({want:g}%), but its proof ({proof_raw:g}) "
                            f"implies {proof_abv:g}% — which does. The two disagree, "
                            "likely a misread of the percentage. Check the image."])
        return _result(field, label, MISMATCH, expected, found,
                       [f"Application says {want:g}% but the label shows {got:g}%."])

    # ABV matches the application. If the label's own proof disagrees with its
    # stated ABV, that internal inconsistency is still worth a look.
    notes, status = [], MATCH
    if proof_abv is not None and abs(proof_abv - got) > 0.001:
        status = REVIEW
        notes.append(f"Label's proof ({proof_raw:g}) doesn't agree with its own ABV "
                     f"({got:g}% would be {got * 2:g} proof).")
    return _result(field, label, status, expected, found, notes)


# net contents
#
# Volume parsing is the one piece that has to be exact — it's arithmetic, not
# judgment, so it stays fully deterministic (no model in this path). Every unit
# a TTB beverage label might state maps to a canonical millilitre factor; the
# key is the unit lowercased with spaces/dots removed and a trailing "s"
# stripped, so "FL. OZ.", "fl oz", and "fluid ounces" all land on "floz".

_UNIT_ML = {
    "ml": 1.0, "milliliter": 1.0, "millilitre": 1.0, "cc": 1.0,
    "cl": 10.0, "centiliter": 10.0, "centilitre": 10.0,
    "dl": 100.0, "deciliter": 100.0, "decilitre": 100.0,
    "l": 1000.0, "liter": 1000.0, "litre": 1000.0,
    "floz": 29.5735, "fluidounce": 29.5735, "oz": 29.5735, "ounce": 29.5735,
    "pt": 473.176, "pint": 473.176,
    "qt": 946.353, "quart": 946.353,
    "gal": 3785.412, "gallon": 3785.412,
}

# a number ("750", "1,750", "1.75", ".75") followed by any of those units.
# word forms come before abbreviations, and bare "l" is last so "ml"/"cl"/"dl"
# match their own alternative first.
_VOL_NUM = r"(\d[\d,]*(?:\.\d+)?|\.\d+)"
_UNIT = (
    r"fl\.?\s*oz\.?|fluid\s*ounces?"
    r"|milliliters?|millilitres?|centiliters?|centilitres?"
    r"|deciliters?|decilitres?|liters?|litres?"
    r"|pints?|pts?\.?|quarts?|qts?\.?|gallons?|gals?\.?|ounces?"
    r"|m\s?l|cc|cl|dl|oz\.?|l\b"
)
_QTY = re.compile(_VOL_NUM + r"\s*(" + _UNIT + r")", re.IGNORECASE)

# beer states compound imperial quantities like "1 PT. 0.9 FL. OZ." — a sum,
# handled before the general case so the parts add instead of the first winning.
_PINT_COMPOUND = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:pts?|pints?)\b\.?[\s,]*"
    r"(?:(\d+(?:\.\d+)?)\s*fl\.?\s*oz\.?)?",
    re.IGNORECASE,
)


def _to_float(num: str) -> float:
    return float(num.replace(",", ""))


def parse_volume_ml(text: str | None) -> float | None:
    """Read a net-contents string as millilitres, or None if it isn't a volume."""
    if not text:
        return None
    if m := _PINT_COMPOUND.search(text):
        return _to_float(m.group(1)) * 473.176 + float(m.group(2) or 0) * 29.5735
    # The first quantity+unit wins. A label that restates one volume two ways —
    # "750 mL (25.4 FL OZ)" — should read as the principal value, not the sum.
    if m := _QTY.search(text):
        unit = re.sub(r"[\s.]", "", m.group(2)).lower().rstrip("s")
        factor = _UNIT_ML.get(unit)
        return _to_float(m.group(1)) * factor if factor else None
    return None


def check_net_contents(expected: str | None, found: str | None) -> dict:
    field, label = "net_contents", "Net contents"
    if not found or not found.strip():
        return _result(field, label, MISSING, expected, found,
                       ["Not found in this image — check the other panels of the label."])
    want, got = parse_volume_ml(expected), parse_volume_ml(found)
    if want is None or got is None:
        # Couldn't make sense of one side as a volume so fall back to text
        return check_text(field, label, expected, found)
    # A small proportional tolerance: enough to absorb fl-oz <-> mL rounding
    # (a "25.4 FL OZ" label is 751 mL, a hair off 750), but far tighter than
    # the gap between any two standard bottle sizes (700 vs 720 vs 750 mL).
    if abs(want - got) <= max(1.0, 0.005 * want):
        notes = []
        if _clean(expected).casefold() != _clean(found).casefold():
            notes.append(f'Same volume, written differently '
                         f'("{found.strip()}" vs "{expected.strip()}").')
        return _result(field, label, MATCH, expected, found, notes)
    return _result(field, label, MISMATCH, expected, found,
                   [f"Application says {expected.strip()} but the label "
                    f"shows {found.strip()}."])


# putting it together
def verify_label(application: dict, extracted: dict) -> dict:
    other_checks = [
        check_text("brand_name", "Brand name",
                   application.get("brand_name", ""), extracted.get("brand_name")),
        check_text("class_type", "Class / type",
                   application.get("class_type", ""), extracted.get("class_type"),
                   fuzzy=0.8),
        check_abv(application.get("alcohol_content", ""),
                  extracted.get("alcohol_content")),
        check_net_contents(application.get("net_contents", ""),
                           extracted.get("net_contents")),
    ]
    warning = govwarning.check(extracted.get("government_warning"),
                               extracted.get("warning_prefix_bold"))
    checks = other_checks + [warning]

    all_statuses = {c["status"] for c in checks}
    other_statuses = {c["status"] for c in other_checks}
    # Fail on a positive conflict anywhere (label says X, application says Y),
    # OR when the mandatory government warning is missing. The warning is
    # required on every alcohol label, so its absence is a problem an agent
    # must resolve — either the label is non-compliant, or this is a partial
    # image and the agent needs the full artwork (their workflow today).
    if MISMATCH in all_statuses or warning["status"] == MISSING:
        overall = "fail"
    # A non-warning field not found, or any soft difference, is a human's call.
    # "Not in this one image" isn't "absent from the product" for brand/net —
    # those can sit on another panel — so that's review, not an auto-fail.
    elif MISSING in other_statuses or REVIEW in all_statuses:
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
