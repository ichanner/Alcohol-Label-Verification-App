"""Final edge-case battery: synthetic labels exercising everything added this
session, run END TO END through the real extractor + verifier.

Each case draws a label with the repo's own generator, sends it through
extract.extract_fields (real API) and verify.verify_label, then checks the
overall verdict and the statuses that matter. Loose assertions where model
phrasing can legitimately vary (e.g. whether a sulfite line is captured with
the warning), strict everywhere the logic must hold.
"""

import asyncio
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from make_test_labels import make_label, centered, font  # noqa: E402
from labelcheck import extract, govwarning, verify  # noqa: E402
from PIL import ImageDraw  # noqa: E402

GOOD = ("GOVERNMENT WARNING:", govwarning.BODY)

CASES = []


def case(name, image, application, want_overall, field_expectations):
    CASES.append((name, image, application, want_overall, field_expectations))


# 1. EU import: comma-decimal ABV and net contents, Holland = Netherlands
case(
    "eu-import-pass",
    make_label(brand="VAN ORANJE", class_type="Genever",
               abv_line="ALC. 5,0% VOL.", net="0,7 L",
               address="Bottled in Schiedam — PRODUCT OF HOLLAND",
               warning=GOOD),
    {"brand_name": "VAN ORANJE", "class_type": "Genever",
     "alcohol_content": "5%", "net_contents": "700 mL",
     "country_of_origin": "Netherlands"},
    {"pass"},
    {"alcohol_content": {"match"}, "net_contents": {"match"},
     "country_of_origin": {"match"}},
)

# 2. fractional pint equals 8 fl oz
case(
    "half-pint-pass",
    make_label(brand="RIVER BEND", class_type="Blended American Whiskey",
               abv_line="40% Alc./Vol. (80 Proof)", net="1/2 PINT",
               address="River Bend Distilling, Memphis, TN",
               warning=GOOD),
    {"brand_name": "RIVER BEND", "class_type": "Blended American Whiskey",
     "alcohol_content": "40%", "net_contents": "8 fl oz"},
    {"pass"},
    {"net_contents": {"match"}},
)

# 3. abbreviation: Co. on the label, Company in the application -> review
case(
    "abbreviation-review",
    make_label(brand="SMITH & SONS CO.", class_type="Straight Rye Whiskey",
               abv_line="45% Alc./Vol. (90 Proof)", net="750 mL",
               address="Smith & Sons, Louisville, KY",
               warning=GOOD),
    {"brand_name": "Smith and Sons Company", "class_type": "Straight Rye Whiskey",
     "alcohol_content": "45%", "net_contents": "750 mL"},
    {"review"},
    {"brand_name": {"review"}},
)

# 4. wrong origin is a confident conflict -> fail
case(
    "wrong-origin-fail",
    make_label(brand="CHATEAU MIREILLE", class_type="Brandy",
               abv_line="40% Alc./Vol.", net="750 mL",
               address="PRODUCT OF FRANCE",
               warning=GOOD),
    {"brand_name": "CHATEAU MIREILLE", "class_type": "Brandy",
     "alcohol_content": "40%", "net_contents": "750 mL",
     "country_of_origin": "Italy"},
    {"fail"},
    {"country_of_origin": {"mismatch"}},
)

# 5. proof-only ABV statement still matches a % application
case(
    "proof-only-pass",
    make_label(brand="OLD CANNON", class_type="Kentucky Straight Bourbon Whiskey",
               abv_line="90 PROOF", net="750 mL",
               address="Old Cannon Distillery, Frankfort, KY",
               warning=GOOD),
    {"brand_name": "OLD CANNON",
     "class_type": "Kentucky Straight Bourbon Whiskey",
     "alcohol_content": "45%", "net_contents": "750 mL"},
    {"pass"},
    {"alcohol_content": {"match"}},
)

# 6. same class words, different order -> review, not fail
case(
    "reordered-class-review",
    make_label(brand="HIGH MEADOW", class_type="Straight Bourbon Kentucky Whiskey",
               abv_line="47% Alc./Vol. (94 Proof)", net="750 mL",
               address="High Meadow Distillers, Lexington, KY",
               warning=GOOD),
    {"brand_name": "HIGH MEADOW",
     "class_type": "Kentucky Straight Bourbon Whiskey",
     "alcohol_content": "47%", "net_contents": "750 mL"},
    {"review"},
    {"class_type": {"review"}},
)


# 7. sulfite declaration right above the warning: must NOT fail the label.
#    (model may capture it with the warning -> review, or separate it -> pass)
img = make_label(brand="VIGNETO DORO", class_type="Red Wine",
                 abv_line="13% Alc./Vol.", net="750 mL",
                 address="PRODUCT OF ITALY", warning=GOOD)
d = ImageDraw.Draw(img)
centered(d, 1100 - 280, "CONTAINS SULFITES", font("sans_bold", 20))
case(
    "sulfites-near-warning-not-fail",
    img,
    {"brand_name": "VIGNETO DORO", "class_type": "Red Wine",
     "alcohol_content": "13%", "net_contents": "750 mL",
     "country_of_origin": "Italy"},
    {"pass", "review"},
    {"government_warning": {"match", "review"}},
)


async def main():
    failures = 0
    for name, img, app, want_overall, field_exp in CASES:
        buf = io.BytesIO()
        img.save(buf, "PNG")
        fields = await extract.extract_fields(buf.getvalue())
        result = verify.verify_label(app, fields)
        by_field = {c["field"]: c["status"] for c in result["checks"]}

        problems = []
        if result["overall"] not in want_overall:
            problems.append(f"overall={result['overall']} want {want_overall}")
        for f, allowed in field_exp.items():
            if by_field.get(f) not in allowed:
                problems.append(f"{f}={by_field.get(f)} want {allowed}")

        mark = "FAIL" if problems else "ok"
        if problems:
            failures += 1
        print(f"{mark:4} {name:32} overall={result['overall']:6} {by_field}")
        for p in problems:
            print(f"      !! {p}")
        if problems:
            print(f"      extracted: { {k: v for k, v in fields.items() if k != 'government_warning'} }")

    print(f"\n{len(CASES) - failures}/{len(CASES)} edge cases behaved as expected")
    return failures


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
