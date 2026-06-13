"""Endpoint tests with the extraction call mocked out — no API key, no network.

These cover the request plumbing the unit tests can't: form parsing, the
optional application fields, the batch CSV contract, and the NDJSON
streaming format the front end consumes.
"""

import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from labelcheck import extract, govwarning
from labelcheck.main import app

EXTRACTED = {
    "brand_name": "OLD TOM DISTILLERY",
    "class_type": "Kentucky Straight Bourbon Whiskey",
    "alcohol_content": "45% Alc./Vol. (90 Proof)",
    "net_contents": "750 mL",
    "producer_name_address": "Distilled and Bottled by Old Tom Distillery Co., Bardstown, KY",
    "country_of_origin": None,
    "government_warning": govwarning.FULL_TEXT,
    "warning_prefix_bold": True,
    "legibility": "good",
    "legibility_notes": None,
}

APPLICATION = {
    "brand_name": "OLD TOM DISTILLERY",
    "class_type": "Kentucky Straight Bourbon Whiskey",
    "alcohol_content": "45%",
    "net_contents": "750 mL",
}


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), "white").save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def client(monkeypatch):
    async def fake_extract(image_bytes, model=None):
        # mirror the real extractor's contract: decode before any model call,
        # so a non-image still fails with UnidentifiedImageError
        Image.open(io.BytesIO(image_bytes))
        return dict(EXTRACTED)
    monkeypatch.setattr(extract, "extract_fields", fake_extract)
    return TestClient(app)


def _image_file(name="label.png"):
    return {"image": (name, _png(), "image/png")}


# --- single check ------------------------------------------------------------------

def test_single_four_field_application_passes(client):
    resp = client.post("/api/verify", data=APPLICATION, files=_image_file())
    assert resp.status_code == 200
    body = resp.json()
    assert body["overall"] == "pass"
    # optional fields the application didn't state are not judged at all
    fields = [c["field"] for c in body["checks"]]
    assert "producer_name_address" not in fields
    assert "country_of_origin" not in fields
    assert body["request_id"]


def test_single_optional_fields_checked_when_given(client):
    form = {**APPLICATION,
            "producer_name_address":
                "Distilled and Bottled by Old Tom Distillery Co., Bardstown, KY",
            "country_of_origin": "France"}
    body = client.post("/api/verify", data=form, files=_image_file()).json()
    by_field = {c["field"]: c["status"] for c in body["checks"]}
    assert by_field["producer_name_address"] == "match"
    # the mocked label states no origin, so a stated one comes back missing
    assert by_field["country_of_origin"] == "missing"
    assert body["overall"] == "review"


def test_single_rejects_non_image(client):
    resp = client.post("/api/verify", data=APPLICATION,
                       files={"image": ("x.txt", b"not an image", "text/plain")})
    assert resp.status_code == 400


def test_model_allowlist_falls_back_to_default(client):
    body = client.post("/api/verify", data={**APPLICATION, "model": "made-up-model"},
                       files=_image_file()).json()
    assert body["model"] == extract.MODEL


# --- batch (NDJSON stream) ---------------------------------------------------------

CSV = (
    "image,brand_name,class_type,alcohol_content,net_contents\n"
    "label.png,OLD TOM DISTILLERY,Kentucky Straight Bourbon Whiskey,45%,750 mL\n"
    "missing.png,GHOST BRAND,Vodka,40%,750 mL\n"
)


def _batch_files(csv_text, *image_names):
    files = [("applications", ("apps.csv", csv_text.encode(), "text/csv"))]
    for name in image_names:
        files.append(("images", (name, _png(), "image/png")))
    return files


def test_batch_streams_ndjson(client):
    resp = client.post("/api/verify-batch", files=_batch_files(CSV, "label.png"))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/x-ndjson")

    lines = [json.loads(line) for line in resp.text.strip().splitlines()]
    assert lines[0]["type"] == "start" and lines[0]["count"] == 2

    results = {l["image"]: l for l in lines if l["type"] == "result"}
    assert results["label.png"]["overall"] == "pass"
    # a row whose image wasn't uploaded errors without sinking the batch
    assert results["missing.png"]["overall"] == "error"

    done = lines[-1]
    assert done["type"] == "done"
    assert done["outcomes"] == {"pass": 1, "error": 1}
    assert done["elapsed_s"] >= 0


def test_batch_optional_csv_columns(client):
    csv_text = (
        "image,brand_name,class_type,alcohol_content,net_contents,country_of_origin\n"
        "label.png,OLD TOM DISTILLERY,Kentucky Straight Bourbon Whiskey,45%,750 mL,France\n"
    )
    resp = client.post("/api/verify-batch", files=_batch_files(csv_text, "label.png"))
    lines = [json.loads(line) for line in resp.text.strip().splitlines()]
    result = next(l for l in lines if l["type"] == "result")
    by_field = {c["field"]: c["status"] for c in result["checks"]}
    assert by_field["country_of_origin"] == "missing"
    assert result["overall"] == "review"


def test_batch_missing_required_columns_rejected(client):
    resp = client.post("/api/verify-batch",
                       files=_batch_files("image,brand_name\nx.png,Y\n", "x.png"))
    assert resp.status_code == 400
    assert "missing columns" in resp.json()["detail"].lower()
