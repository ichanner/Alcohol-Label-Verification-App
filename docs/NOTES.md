# Approach, assumptions, trade-offs

Notes on the decisions behind the prototype, roughly in the order the
discovery interviews raised them.

## The shape of the thing: transcribe, then compare

The core design decision is that the model never judges compliance. Claude
reads the label image and returns the fields verbatim (one call per label,
structured JSON out — `labelcheck/extract.py`); deterministic Python compares
those fields against the application (`verify.py`, `govwarning.py`).

Why split it this way:

- **Explainability.** Agents are accountable for approvals. Every flag comes
  with the application value, the label value, and a plain-English reason
  produced by inspectable code — not "the model said no".
- **Consistency.** The same transcription always produces the same verdict.
  Tightening a rule is a code change with a unit test, not prompt surgery.
- **Testability.** All the decision logic runs offline in milliseconds
  (`tests/`), with the interview anecdotes as test cases.

The transcription prompt explicitly forbids the model from "fixing" what it
reads — the failure mode to avoid is the model autocompleting the government
warning from memory and hiding a real violation.

## Speed (the 30-second-scanner story)

The old vendor pilot died because agents could beat the machine by eye. Choices
made for latency:

- **Haiku by default.** Label transcription is a reading task, not a reasoning
  task; the fastest vision model is the right default. `EXTRACTION_MODEL` swaps
  it without a code change.
- **One model call per label.** No multi-step agent loop, no second pass.
- **Images are downscaled and re-encoded** before upload (1600px long edge) —
  label text survives, payload and token count drop.
- The UI reports elapsed time on every check, so whether we're keeping the
  ~5s promise is always visible rather than a claim in a slide deck.

## The government warning check

Strictest check in the app, per the regulation (27 CFR 16.21–16.22) and per
Jenny's experience: the body must match word for word (whitespace and line
wrapping aside), and `GOVERNMENT WARNING` must be capitalized — a title-case
lead-in is an outright mismatch, which mirrors how agents actually reject.
When the text differs, the result pinpoints the first diverging word instead
of a bare "doesn't match".

Bold type is the one requirement a transcription can't establish reliably, so
it's handled honestly: the model reports bold/not-bold/can't-tell, and anything
short of a confident "bold" routes the label to **needs review** — never an
automatic fail, never a silent pass.

## "You need judgment" (the STONE'S THROW problem)

Dave's worry about dumb pattern-matching is handled with a three-way outcome
instead of a binary one:

- Case-only differences (`STONE'S THROW` vs `Stone's Throw`) **match, with a
  note** — same for curly vs straight apostrophes and volume-unit rewrites
  (`75 cL` vs `750 mL`).
- Near-matches (a likely typo) go to **review** with a similarity score, so a
  human applies the judgment.
- ABV comparison is numeric, not textual — `45%` matches
  `45% Alc./Vol. (90 Proof)`. As a bonus, if a label's own proof contradicts
  its ABV, that internal inconsistency gets flagged too.

The tool proposes; the agent disposes. Nothing in the UI claims to approve an
application.

## Batch mode (Janet's 300-label dumps)

CSV + images in one upload, results in one table. Extraction calls run
concurrently but capped (semaphore of 6) so a 300-label batch doesn't turn
into 300 simultaneous API calls; a row that errors reports itself and the rest
of the batch carries on. A ~300-label batch works out to a few minutes of wall
time rather than a day of agent time.

## Imperfect images (Jenny's wish)

A vision model is genuinely better here than classical OCR — decorative
typefaces, curved text and mild skew are routine for it. The bundled
`old-tom-angled.png` (rotated, blurred, off-center) exercises this. The model
also self-reports legibility; a **poor** rating blocks a clean pass, because a
confident verdict from an unreadable photo is exactly the kind of false
comfort that erodes trust in the tool.

## The firewall question (Marcus)

The prototype needs outbound HTTPS to exactly one host: `api.anthropic.com`.
That's a single allowlist entry rather than the constellation of endpoints
that broke the scanning vendor's pilot — but it is still an external
dependency, and a production version inside the TTB network would more
realistically use Claude through FedRAMP-authorized infrastructure (e.g. AWS
GovCloud Bedrock) the agency already operates under. The extraction call is
isolated in one small module precisely so that swap is cheap. When the network
is blocked, the UI says so in words instead of spinning.

## Assumptions

- Application data arrives as typed fields (it would come from COLA in real
  life; here it's the form or a CSV). No COLA integration, per Marcus.
- Distilled-spirits-style labels are the reference case, matching the brief's
  example. The five checks are the common-denominator ones; commodity-specific
  rules are out of scope (below).
- One image per application. Multi-panel labels (front + back) would need a
  small extension to accept several images per row.
- No persistence and no auth: nothing is stored server-side, uploads live in
  memory for the duration of a request. Fine for a prototype, revisit for
  production (retention policy, audit trail, PIV/SSO).

## Known limitations / honest trade-offs

- **Transcription can still misread.** Rare on clean artwork, possible on bad
  photos. The legibility gate catches much of it, but a production rollout
  should measure extraction accuracy against a labeled set of real COLA images
  before anyone trusts a green checkmark.
- **Bold detection is best-effort** (see above) — by design it can only cause
  review, not pass/fail.
- **ABV tolerance rules aren't modeled.** TTB allows small labeling tolerances
  for some commodities; this prototype expects the form and label to state the
  same number, which is the conservative reading.
- **Commodity-specific requirements** (sulfite declarations, country of origin
  for imports, name-and-address rules, type size minimums) are out of scope.
  Type size in particular needs known physical dimensions, which a photo alone
  doesn't give you.
- **Batch results arrive all at once** rather than streaming row by row. For
  300-label batches a progress stream would be the first UX improvement.

## What I'd do next

1. Collect a few hundred real (public) COLA labels and score extraction
   accuracy per field — that number decides how much the tool can be trusted.
2. Stream batch results so agents can start working the failures immediately.
3. Accept front + back label images per application.
4. Per-commodity rule packs (wine/beer/spirits) on top of the same
   transcription, starting with the mandatory-field differences.
5. A "disagree" button that records agent overrides — both for trust and as
   the seed of an evaluation set.
