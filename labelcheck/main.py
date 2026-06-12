"""
POST /api/verify — one application + one label image
POST /api/verify-batch — a CSV of applications + their label images
"""

import asyncio
import csv
import io
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from PIL import UnidentifiedImageError

load_dotenv()

from . import extract, verify  # noqa E402 extract reads env at import

MAX_UPLOAD = 8 * 1024 * 1024   # 8 MB per image is plenty
BATCH_CONCURRENCY = 6          # parallel extraction calls in batch mode

ROOT = Path(__file__).resolve().parent.parent

app = FastAPI(title="labelcheck")

# Every decision emits one structured JSON line: what was checked, by which
# model, and what came back. Stdout here; in production this stream is the
# audit trail an agency actually needs (ship it to CloudWatch/Splunk/etc),
# and the request_id in each response lets an agent cite a specific decision.
audit = logging.getLogger("labelcheck.audit")
logging.basicConfig(level=logging.INFO, format="%(message)s")


def _audit(event: str, **fields):
    audit.info(json.dumps({
        "event": event,
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **fields,
    }, ensure_ascii=False))


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


async def _check_one(application: dict, image_bytes: bytes,
                     model: str | None = None) -> dict:
    started = time.perf_counter()
    fields = await extract.extract_fields(image_bytes, model=model)
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
    rid = uuid.uuid4().hex[:12]
    data = await _read_image(image)
    try:
        result = await _check_one(application, data)
    except UnidentifiedImageError as e:
        _audit("verify.rejected", request_id=rid, image=image.filename, reason=_friendly(e))
        raise HTTPException(400, _friendly(e))
    except (RuntimeError, anthropic.APIConnectionError, anthropic.APIStatusError) as e:
        _audit("verify.error", request_id=rid, image=image.filename, reason=_friendly(e))
        raise HTTPException(502, _friendly(e))

    result["request_id"] = rid
    _audit("verify.decision", request_id=rid, image=image.filename,
           model=extract.MODEL, overall=result["overall"],
           checks={c["field"]: c["status"] for c in result["checks"]},
           elapsed_s=result["elapsed_s"])
    return result


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

    '''
    Bounded fan-out: big importers dump a few hundred applications at once,
    but we don't want a few hundred simultaneous API calls
    '''
    sem = asyncio.Semaphore(BATCH_CONCURRENCY)
    started = time.perf_counter()

    batch_id = uuid.uuid4().hex[:12]

    async def run_row(row: dict) -> dict:
        name = (row.get("image") or "").strip()
        rid = uuid.uuid4().hex[:12]
        summary = {"image": name, "brand_name": row.get("brand_name", ""),
                   "request_id": rid}
        if name not in image_data:
            _audit("verify.rejected", request_id=rid, batch_id=batch_id,
                   image=name, reason="no uploaded image with this filename")
            return {**summary, "overall": "error",
                    "error": "No uploaded image with this filename."}
        async with sem:
            try:
                result = await _check_one(row, image_data[name],
                                          model=extract.BATCH_MODEL)
            except Exception as e:  # one bad row shouldn't sink the batch
                _audit("verify.error", request_id=rid, batch_id=batch_id,
                       image=name, reason=_friendly(e))
                return {**summary, "overall": "error", "error": _friendly(e)}
        _audit("verify.decision", request_id=rid, batch_id=batch_id, image=name,
               model=extract.BATCH_MODEL, overall=result["overall"],
               checks={c["field"]: c["status"] for c in result["checks"]},
               elapsed_s=result["elapsed_s"])
        return {**summary, **result}

    results = await asyncio.gather(*(run_row(r) for r in rows))
    counts: dict[str, int] = {}
    for r in results:
        counts[r["overall"]] = counts.get(r["overall"], 0) + 1
    _audit("batch.done", batch_id=batch_id, rows=len(results), outcomes=counts,
           elapsed_s=round(time.perf_counter() - started, 2))
    return {
        "results": results,
        "count": len(results),
        "elapsed_s": round(time.perf_counter() - started, 2),
    }


# Static front end + bundled sample labels. Mounted last so /api/* wins
app.mount("/samples", StaticFiles(directory=ROOT / "samples"), name="samples")
app.mount("/", StaticFiles(directory=ROOT / "static", html=True), name="static")
