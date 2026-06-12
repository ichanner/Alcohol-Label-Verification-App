"""The health warning statement check (27 CFR Part 16).

No fuzzy matching on this one. The wording is fixed by regulation word for
word, and GOVERNMENT WARNING has to be capitalized and bold (the rest of
the statement actually must NOT be bold, oddly). Agents reject labels over
a title-case "Government Warning", so this check is strict on purpose.
"""

import re

PREFIX = "GOVERNMENT WARNING:"
BODY = (
    "(1) According to the Surgeon General, women should not drink alcoholic "
    "beverages during pregnancy because of the risk of birth defects. "
    "(2) Consumption of alcoholic beverages impairs your ability to drive a "
    "car or operate machinery, and may cause health problems."
)
FULL_TEXT = f"{PREFIX} {BODY}"

_PREFIX_RE = re.compile(r"(government\s+warning\s*:?)\s*", re.IGNORECASE)


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _first_difference(expected: str, found: str) -> str:
    exp, got = expected.split(), found.split()
    for i, (e, g) in enumerate(zip(exp, got)):
        if e.casefold() != g.casefold():
            return (f'Wording differs at word {i + 1}: should read "{e}", '
                    f'label has "{g}".')
    if len(got) < len(exp):
        return f'Statement is cut short — text missing from "{exp[len(got)]}" onward.'
    return f'Statement has extra text starting at "{got[len(exp)]}".'


def check(found: str | None, prefix_bold: bool | None) -> dict:
    base = {
        "field": "government_warning",
        "label": "Government warning",
        "expected": FULL_TEXT,
        "found": found,
    }
    if not found or not found.strip():
        return {**base, "status": "missing",
                "notes": ["No government warning statement found on the label."]}

    text = _squash(found)
    notes = []
    status = "match"

    m = _PREFIX_RE.match(text)
    if not m:
        return {**base, "status": "mismatch",
                "notes": ['Statement doesn\'t open with "GOVERNMENT WARNING:".']}

    prefix = _squash(m.group(1))
    if prefix != prefix.upper():
        status = "mismatch"
        notes.append('"GOVERNMENT WARNING" must be in capitals — '
                     f'label has "{m.group(1).strip()}".')
    if not prefix.endswith(":"):
        status = "mismatch"
        notes.append('Missing the colon after "GOVERNMENT WARNING".')

    body = text[m.end():]
    if _squash(body).casefold() != _squash(BODY).casefold():
        status = "mismatch"
        notes.append(_first_difference(BODY, body))

    '''
    Bold type is the one thing we can't verify reliably from a
    transcription, so it never auto-fails so worst case it sends the label
    to a human instead of quietly passing it
    '''
    if status == "match":
        if prefix_bold is False:
            status = "review"
            notes.append('"GOVERNMENT WARNING" doesn\'t appear to be in bold type '
                         '— check by eye.')
        elif prefix_bold is None:
            status = "review"
            notes.append('Couldn\'t tell from the image whether "GOVERNMENT WARNING" '
                         'is bold — check by eye.')

    return {**base, "status": status, "notes": notes}
