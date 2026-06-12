"""Checks that _prep_image survives the formats people actually upload:
phone photos with EXIF rotation, palette PNGs, CMYK JPEGs, transparency."""

import base64
import io

import pytest
from PIL import Image

from labelcheck.extract import _prep_image


def _png(mode, size=(60, 40)):
    buf = io.BytesIO()
    Image.new(mode, size, "white" if mode != "P" else 0).save(buf, "PNG")
    return buf.getvalue()


def _decoded(b64):
    return Image.open(io.BytesIO(base64.standard_b64decode(b64)))


def test_plain_rgb_png():
    out = _decoded(_prep_image(_png("RGB")))
    assert out.format == "JPEG"


def test_rgba_and_palette_modes_convert():
    for mode in ("RGBA", "P", "L"):
        out = _decoded(_prep_image(_png(mode)))
        assert out.mode == "RGB"


def test_cmyk_jpeg_converts():
    buf = io.BytesIO()
    Image.new("CMYK", (60, 40)).save(buf, "JPEG")
    out = _decoded(_prep_image(buf.getvalue()))
    assert out.mode == "RGB"


def test_exif_rotation_is_applied():
    # a landscape image tagged "rotate 90" should come out portrait
    img = Image.new("RGB", (80, 40), "white")
    exif = Image.Exif()
    exif[274] = 6  # orientation: rotated 90 degrees clockwise
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    out = _decoded(_prep_image(buf.getvalue()))
    assert (out.width, out.height) == (40, 80)


def test_big_image_gets_downscaled():
    buf = io.BytesIO()
    Image.new("RGB", (4000, 3000), "white").save(buf, "JPEG")
    out = _decoded(_prep_image(buf.getvalue()))
    assert max(out.size) <= 1600


def test_garbage_bytes_raise():
    with pytest.raises(Exception):
        _prep_image(b"this is not an image at all")
