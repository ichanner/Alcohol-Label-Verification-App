"""Runs the extractor against real-world label photos and scores it.

The synthetic samples prove the plumbing; this answers the question that
actually matters: can the model read real commercial labels (script fonts,
glare, curved glass, tiny print)? Images come from Wikimedia Commons, the
ground truth in eval/labels.csv was transcribed by hand from each photo.

Scoring is per field, and only fields a human can actually read in the photo
get scored (blank cell = not visible / not scored). Matching is forgiving on
formatting and strict on content: brands compare by containment after
normalization, ABV and volume go through the same parsers the app uses, and
every photo here lacks a government warning, so any warning "found" would be
the model inventing one from memory.

Usage:
  python scripts/eval_real_labels.py            # score eval/images/ (needs API key)
  python scripts/eval_real_labels.py --fetch    # (re)download the images first
"""

import asyncio
import csv
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from labelcheck import extract, govwarning  # noqa: E402
from labelcheck.verify import parse_abv, parse_volume_ml  # noqa: E402

IMAGES = ROOT / "eval" / "images"
MANIFEST = ROOT / "eval" / "labels.csv"
UA = {"User-Agent": "labelcheck-eval/0.1 (TTB take-home prototype; one-off fetch)"}


def load_manifest():
    with open(MANIFEST, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# images that don't live on Commons get fetched straight from the source
DIRECT_URLS = {
    "ttb-hws1.png": ("https://www.ttb.gov/system/files/styles/wide/private/images/"
                     "beer/labeling/health-warning-statement/hws1.png"),
    "ttb-hws2.png": ("https://www.ttb.gov/system/files/styles/wide/private/images/"
                     "beer/labeling/health-warning-statement/hws2.png"),
}


def fetch_images(rows):
    IMAGES.mkdir(parents=True, exist_ok=True)
    for r in [r for r in rows if r["image"] in DIRECT_URLS]:
        dest = IMAGES / r["image"]
        if not (dest.exists() and dest.stat().st_size > 10_000):
            dest.write_bytes(urllib.request.urlopen(urllib.request.Request(
                DIRECT_URLS[r["image"]], headers=UA), timeout=60).read())
            print(f"fetched {dest.name}")
    rows = [r for r in rows if r["image"] not in DIRECT_URLS]
    titles = "|".join(r["source_commons_title"] for r in rows)
    api = ("https://commons.wikimedia.org/w/api.php?action=query&prop=imageinfo"
           "&iiprop=url&iiurlwidth=1600&format=json&titles=" + urllib.parse.quote(titles))
    import json
    data = json.load(urllib.request.urlopen(urllib.request.Request(api, headers=UA), timeout=30))
    by_title = {p["title"]: p["imageinfo"][0] for p in data["query"]["pages"].values()}
    for r in rows:
        dest = IMAGES / r["image"]
        if dest.exists() and dest.stat().st_size > 10_000:
            continue
        info = by_title[r["source_commons_title"]]
        url = info.get("thumburl") or info["url"]
        dest.write_bytes(urllib.request.urlopen(
            urllib.request.Request(url, headers=UA), timeout=60).read())
        print(f"fetched {dest.name}")
        time.sleep(3)  # be polite, Commons rate-limits


def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", (s or "").replace("’", "'").casefold()).strip()


def score(row, got):
    """Returns a list of (field, ok_or_None, detail). None = not scored."""
    out = []

    want = norm(row["brand"])
    found = norm(got.get("brand_name"))
    ok = bool(found) and (want in found or found in want)
    out.append(("brand", ok, got.get("brand_name")))

    if row["class_contains"]:
        ok = norm(row["class_contains"]) in norm(got.get("class_type"))
        out.append(("class", ok, got.get("class_type")))
    else:
        out.append(("class", None, got.get("class_type")))

    if row["abv"]:
        got_abv = parse_abv(got.get("alcohol_content"))
        ok = got_abv is not None and abs(got_abv - float(row["abv"])) < 0.01
        out.append(("abv", ok, got.get("alcohol_content")))
    else:
        out.append(("abv", None, got.get("alcohol_content")))

    if row["net_ml"]:
        got_ml = parse_volume_ml(got.get("net_contents"))
        ok = got_ml is not None and abs(got_ml - float(row["net_ml"])) <= 2
        out.append(("net", ok, got.get("net_contents")))
    else:
        out.append(("net", None, got.get("net_contents")))

    if row["warning_present"] == "yes":
        # the label really carries the US warning: it should be transcribed
        # well enough that the strict check accepts it (review = bold doubt)
        res = govwarning.check(got.get("government_warning"),
                               got.get("warning_prefix_bold"))
        ok = res["status"] in ("match", "review")
        out.append(("warning-read", ok,
                    res["status"] + (": " + res["notes"][0] if res["notes"] else "")))
    elif row["warning_present"] == "foreign":
        # a non-US warning is on the label (e.g. the UK "Drink Responsibly"
        # box on an import). The strict checker must NOT accept it as the
        # 27 CFR statement — correct outcome is mismatch or missing.
        res = govwarning.check(got.get("government_warning"),
                               got.get("warning_prefix_bold"))
        ok = res["status"] not in ("match", "review")
        out.append(("foreign-warning-rejected", ok,
                    res["status"] + (": " + res["notes"][0] if res["notes"] else "")))
    else:
        # no warning on the label, so "found one" means hallucination
        invented = bool(got.get("government_warning"))
        out.append(("no-invented-warning", not invented,
                    "INVENTED A WARNING" if invented else "correctly absent"))
    return out


async def run_once(rows, model, verbose=True):
    sem = asyncio.Semaphore(4)

    async def one(row):
        path = IMAGES / row["image"]
        if not path.exists():
            return row, None, 0.0
        t0 = time.perf_counter()
        async with sem:
            fields = await extract.extract_fields(path.read_bytes(), model=model)
        return row, fields, time.perf_counter() - t0

    results = await asyncio.gather(*(one(r) for r in rows))

    totals, outcomes, times = {}, {}, []
    for row, fields, took in results:
        times.append(took)
        if verbose:
            print(f"\n{row['image']}  ({took:.1f}s)   [{row['what_makes_it_hard']}]")
        if fields is None:
            print("  image missing — run with --fetch first")
            continue
        if verbose and fields.get("legibility") != "good":
            print(f"  model flagged legibility: {fields['legibility']} "
                  f"({fields.get('legibility_notes')})")
        for field, ok, detail in score(row, fields):
            if ok is None:
                mark = " . "
            else:
                mark = " ok" if ok else "BAD"
                hit, n = totals.get(field, (0, 0))
                totals[field] = (hit + ok, n + 1)
                outcomes[(row["image"], field)] = ok
            if verbose:
                print(f"  {mark}  {field:20s} {str(detail)[:80]}")
    return totals, outcomes, times


async def run(runs, model):
    rows = load_manifest()
    per_run, all_outcomes, all_times = [], [], []
    for i in range(runs):
        if runs > 1:
            print(f"\n######## run {i + 1} of {runs} (model: {model or extract.MODEL}) ########")
        totals, outcomes, times = await run_once(rows, model, verbose=(i == 0))
        per_run.append(totals)
        all_outcomes.append(outcomes)
        all_times.extend(times)

    print(f"\n=== per-field accuracy, model {model or extract.MODEL}, "
          f"{runs} run(s), scored fields only ===")
    for field in per_run[0]:
        cells = [f"{t[field][0]}/{t[field][1]}" for t in per_run]
        print(f"  {field:22s} {'  '.join(cells)}")

    # an answer that flips between runs is worth knowing about
    if runs > 1:
        keys = sorted(set().union(*all_outcomes))
        unstable = [k for k in keys
                    if len({o.get(k) for o in all_outcomes if k in o}) > 1]
        if unstable:
            print("\n  flipped between runs:")
            for image, field in unstable:
                print(f"    {image}: {field}")
        else:
            print("\n  no result flipped between runs")

    ts = sorted(all_times)
    print(f"\n  latency: median {ts[len(ts) // 2]:.1f}s, "
          f"p90 {ts[int(len(ts) * 0.9)]:.1f}s, max {ts[-1]:.1f}s")


def _arg(flag, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


if __name__ == "__main__":
    if "--fetch" in sys.argv:
        fetch_images(load_manifest())
    else:
        asyncio.run(run(int(_arg("--runs", "1")), _arg("--model")))
