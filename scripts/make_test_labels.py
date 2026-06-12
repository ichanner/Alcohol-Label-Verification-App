"""Makes the sample labels in samples/.

No real COLA artwork to bundle, so these are drawn with Pillow. One clean
label, then variants with the stuff agents actually reject (wrong ABV,
title-case warning, missing warning), plus a skewed blurry one for the
bad-photo path.

Run from the repo root: python scripts/make_test_labels.py
"""

import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from labelcheck import govwarning  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "samples"

W, H = 880, 1100
CREAM = (246, 240, 226)
INK = (32, 28, 24)

# font lookup, macOS paths first then the usual Linux ones. Pillow's
# built-in bitmap font is the last resort, ugly but the script still runs
FONTS = {
    "serif": [
        "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    ],
    "serif_bold": [
        "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
        "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    ],
    "sans": [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
    "sans_bold": [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
}


def font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    for path in FONTS[kind]:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def centered(draw, y, text, f, fill=INK):
    w = draw.textlength(text, font=f)
    draw.text(((W - w) / 2, y), text, font=f, fill=fill)
    return y + f.size


def warning_block(draw, y, prefix, body, size=19):
    """Wraps the warning with a bold lead-in, like real labels print it."""
    f_bold, f_reg = font("sans_bold", size), font("sans", size)
    margin, width = 70, W - 140
    line_h = int(size * 1.45)
    space = draw.textlength(" ", font=f_reg)
    x = margin
    words = [(w, f_bold) for w in prefix.split()] + [(w, f_reg) for w in body.split()]
    for word, f in words:
        w = draw.textlength(word, font=f)
        if x + w > margin + width:
            x, y = margin, y + line_h
        draw.text((x, y), word, font=f, fill=INK)
        x += w + space
    return y + line_h


def make_label(brand, class_type, abv_line, net, address, warning=None):
    img = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(img)

    # double border, like an old spirits label
    d.rectangle([28, 28, W - 28, H - 28], outline=INK, width=4)
    d.rectangle([42, 42, W - 42, H - 42], outline=INK, width=2)

    y = 150
    for chunk in textwrap.wrap(brand, 16):
        y = centered(d, y, chunk, font("serif_bold", 68)) + 14
    d.line([W * 0.3, y + 6, W * 0.7, y + 6], fill=INK, width=2)
    y += 40

    for chunk in textwrap.wrap(class_type, 26):
        y = centered(d, y, chunk, font("serif", 36)) + 10
    y += 60

    y = centered(d, y, abv_line, font("sans", 28)) + 24
    y = centered(d, y, net, font("sans", 28)) + 90
    centered(d, y, address, font("sans", 20))

    if warning:
        prefix, body = warning
        warning_block(d, H - 240, prefix, body)

    return img


def rough_photo(img):
    """Fakes a bad phone shot: skewed, slightly blurred, on a grey table."""
    rotated = img.rotate(7, expand=True, fillcolor=(120, 118, 115), resample=Image.BICUBIC)
    return rotated.filter(ImageFilter.GaussianBlur(1.1))


def main():
    OUT.mkdir(exist_ok=True)

    old_tom = dict(
        brand="OLD TOM DISTILLERY",
        class_type="Kentucky Straight Bourbon Whiskey",
        abv_line="45% Alc./Vol. (90 Proof)",
        net="750 mL",
        address="Distilled and Bottled by Old Tom Distillery Co., Bardstown, KY",
    )
    good_warning = ("GOVERNMENT WARNING:", govwarning.BODY)

    labels = {
        "old-tom-correct.png": make_label(**old_tom, warning=good_warning),
        "old-tom-wrong-abv.png": make_label(
            **{**old_tom, "abv_line": "40% Alc./Vol. (80 Proof)"}, warning=good_warning),
        "old-tom-titlecase-warning.png": make_label(
            **old_tom, warning=("Government Warning:", govwarning.BODY)),
        "old-tom-missing-warning.png": make_label(**old_tom),
        "stones-throw.png": make_label(
            brand="STONE’S THROW",
            class_type="Straight Rye Whiskey",
            abv_line="42% Alc./Vol. (84 Proof)",
            net="700 mL",
            address="Stone's Throw Spirits, Hudson, NY",
            warning=good_warning),
    }
    labels["old-tom-angled.png"] = rough_photo(labels["old-tom-correct.png"])

    for name, img in labels.items():
        img.save(OUT / name)
        print(f"wrote samples/{name}")


if __name__ == "__main__":
    main()
