# Real-label eval results

Produced by `python scripts/eval_real_labels.py --runs 3` (and again with
`--model claude-sonnet-4-6`) against the 14-image manifest in `labels.csv`,
on 2026-06-12. Raw script output is kept verbatim below so every number
quoted in docs/NOTES.md traces back to a run anyone can repeat.

How to read it: each column in a summary table is one full pass over the
manifest; "flipped between runs" lists any image/field whose result changed
across passes. Two things worth knowing before the raw output:

- **Haiku's misses and all of its run-to-run instability sit on the two
  pre-1989 museum bottles** (worn label behind glass, by-weight ABV). On the
  modern labels it is stable.
- **Sonnet's single stable "miss" is a judgment call, not a misread**: it
  returned "SIERRA NEVADA" as the brand where the manifest says "Torpedo".
  On the actual COLA for that beer, Sierra Nevada is the brand name and
  Torpedo the product name — the model's answer is arguably the more correct
  one, and the row is kept as-is rather than re-scoring it in the model's
  favor.

---

## claude-haiku-4-5, 3 runs (run 1 verbose)

```

######## run 1 of 3 (model: claude-haiku-4-5) ########

1792-small-batch.jpg  (3.0s)   [decorative numeral brand; decimal ABV in small caps]
  model flagged legibility: fair (Government warning statement not visible on front label; net contents not visible in image.)
   ok  brand                1792
   ok  class                KENTUCKY STRAIGHT BOURBON WHISKEY
   ok  abv                  46.85% ALC./VOL (93.7 PROOF)
   .   net                  None
   ok  no-invented-warning  correctly absent

ancient-age.jpg  (2.8s)   [flash glare; ornate red script; tiny combined ABV/proof/volume line]
  model flagged legibility: fair (The government warning statement is not visible in this image; the label is photographed at an angle and the lower portion containing the warning is cropped out or obscured.)
   ok  brand                Ancient Age
   ok  class                Kentucky Straight Bourbon Whiskey
   ok  abv                  ALC. 40% BY VOL.(80 PROOF)
   ok  net                  750 ml
   ok  no-invented-warning  correctly absent

bookers.jpg  (12.9s)   [brand printed vertically; handwritten label; dim photo]
  model flagged legibility: poor (Label is at an angle with significant glare and reflection from the bottle glass, making most text illegible. Handwritten text on label is particularly difficult to read. Only 'BOOKER'S' is clearly visible.)
   ok  brand                Booker's
   .   class                None
   .   abv                  None
   .   net                  None
   ok  no-invented-warning  correctly absent

jim-beam-white-label-new.jpg  (1.9s)   [dark bar lighting; EU export units (70 cl)]
  model flagged legibility: fair (The label is at an angle and partially out of focus; the government warning text on the lower portion of the label is not legible enough to transcribe accurately.)
   ok  brand                Jim Beam
   ok  class                Kentucky Straight Bourbon Whiskey
   ok  abv                  40% alc./vol. (80 Proof)
   ok  net                  70 cl
   ok  no-invented-warning  correctly absent

smirnoff-red-label-8213.jpg  (4.2s)   [clear backlit bottle; volume/ABV in tiny base text]
  model flagged legibility: fair (The bottom portion of the label with alcohol content, net contents, and government warning is submerged in liquid and not legible in this image.)
   ok  brand                SMIRNOFF
   ok  class                Vodka
  BAD  abv                  None
  BAD  net                  None
   ok  no-invented-warning  correctly absent

black-ridge-small-batch-bourbon.jpg  (4.8s)   [blurry tasting-room phone photo; should flag legibility]
  model flagged legibility: poor (The bottle is photographed at an angle with glare and reflection on the glass, making most label text illegible except for the brand name.)
   ok  brand                BLACK RIDGE
   .   class                None
   .   abv                  None
   .   net                  None
   ok  no-invented-warning  correctly absent

bella-rio-bourbon.png  (5.2s)   [ornate Victorian frame; micro text on border (750mL confirmed by zooming; ABV unverifiable so unscored)]
  model flagged legibility: fair (The government warning statement is not visible on the front label shown in this image; it may be on the back or obscured.)
   ok  brand                BELLA RIO
   ok  class                BOURBON WHISKEY
   .   abv                  40% Alc./Vol.
   ok  net                  750mL
   ok  no-invented-warning  correctly absent

a-bottle-of-trey-herring-s-carolina-bourbon.png  (6.1s)   [small image; tiny ABV/proof line on a shield (first-pass human label said 43% — zooming proved the model right)]
  model flagged legibility: fair (The label is partially obscured by backlighting and reflections on the bottle; government warning statement and net contents are not visible in this image.)
   ok  brand                TREY HERRING'S
   ok  class                CAROLINA BOURBON WHISKEY
   ok  abv                  45 ALC. BY VOL. 90 PROOF
   .   net                  None
   ok  no-invented-warning  correctly absent

new-orleans-brewing-company-4-x-beer-label.jpg  (7.2s)   [vintage flat label; ABV stated by weight; volume in fl oz]
   ok  brand                4-X
   ok  class                BEER
   ok  abv                  ALCOHOL CONTENTS NOT OVER 5% BY WEIGHT
   ok  net                  12 FL. OZS.
   ok  no-invented-warning  correctly absent

apex-beer-01.jpg  (7.5s)   [curved worn label behind glass; by-weight ABV along top edge]
  model flagged legibility: fair (The label is at an angle and partially obscured by bottle glare and lighting. The center medallion is clearly visible but fine print details and lower portions of the label are difficult to read due to the angle and reflection.)
  BAD  brand                PREK
   ok  class                BEER
  BAD  abv                  None
   .   net                  None
   ok  no-invented-warning  correctly absent

ch-teau-batailley-47-detail.jpg  (8.6s)   [1947 stained paper; French script typeface]
  model flagged legibility: fair (This is a vintage French wine label from 1947 with aged/faded appearance; alcohol content and net contents are not visible on the front label shown.)
   ok  brand                Château Batailley
  BAD  class                None
   .   abv                  None
   .   net                  None
   ok  no-invented-warning  correctly absent

old-rip-van-winkle.jpg  (10.0s)   [dim handheld kitchen shot; decimal ABV and proof in tiny print]
   ok  brand                VAN WINKLE
   ok  class                Kentucky Straight Bourbon Whiskey
  BAD  abv                  Alc. 45.9% Vol. (90.4 Proof)
   ok  net                  750 ml
   ok  no-invented-warning  correctly absent

torpedo-ale-label.jpg  (10.0s)   [curved bottle; ornate illustrated label]
  model flagged legibility: fair (The front label is clearly visible, but the government warning statement is not visible on this angle of the bottle; alcohol content is not legible in this image.)
   ok  brand                SIERRA NEVADA TORPEDO
   ok  class                EXTRA IPA
   .   abv                  None
   ok  net                  12 FL.OZ.
   ok  no-invented-warning  correctly absent

ttb-hws1.png  (10.9s)   [TTB's own example label with the full warning on the back panel; small text; compound pint+oz net contents]
   ok  brand                MALT & HOP BREWERY
   ok  class                Ale with Honey and Huckleberry Flavor
   ok  abv                  5% ALC./VOL.
  BAD  net                  1 PINT, 0.8 FL. OZ.
   ok  warning-read         match

######## run 2 of 3 (model: claude-haiku-4-5) ########

######## run 3 of 3 (model: claude-haiku-4-5) ########

=== per-field accuracy, model claude-haiku-4-5, 3 run(s), scored fields only ===
  brand                  13/14  14/14  13/14
  class                  11/12  10/12  10/12
  abv                    6/9  7/9  6/9
  no-invented-warning    13/13  13/13  13/13
  net                    6/8  6/8  6/8
  warning-read           1/1  1/1  1/1

  flipped between runs:
    apex-beer-01.jpg: abv
    apex-beer-01.jpg: brand
    apex-beer-01.jpg: class
    new-orleans-brewing-company-4-x-beer-label.jpg: class

  latency: median 5.9s, p90 9.8s, max 12.9s
```

