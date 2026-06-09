"""Projects the TICKET-007 `signals` dict onto a fixed-order numeric
feature vector, shared by both classifiers (v1 reads `signals` directly
for readability, but uses the same FEATURE_NAMES order for testing; v2
uses `signals_to_vector` as its model input)."""

FEATURE_NAMES = [
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
]


def signals_to_vector(signals: dict) -> list[float]:
    """Booleans -> 0.0/1.0, `sources_count` -> raw 0.0-3.0,
    `enrichment_provider_confidence` -> 0.0-1.0 (divided by 100)."""
    vector = []
    for name in FEATURE_NAMES:
        value = signals[name]
        if name == "sources_count":
            vector.append(float(value))
        elif name == "enrichment_provider_confidence":
            vector.append(value / 100.0)
        else:
            vector.append(1.0 if value else 0.0)
    return vector
