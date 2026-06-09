import pytest

from data_comparison.conflict_resolver import ConflictResolver
from data_comparison.email_matcher import EmailMatcher
from data_comparison.fuzzy_matcher import FuzzyNameMatcher
from data_comparison.phone_matcher import PhoneMatcher
from data_comparison.signal_fusion import SignalFusionEngine
from data_sources.loader import load_companies
from data_sources.mocks import MockProviderClient

SIGNAL_KEYS = {
    "has_registry_name",
    "has_listing_name",
    "has_enrichment_email",
    "has_listing_phone",
    "has_enrichment_phone",
    "sources_count",
    "name_sources_agree",
    "email_matches_name",
    "phone_sources_agree",
    "generic_email",
    "role_is_decision_maker",
    "enrichment_provider_confidence",
    "has_conflict",
}


@pytest.fixture
def name_matcher():
    return FuzzyNameMatcher()


@pytest.fixture
def email_matcher():
    return EmailMatcher()


@pytest.fixture
def phone_matcher():
    return PhoneMatcher()


@pytest.fixture
def conflict_resolver():
    return ConflictResolver()


@pytest.fixture
def fusion_engine(name_matcher, email_matcher, phone_matcher, conflict_resolver):
    return SignalFusionEngine(
        mock_client=MockProviderClient(),
        name_matcher=name_matcher,
        email_matcher=email_matcher,
        phone_matcher=phone_matcher,
        conflict_resolver=conflict_resolver,
    )


# --- ConflictResolver -----------------------------------------------------

def test_resolve_picks_registry_when_names_agree(name_matcher, conflict_resolver):
    registry = {"name": "Daniel Ortega", "role": "Owner", "source_url": "mock://registry"}
    listing = {"name": "Daniel Ortega", "phone": "x", "source_url": "mock://listing"}

    chosen, conflicts = conflict_resolver.resolve(registry, listing, name_matcher)

    assert chosen == {"name": "Daniel Ortega", "role": "Owner", "name_source": "registry"}
    assert conflicts == []


def test_resolve_flags_conflict_when_names_disagree(name_matcher, conflict_resolver):
    # Coastal Breeze Pool Service
    registry = {"name": "Tina Alvarez", "role": "Manager", "source_url": "mock://registry"}
    listing = {"name": "Marcus Webb", "phone": "x", "source_url": "mock://listing"}

    chosen, conflicts = conflict_resolver.resolve(registry, listing, name_matcher)

    assert chosen["name"] == "Tina Alvarez"
    assert chosen["name_source"] == "registry"
    assert len(conflicts) == 1
    assert conflicts[0]["field"] == "name"
    assert conflicts[0]["registry"] == "Tina Alvarez"
    assert conflicts[0]["listing"] == "Marcus Webb"


def test_resolve_falls_back_to_listing_when_registry_missing(name_matcher, conflict_resolver):
    listing = {"name": "Jeff (manager)", "phone": "x", "source_url": "mock://listing"}

    chosen, conflicts = conflict_resolver.resolve(None, listing, name_matcher)

    assert chosen == {"name": "Jeff", "role": None, "name_source": "listing"}
    assert conflicts == []


def test_resolve_with_no_names_returns_none(name_matcher, conflict_resolver):
    chosen, conflicts = conflict_resolver.resolve(None, None, name_matcher)
    assert chosen == {"name": None, "role": None, "name_source": None}
    assert conflicts == []


# --- SignalFusionEngine: representative companies (TICKET-007 TDD table) --

def test_cedar_ridge_plumbing(fusion_engine):
    fc = fusion_engine.fuse("Cedar Ridge Plumbing LLC", "4821 Maple Ave, Lincoln, NE 68504")

    assert fc.signals["sources_count"] == 3
    assert fc.signals["name_sources_agree"] is True
    assert fc.signals["email_matches_name"] is True
    assert fc.signals["has_conflict"] is False
    assert fc.candidate_name == "Daniel Ortega"
    assert fc.candidate_role == "Owner"
    assert fc.candidate_email == "d.ortega@cedarridgeplumbing.com"


def test_pioneer_landscaping(fusion_engine):
    fc = fusion_engine.fuse("Pioneer Landscaping Inc", "940 Prairie View Dr, Boise, ID 83704")

    assert fc.signals["sources_count"] == 3
    assert fc.signals["phone_sources_agree"] is True
    assert fc.signals["email_matches_name"] is True
    assert fc.candidate_phone == "+1-208-555-0175"


def test_harbor_light_electric(fusion_engine):
    fc = fusion_engine.fuse("Harbor Light Electric", "22 Dockside Ave, New Bedford, MA 02740")

    assert fc.signals["name_sources_agree"] is True  # "Sean Murphy" vs "S. Murphy"
    assert fc.signals["sources_count"] == 2
    assert fc.signals["has_enrichment_email"] is False
    assert fc.signals["enrichment_provider_confidence"] == 0
    assert fc.candidate_name == "Sean Murphy"


def test_coastal_breeze_pool_service(fusion_engine):
    fc = fusion_engine.fuse("Coastal Breeze Pool Service", "233 Seagrape Way, Sarasota, FL 34236")

    assert fc.signals["has_conflict"] is True
    assert len(fc.conflicts) == 1
    conflict = fc.conflicts[0]
    assert conflict["registry"] == "Tina Alvarez"
    assert conflict["listing"] == "Marcus Webb"


