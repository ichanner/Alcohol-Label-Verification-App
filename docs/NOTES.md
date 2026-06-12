# Notes: approach, assumptions, trade-offs

## Transcribe, then compare

The model never judges compliance. Claude reads the label image and returns
the fields verbatim (one call per label, structured JSON, labelcheck/extract.py).
Plain Python compares those fields against the application (verify.py,
govwarning.py).

Reasons for the split:

- Agents are accountable for approvals, so every flag shows the application
  value, the label value, and a reason produced by code you can read. Not
  "the model said no".
- Same transcription in, same verdict out. Tightening a rule is a code change
  with a unit test, not prompt surgery.
- All the decision logic runs offline in milliseconds (tests/). The interview
  anecdotes are the test cases.

The transcription prompt forbids the model from fixing what it reads. The
failure mode I care about is the model autocompleting the government warning
from memory and hiding a real violation.

## Speed

The old vendor pilot died at 30-40s per label because agents could beat it by
eye. What keeps this one fast:

- Haiku by default. Transcription is a reading task, the fastest vision model
  is the right default. EXTRACTION_MODEL swaps it without a code change.
- One model call per label. No agent loop, no second pass.
- Images get downscaled and re-encoded before upload (1600px long edge).
  Label text survives, payload and token count drop.
- The UI prints elapsed time on every check so the ~5s promise stays visible.

## Hosted frontier model vs something local

Worth writing down since it's a fair question for a government system.

Classical OCR (tesseract etc) was ruled out first. Label typography is
hostile (script faces, arched lettering, curved glass) and the warning check
needs verbatim case-preserving transcription plus field association. That's
where OCR pipelines turn into piles of heuristics. The eval below would have
been rough on it.

A locally hosted open-weights vision model is the more serious option. It
loses for a prototype on practical grounds: decent open vision models need
GPU hosting to get anywhere near the 5 second budget, which is a lot of
infrastructure for a proof of concept that had to ship deployed. The model
touches exactly one function (extract.py) so swapping backends later is a
one-module change, and eval/RESULTS.md is the accuracy bar a local
replacement would have to beat.

The discovery notes anticipate cloud APIs anyway. Marcus's firewall story is
about endpoint sprawl, not a ban. So: one allowlisted endpoint now, a FedRAMP
hosting path for production (below), and a swappable extraction layer if
policy ever demands on-prem.

## The government warning check

Strictest check in the app, per 27 CFR 16.21-16.22 and per Jenny: the body
must match word for word (whitespace and line wrapping aside), and GOVERNMENT
WARNING must be capitalized. A title-case lead-in is an outright mismatch,
which is how agents actually reject. When the text differs the result points
at the first diverging word instead of a bare "doesn't match".

Bold type can't be verified reliably from a transcription. The model reports
bold / not bold / can't tell, and anything short of a confident "bold" routes
to needs-review. Never an automatic fail, never a silent pass.

## The STONE'S THROW problem

Dave's worry about dumb pattern matching. Three-way outcomes instead of
binary:

- Case-only differences (STONE'S THROW vs Stone's Throw) match, with a note.
  Same for curly vs straight apostrophes and unit rewrites (75 cL vs 750 mL).
- Near matches (likely typo) go to review with a similarity score. A human
  applies the judgment.
- ABV compares numerically, so "45%" matches "45% Alc./Vol. (90 Proof)". If a
  label's own proof contradicts its ABV, that gets flagged too.

Nothing in the UI claims to approve an application. It recommends, the agent
decides.

## Batch mode

CSV + images in one upload, results in one table. Extraction calls run
concurrently but capped at 6 so a 300-label dump doesn't become 300
simultaneous API calls. A row that errors reports itself, the rest carry on.
~300 labels works out to a few minutes of wall time instead of a day of agent
time.

## Imperfect images

Vision models handle decorative type, curved text and mild skew fine, which
covers most of what Jenny described. samples/old-tom-angled.png exercises it.
The model also self-reports legibility, and a "poor" rating blocks a clean
pass. A confident verdict from an unreadable photo is the kind of false
comfort that kills trust in a tool like this.

## Measured on real labels

Synthetic samples prove the plumbing, not the model, so there's a real-world
eval in the repo: 19 images. 17 photos of real commercial labels from
Wikimedia Commons plus two TTB example labels from the ttb.gov labeling
guidance (those carry the full US warning). eval/labels.csv has the
hand-transcribed ground truth and attribution.
`python scripts/eval_real_labels.py --fetch` re-downloads the images, run it
again without the flag to score. The set spans whiskey, vodka, tequila, an EU
aperitif, vintage wine and champagne, and beer, and is deliberately ugly:
flash glare, dark bar lighting, curved glass, a museum case, a stained 1947
Bordeaux, by-weight beer ABVs, EU export units, vertical and handwritten type,
compound pint+ounce net contents. Three images exercise the warning directly:
two with the real US warning, and a Krug champagne carrying a *UK* "Drink
Responsibly" box (an import) that the strict checker must refuse to accept.

Both candidate models ran the set 3 times each (114 reads). Raw output is in
eval/RESULTS.md. Scored only where a human can read the image:

| field | haiku 4.5 (3 runs) | sonnet 4.6 (3 runs) |
|---|---|---|
| brand name | 18-19 / 19 | 18/19 every run |
| class/type | 12-13 / 14 | 14/14 every run |
| alcohol content | 8/11 | 11/11 every run |
| net contents | 9/11 | 11/11 every run |
| US warning transcribed + strict check passes | 2/2 (one run 1/2) | 2/2 every run |
| foreign (UK) warning correctly rejected | 1/1 every run | 1/1 every run |
| invented warnings on the 16 warning-free images | 0 | 0 |
| latency | median 7.4s, p90 12.1s | median 11.4s, p90 18.9s |

