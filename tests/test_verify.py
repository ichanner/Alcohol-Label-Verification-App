"""Tests for the comparison logic. A lot of these come straight out of the
discovery notes (the STONE'S THROW capitalization story, the title-case
warning catch, etc)."""

from labelcheck import govwarning, verify
from labelcheck.verify import MATCH, MISMATCH, MISSING, REVIEW


# --- brand name ----------------------------------------------------------------

def test_brand_exact_match():
    r = verify.check_text("brand_name", "Brand", "OLD TOM DISTILLERY", "OLD TOM DISTILLERY")
    assert r["status"] == MATCH
    assert r["notes"] == []


def test_brand_case_difference_matches_with_note():
    # Dave's example: same brand, different case — flagged, not failed.
    r = verify.check_text("brand_name", "Brand", "Stone's Throw", "STONE'S THROW")
    assert r["status"] == MATCH
    assert "capitalization" in r["notes"][0]


def test_brand_curly_apostrophe_is_fine():
    r = verify.check_text("brand_name", "Brand", "Stone's Throw", "Stone’s Throw")
    assert r["status"] == MATCH


def test_diacritics_fold_to_match():
    # "Château" and "Chateau", "Añejo" and "Anejo" are the same word.
    assert verify.check_text("brand_name", "Brand",
                             "Chateau Batailley", "Château Batailley")["status"] == MATCH
    assert verify.check_text("class_type", "Class",
                             "Tequila Anejo", "Tequila Añejo")["status"] == MATCH


def test_ampersand_equals_and():
    # "Malt & Hop" and "Malt and Hop" are the same brand.
    assert verify.check_text("brand_name", "Brand",
                             "Malt & Hop", "Malt and Hop")["status"] == MATCH
    # and it must not paper over a genuinely different name
    assert verify.check_text("brand_name", "Brand",
                             "Malt & Hop", "Hops & Grain")["status"] == MISMATCH


def test_brand_typo_needs_review():
    r = verify.check_text("brand_name", "Brand", "OLD TOM DISTILLERY", "OLD TOM DISTILERY")
    assert r["status"] == REVIEW


def test_brand_different_name_is_mismatch():
    r = verify.check_text("brand_name", "Brand", "OLD TOM DISTILLERY", "RIVERBEND GIN CO")
    assert r["status"] == MISMATCH


def test_label_adds_qualifier_is_review_not_fail():
    # The label states the same thing plus an extra word — agent's call, not
    # a hard fail. ("Malt & Hop" vs "Malt & Hop Brewery" came up in testing.)
    r = verify.check_text("brand_name", "Brand", "Malt & Hop", "MALT & HOP BREWERY")
    assert r["status"] == REVIEW
    r2 = verify.check_text("class_type", "Class", "Ale",
                           "Ale with Honey and Huckleberry Flavor", fuzzy=0.8)
    assert r2["status"] == REVIEW


def test_substring_word_boundary_not_fooled():
    # "Ale" must not be treated as contained in "Pale Ale Lager"? It IS a
    # whole word there, so that's a legitimate review. But "Ale" vs "Tale"
    # must NOT match as containment (different word).
    r = verify.check_text("class_type", "Class", "Ale", "Tale of Two Barrels", fuzzy=0.8)
    assert r["status"] == MISMATCH


def test_brand_missing_from_label():
    r = verify.check_text("brand_name", "Brand", "OLD TOM DISTILLERY", None)
    assert r["status"] == MISSING


# --- alcohol content -------------------------------------------------------------

def test_abv_parses_common_formats():
    assert verify.parse_abv("45% Alc./Vol. (90 Proof)") == 45.0
    assert verify.parse_abv("ALC. 13.5% BY VOL.") == 13.5
    assert verify.parse_abv("90 PROOF") == 45.0
    assert verify.parse_abv("45") == 45.0
    assert verify.parse_abv(None) is None


def test_abv_match_despite_formatting():
    r = verify.check_abv("45%", "45% Alc./Vol. (90 Proof)")
    assert r["status"] == MATCH


