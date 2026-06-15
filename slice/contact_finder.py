"""Contact Finder -- Stage B slice.

Pipeline: load companies + mock provider data -> resolve identity ->
resolve contact method -> score -> apply threshold gate -> write output.

See ../PLAN.md for the design rationale, DOCUMENTATION.md for the full
decision criteria (scoring formula, review_reason taxonomy, worked
examples), and README.md for notes on where the implementation adapted
the plan once real mock shapes were known.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPANIES_CSV = ROOT / "challenge" / "data" / "companies.csv"
MOCKS_JSON = ROOT / "challenge" / "mocks" / "enrichment_responses.json"

CONFIDENCE_THRESHOLD = 70

# Identity (contact_name / contact_role) base scores.
IDENTITY_BASE_REGISTRY = 40
IDENTITY_BASE_REGISTERED_AGENT = 15  # often a third-party compliance service, not staff
IDENTITY_BASE_LISTING_ONLY = 20

# Contact method (contact_email_or_phone) base scores.
CONTACT_WEIGHT_ENRICHMENT = 30  # scaled by enrichment.provider_confidence / 100
CONTACT_BASE_LISTING_PHONE = 10  # generic business line, no enrichment to corroborate

# Cross-source agreement bonus.
AGREEMENT_BONUS_SINGLE = 15
AGREEMENT_BONUS_MULTI = 20

# Applied when registry and listing name two different people.
CONFLICT_PENALTY = 20

HONORIFICS = {"dr", "mr", "mrs", "ms", "mx", "prof"}
ROLE_HINT_RE = re.compile(r"\(([^)]+)\)")


def normalize_name_tokens(name: str) -> list[str]:
    """Lowercase tokens with parentheticals, punctuation and honorifics stripped."""
    name = ROLE_HINT_RE.sub("", name)
    name = re.sub(r"[^a-zA-Z\s]", "", name)
    return [t.lower() for t in name.split() if t.lower() not in HONORIFICS]


def extract_role_hint(name: str) -> str:
    """Pull a role out of a trailing parenthetical, e.g. 'Jeff (manager)' -> 'Manager'."""
    match = ROLE_HINT_RE.search(name)
    return match.group(1).strip().title() if match else ""


def strip_role_hint(name: str) -> str:
    """Drop a trailing parenthetical role hint, e.g. 'Jeff (manager)' -> 'Jeff'."""
    return ROLE_HINT_RE.sub("", name).strip()


def names_match(name_a: str, name_b: str) -> bool:
    """Two names are treated as the same person if they share a surname (last token)."""
    tokens_a, tokens_b = normalize_name_tokens(name_a), normalize_name_tokens(name_b)
    if not tokens_a or not tokens_b:
        return False
    return tokens_a[-1] == tokens_b[-1]


def email_matches_name(email: str, name: str) -> bool:
    """True if the email's local part contains a first-name or surname token from `name`."""
    local_part = email.split("@", 1)[0].lower()
    local_tokens = set(re.split(r"[._\-]+", local_part))
    return any(tok in local_tokens for tok in normalize_name_tokens(name) if len(tok) > 1)


@dataclass
class Identity:
    """Resolved contact_name/contact_role, its score contribution, and provenance.

    The `conflicting_*` fields are only populated when `conflict` is True,
    i.e. registry and listing point at different people. In that case
    `name`/`role` still hold the (higher-authority) registry identity, while
    `conflicting_*` records the listing's identity for use in `notes`.
    """

    name: str = ""
    role: str = ""
    base_score: float = 0.0
    source_urls: list[str] = field(default_factory=list)
    conflict: bool = False
    conflicting_name: str = ""
    conflicting_role: str = ""
    conflicting_source_url: str = ""


@dataclass
class Contact:
    """Resolved contact_email_or_phone, its score contribution, and provenance."""

    value: str = ""
    base_score: float = 0.0
    source_urls: list[str] = field(default_factory=list)