The two safety-critical numbers are the ones I care about, and both are
perfect across all 114 reads: neither model ever invented a warning where
none exists, and both correctly rejected the UK warning on the import instead
of green-lighting it as US-compliant. Inventing the statutory text it knows by
heart, or rubber-stamping a foreign warning, were the two failure modes that
would actually matter for compliance, and neither happened once.

Differences: all of haiku's misses and run-to-run wobble sit on the hard
cases — "PREX/PREXY" for APEX through museum glass, two 0.1-digit slips in
micro-print (Van Winkle 45.3 vs 45.2, where its own "90.4 Proof" read
contradicts it and the proof cross-check catches the inconsistency; TTB hws1
0.8 vs 0.9 fl oz), and a few nulls it flags itself and routes to review.
Sonnet read every legible field, didn't flip once across runs, and its only
"miss" is a naming judgment: "SIERRA NEVADA" where my ground truth says
Torpedo, and on the real COLA Sierra Nevada *is* the brand, so it arguably
out-judged the manifest.

The config that falls out of this: haiku for the interactive check (5s budget,
artwork is usually clean), sonnet as the batch opt-in
(BATCH_EXTRACTION_MODEL=claude-sonnet-4-6) where nobody is watching a spinner.
Defaults keep both on haiku.

The eval earns its keep as a dev tool, which is the real reason to have one.
It caught a parser gap (the "1 PINT, 0.9 FL. OZ." compound format
parse_volume_ml didn't handle), it corrected my own ground truth twice (a 43%
I'd misread as the model's error when the label says 45%, and a 750mL
micro-print I'd missed), and — best of all — it caught the checker
*false-failing* a compliant label: TTB's hws2 prints the warning next to
"CONTAINS: SULFITES", the model captured both, and the strict check rejected a
warning that's actually word-perfect. Fixed so a complete-but-trailing-text
warning routes to review, not fail (truncated/reworded still fail). A
false-fail on a compliant label is exactly the kind of thing that makes an
agent stop trusting the tool, so finding it before shipping was worth more
than any single accuracy point.

Real COLA submissions are flat print-ready artwork, much closer to the clean
synthetic samples (~3s, reliably extracted) than to photos through museum
glass, so these numbers are a hard-mode floor. n=19 is still a smoke test, not
a benchmark — the production measurement program (a few hundred real COLA
images) is the top next step below.

## Firewall

Outbound HTTPS to exactly one host, api.anthropic.com. One allowlist entry
instead of the constellation of endpoints that broke the vendor pilot. Still
an external dependency though. A production version inside the TTB network
would use Claude through FedRAMP-authorized infrastructure (AWS GovCloud
Bedrock) instead, and the extraction call is isolated in one module so that
swap is cheap. When the network is blocked the UI says so in words instead of
spinning.

## Production path

The frame that matters for a federal AI system is NIST's AI RMF. How this
maps:

- Govern: the tool never approves anything. Verdicts are recommendations to a
  named agent, near-matches force review, nothing claims authority.
- Map: intended use, out-of-scope rules and known failure modes are written
  down here instead of discovered in production.
- Measure: the eval is versioned in the repo (ground truth, per-field
  accuracy, run variance, model comparison). An agent-override signal (next
  steps) would keep measurement going after rollout.
- Manage: every decision emits a structured JSON audit line (request id,
  model, per-field statuses, latency) and every response carries its
  request_id, so an approval traces back to a specific model decision. The
  model is pinned by config, so an upgrade is deliberate and testable.

Prototype security posture, per Marcus's "don't do anything crazy": no
secrets in the repo, nothing stored server-side, uploads live in memory for
one request, one outbound host. Production adds the parts a prototype
shouldn't fake: FedRAMP hosting, PIV/SSO in front, a retention policy for the
audit stream, and CI that runs the unit tests plus a regression slice of the
eval before any model or prompt change ships.

## Assumptions

- Application data arrives as typed fields. It would come from COLA in real
  life, here it's the form or a CSV. No COLA integration, per Marcus.
- Distilled-spirits labels are the reference case, matching the brief. The
  five checks are the common denominator, commodity-specific rules are out of
  scope (below).
- One image per application. Front + back would need a small extension.
- No persistence, no auth. Fine for a prototype, revisit for production.

## Known limitations

- Transcription can still misread. Rare on clean artwork, possible on bad
  photos. The measured failure mode is a flagged null rather than a silent
  wrong value, with one true misread on a 90-year-old bottle behind glass.
  Still needs the full-scale benchmark on real COLA artwork.
- Bold detection is best-effort, and by design can only cause review, not
  pass/fail.
- ABV tolerance rules aren't modeled. TTB allows small tolerances for some
  commodities; this expects the form and label to state the same number,
  which is the conservative reading.
- Commodity-specific requirements (sulfites, country of origin, name and
  address rules, type size minimums) are out of scope. Type size needs
  physical dimensions a photo doesn't give you.
- Batch results arrive all at once. For 300-label batches a progress stream
  is the first UX improvement.

## Next

1. Scale the eval from n=14 to a few hundred real COLA images. That number
   decides how much the tool can be trusted.
2. Stream batch results so agents can start on failures immediately.
3. Front + back label images per application.
4. Per-commodity rule packs (wine/beer/spirits) on the same transcription.
5. A "disagree" button recording agent overrides, both for trust and as the
   seed of a bigger eval set.