def test_abv_mismatch():
    r = verify.check_abv("45%", "40% Alc./Vol. (80 Proof)")
    assert r["status"] == MISMATCH
    assert "45" in r["notes"][0] and "40" in r["notes"][0]


def test_abv_blank_application_is_review_optional():
    # ABV is optional (wine/beer exemptions); blank should read as intentional,
    # not a parse error.
    r = verify.check_abv("", "12% Alc./Vol.")
    assert r["status"] == REVIEW
    assert "optional" in r["notes"][0].lower()


def test_abv_inconsistent_proof_flagged():
    # ABV agrees with the application but the label's own proof is wrong.
    r = verify.check_abv("45%", "45% Alc./Vol. (80 Proof)")
    assert r["status"] == REVIEW


def test_abv_misread_percent_caught_by_proof():
    # The Van Winkle case: model misreads 45.2% as 45.9%, but reads the proof
    # (90.4) correctly. The proof implies 45.2%, matching the application, so
    # this is a likely misread -> review, not a hard mismatch.
    r = verify.check_abv("45.2%", "Alc. 45.9% Vol. (90.4 Proof)")
    assert r["status"] == REVIEW
    assert "proof" in r["notes"][0].lower() and "misread" in r["notes"][0].lower()


def test_abv_genuine_mismatch_with_matching_proof_still_fails():
    # Both % and proof say 40 while the application says 45 — that's a real
    # mismatch, not a misread, and must still fail.
    r = verify.check_abv("45%", "40% Alc./Vol. (80 Proof)")
    assert r["status"] == MISMATCH


# --- net contents ----------------------------------------------------------------

def test_volume_parsing_and_units():
    assert verify.parse_volume_ml("750 mL") == 750
    assert verify.parse_volume_ml("750ML") == 750
    assert verify.parse_volume_ml("75 cl") == 750
    assert verify.parse_volume_ml("1.75 L") == 1750
    assert verify.parse_volume_ml("smooth and mellow") is None


def test_net_contents_same_volume_different_unit():
    r = verify.check_net_contents("750 mL", "75 cL")
    assert r["status"] == MATCH
    assert "Same volume" in r["notes"][0]


def test_volume_pints_and_compound_quantities():
    # the "1 PT. 0.9 FL. OZ." format on US beer bottles (~500 mL)
    assert abs(verify.parse_volume_ml("1 PT. 0.9 FL. OZ.") - 499.8) < 0.5
    assert abs(verify.parse_volume_ml("1 pint") - 473.2) < 0.1
    r = verify.check_net_contents("500 mL", "1 PINT, 0.9 FL. OZ.")
    assert r["status"] == MATCH


def test_net_contents_mismatch():
    r = verify.check_net_contents("750 mL", "700 mL")
    assert r["status"] == MISMATCH


def test_net_contents_floz_rounding_matches():
    # "25.4 FL OZ" is 751 mL — the same 750 mL bottle, rounded. Should match.
    assert verify.check_net_contents("750 mL", "25.4 fl oz")["status"] == MATCH
    # but adjacent standard sizes must still be caught as different
    assert verify.check_net_contents("750 mL", "720 mL")["status"] == MISMATCH


# --- government warning -----------------------------------------------------------

def test_warning_exact_text_passes():
    r = govwarning.check(govwarning.FULL_TEXT, prefix_bold=True)
    assert r["status"] == MATCH


def test_warning_title_case_prefix_rejected():
    # Jenny's catch: "Government Warning" in title case gets rejected outright.
    text = govwarning.FULL_TEXT.replace("GOVERNMENT WARNING:", "Government Warning:")
    r = govwarning.check(text, prefix_bold=True)
    assert r["status"] == MISMATCH
    assert "capitals" in r["notes"][0]


def test_warning_reworded_body_rejected():
    text = govwarning.FULL_TEXT.replace("should not drink", "should avoid")
    r = govwarning.check(text, prefix_bold=True)
    assert r["status"] == MISMATCH
    assert "differs at word" in r["notes"][0]