def resolve_identity(registry: dict | None, listing: dict | None) -> Identity:
    """Resolve contact_name/contact_role from the registry (authoritative) and listing.

    registry is preferred when present. If registry and listing name two
    different people (different surnames), that is an identity conflict:
    we still report the registry identity (higher authority) but flag it.
    """
    registry_name = registry.get("name") if registry else None
    registry_role = (registry.get("role") if registry else None) or ""

    raw_listing_name = listing.get("name") if listing else None
    listing_name = strip_role_hint(raw_listing_name) if raw_listing_name else None
    listing_role = extract_role_hint(raw_listing_name) if raw_listing_name else ""

    if registry_name and listing_name and not names_match(registry_name, listing_name):
        base = IDENTITY_BASE_REGISTERED_AGENT if registry_role == "Registered Agent" else IDENTITY_BASE_REGISTRY
        return Identity(
            name=registry_name,
            role=registry_role,
            base_score=base,
            source_urls=[registry["source_url"]],
            conflict=True,
            conflicting_name=listing_name,
            conflicting_role=listing_role,
            conflicting_source_url=listing["source_url"],
        )

    if registry_name:
        base = IDENTITY_BASE_REGISTERED_AGENT if registry_role == "Registered Agent" else IDENTITY_BASE_REGISTRY
        return Identity(name=registry_name, role=registry_role, base_score=base, source_urls=[registry["source_url"]])

    if listing_name:
        return Identity(name=listing_name, role=listing_role, base_score=IDENTITY_BASE_LISTING_ONLY, source_urls=[listing["source_url"]])

    return Identity()


def resolve_contact(enrichment: dict | None, listing: dict | None, identity: Identity) -> Contact:
    """Resolve contact_email_or_phone: prefer enrichment, fall back to a listing phone.

    If identity is in conflict, a listing phone belongs to the *other*
    (unconfirmed) person and is not used as the output contact.
    """
    if enrichment:
        value = enrichment.get("email") or enrichment.get("phone") or ""
        if value:
            provider_confidence = enrichment.get("provider_confidence", 0)
            return Contact(
                value=value,
                base_score=CONTACT_WEIGHT_ENRICHMENT * provider_confidence / 100,
                source_urls=[enrichment["source_url"]],
            )

    if listing and listing.get("phone") and not identity.conflict:
        return Contact(value=listing["phone"], base_score=CONTACT_BASE_LISTING_PHONE, source_urls=[listing["source_url"]])

    return Contact()


def compute_agreement_bonus(registry: dict | None, listing: dict | None, enrichment: dict | None, identity: Identity) -> tuple[int, list[str]]:
    """Independent-source agreement raises confidence; conflicts earn no bonus."""
    if identity.conflict:
        return 0, []

    agreements: list[str] = []

    registry_name = registry.get("name") if registry else None
    raw_listing_name = listing.get("name") if listing else None
    listing_name = strip_role_hint(raw_listing_name) if raw_listing_name else None
    if registry_name and listing_name and names_match(registry_name, listing_name):
        agreements.append("registry_listing_name_match")

    enrichment_phone = enrichment.get("phone") if enrichment else None
    listing_phone = listing.get("phone") if listing else None
    if enrichment_phone and listing_phone and enrichment_phone == listing_phone:
        agreements.append("enrichment_listing_phone_match")

    enrichment_email = enrichment.get("email") if enrichment else None
    if enrichment_email and identity.name and email_matches_name(enrichment_email, identity.name):
        agreements.append("enrichment_email_identity_match")

    if not agreements:
        bonus = 0
    elif len(agreements) == 1:
        bonus = AGREEMENT_BONUS_SINGLE
    else:
        bonus = AGREEMENT_BONUS_MULTI
    return bonus, agreements


