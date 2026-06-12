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

Synthetic samples prove the plumbing, not the model, so there's a small
real-world eval in the repo: 14 images. 13 photos of real commercial labels
from Wikimedia Commons plus TTB's own example label from the ttb.gov labeling
guidance (that one shows the full warning on a back panel). eval/labels.csv
has the hand-transcribed ground truth and attribution.
`python scripts/eval_real_labels.py --fetch` re-downloads the images, run it
again without the flag to score. The set is deliberately ugly: flash glare,
dark bar lighting, curved glass, a museum case, a stained 1947 Bordeaux,
by-weight beer ABVs, a 70 cl bottle, vertical and handwritten type, compound
pint+ounce net contents.

Both candidate models ran the set 3 times each. Raw output is in
eval/RESULTS.md. Scored only where a human can read the image:

| field | haiku 4.5 (3 runs) | sonnet 4.6 (3 runs) |
|---|---|---|
| brand name | 13-14 / 14 | 13/14 every run |
| class/type | 10-11 / 12 | 12/12 every run |
| alcohol content | 6-7 / 9 | 9/9 every run |
| net contents | 6/8 | 8/8 every run |
| TTB example warning transcribed + strict check passes | 1/1 | 1/1 |
| invented warnings on the 13 warning-free images | 0 | 0 |
| latency | median 5.9s, p90 9.8s | median 8.6s, p90 14.6s |

The result I actually care about: both models transcribed the warning
verbatim off a 691px two-panel image and the strict checker passed it, and in
84 reads neither model ever invented a warning on an image that doesn't show
one. They know the statutory text, so filling it in "helpfully" was the
failure mode I was most worried about.

Differences: all of haiku's misses and all of its run-to-run wobble sit on
the two pre-1989 museum bottles ("PREX" for APEX through display glass,
by-weight ABV lines), plus two digit slips in tiny print: 45.9 where a dim
shot reads 45.2 (the label's own "90.4 Proof" contradicts it, which the proof
cross-check catches) and 0.8 where TTB's micro-print says 0.9. The rest of
its misses were nulls it flagged itself, which route to review. Sonnet read
everything and didn't flip once across runs, including micro text haiku gave
up on. Its one "miss" is a naming judgment: it said the brand was SIERRA
NEVADA where my ground truth says Torpedo, and on the real COLA Sierra Nevada
is the brand, so it arguably out-judged my manifest.

The config that falls out of this: haiku for the interactive check (5s
budget, artwork is usually clean), sonnet as the batch opt-in
(BATCH_EXTRACTION_MODEL=claude-sonnet-4-6) where nobody is watching a
spinner. Defaults keep both on haiku so out-of-the-box behavior is
consistent.

Caveats. The models corrected me twice (my first-pass ground truth said 43%
on one bourbon, zooming proved 45%; and a 750mL micro-print I'd missed
entirely). The eval also caught a parser gap: TTB's example uses "1 PINT, 0.9
FL. OZ.", which parse_volume_ml didn't handle until then. And real COLA
submissions are flat print-ready artwork, much closer to the clean synthetic
samples (~3s, reliably extracted) than to photos through museum glass, so
these numbers are a hard-mode floor. n=14 is a smoke test, not a benchmark.

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