def test_warning_with_trailing_declaration_is_review_not_fail():
    # Real labels print the warning right next to other mandatory text (e.g.
    # a sulfite declaration), which the model can capture together. The
    # warning itself is correct, so this should flag for review, not fail.
    text = govwarning.FULL_TEXT + " CONTAINS: SULFITES"
    r = govwarning.check(text, prefix_bold=True)
    assert r["status"] == REVIEW
    assert "extra text" in r["notes"][0].lower()


def test_warning_truncated_rejected():
    text = " ".join(govwarning.FULL_TEXT.split()[:20])
    r = govwarning.check(text, prefix_bold=True)
    assert r["status"] == MISMATCH
    assert "cut short" in r["notes"][0]


def test_warning_missing():
    r = govwarning.check(None, prefix_bold=None)
    assert r["status"] == MISSING


def test_warning_not_bold_needs_review_not_fail():
    r = govwarning.check(govwarning.FULL_TEXT, prefix_bold=False)
    assert r["status"] == REVIEW


def test_warning_whitespace_and_linebreaks_ok():
    # Labels wrap the statement over several lines; that shouldn't matter.
    wrapped = govwarning.FULL_TEXT.replace("Surgeon General,", "Surgeon\nGeneral,")
    r = govwarning.check(wrapped, prefix_bold=True)
    assert r["status"] == MATCH


# --- overall verdict ---------------------------------------------------------------

def _extraction(**overrides):
    fields = {
        "brand_name": "OLD TOM DISTILLERY",
        "class_type": "Kentucky Straight Bourbon Whiskey",
        "alcohol_content": "45% Alc./Vol. (90 Proof)",
        "net_contents": "750 mL",
        "government_warning": govwarning.FULL_TEXT,
        "warning_prefix_bold": True,
        "legibility": "good",
        "legibility_notes": None,
    }
    fields.update(overrides)
    return fields


APPLICATION = {
    "brand_name": "OLD TOM DISTILLERY",
    "class_type": "Kentucky Straight Bourbon Whiskey",
    "alcohol_content": "45%",
    "net_contents": "750 mL",
}


def test_clean_label_passes():
    result = verify.verify_label(APPLICATION, _extraction())
    assert result["overall"] == "pass"


def test_one_mismatch_fails_the_label():
    result = verify.verify_label(APPLICATION, _extraction(alcohol_content="40% Alc./Vol."))
    assert result["overall"] == "fail"


def test_missing_warning_fails():
    # The warning is mandatory on every alcohol label, so a missing one is
    # always a problem to resolve — fail, not a soft review (Sarah/Jenny).
    result = verify.verify_label(APPLICATION, _extraction(government_warning=None))
    assert result["overall"] == "fail"


def test_visible_wrong_warning_still_fails():
    # A title-case warning IS visible and IS wrong — that's a real, observed
    # violation and must still fail (Jenny's catch).
    bad = govwarning.FULL_TEXT.replace("GOVERNMENT WARNING:", "Government Warning:")
    result = verify.verify_label(APPLICATION, _extraction(government_warning=bad))
    assert result["overall"] == "fail"


def test_missing_non_warning_field_is_review_not_fail():
    # Net contents not visible in the image, but everything else (including the
    # warning) matches — net can be on another panel, so this is review.
    result = verify.verify_label(APPLICATION, _extraction(net_contents=None))
    assert result["overall"] == "review"


def test_fuzzy_field_demotes_to_review():
    result = verify.verify_label(
        APPLICATION, _extraction(class_type="Kentucky Strait Bourbon Whiskey"))
    assert result["overall"] == "review"


def test_poor_legibility_blocks_a_clean_pass():
    result = verify.verify_label(
        APPLICATION, _extraction(legibility="poor", legibility_notes="glare across the bottom"))
    assert result["overall"] == "review"
    assert any("Image quality" in n for n in result["notes"])