def test_sunbelt_roofing_co(fusion_engine):
    fc = fusion_engine.fuse("Sunbelt Roofing Co", "7714 Desert Bloom Rd, Mesa, AZ 85207")

    assert fc.signals["phone_sources_agree"] is True
    assert fc.signals["has_listing_name"] is False
    assert fc.candidate_name is None  # generic enrichment email "office@..." -> no fallback


def test_lakeside_auto_glass(fusion_engine):
    fc = fusion_engine.fuse("Lakeside Auto Glass", "88 Lakeshore Dr, Madison, WI 53703")

    # Listing supplies "Jeff (manager)" -> normalized to "Jeff"; the
    # enrichment email "jeff@lakesideglass.net" corroborates it.
    assert fc.candidate_name == "Jeff"
    assert fc.signals["email_matches_name"] is True
    assert fc.signals["generic_email"] is False


def test_riverside_print_and_sign(fusion_engine):
    fc = fusion_engine.fuse("Riverside Print & Sign", "302 W 3rd St, Davenport, IA 52801")

    assert fc.signals["sources_count"] == 1
    assert fc.signals["generic_email"] is True
    assert fc.signals["enrichment_provider_confidence"] == 41
    assert fc.candidate_name is None


def test_northgate_hvac_services(fusion_engine):
    fc = fusion_engine.fuse("Northgate HVAC Services", "56 Industrial Pkwy, Akron, OH 44310")

    assert fc.signals["has_registry_name"] is True
    assert fc.signals["role_is_decision_maker"] is False
    assert fc.candidate_role == "Registered Agent"


def test_redwood_cabinetry_absent(fusion_engine):
    fc = fusion_engine.fuse("Redwood Cabinetry", "509 Timber Ct, Eugene, OR 97401")

    assert fc.signals["sources_count"] == 0
    assert fc.candidate_name is None
    assert fc.candidate_email is None
    assert fc.candidate_phone is None
    for key in (
        "has_registry_name", "has_listing_name", "has_enrichment_email",
        "has_listing_phone", "has_enrichment_phone", "name_sources_agree",
        "email_matches_name", "phone_sources_agree", "generic_email",
        "role_is_decision_maker", "has_conflict",
    ):
        assert fc.signals[key] is False
    assert fc.signals["enrichment_provider_confidence"] == 0


# --- SignalFusionEngine: nickname conflict cascades through email match ---

def test_ironclad_welding_shop_nickname_conflict(fusion_engine):
    # "Robert Kowalski" (registry) vs "Bob Kowalski" (listing) scores ~81,
    # below FUZZY_NAME_THRESHOLD=85 (ADR-0002 known limitation), so this
    # is treated as a genuine name conflict even though it's the same
    # person under a nickname.
    fc = fusion_engine.fuse("Ironclad Welding Shop", "1701 Foundry Rd, Pittsburgh, PA 15201")

    assert fc.signals["name_sources_agree"] is False
    assert fc.signals["has_conflict"] is True
    assert fc.candidate_name == "Robert Kowalski"
    # The enrichment email "bob@..." matches the listing's "Bob Kowalski",
    # not the chosen registry name "Robert Kowalski".
    assert fc.signals["email_matches_name"] is False
    assert fc.signals["phone_sources_agree"] is True


# --- SignalFusionEngine: full sweep over every CSV row ---------------------

def test_fuse_runs_for_every_company_without_error(fusion_engine):
    companies = load_companies()
    assert len(companies) == 30

    for company in companies:
        fc = fusion_engine.fuse(company["company_name"], company["mailing_address"])

        assert fc.company_name == company["company_name"]
        assert fc.mailing_address == company["mailing_address"]
        assert set(fc.signals.keys()) == SIGNAL_KEYS
        assert 0 <= fc.signals["sources_count"] <= 3
        assert set(fc.sources) <= {"registry", "listing", "enrichment"}
        assert fc.signals["sources_count"] == len(fc.sources)

        if fc.signals["sources_count"] == 0:
            assert fc.candidate_name is None
            assert fc.candidate_email is None
            assert fc.candidate_phone is None
            assert fc.source_urls == {}


def test_brookside_veterinary_clinic_honorific_agreement(fusion_engine):
    fc = fusion_engine.fuse("Brookside Veterinary Clinic", "760 Willow Bend, Chattanooga, TN 37402")

    assert fc.signals["name_sources_agree"] is True  # "Dr. Emily Hart" vs "Dr. Emily Hart"
    assert fc.candidate_name == "Emily Hart"  # honorific stripped by normalize()
    assert fc.signals["email_matches_name"] is True


# --- SignalFusionEngine: email-derived-name fallback (synthetic case) -----

class _StubMockClient:
    """Synthetic provider response: no registry/listing name, but a
    non-generic enrichment email -- exercises the email-derived-name
    fallback, which never triggers on the real 18-company mock set."""

    def query_all(self, company_name):
        return {
            "registry": None,
            "listing": None,
            "enrichment": {
                "email": "jeff@example.com",
                "phone": None,
                "provider_confidence": 50,
                "source_url": "mock://enrichment/example",
            },
        }


def test_email_derived_name_fallback(name_matcher, email_matcher, phone_matcher, conflict_resolver):
    engine = SignalFusionEngine(
        mock_client=_StubMockClient(),
        name_matcher=name_matcher,
        email_matcher=email_matcher,
        phone_matcher=phone_matcher,
        conflict_resolver=conflict_resolver,
    )

    fc = engine.fuse("Example Co", "1 Main St, Springfield, IL 62701")

    assert fc.candidate_name == "Jeff"
    assert fc.signals["email_matches_name"] is True
    assert fc.source_urls["name"] == ["mock://enrichment/example"]
