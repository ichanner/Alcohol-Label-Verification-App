"""Reads a label image with Claude and hands back the fields, verbatim.

The model is used strictly as a transcriber — it never decides whether a
label passes. That keeps every decision explainable (see verify.py) and keeps
the call fast: one round trip per label, structured JSON out.

Haiku is the default model because the brief was blunt about speed — agents
abandoned the last tool at 30-40s per label, and anything past ~5s is dead on
arrival. Set EXTRACTION_MODEL if you ever want to trade speed for accuracy.
"""

import base64
import io
import json
import os

import anthropic
from PIL import Image

MODEL = os.environ.get("EXTRACTION_MODEL", "claude-haiku-4-5")
MAX_EDGE = 1600   # px — bigger buys nothing for label text, costs upload + token time
JPEG_QUALITY = 85

SCHEMA = {
    "type": "object",
    "properties": {
        "brand_name": {
            "type": ["string", "null"],
            "description": "Brand name exactly as printed, preserving capitalization.",
        },
        "class_type": {
            "type": ["string", "null"],
            "description": "Class/type designation, e.g. 'Kentucky Straight Bourbon Whiskey'.",
        },
        "alcohol_content": {
            "type": ["string", "null"],
            "description": "Alcohol content exactly as printed, e.g. '45% Alc./Vol. (90 Proof)'.",
        },
        "net_contents": {
            "type": ["string", "null"],
            "description": "Net contents exactly as printed, e.g. '750 mL'.",
        },
        "government_warning": {
            "type": ["string", "null"],
            "description": "The complete government warning statement, transcribed "
                           "verbatim with the exact capitalization printed on the label.",
        },
        "warning_prefix_bold": {
            "type": ["boolean", "null"],
            "description": "True if the words 'GOVERNMENT WARNING' are printed in bold "
                           "type, false if clearly not, null if you can't tell.",
        },
        "legibility": {
            "type": "string",
            "enum": ["good", "fair", "poor"],
            "description": "How readable the label text is in this image.",
        },
        "legibility_notes": {
            "type": ["string", "null"],
            "description": "Anything making the label hard to read: glare, blur, angle, crop.",
        },
    },
    "required": ["brand_name", "class_type", "alcohol_content", "net_contents",
                 "government_warning", "warning_prefix_bold", "legibility",
                 "legibility_notes"],
    "additionalProperties": False,
}

SYSTEM = """\
You transcribe text from alcohol beverage label images for a TTB compliance check.

Copy text exactly as printed — keep the original capitalization, punctuation and
spelling, and do not fix anything that looks like a mistake. The downstream check
compares characters, so a "corrected" transcription would hide real violations.

In particular: transcribe the government warning statement as it actually appears
on this label, even where it differs from the official wording you know. Never
fill in text from memory.

If a field isn't on the label, use null. Labels are sometimes photographed at an
angle, blurry, or with glare on the bottle; read what you can and report problems
in legibility_notes."""

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "ANTHROPIC_API_KEY isn't set. Put it in a .env file or export it "
                "before starting the server — see the README."
            )
        _client = anthropic.AsyncAnthropic(max_retries=1, timeout=30.0)
    return _client


def _prep_image(data: bytes) -> str:
    """Downscale and re-encode as JPEG so the API call stays quick."""
    img = Image.open(io.BytesIO(data))
    if img.mode != "RGB":
        img = img.convert("RGB")
    if max(img.size) > MAX_EDGE:
        img.thumbnail((MAX_EDGE, MAX_EDGE))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=JPEG_QUALITY)
    return base64.standard_b64encode(out.getvalue()).decode("ascii")


async def extract_fields(image_bytes: bytes) -> dict:
    image_b64 = _prep_image(image_bytes)  # validate the image before anything else
    message = await _get_client().messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": image_b64,
                    },
                },
                {"type": "text", "text": "Transcribe this label."},
            ],
        }],
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
    )
    # With a structured output format the first content block is guaranteed
    # to be text containing valid JSON for our schema.
    return json.loads(message.content[0].text)
