"""Synthetic labeled training data for the v2 decision-tree classifier.

We only have 30 companies (18 with mock data), and most of those are held
out as ground truth for TICKET-010's evaluation -- far too few to both
train and evaluate a model without leaking the test set into training.
Instead, this module programmatically generates (signals, bucket) examples
that encode the same domain principles as v1 (ADR-0004) -- more agreeing
sources raises confidence, conflicts and lone generic emails lower it, zero
sources means cannot_verify -- via an independently-derived weighting
formula plus injected noise. See ADR-0005 for the full rationale.
"""

import random

from classification.features import signals_to_vector

BOOLEAN_SIGNAL_KEYS = [
    "has_registry_name",
    "has_listing_name",
    "has_enrichment_email",
    "has_listing_phone",
    "has_enrichment_phone",
    "name_sources_agree",
    "email_matches_name",
    "phone_sources_agree",
    "generic_email",
    "role_is_decision_maker",
    "has_conflict",
]

_ZERO_SOURCE_SIGNALS = {key: False for key in BOOLEAN_SIGNAL_KEYS}
_ZERO_SOURCE_SIGNALS["sources_count"] = 0
_ZERO_SOURCE_SIGNALS["enrichment_provider_confidence"] = 0


def _sample_signals(rng: random.Random) -> dict:
    sources_count = rng.choice([0, 1, 2, 3])
    if sources_count == 0:
        return dict(_ZERO_SOURCE_SIGNALS)

    signals = {key: rng.random() < 0.5 for key in BOOLEAN_SIGNAL_KEYS}
    signals["sources_count"] = sources_count

    if signals["has_enrichment_email"] or signals["has_enrichment_phone"]:
        # Same 0-100 scale as the real `provider_confidence` field
        # (config.settings via signal_fusion); signals_to_vector divides by
        # 100 for both real and synthetic signals alike.
        signals["enrichment_provider_confidence"] = rng.uniform(0, 100)
    else:
        signals["enrichment_provider_confidence"] = 0

    return signals


def _label_signals(signals: dict, rng: random.Random) -> str:
    if signals["sources_count"] == 0:
        return "cannot_verify"

    score = 40
    score += 5 * signals["sources_count"]
    if signals["has_registry_name"]:
        score += 18
    if signals["name_sources_agree"]:
        score += 12
    if signals["email_matches_name"]:
        score += 12
    if signals["phone_sources_agree"]:
        score += 6
    if signals["role_is_decision_maker"]:
        score += 6
    if signals["generic_email"] and signals["sources_count"] == 1:
        score -= 18
    if signals["has_conflict"]:
        score -= 28

    score += rng.gauss(0, 6)
    score = max(0, min(100, score))

    if score >= 80:
        return "high"
    if score >= 60:
        return "medium"
    if score >= 30:
        return "low"
    return "cannot_verify"


def generate_training_set(n: int = 400, seed: int = 42) -> tuple[list[list[float]], list[str]]:
    """Returns (X, y): X are feature vectors in `features.FEATURE_NAMES`
    order, y are bucket labels in {"high","medium","low","cannot_verify"}.
    Deterministic given `seed`."""
    rng = random.Random(seed)
    X: list[list[float]] = []
    y: list[str] = []
    for _ in range(n):
        signals = _sample_signals(rng)
        X.append(signals_to_vector(signals))
        y.append(_label_signals(signals, rng))
    return X, y
