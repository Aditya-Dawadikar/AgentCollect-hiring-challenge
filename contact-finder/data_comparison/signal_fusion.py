"""Fuses registry/listing/enrichment provider data for one company into a
FusedContact: a best-guess candidate, per-field source-URL provenance, the
`signals` dict consumed by both classifiers, and any identity conflicts.
"""

from dataclasses import dataclass

from config import settings
from data_comparison.conflict_resolver import ConflictResolver
from data_comparison.email_matcher import EmailMatcher
from data_comparison.fuzzy_matcher import FuzzyNameMatcher
from data_comparison.phone_matcher import PhoneMatcher
from data_sources.mocks import MockProviderClient


@dataclass
class FusedContact:
    company_name: str
    mailing_address: str
    candidate_name: str | None
    candidate_role: str | None
    candidate_email: str | None
    candidate_phone: str | None
    sources: list[str]
    source_urls: dict[str, list[str]]
    signals: dict
    conflicts: list[dict]


class SignalFusionEngine:
    def __init__(self, mock_client: MockProviderClient,
                 name_matcher: FuzzyNameMatcher,
                 email_matcher: EmailMatcher,
                 phone_matcher: PhoneMatcher,
                 conflict_resolver: ConflictResolver):
        self.mock_client = mock_client
        self.name_matcher = name_matcher
        self.email_matcher = email_matcher
        self.phone_matcher = phone_matcher
        self.conflict_resolver = conflict_resolver

    def fuse(self, company_name: str, mailing_address: str) -> FusedContact:
        records = self.mock_client.query_all(company_name)
        registry = records["registry"]
        listing = records["listing"]
        enrichment = records["enrichment"]

        sources = [provider for provider, record in records.items() if record is not None]

        chosen, conflicts = self.conflict_resolver.resolve(registry, listing, self.name_matcher)
        candidate_name = chosen["name"]
        candidate_role = chosen["role"]

        source_urls: dict[str, list[str]] = {}

        registry_name = (registry or {}).get("name")
        listing_name = (listing or {}).get("name")
        if registry_name:
            source_urls.setdefault("name", []).append(registry["source_url"])
        if listing_name:
            source_urls.setdefault("name", []).append(listing["source_url"])

        if registry and registry.get("role"):
            source_urls.setdefault("role", []).append(registry["source_url"])

        candidate_email = (enrichment or {}).get("email")
        if candidate_email:
            source_urls.setdefault("email", []).append(enrichment["source_url"])

        listing_phone = (listing or {}).get("phone")
        enrichment_phone = (enrichment or {}).get("phone")
        candidate_phone = listing_phone or enrichment_phone
        if listing_phone:
            source_urls.setdefault("phone", []).append(listing["source_url"])
        if enrichment_phone:
            source_urls.setdefault("phone", []).append(enrichment["source_url"])

        # Fallback: if neither registry nor listing named anyone, but
        # enrichment gave us a non-generic mailbox (e.g. "jeff@..."), use
        # that as a low-confidence display name.
        if not candidate_name and candidate_email and not self.email_matcher.is_generic(candidate_email):
            tokens = [tok for tok in self.email_matcher.name_tokens(candidate_email) if tok]
            if tokens:
                candidate_name = self.name_matcher.normalize(" ".join(tokens)) or None
                if candidate_name:
                    source_urls.setdefault("name", []).append(enrichment["source_url"])

        generic_email = self.email_matcher.is_generic(candidate_email)
        email_matches_name = self.email_matcher.matches_name(
            candidate_email, candidate_name, self.name_matcher
        )

        role_lower = (candidate_role or "").strip().lower()
        role_is_decision_maker = (
            candidate_role is not None
            and role_lower not in settings.NON_DECISION_MAKER_ROLES
        )

        signals = {
            "has_registry_name": bool(registry_name),
            "has_listing_name": bool(listing_name),
            "has_enrichment_email": bool((enrichment or {}).get("email")),
            "has_listing_phone": bool(listing_phone),
            "has_enrichment_phone": bool(enrichment_phone),
            "sources_count": len(sources),
            "name_sources_agree": bool(
                registry_name and listing_name
                and self.name_matcher.match(registry_name, listing_name)
            ),
            "email_matches_name": email_matches_name,
            "phone_sources_agree": self.phone_matcher.match(listing_phone, enrichment_phone),
            "generic_email": generic_email,
            "role_is_decision_maker": role_is_decision_maker,
            "enrichment_provider_confidence": (enrichment or {}).get("provider_confidence") or 0,
            "has_conflict": len(conflicts) > 0,
        }

        return FusedContact(
            company_name=company_name,
            mailing_address=mailing_address,
            candidate_name=candidate_name,
            candidate_role=candidate_role,
            candidate_email=candidate_email,
            candidate_phone=candidate_phone,
            sources=sources,
            source_urls=source_urls,
            signals=signals,
            conflicts=conflicts,
        )
