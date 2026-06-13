# labelcheck

A prototype for TTB label compliance agents. You give it the application data
(brand name, class/type, alcohol content, net contents) and the label artwork;
it reads the label and tells you, field by field, whether they agree — including
the strict word-for-word check on the government health warning statement.

Claude (vision) does exactly one job here: transcribe the label. Every pass/fail
decision is made by ordinary code in [`labelcheck/verify.py`](labelcheck/verify.py),
so an agent can always see *why* something was flagged. Clean print-ready
artwork checks in a few seconds; rough photos take longer (the eval in
`docs/NOTES.md` has measured numbers). Batch mode handles the 200-application
dumps that show up in peak season, streaming results row by row as labels
finish.

**Deployed prototype:** https://alcohol-label-verification-app-scg8.onrender.com

## Running it locally

You'll need Python 3.11+ and an Anthropic API key.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then put your ANTHROPIC_API_KEY in .env
uvicorn labelcheck.main:app --reload
```

Open http://127.0.0.1:8000. If you don't have a label image handy, click
**"Load a sample label"** — the repo ships with test labels in `samples/`.

## Using it

**Check one label** — fill in the application fields, drop in the label image,
hit the button. Alcohol content is optional (some wine and beer are exempt from
stating it), and so are the bottler's name & address and the country of origin
(imports only) — optional fields are checked when you fill them in and skipped
when you don't. You get an overall verdict (pass / needs review / problems
found) plus a per-field breakdown showing what the application says next to
what the label actually shows. A Haiku/Sonnet toggle lets you trade speed for
accuracy per check.

**Check a batch** — upload a CSV plus the label images it references. Results
stream into the table row by row as each label finishes, so on a big batch you
can start working the failures while the rest are still running. CSV columns:

```csv
image,brand_name,class_type,alcohol_content,net_contents
old-tom-correct.png,OLD TOM DISTILLERY,Kentucky Straight Bourbon Whiskey,45%,750 mL
```

`producer_name_address` and `country_of_origin` columns are optional — rows
that fill them in get those fields checked too.

`samples/applications.csv` is a working example that pairs with the bundled
images — upload it together with all six PNGs to see one of everything: a pass,
a wrong ABV, a title-case government warning, a missing warning, a
capitalization-only brand difference, and a badly photographed label.

### What the verdicts mean

- **match** — agrees with the application
- **review** — probably fine but a human should look (e.g. `STONE'S THROW` on
  the label vs `Stone's Throw` on the form, or a label whose photo is too rough
  to trust)
- **mismatch / missing** — disagrees with the application, or isn't on the
  label at all

The government warning check is intentionally stricter than the rest: the
wording must match 27 CFR 16.21 word for word and `GOVERNMENT WARNING` must be
in capitals. Bold type can't be judged reliably from a transcription, so a
suspected-not-bold lead-in sends the label to review rather than failing it.

## Tests

```bash
.venv/bin/python -m pytest
```

The suite covers the comparison logic — no API key or network needed.
`scripts/make_test_labels.py` regenerates the sample images if you want to
tweak them.

There's also a small eval against photos of real commercial labels (this one
does need an API key): `python scripts/eval_real_labels.py --fetch` downloads
the images from Wikimedia Commons, then run it again without the flag to
score. Method and results are written up in [docs/NOTES.md](docs/NOTES.md).

## Deploying

The repo includes a `render.yaml` blueprint: push to GitHub, create a new
**Blueprint** on [Render](https://render.com), point it at the repo, and set
`ANTHROPIC_API_KEY` when prompted. Any container host works too:

```bash
docker build -t labelcheck .
docker run -p 8000:8000 -e ANTHROPIC_API_KEY=sk-ant-... labelcheck
```

## Configuration

| Variable | Default | What it does |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required. The key used for label reading. |
| `EXTRACTION_MODEL` | `claude-haiku-4-5` | Which Claude model reads labels in the interactive check. Haiku keeps results inside the ~5s budget. |
| `BATCH_EXTRACTION_MODEL` | same as above | Batch jobs aren't latency-bound, so they can run `claude-sonnet-4-6` for measurably better accuracy on rough images (numbers in [eval/RESULTS.md](eval/RESULTS.md)). |

## Project layout

```
labelcheck/          the app
  main.py            FastAPI routes (single check, batch check, static files)
  extract.py         the one Claude call — image in, verbatim fields out
  verify.py          field comparisons; all pass/fail logic lives here
  govwarning.py      the strict 27 CFR Part 16 warning-statement check
static/              the front end (plain HTML/CSS/JS, no build step)
samples/             generated test labels + a batch CSV that uses them
eval/                real-label eval: hand-labeled ground truth manifest
scripts/             the label generator + the real-label eval runner
tests/               unit tests for the comparison logic
```

Design decisions, assumptions and known limitations are written up in
[docs/NOTES.md](docs/NOTES.md); the upload/prompt-injection threat model is in
[docs/SECURITY.md](docs/SECURITY.md).
