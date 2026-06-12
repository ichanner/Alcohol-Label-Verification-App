# Real-label eval results

Produced by `python scripts/eval_real_labels.py --runs 3` (and again with
`--model claude-sonnet-4-6`) against the 19-image manifest in `labels.csv`,
on 2026-06-12. Raw script output is kept verbatim below so every number
quoted in docs/NOTES.md traces back to a run anyone can repeat.

How to read it: each column in a summary table is one full pass over the
manifest; "flipped between runs" lists any image/field whose result changed
across passes. Scored fields only — a field is scored only where a human can
actually read it in the image (blank ground-truth cell = not scored).

The 19 images span whiskey, vodka, tequila, an EU aperitif, vintage wine and
champagne, and modern beer, deliberately chosen to be hard: flash glare, dark
bar lighting, curved glass, a museum case, a stained 1947 Bordeaux, by-weight
beer ABVs, EU export units, vertical and handwritten type, compound pint+ounce
net contents. Three of them exercise the government warning directly: two
TTB example labels that carry the full US warning, and a Krug champagne that
carries a *UK* "Drink Responsibly" box (an import), which the strict checker
must refuse to accept as the 27 CFR statement.

Headline (best of the per-run columns below):

| field | haiku 4.5 | sonnet 4.6 |
|---|---|---|
| brand name | 18-19 / 19 | 18/19 (stable) |
| class/type | 12-13 / 14 | 14/14 (stable) |
| alcohol content | 8/11 | 11/11 (stable) |
| net contents | 9/11 | 11/11 (stable) |
| US warning transcribed + strict check passes | 2/2 (one run 1/2) | 2/2 (stable) |
| foreign (UK) warning correctly rejected | 1/1 every run | 1/1 every run |
| no warning invented on the 16 warning-free images | 16/16 every run | 16/16 every run |
| latency | median 7.4s, p90 12.1s | median 11.4s, p90 18.9s |

The two safety-critical behaviors are perfect across all 114 reads: neither
model ever invented a warning where none exists, and both correctly rejected
the UK warning on the import rather than green-lighting it as US-compliant.

The misses are all the genuinely hard cases, never silent wrong verdicts:

- haiku's only real brand misread, every run, is "PREX/PREXY" for APEX on a
  ~90-year-old bottle behind museum glass. Its other misses are nulls it
  flags itself (backlit Smirnoff micro-print, the 1947 Bordeaux class) which
  route to needs-review, plus two 0.1-digit slips in micro-print (Van Winkle
  45.3 vs 45.2 — its own "90.4 Proof" read contradicts it, which the
  proof-vs-ABV cross-check catches; TTB hws1 "0.8" vs "0.9" fl oz).
- sonnet's single "miss" is a naming judgment, not a misread: it returns
  "SIERRA NEVADA" as the brand on the Torpedo label, and on the real COLA
  Sierra Nevada *is* the brand name, so it arguably out-judged the manifest.

This run also caught a real checker bug. The TTB hws2 label prints the
government warning immediately followed by "CONTAINS: SULFITES"; the model
captured both into the warning field, and the strict checker was hard-failing
a label whose warning is word-perfect. That's a false positive. Fixed: a
complete, correct warning followed by extra text now routes to review (the
warning is compliant; a human confirms the trailing text is a separate
declaration), while truncated or reworded warnings still hard-fail. Locked in
by test_warning_with_trailing_declaration_is_review_not_fail.

Config this measures out to: haiku for the interactive check (5s budget, clean
artwork), sonnet as the batch opt-in (BATCH_EXTRACTION_MODEL=claude-sonnet-4-6)
where accuracy per label is worth the latency. Defaults keep both on haiku.

---

## claude-haiku-4-5, n=19, 3 runs (run 1 verbose)

