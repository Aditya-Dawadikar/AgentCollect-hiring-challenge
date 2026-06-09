"""Hand-tuned, explainable confidence classifier. See ADR-0004 for the
weight table and the rationale behind every weight and penalty."""

from classification.base_classifier import BaseClassifier
from config import settings


def _classify(score: int) -> str:
    if score >= 80:
        return "high"
    if score >= 60:
        return "medium"
    if score >= 30:
        return "low"
    return "cannot_verify"


class RuleBasedClassifier(BaseClassifier):
    def __init__(self, threshold: int = settings.CONFIDENCE_THRESHOLD):
        self.threshold = threshold

    def score(self, signals: dict) -> dict:
        if signals["sources_count"] == 0:
            return {
                "confidence_score": 0,
                "classification": "cannot_verify",
                "needs_human_review": True,
            }

        total = 0
        if signals["has_registry_name"]:
            total += 35
        if signals["has_enrichment_email"] and not signals["generic_email"]:
            total += 20
        if signals["has_listing_phone"] or signals["has_enrichment_phone"]:
            total += 10
        if signals["name_sources_agree"]:
            total += 15
        if signals["email_matches_name"]:
            total += 10
        if signals["phone_sources_agree"]:
            total += 5
        if signals["role_is_decision_maker"]:
            total += 5
        if signals["has_conflict"]:
            total -= 25
        if signals["generic_email"] and signals["sources_count"] == 1:
            total -= 10

        confidence_score = max(0, min(100, total))
        return {
            "confidence_score": confidence_score,
            "classification": _classify(confidence_score),
            "needs_human_review": confidence_score < self.threshold,
        }
