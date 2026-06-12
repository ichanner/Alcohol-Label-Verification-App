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


def test_brand_typo_needs_review():
    r = verify.check_text("brand_name", "Brand", "OLD TOM DISTILLERY", "OLD TOM DISTILERY")
    assert r["status"] == REVIEW


def test_brand_different_name_is_mismatch():
    r = verify.check_text("brand_name", "Brand", "OLD TOM DISTILLERY", "RIVERBEND GIN CO")
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


def test_abv_inconsistent_proof_flagged():
    # ABV agrees with the application but the label's own proof is wrong.
    r = verify.check_abv("45%", "45% Alc./Vol. (80 Proof)")
    assert r["status"] == REVIEW


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


def test_fuzzy_field_demotes_to_review():
    result = verify.verify_label(
        APPLICATION, _extraction(class_type="Kentucky Strait Bourbon Whiskey"))
    assert result["overall"] == "review"


def test_poor_legibility_blocks_a_clean_pass():
    result = verify.verify_label(
        APPLICATION, _extraction(legibility="poor", legibility_notes="glare across the bottom"))
    assert result["overall"] == "review"
    assert any("Image quality" in n for n in result["notes"])