```

######## run 1 of 3 (model: claude-haiku-4-5) ########

1792-small-batch.jpg  (3.4s)   [decorative numeral brand; decimal ABV in small caps]
  model flagged legibility: fair (Government warning statement not visible on this front-facing label image; back or side label would be needed for complete compliance check.)
   ok  brand                1792
   ok  class                KENTUCKY STRAIGHT BOURBON WHISKEY
   ok  abv                  46.85% ALC./VOL (93.7 PROOF)
   .   net                  None
   ok  no-invented-warning  correctly absent

ancient-age.jpg  (2.7s)   [flash glare; ornate red script; tiny combined ABV/proof/volume line]
  model flagged legibility: fair (The government warning statement is not visible on the front label shown in this image; it may be on the back or side of the bottle which is not pictured.)
   ok  brand                Ancient Age
   ok  class                Kentucky Straight Bourbon Whiskey
   ok  abv                  ALC. 40% BY VOL.(80 PROOF)
   ok  net                  750 ml
   ok  no-invented-warning  correctly absent

bookers.jpg  (2.4s)   [brand printed vertically; handwritten label; dim photo]
  model flagged legibility: poor (The label is at an angle and partially obscured by the bottle's curve and lighting; most text on the front label is illegible or cut off from view.)
   ok  brand                Booker's
   .   class                None
   .   abv                  None
   .   net                  None
   ok  no-invented-warning  correctly absent

jim-beam-white-label-new.jpg  (2.3s)   [dark bar lighting; EU export units (70 cl)]
  model flagged legibility: fair (Label is at an angle and partially obscured; government warning text on lower left is not legible in this image due to the bottle's perspective and lighting.)
   ok  brand                Jim Beam
   ok  class                Kentucky Straight Bourbon Whiskey
   ok  abv                  40% alc./vol. (80 Proof)
   ok  net                  70 cl
   ok  no-invented-warning  correctly absent

smirnoff-red-label-8213.jpg  (4.7s)   [clear backlit bottle; volume/ABV in tiny base text]
  model flagged legibility: fair (The lower portion of the label is obscured by liquid in the bottle and the angle of the photograph, making the alcohol content, net contents, and government warning difficult or impossible to read clearly.)
   ok  brand                SMIRNOFF
   ok  class                Vodka
  BAD  abv                  None
  BAD  net                  None
   ok  no-invented-warning  correctly absent

black-ridge-small-batch-bourbon.jpg  (4.5s)   [blurry tasting-room phone photo; should flag legibility]
  model flagged legibility: poor (The bottle is photographed at an angle with significant glare and backlighting, making most label text illegible except for the brand name 'BLACK RIDGE' which is clearly visible on the front.)
   ok  brand                BLACK RIDGE
   .   class                None
   .   abv                  None
   .   net                  None
   ok  no-invented-warning  correctly absent

bella-rio-bourbon.png  (5.0s)   [ornate Victorian frame; micro text on border (750mL confirmed by zooming; ABV unverifiable so unscored)]
  model flagged legibility: fair (The government warning statement is not visible on the front label shown in this image; it may be on the back or side of the bottle.)
   ok  brand                BELLA RIO
   ok  class                BOURBON WHISKEY
   .   abv                  40% Alc./Vol.
   ok  net                  750mL
   ok  no-invented-warning  correctly absent

a-bottle-of-trey-herring-s-carolina-bourbon.png  (5.6s)   [small image; tiny ABV/proof line on a shield (first-pass human label said 43% — zooming proved the model right)]
  model flagged legibility: fair (The label is partially obscured by backlighting and glare on the bottle; government warning text and net contents are not visible in this image.)
   ok  brand                TREY HERRING'S
   ok  class                CAROLINA BOURBON WHISKEY
   ok  abv                  45 ALC. BY VOL. 90 PROOF
   .   net                  None
   ok  no-invented-warning  correctly absent

new-orleans-brewing-company-4-x-beer-label.jpg  (7.2s)   [vintage flat label; ABV stated by weight; volume in fl oz]
  model flagged legibility: fair (This is a vintage label with small text and some areas obscured by the eagle design; government warning statement is not visible on this label.)
   ok  brand                4X
   ok  class                BEER
   ok  abv                  ALCOHOL CONTENTS NOT OVER 5% BY WEIGHT
   ok  net                  12 FL. OZS.
   ok  no-invented-warning  correctly absent

apex-beer-01.jpg  (7.8s)   [curved worn label behind glass; by-weight ABV along top edge]
  model flagged legibility: fair (Label is partially obscured by bottle angle and glare; top portion shows text 'DOES NOT CONTAIN OVER 4% ALCOHOL BY WEIGHT' but government warning and net contents are not clearly visible in this image.)
  BAD  brand                PREXY
   ok  class                BEER
  BAD  abv                  None
   .   net                  None
   ok  no-invented-warning  correctly absent

ch-teau-batailley-47-detail.jpg  (7.9s)   [1947 stained paper; French script typeface]
  model flagged legibility: fair (This is a vintage French wine label from 1947 with aged, faded text and no visible alcohol content, net contents, or U.S. government warning statements.)
   ok  brand                Château Batailley
  BAD  class                None
   .   abv                  None
   .   net                  None
   ok  no-invented-warning  correctly absent

old-rip-van-winkle.jpg  (8.1s)   [dim handheld kitchen shot; decimal ABV and proof in tiny print]
   ok  brand                VAN WINKLE
   ok  class                Kentucky Straight Bourbon Whiskey
  BAD  abv                  Alc. 45.3% Vol. (90.4 Proof)
   ok  net                  750 ml
   ok  no-invented-warning  correctly absent

torpedo-ale-label.jpg  (9.6s)   [curved bottle; ornate illustrated label]
  model flagged legibility: fair (The image shows the front label clearly, but the back label where government warnings and alcohol content would typically appear is not visible in this photograph.)
   ok  brand                SIERRA NEVADA TORPEDO EXTRA IPA
   ok  class                Extra IPA
   .   abv                  None
   ok  net                  12 FL.OZ.
   ok  no-invented-warning  correctly absent

ttb-hws1.png  (10.2s)   [TTB's own example label with the full warning on the back panel; small text; compound pint+oz net contents]
   ok  brand                MALT & HOP BREWERY
   ok  class                Ale with Honey and Huckleberry Flavor
   ok  abv                  5% ALC./VOL.
  BAD  net                  1 PINT, 0.8 FL. OZ
   ok  warning-read         match

ttb-hws2.png  (10.3s)   [second TTB example; full US warning plus a sulfite declaration on a busy single panel; 1 pint net]
   ok  brand                Malt & Hop Brewery
   ok  class                Grape Ale
   .   abv                  None
   ok  net                  1 PINT (16 FL. OZ)
   ok  warning-read         review: Warning text is correct, but extra text was captured with it ("CONTAINS:

krug-champagne-back-label-with-id-number.jpg  (11.4s)   [imported product carrying a UK "Drink Responsibly" box not the US 27 CFR statement; dark glare; the checker must reject it]
  model flagged legibility: fair (Label is photographed at an angle with significant glare and shadow, making it difficult to read all text clearly. The back label is visible but key front label information including alcohol content and net contents are not clearly legible in this image.)
   ok  brand                KRUG
   .   class                GRANDE CUVEE
   .   abv                  None
   .   net                  None
   ok  foreign-warning-rejected missing: No government warning statement found on the label.

tequila-anejo-label.jpg  (11.7s)   [imported spirit; reflective glass; strip stamp over the label; ABV and net cut off at the edge]
  model flagged legibility: fair (Label is at an angle and partially obscured by a sticker; back label visible but government warning and alcohol content/net contents are not clearly readable in this image.)
   ok  brand                CONMEMORATIVO
   ok  class                TEQUILA AÑEJO
   .   abv                  None
   .   net                  None
   ok  no-invented-warning  correctly absent

aperol-002-2025-06-08.jpg  (13.0s)   [EU export label in German; 11% vol and 70cl in small print at the base]
  model flagged legibility: fair (Label text is partially visible but some sections are obscured by bottle curvature and angle; the government warning field is not clearly legible on this label.)
   ok  brand                APEROL
   .   class                None
   ok  abv                  11% vol.
   ok  net                  70 cl
   ok  no-invented-warning  correctly absent

wine-label-santa-lucia-wineries-californ.jpg  (12.1s)   [vintage wine label; diagonal DEMI SEC overstamp crosses the text; 8 fl oz net]
   ok  brand                SANTA LUCIA BRAND
   .   class                CALIFORNIA PINK CHAMPAGNE
   ok  abv                  ALCOHOL 12% BY VOLUME
   ok  net                  8 FL. OZ.
   ok  no-invented-warning  correctly absent

######## run 2 of 3 (model: claude-haiku-4-5) ########

######## run 3 of 3 (model: claude-haiku-4-5) ########

=== per-field accuracy, model claude-haiku-4-5, 3 run(s), scored fields only ===
  brand                  18/19  19/19  18/19
  class                  13/14  12/14  12/14
  abv                    8/11  8/11  8/11
  no-invented-warning    16/16  16/16  16/16
  net                    9/11  9/11  9/11
  warning-read           2/2  2/2  1/2
  foreign-warning-rejected 1/1  1/1  1/1

  flipped between runs:
    apex-beer-01.jpg: brand
    apex-beer-01.jpg: class
    ttb-hws1.png: warning-read

  latency: median 7.4s, p90 12.1s, max 14.3s
```

