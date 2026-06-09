import pytest

from data_comparison.email_matcher import EmailMatcher
from data_comparison.fuzzy_matcher import FuzzyNameMatcher
from data_comparison.phone_matcher import PhoneMatcher


@pytest.fixture
def name_matcher():
    return FuzzyNameMatcher()


@pytest.fixture
def email_matcher():
    return EmailMatcher()


@pytest.fixture
def phone_matcher():
    return PhoneMatcher()


# --- FuzzyNameMatcher -------------------------------------------------

def test_abbreviated_first_name_matches(name_matcher):
    # Harbor Light Electric: registry "Sean Murphy" vs listing "S. Murphy"
    assert name_matcher.match("Sean Murphy", "S. Murphy") is True


def test_honorific_is_stripped_before_matching(name_matcher):
    # Brookside Veterinary Clinic: "Dr. Emily Hart" vs "Emily Hart"
    assert name_matcher.match("Dr. Emily Hart", "Emily Hart") is True


def test_different_people_do_not_match(name_matcher):
    # Coastal Breeze Pool Service: registry "Tina Alvarez" vs listing "Marcus Webb"
    assert name_matcher.match("Tina Alvarez", "Marcus Webb") is False


def test_parenthetical_role_suffix_is_stripped(name_matcher):
    # Lakeside Auto Glass: listing name "Jeff (manager)"
    assert name_matcher.normalize("Jeff (manager)") == "Jeff"


def test_match_with_missing_name_is_false(name_matcher):
    assert name_matcher.match(None, "Daniel Ortega") is False
    assert name_matcher.match("", "Daniel Ortega") is False


def test_nickname_pairs_are_a_known_gap(name_matcher):
    # Ironclad Welding Shop: registry "Robert Kowalski" vs listing "Bob Kowalski"
    # Documented limitation (ADR-0002): pure string similarity does not
    # bridge "Robert" <-> "Bob" at threshold 85.
    assert name_matcher.match("Robert Kowalski", "Bob Kowalski") is False


# --- EmailMatcher -------------------------------------------------------

def test_generic_mailbox_local_parts_are_detected(email_matcher):
    assert email_matcher.is_generic("info@riversideprint.biz") is True
    assert email_matcher.is_generic("office@sunbeltroofingaz.com") is True
    assert email_matcher.is_generic("d.ortega@cedarridgeplumbing.com") is False


def test_email_matches_first_initial_dot_lastname(email_matcher, name_matcher):
    # Cedar Ridge Plumbing LLC
    assert email_matcher.matches_name(
        "d.ortega@cedarridgeplumbing.com", "Daniel Ortega", name_matcher
    ) is True


def test_email_matches_first_name_only(email_matcher, name_matcher):
    # Bayview Auto Repair
    assert email_matcher.matches_name(
        "karen@bayviewauto.com", "Karen Liu", name_matcher
    ) is True


def test_generic_email_does_not_match_name(email_matcher, name_matcher):
    assert email_matcher.matches_name(
        "info@riversideprint.biz", "Daniel Ortega", name_matcher
    ) is False


def test_email_match_requires_both_values(email_matcher):
    assert email_matcher.match(None, "info@example.com") is False
    assert email_matcher.match("a@example.com", "A@Example.com") is True


# --- PhoneMatcher ---------------------------------------------------------

def test_identical_phone_numbers_match(phone_matcher):
    # Sunbelt Roofing Co: listing phone == enrichment phone
    assert phone_matcher.match("+1-480-555-0133", "+1-480-555-0133") is True


def test_phone_normalization_strips_country_code(phone_matcher):
    assert phone_matcher.normalize("+1-480-555-0133") == "4805550133"
    assert phone_matcher.normalize("(480) 555-0133") == "4805550133"


def test_missing_phone_never_matches(phone_matcher):
    assert phone_matcher.match(None, "+1-480-555-0133") is False
    assert phone_matcher.match("", "") is False