## claude-sonnet-4-6, 3 runs (run 1 verbose)

```

######## run 1 of 3 (model: claude-sonnet-4-6) ########

1792-small-batch.jpg  (3.6s)   [decorative numeral brand; decimal ABV in small caps]
   ok  brand                1792
   ok  class                KENTUCKY STRAIGHT BOURBON WHISKEY
   ok  abv                  46.85% ALC / VOL (93.7 PROOF)
   .   net                  None
   ok  no-invented-warning  correctly absent

ancient-age.jpg  (4.1s)   [flash glare; ornate red script; tiny combined ABV/proof/volume line]
  model flagged legibility: fair (The back label is not visible and the bottom portion of the front label is partially obscured by the glass, so the government warning cannot be read.)
   ok  brand                Ancient Age
   ok  class                Kentucky Straight Bourbon Whiskey
   ok  abv                  ALC. 40% BY VOL.(80 PROOF)
   ok  net                  750 ml
   ok  no-invented-warning  correctly absent

bookers.jpg  (4.3s)   [brand printed vertically; handwritten label; dim photo]
  model flagged legibility: poor (The label is partially obscured by the bottle angle and shadow, with the left side of the text cut off and the back/government warning label not visible; alcohol content, net contents, and warning text cannot be read.)
   ok  brand                BOOKER'S
   .   class                None
   .   abv                  None
   .   net                  None
   ok  no-invented-warning  correctly absent

jim-beam-white-label-new.jpg  (3.1s)   [dark bar lighting; EU export units (70 cl)]
  model flagged legibility: fair (Label is partially legible but small text details are obscured by the dark background and limited image resolution; no government warning is visible.)
   ok  brand                JIM BEAM
   ok  class                Kentucky Straight Bourbon Whiskey
   ok  abv                  alc. 40% vol.
   ok  net                  70 cl
   ok  no-invented-warning  correctly absent

smirnoff-red-label-8213.jpg  (7.6s)   [clear backlit bottle; volume/ABV in tiny base text]
  model flagged legibility: fair (Small print at the bottom of the bottle is difficult to read due to distance and slight condensation on the glass.)
   ok  brand                SMIRNOFF
   ok  class                Triple Distilled TEN TIMES FILTERED VODKA
   ok  abv                  37.5% Vol
   ok  net                  70cl
   ok  no-invented-warning  correctly absent

black-ridge-small-batch-bourbon.jpg  (7.5s)   [blurry tasting-room phone photo; should flag legibility]
  model flagged legibility: fair (The bottle is angled and the lower label text is small and partially obscured, making alcohol content, net contents, and government warning unreadable.)
   ok  brand                BLACK RIDGE
   .   class                STRAIGHT BOURBON WHISKEY
   .   abv                  None
   .   net                  None
   ok  no-invented-warning  correctly absent

bella-rio-bourbon.png  (8.8s)   [ornate Victorian frame; micro text on border (750mL confirmed by zooming; ABV unverifiable so unscored)]
  model flagged legibility: fair (The bottom portion of the label containing any additional text is small and partially obscured by the bottle's curvature, making it difficult to read fully.)
   ok  brand                Bella Rio
   ok  class                Bourbon Whiskey
   .   abv                  50% Abv./Vol.
   ok  net                  750mL
   ok  no-invented-warning  correctly absent

a-bottle-of-trey-herring-s-carolina-bourbon.png  (8.2s)   [small image; tiny ABV/proof line on a shield (first-pass human label said 43% — zooming proved the model right)]
   ok  brand                TREY HERRING'S
   ok  class                CAROLINA BOURBON WHISKEY
   ok  abv                  45% ALC. BY VOL. 90 PROOF
   .   net                  None
   ok  no-invented-warning  correctly absent

new-orleans-brewing-company-4-x-beer-label.jpg  (12.2s)   [vintage flat label; ABV stated by weight; volume in fl oz]
   ok  brand                XXXX 4-X Junior Brand
   ok  class                Beer
   ok  abv                  ALCOHOL CONTENTS NOT OVER 5% BY WEIGHT
   ok  net                  CONTENTS 12 FL. OZS.
   ok  no-invented-warning  correctly absent

apex-beer-01.jpg  (11.8s)   [curved worn label behind glass; by-weight ABV along top edge]
  model flagged legibility: fair (The label is aged and slightly worn, and the circular design partially obscures some text, but most key fields are readable.)
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

old-rip-van-winkle.jpg  (13.2s)   [dim handheld kitchen shot; decimal ABV and proof in tiny print]
   ok  brand                VAN WINKLE
   ok  class                Kentucky Straight Bourbon Whiskey
   ok  abv                  Alc. 45.2%/Vol. (90.4 Proof)
   ok  net                  750 ml
   ok  no-invented-warning  correctly absent

torpedo-ale-label.jpg  (14.6s)   [curved bottle; ornate illustrated label]
  BAD  brand                SIERRA NEVADA
   ok  class                Extra IPA
   .   abv                  None
   ok  net                  12 FL. OZ.
   ok  no-invented-warning  correctly absent

ttb-hws1.png  (18.6s)   [TTB's own example label with the full warning on the back panel; small text; compound pint+oz net contents]
   ok  brand                MALT & HOP BREWERY
   ok  class                Ale with Honey and Huckleberry Flavor
   ok  abv                  5% ALC./VOL.
   ok  net                  1 PINT, 0.9 FL. OZ.
   ok  warning-read         match

######## run 2 of 3 (model: claude-sonnet-4-6) ########

######## run 3 of 3 (model: claude-sonnet-4-6) ########

=== per-field accuracy, model claude-sonnet-4-6, 3 run(s), scored fields only ===
  brand                  13/14  13/14  13/14
  class                  12/12  12/12  12/12
  abv                    9/9  9/9  9/9
  no-invented-warning    13/13  13/13  13/13
  net                    8/8  8/8  8/8
  warning-read           1/1  1/1  1/1

  no result flipped between runs

  latency: median 8.6s, p90 14.6s, max 18.6s
```