def score_company(company_name: str, mailing_address: str, mock_record: dict) -> dict:
    """Run one company through the full pipeline and build its output row.

    Orchestrates identity resolution, contact resolution, agreement bonus,
    confidence scoring, the threshold gate, and review-reason classification.
    See DOCUMENTATION.md for the scoring formula and worked examples; this
    function is the implementation of that spec.
    """
    registry = mock_record.get("registry")
    listing = mock_record.get("listing")
    enrichment = mock_record.get("enrichment")

    identity = resolve_identity(registry, listing)
    contact = resolve_contact(enrichment, listing, identity)
    agreement_bonus, agreements = compute_agreement_bonus(registry, listing, enrichment, identity)

    raw_score = identity.base_score + contact.base_score + agreement_bonus
    if identity.conflict:
        raw_score -= CONFLICT_PENALTY
    confidence_score = max(0, min(100, round(raw_score)))

    # Gate on score AND on having an actual contact method -- a row can
    # score high on identity alone (e.g. a confident name with no way to
    # reach them) but still have nothing usable to hand to a human.
    needs_human_review = confidence_score < CONFIDENCE_THRESHOLD or not contact.value
    contact_value = "" if needs_human_review else contact.value

    # First match wins -- ordered from "nothing to go on" to "right at the
    # threshold" so each row gets the most specific applicable reason.
    if not (registry or listing or enrichment):
        review_reason = "no_sources"
    elif identity.conflict:
        review_reason = "identity_conflict"
    elif not contact.value:
        review_reason = "no_contact_method"
    elif confidence_score < CONFIDENCE_THRESHOLD:
        review_reason = "low_confidence" if agreements else "single_weak_source"
    else:
        review_reason = ""

    notes = ""
    if identity.conflict:
        role_suffix = f", {identity.conflicting_role}" if identity.conflicting_role else ""
        notes = (
            f"listing names a different person ({identity.conflicting_name}{role_suffix}) "
            f"at {identity.conflicting_source_url}; not used as the contact."
        )
    elif identity.role == "Registered Agent":
        notes = "registry match is a Registered Agent -- often a third-party filing service, not company staff."

    sources = sorted(
        name for name, record in (("registry", registry), ("listing", listing), ("enrichment", enrichment)) if record
    )

    return {
        "company_name": company_name,
        "mailing_address": mailing_address,
        "contact_name": identity.name,
        "contact_role": identity.role,
        "contact_email_or_phone": contact_value,
        "confidence_score": confidence_score,
        "source": sources,
        "needs_human_review": needs_human_review,
        "review_reason": review_reason,
        "notes": notes,
        "provenance": {
            "contact_name": identity.source_urls,
            "contact_role": identity.source_urls,
            "contact_email_or_phone": contact.source_urls if contact_value else [],
        },
    }


def load_companies(csv_path: Path = COMPANIES_CSV) -> list[dict]:
    """Load companies.csv rows as dicts with at least company_name/mailing_address."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_mock_data(json_path: Path = MOCKS_JSON) -> dict:
    """Load the mock provider fixtures, keyed by company_name."""
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


def run(csv_path: Path = COMPANIES_CSV, json_path: Path = MOCKS_JSON) -> list[dict]:
    """Score every company in `csv_path` against its fixtures in `json_path`.

    Companies with no matching entry in the mock data are scored with an
    empty record (`{}`), which resolves to `review_reason == "no_sources"`.
    """
    companies = load_companies(csv_path)
    mock_data = load_mock_data(json_path)
    return [
        score_company(row["company_name"], row["mailing_address"], mock_data.get(row["company_name"], {}))
        for row in companies
    ]


CSV_COLUMNS = [
    "company_name",
    "mailing_address",
    "contact_name",
    "contact_role",
    "contact_email_or_phone",
    "confidence_score",
    "source",
    "needs_human_review",
    "review_reason",
    "notes",
]


def write_outputs(results: list[dict], out_dir: Path) -> None:
    """Write the full results to output.json and a flattened view to output.csv.

    output.csv drops the nested `provenance` field and joins `source`
    (a list) into a `;`-separated string for spreadsheet friendliness.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(out_dir / "output.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    with open(out_dir / "output.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in results:
            writer.writerow({**row, "source": ";".join(row["source"])})


def main() -> None:
    results = run()
    write_outputs(results, Path(__file__).resolve().parent)

    total = len(results)
    passed = sum(1 for r in results if not r["needs_human_review"])
    review = total - passed
    no_data = sum(1 for r in results if r["review_reason"] == "no_sources")

    print(f"Processed {total} companies")
    print(f"  confident (no review needed): {passed}")
    print(f"  needs_human_review:           {review}  (of which no_sources: {no_data})")


if __name__ == "__main__":
    main()
