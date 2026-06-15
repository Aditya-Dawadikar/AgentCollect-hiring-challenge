import contact_finder as cf


# ---- name helpers -----------------------------------------------------

def test_normalize_name_tokens_strips_honorifics_and_parens():
    assert cf.normalize_name_tokens("Dr. Emily Hart") == ["emily", "hart"]
    assert cf.normalize_name_tokens("Jeff (manager)") == ["jeff"]


def test_extract_and_strip_role_hint():
    assert cf.extract_role_hint("Jeff (manager)") == "Manager"
    assert cf.strip_role_hint("Jeff (manager)") == "Jeff"
    assert cf.extract_role_hint("Daniel Ortega") == ""


def test_names_match_on_surname_only():
    assert cf.names_match("Robert Kowalski", "Bob Kowalski") is True
    assert cf.names_match("Sean Murphy", "S. Murphy") is True
    assert cf.names_match("Tina Alvarez", "Marcus Webb") is False


def test_email_matches_name():
    assert cf.email_matches_name("d.ortega@example.com", "Daniel Ortega") is True
    assert cf.email_matches_name("karen@example.com", "Karen Liu") is True
    assert cf.email_matches_name("info@example.com", "Daniel Ortega") is False
    assert cf.email_matches_name("jeff@example.com", "Jeff") is True


# ---- resolve_identity ---------------------------------------------------

def test_identity_registry_only():
    registry = {"name": "Daniel Ortega", "role": "Owner", "source_url": "mock://registry/x"}
    identity = cf.resolve_identity(registry, None)
    assert identity.name == "Daniel Ortega"
    assert identity.role == "Owner"
    assert identity.base_score == cf.IDENTITY_BASE_REGISTRY
    assert identity.conflict is False


def test_identity_listing_only_with_role_hint():
    listing = {"name": "Jeff (manager)", "phone": "+1-555-0100", "source_url": "mock://listing/x"}
    identity = cf.resolve_identity(None, listing)
    assert identity.name == "Jeff"
    assert identity.role == "Manager"
    assert identity.base_score == cf.IDENTITY_BASE_LISTING_ONLY


def test_identity_registered_agent_gets_reduced_base_score():
    registry = {"name": "Thomas Reed", "role": "Registered Agent", "source_url": "mock://registry/x"}
    identity = cf.resolve_identity(registry, None)
    assert identity.base_score == cf.IDENTITY_BASE_REGISTERED_AGENT
    assert identity.base_score < cf.IDENTITY_BASE_REGISTRY


def test_identity_conflict_when_registry_and_listing_disagree():
    registry = {"name": "Tina Alvarez", "role": "Manager", "source_url": "mock://registry/x"}
    listing = {"name": "Marcus Webb", "phone": "+1-555-0100", "source_url": "mock://listing/x"}
    identity = cf.resolve_identity(registry, listing)
    assert identity.conflict is True
    assert identity.name == "Tina Alvarez"  # registry wins on authority
    assert identity.conflicting_name == "Marcus Webb"


def test_identity_no_sources():
    identity = cf.resolve_identity(None, None)
    assert identity.name == ""
    assert identity.base_score == 0


# ---- resolve_contact ----------------------------------------------------

def test_contact_prefers_enrichment_email_over_listing_phone():
    enrichment = {"email": "a@example.com", "phone": None, "provider_confidence": 80, "source_url": "mock://enrichment/x"}
    listing = {"name": "A", "phone": "+1-555-0100", "source_url": "mock://listing/x"}
    identity = cf.Identity(name="A")
    contact = cf.resolve_contact(enrichment, listing, identity)
    assert contact.value == "a@example.com"
    assert contact.base_score == cf.CONTACT_WEIGHT_ENRICHMENT * 0.80


def test_contact_falls_back_to_listing_phone_when_no_enrichment():
    listing = {"name": "A", "phone": "+1-555-0100", "source_url": "mock://listing/x"}
    identity = cf.Identity(name="A")
    contact = cf.resolve_contact(None, listing, identity)
    assert contact.value == "+1-555-0100"
    assert contact.base_score == cf.CONTACT_BASE_LISTING_PHONE


def test_conflicting_identity_does_not_borrow_listing_phone():
    listing = {"name": "Marcus Webb", "phone": "+1-555-0100", "source_url": "mock://listing/x"}
    identity = cf.Identity(name="Tina Alvarez", conflict=True)
    contact = cf.resolve_contact(None, listing, identity)
    assert contact.value == ""
    assert contact.base_score == 0


# ---- compute_agreement_bonus --------------------------------------------

def test_agreement_bonus_zero_when_nothing_corroborates():
    enrichment = {"email": "info@example.com", "phone": None, "provider_confidence": 40, "source_url": "x"}
    identity = cf.Identity()  # no name found, so email-identity match can't apply
    bonus, agreements = cf.compute_agreement_bonus(None, None, enrichment, identity)
    assert bonus == 0
    assert agreements == []