## claude-sonnet-4-6, n=19, 3 runs (run 1 verbose)

```

######## run 1 of 3 (model: claude-sonnet-4-6) ########

1792-small-batch.jpg  (3.6s)   [decorative numeral brand; decimal ABV in small caps]
   ok  brand                1792
   ok  class                KENTUCKY STRAIGHT BOURBON WHISKEY
   ok  abv                  46.85% ALC / VOL (93.7 PROOF)
   .   net                  None
   ok  no-invented-warning  correctly absent

ancient-age.jpg  (3.9s)   [flash glare; ornate red script; tiny combined ABV/proof/volume line]
   ok  brand                Ancient Age
   ok  class                Kentucky Straight Bourbon Whiskey
   ok  abv                  ALC. 40% BY VOL.(80 PROOF)
   ok  net                  750 ml
   ok  no-invented-warning  correctly absent

bookers.jpg  (5.1s)   [brand printed vertically; handwritten label; dim photo]
  model flagged legibility: poor (The bottle is angled and the label is partially obscured/wrapped around the bottle, cutting off the left side of the text and hiding most field information including alcohol content, net contents, and any government warning.)
   ok  brand                BOOKER'S
   .   class                None
   .   abv                  None
   .   net                  None
   ok  no-invented-warning  correctly absent

jim-beam-white-label-new.jpg  (2.9s)   [dark bar lighting; EU export units (70 cl)]
  model flagged legibility: fair (The image is slightly dark and the bottle is at a mild angle, making smaller text difficult to read clearly.)
   ok  brand                JIM BEAM
   ok  class                Kentucky Straight Bourbon Whiskey
   ok  abv                  alc. 40% vol.
   ok  net                  70 cl
   ok  no-invented-warning  correctly absent

smirnoff-red-label-8213.jpg  (7.5s)   [clear backlit bottle; volume/ABV in tiny base text]
  model flagged legibility: fair (The bottom portion of the label is partially obscured by condensation and the text at the very base of the bottle is too small and blurry to read fully.)
   ok  brand                SMIRNOFF
   ok  class                Triple Distilled TEN TIMES FILTERED VODKA
   ok  abv                  37.5% Vol
   ok  net                  70cl
   ok  no-invented-warning  correctly absent

black-ridge-small-batch-bourbon.jpg  (7.6s)   [blurry tasting-room phone photo; should flag legibility]
  model flagged legibility: fair (The bottom portion of the label is partially obscured by the bottle angle and low position, making the class type, alcohol content, net contents, and government warning largely illegible; only partial text is visible.)
   ok  brand                BLACK RIDGE
   .   class                STRAIGHT BOURBON WHISKEY
   .   abv                  None
   .   net                  None
   ok  no-invented-warning  correctly absent

bella-rio-bourbon.png  (7.9s)   [ornate Victorian frame; micro text on border (750mL confirmed by zooming; ABV unverifiable so unscored)]
  model flagged legibility: fair (The bottom portion of the label with fine print is small and partially obscured, making the government warning unreadable.)
   ok  brand                Bella Rio
   ok  class                Bourbon Whiskey
   .   abv                  50% Abv./Vol.
   ok  net                  750mL
   ok  no-invented-warning  correctly absent

a-bottle-of-trey-herring-s-carolina-bourbon.png  (9.2s)   [small image; tiny ABV/proof line on a shield (first-pass human label said 43% — zooming proved the model right)]
  model flagged legibility: fair (The back label is not visible in this image, so government warning and net contents cannot be read; the front label text is legible despite slight glare on the bottle.)
   ok  brand                TREY HERRING'S
   ok  class                CAROLINA BOURBON WHISKEY
   ok  abv                  45% ALC. BY VOL. 90 PROOF
   .   net                  None
   ok  no-invented-warning  correctly absent

new-orleans-brewing-company-4-x-beer-label.jpg  (11.4s)   [vintage flat label; ABV stated by weight; volume in fl oz]
   ok  brand                XXXX 4-X
   ok  class                Beer
   ok  abv                  ALCOHOL CONTENTS NOT OVER 5% BY WEIGHT
   ok  net                  CONTENTS 12 FL. OZS.
   ok  no-invented-warning  correctly absent

apex-beer-01.jpg  (11.4s)   [curved worn label behind glass; by-weight ABV along top edge]
  model flagged legibility: fair (The label is aged and slightly worn, and the bottle's curvature makes some edge text difficult to read fully.)
   ok  brand                APEX
   ok  class                BEER
   ok  abv                  DOES NOT CONTAIN OVER 4% ALCOHOL BY WEIGHT
   .   net                  None
   ok  no-invented-warning  correctly absent

ch-teau-batailley-47-detail.jpg  (10.7s)   [1947 stained paper; French script typeface]
   ok  brand                Château Batailley
   ok  class                Appellation Pauillac contrôlée
   .   abv                  None
   .   net                  None
   ok  no-invented-warning  correctly absent

old-rip-van-winkle.jpg  (13.4s)   [dim handheld kitchen shot; decimal ABV and proof in tiny print]
   ok  brand                VAN WINKLE Special Reserve
   ok  class                Kentucky Straight Bourbon Whiskey
   ok  abv                  Alc. 45.2%/Vol. (90.4 Proof)
   ok  net                  750 ml
   ok  no-invented-warning  correctly absent

torpedo-ale-label.jpg  (14.0s)   [curved bottle; ornate illustrated label]
  BAD  brand                SIERRA NEVADA
   ok  class                EXTRA IPA
   .   abv                  None
   ok  net                  12 FL. OZ.
   ok  no-invented-warning  correctly absent

ttb-hws1.png  (15.7s)   [TTB's own example label with the full warning on the back panel; small text; compound pint+oz net contents]
   ok  brand                MALT & HOP
   ok  class                Ale with Honey and Huckleberry Flavor
   ok  abv                  5% ALC./VOL.
   ok  net                  1 PINT, 0.9 FL. OZ.
   ok  warning-read         match

ttb-hws2.png  (15.6s)   [second TTB example; full US warning plus a sulfite declaration on a busy single panel; 1 pint net]
   ok  brand                Malt & Hop Brewery
   ok  class                Grape Ale
   .   abv                  None
   ok  net                  1 PINT (16 FL. OZ)
   ok  warning-read         match

krug-champagne-back-label-with-id-number.jpg  (17.1s)   [imported product carrying a UK "Drink Responsibly" box not the US 27 CFR statement; dark glare; the checker must reject it]
  model flagged legibility: fair (Dark lighting and glare in the centre of the label obscure some text, particularly the alcohol content and net contents which do not appear visible on this back label.)
   ok  brand                KRUG
   .   class                GRANDE CUVÉE
   .   abv                  None
   .   net                  None
   ok  foreign-warning-rejected missing: No government warning statement found on the label.

tequila-anejo-label.jpg  (17.8s)   [imported spirit; reflective glass; strip stamp over the label; ABV and net cut off at the edge]
  model flagged legibility: fair (The alcohol content and net contents printed on the sides of the bottle are not legible due to angle and glare, and no government warning panel is visible in this image.)
   ok  brand                CONMEMORATIVO
   ok  class                TEQUILA AÑEJO
   .   abv                  None
   .   net                  None
   ok  no-invented-warning  correctly absent

aperol-002-2025-06-08.jpg  (19.4s)   [EU export label in German; 11% vol and 70cl in small print at the base]
  model flagged legibility: fair (The back label text is partially obscured by the bottle's curvature and the orange liquid inside, making some smaller text difficult to read fully.)
   ok  brand                APEROL
   .   class                APERITIF MIT ALKOHOL · BITTER MIT FARBSTOFF
   ok  abv                  11% vol.
   ok  net                  70 cl
   ok  no-invented-warning  correctly absent

wine-label-santa-lucia-wineries-californ.jpg  (20.0s)   [vintage wine label; diagonal DEMI SEC overstamp crosses the text; 8 fl oz net]
   ok  brand                SANTA LUCIA
   .   class                Sparkling Wine CALIFORNIA PINK CHAMPAGNE Bulk Process
   ok  abv                  ALCOHOL 12% BY VOLUME
   ok  net                  CONTENTS 8 FL. OZ.
   ok  no-invented-warning  correctly absent

######## run 2 of 3 (model: claude-sonnet-4-6) ########

######## run 3 of 3 (model: claude-sonnet-4-6) ########

=== per-field accuracy, model claude-sonnet-4-6, 3 run(s), scored fields only ===
  brand                  18/19  18/19  18/19
  class                  14/14  14/14  14/14
  abv                    11/11  11/11  11/11
  no-invented-warning    16/16  16/16  16/16
  net                    11/11  11/11  11/11
  warning-read           2/2  2/2  2/2
  foreign-warning-rejected 1/1  1/1  1/1

  no result flipped between runs

  latency: median 11.4s, p90 18.9s, max 22.0s
```
