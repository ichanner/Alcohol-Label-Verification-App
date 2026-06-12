"""FastAPI app: two JSON endpoints plus the static front end.

POST /api/verify        — one application + one label image
POST /api/verify-batch  — a CSV of applications + their label images
"""

import asyncio
import csv
import io
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from PIL import UnidentifiedImageError

load_dotenv()

from . import extract, verify  # noqa: E402  (extract reads env at import)

MAX_UPLOAD = 8 * 1024 * 1024   # 8 MB per image is plenty for label artwork
BATCH_CONCURRENCY = 6          # parallel extraction calls in batch mode

ROOT = Path(__file__).resolve().parent.parent

app = FastAPI(title="labelcheck")


@app.get("/api/health")
async def health():
    return {"ok": True, "model": extract.MODEL}


async def _read_image(upload: UploadFile) -> bytes:
    data = await upload.read()
    if not data:
        raise HTTPException(400, f"{upload.filename or 'image'} is empty.")
    if len(data) > MAX_UPLOAD:
        raise HTTPException(400, f"{upload.filename} is over the "
                                 f"{MAX_UPLOAD // 2**20} MB limit.")
    return data


async def _check_one(application: dict, image_bytes: bytes) -> dict:
    started = time.perf_counter()
    fields = await extract.extract_fields(image_bytes)
    result = verify.verify_label(application, fields)
    result["extracted"] = fields
    result["elapsed_s"] = round(time.perf_counter() - started, 2)
    return result


def _friendly(e: Exception) -> str:
    if isinstance(e, RuntimeError):
        return str(e)
    if isinstance(e, anthropic.APIConnectionError):
        return ("Couldn't reach the extraction service. On a restricted network, "
                "api.anthropic.com needs to be reachable.")
    if isinstance(e, anthropic.APIStatusError):
        return f"Extraction service error ({e.status_code}) — try again."
    if isinstance(e, UnidentifiedImageError):
        return "That file isn't an image we can read (use PNG, JPEG or WebP)."
    return f"Unexpected error ({e.__class__.__name__})."


@app.post("/api/verify")
async def verify_single(
    image: UploadFile = File(...),
    brand_name: str = Form(""),
    class_type: str = Form(""),
    alcohol_content: str = Form(""),
    net_contents: str = Form(""),
):
    application = {
        "brand_name": brand_name,
        "class_type": class_type,
        "alcohol_content": alcohol_content,
        "net_contents": net_contents,
    }
    data = await _read_image(image)
    try:
        return await _check_one(application, data)
    except UnidentifiedImageError as e:
        raise HTTPException(400, _friendly(e))
    except (RuntimeError, anthropic.APIConnectionError, anthropic.APIStatusError) as e:
        raise HTTPException(502, _friendly(e))


@app.post("/api/verify-batch")
async def verify_batch(
    applications: UploadFile = File(...),
    images: list[UploadFile] = File(...),
):
    try:
        text = (await applications.read()).decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(400, "Couldn't read the CSV — it needs to be plain UTF-8 text.")
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise HTTPException(400, "The CSV has no data rows.")
    required = {"image", "brand_name", "class_type", "alcohol_content", "net_contents"}
    missing = required - set(rows[0])
    if missing:
        raise HTTPException(400, f"CSV is missing columns: {', '.join(sorted(missing))}.")

    image_data = {}
    for up in images:
        image_data[up.filename] = await _read_image(up)

    # Bounded fan-out: big importers dump a few hundred applications at once,
    # but we don't want a few hundred simultaneous API calls.
    sem = asyncio.Semaphore(BATCH_CONCURRENCY)
    started = time.perf_counter()

    async def run_row(row: dict) -> dict:
        name = (row.get("image") or "").strip()
        summary = {"image": name, "brand_name": row.get("brand_name", "")}
        if name not in image_data:
            return {**summary, "overall": "error",
                    "error": "No uploaded image with this filename."}
        async with sem:
            try:
                result = await _check_one(row, image_data[name])
            except Exception as e:  # one bad row shouldn't sink the batch
                return {**summary, "overall": "error", "error": _friendly(e)}
        return {**summary, **result}

    results = await asyncio.gather(*(run_row(r) for r in rows))
    return {
        "results": results,
        "count": len(results),
        "elapsed_s": round(time.perf_counter() - started, 2),
    }


# Static front end + bundled sample labels. Mounted last so /api/* wins.
app.mount("/samples", StaticFiles(directory=ROOT / "samples"), name="samples")
app.mount("/", StaticFiles(directory=ROOT / "static", html=True), name="static")