def test_agreement_bonus_single_for_one_corroboration():
    registry = {"name": "Karen Liu", "role": "Owner", "source_url": "x"}
    enrichment = {"email": "karen@example.com", "phone": None, "provider_confidence": 78, "source_url": "y"}
    identity = cf.resolve_identity(registry, None)
    bonus, agreements = cf.compute_agreement_bonus(registry, None, enrichment, identity)
    assert bonus == cf.AGREEMENT_BONUS_SINGLE
    assert agreements == ["enrichment_email_identity_match"]


def test_agreement_bonus_multi_when_two_signals_corroborate():
    registry = {"name": "Maria Gomez", "role": "President", "source_url": "x"}
    listing = {"name": "Maria Gomez", "phone": "+1-208-555-0175", "source_url": "y"}
    enrichment = {"email": "maria@example.com", "phone": "+1-208-555-0175", "provider_confidence": 88, "source_url": "z"}
    identity = cf.resolve_identity(registry, listing)
    bonus, agreements = cf.compute_agreement_bonus(registry, listing, enrichment, identity)
    assert bonus == cf.AGREEMENT_BONUS_MULTI
    assert len(agreements) >= 2


def test_agreement_bonus_is_zero_on_conflict():
    registry = {"name": "Tina Alvarez", "role": "Manager", "source_url": "x"}
    listing = {"name": "Marcus Webb", "phone": "+1-555-0100", "source_url": "y"}
    identity = cf.resolve_identity(registry, listing)
    bonus, agreements = cf.compute_agreement_bonus(registry, listing, None, identity)
    assert bonus == 0
    assert agreements == []


# ---- score_company integration (using real mock fixtures) ---------------

MOCKS = cf.load_mock_data()


def test_all_sources_agree_scores_high_and_passes():
    row = cf.score_company("Cedar Ridge Plumbing LLC", "addr", MOCKS["Cedar Ridge Plumbing LLC"])
    assert row["confidence_score"] >= cf.CONFIDENCE_THRESHOLD
    assert row["needs_human_review"] is False
    assert row["contact_email_or_phone"] == "d.ortega@cedarridgeplumbing.com"
    assert "registry" in row["source"] and "enrichment" in row["source"]
    assert row["provenance"]["contact_email_or_phone"] == ["mock://enrichment/cedar-ridge-plumbing"]


def test_single_weak_enrichment_guess_scores_low_and_is_blanked():
    row = cf.score_company("Riverside Print & Sign", "addr", MOCKS["Riverside Print & Sign"])
    assert row["confidence_score"] < cf.CONFIDENCE_THRESHOLD
    assert row["needs_human_review"] is True
    assert row["contact_email_or_phone"] == ""
    assert row["review_reason"] == "single_weak_source"


def test_identity_conflict_company_flags_review_and_reports_higher_authority_name():
    row = cf.score_company("Coastal Breeze Pool Service", "addr", MOCKS["Coastal Breeze Pool Service"])
    assert row["needs_human_review"] is True
    assert row["review_reason"] == "identity_conflict"
    assert row["contact_name"] == "Tina Alvarez"  # registry, higher authority
    assert row["contact_email_or_phone"] == ""
    assert "Marcus Webb" in row["notes"]


def test_registered_agent_only_has_no_contact_method():
    row = cf.score_company("Northgate HVAC Services", "addr", MOCKS["Northgate HVAC Services"])
    assert row["contact_name"] == "Thomas Reed"
    assert row["contact_role"] == "Registered Agent"
    assert row["contact_email_or_phone"] == ""
    assert row["needs_human_review"] is True
    assert row["review_reason"] == "no_contact_method"


def test_company_absent_from_mocks_is_cannot_verify():
    row = cf.score_company("Some Company Not In Mocks", "addr", {})
    assert row["confidence_score"] == 0
    assert row["needs_human_review"] is True
    assert row["review_reason"] == "no_sources"
    assert row["contact_name"] == ""
    assert row["contact_email_or_phone"] == ""
    assert row["source"] == []


# ---- threshold gate invariants ------------------------------------------

def test_every_row_below_threshold_has_blank_contact_and_review_flag():
    for row in cf.run():
        if row["confidence_score"] < cf.CONFIDENCE_THRESHOLD:
            assert row["contact_email_or_phone"] == ""
            assert row["needs_human_review"] is True


def test_every_emitted_contact_has_provenance():
    for row in cf.run():
        if row["contact_email_or_phone"]:
            assert row["provenance"]["contact_email_or_phone"], row["company_name"]


def test_run_covers_full_csv():
    companies = cf.load_companies()
    results = cf.run()
    assert len(results) == len(companies) == 30
