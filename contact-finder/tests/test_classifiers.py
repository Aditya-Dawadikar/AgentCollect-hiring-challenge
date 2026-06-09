import pytest

from classification.features import FEATURE_NAMES, signals_to_vector
from classification.v1_rule_based import RuleBasedClassifier
from data_comparison.conflict_resolver import ConflictResolver
from data_comparison.email_matcher import EmailMatcher
from data_comparison.fuzzy_matcher import FuzzyNameMatcher
from data_comparison.phone_matcher import PhoneMatcher
from data_comparison.signal_fusion import SignalFusionEngine
from data_sources.mocks import MockProviderClient

ZERO_SIGNALS = {
    "has_registry_name": False,
    "has_listing_name": False,
    "has_enrichment_email": False,
    "has_listing_phone": False,
    "has_enrichment_phone": False,
    "sources_count": 0,
    "name_sources_agree": False,
    "email_matches_name": False,
    "phone_sources_agree": False,
    "generic_email": False,
    "role_is_decision_maker": False,
    "enrichment_provider_confidence": 0,
    "has_conflict": False,
}


def _signals(**overrides):
    merged = dict(ZERO_SIGNALS)
    merged.update(overrides)
    return merged


@pytest.fixture
def fusion_engine():
    return SignalFusionEngine(
        mock_client=MockProviderClient(),
        name_matcher=FuzzyNameMatcher(),
        email_matcher=EmailMatcher(),
        phone_matcher=PhoneMatcher(),
        conflict_resolver=ConflictResolver(),
    )


@pytest.fixture
def classifier():
    return RuleBasedClassifier()


# --- features.signals_to_vector -------------------------------------------

def test_feature_names_has_thirteen_entries():
    assert len(FEATURE_NAMES) == 13
    assert len(set(FEATURE_NAMES)) == 13  # no duplicates


def test_signals_to_vector_projects_booleans_and_scales():
    signals = _signals(
        has_registry_name=True,
        sources_count=3,
        enrichment_provider_confidence=84,
        has_conflict=True,
    )
    vector = signals_to_vector(signals)

    assert len(vector) == 13
    assert vector[FEATURE_NAMES.index("has_registry_name")] == 1.0
    assert vector[FEATURE_NAMES.index("has_listing_name")] == 0.0
    assert vector[FEATURE_NAMES.index("sources_count")] == 3.0
    assert vector[FEATURE_NAMES.index("enrichment_provider_confidence")] == pytest.approx(0.84)
    assert vector[FEATURE_NAMES.index("has_conflict")] == 1.0


# --- RuleBasedClassifier: unit tests on hand-built signals -----------------

def test_zero_sources_short_circuits_to_cannot_verify(classifier):
    result = classifier.score(ZERO_SIGNALS)
    assert result == {
        "confidence_score": 0,
        "classification": "cannot_verify",
        "needs_human_review": True,
    }


def test_conflict_penalty_reduces_score_by_25(classifier):
    base = _signals(
        sources_count=2,
        has_registry_name=True,
        has_listing_phone=True,
        role_is_decision_maker=True,
    )
    with_conflict = dict(base, has_conflict=True)

    base_result = classifier.score(base)
    conflict_result = classifier.score(with_conflict)

    assert base_result["confidence_score"] - conflict_result["confidence_score"] == 25


def test_generic_email_single_source_penalty(classifier):
    signals = _signals(
        sources_count=1,
        has_enrichment_email=True,
        generic_email=True,
    )
    result = classifier.score(signals)

    # has_enrichment_email + generic_email -> the +20 doesn't apply
    # (generic), and the -10 single-source penalty applies.
    assert result["confidence_score"] == 0
    assert result["classification"] == "cannot_verify"
    assert result["needs_human_review"] is True


def test_score_clamped_to_zero_when_penalties_exceed_total(classifier):
    signals = _signals(
        sources_count=2,
        has_registry_name=False,
        has_conflict=True,
    )
    result = classifier.score(signals)
    assert result["confidence_score"] == 0


def test_score_clamped_to_one_hundred(classifier):
    signals = _signals(
        sources_count=3,
        has_registry_name=True,
        has_enrichment_email=True,
        has_listing_phone=True,
        has_enrichment_phone=True,
        name_sources_agree=True,
        email_matches_name=True,
        phone_sources_agree=True,
        role_is_decision_maker=True,
    )
    result = classifier.score(signals)
    # 35+20+10+15+10+5+5 = 100, already at the ceiling.
    assert result["confidence_score"] == 100
    assert result["classification"] == "high"


# --- RuleBasedClassifier: integration via real fuse() (TICKET-008 TDD table) --

def test_cedar_ridge_plumbing_scores_high(fusion_engine, classifier):
    fc = fusion_engine.fuse("Cedar Ridge Plumbing LLC", "4821 Maple Ave, Lincoln, NE 68504")
    result = classifier.score(fc.signals)

    assert result["confidence_score"] == 95
    assert result["classification"] == "high"
    assert result["needs_human_review"] is False


def test_pioneer_landscaping_scores_high(fusion_engine, classifier):
    fc = fusion_engine.fuse("Pioneer Landscaping Inc", "940 Prairie View Dr, Boise, ID 83704")
    result = classifier.score(fc.signals)

    assert result["confidence_score"] == 100
    assert result["classification"] == "high"
    assert result["needs_human_review"] is False


def test_riverside_print_and_sign_scores_cannot_verify(fusion_engine, classifier):
    fc = fusion_engine.fuse("Riverside Print & Sign", "302 W 3rd St, Davenport, IA 52801")
    result = classifier.score(fc.signals)

    assert result["confidence_score"] == 0
    assert result["classification"] == "cannot_verify"
    assert result["needs_human_review"] is True


def test_lakeside_auto_glass_scores_low(fusion_engine, classifier):
    fc = fusion_engine.fuse("Lakeside Auto Glass", "88 Lakeshore Dr, Madison, WI 53703")
    result = classifier.score(fc.signals)

    assert result["confidence_score"] == 40
    assert result["classification"] == "low"
    assert result["needs_human_review"] is True


def test_coastal_breeze_pool_service_conflict_penalty(fusion_engine, classifier):
    fc = fusion_engine.fuse("Coastal Breeze Pool Service", "233 Seagrape Way, Sarasota, FL 34236")
    result = classifier.score(fc.signals)

    # Without the -25 conflict penalty this would score 50
    # (has_registry_name 35 + has phone 10 + role_is_decision_maker 5).
    assert result["confidence_score"] == 25
    assert result["classification"] == "cannot_verify"
    assert result["needs_human_review"] is True


def test_redwood_cabinetry_no_data(fusion_engine, classifier):
    fc = fusion_engine.fuse("Redwood Cabinetry", "509 Timber Ct, Eugene, OR 97401")
    result = classifier.score(fc.signals)

    assert result == {
        "confidence_score": 0,
        "classification": "cannot_verify",
        "needs_human_review": True,
    }


# --- RuleBasedClassifier: full sweep over every CSV row --------------------

def test_score_runs_for_every_company_without_error(fusion_engine, classifier):
    from data_sources.loader import load_companies

    for company in load_companies():
        fc = fusion_engine.fuse(company["company_name"], company["mailing_address"])
        result = classifier.score(fc.signals)

        assert 0 <= result["confidence_score"] <= 100
        assert result["classification"] in {"high", "medium", "low", "cannot_verify"}
        assert isinstance(result["needs_human_review"], bool)
        assert result["needs_human_review"] == (result["confidence_score"] < classifier.threshold)
