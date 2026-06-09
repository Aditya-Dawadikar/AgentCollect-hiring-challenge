# TICKET-007: Signal fusion & conflict resolution

**Status:** done
**Branch:** `feat/TICKET-007-signal-fusion`
**Depends on:** TICKET-005, TICKET-006

## Goal

For a given company, call `MockProviderClient.query_all()`, run the three
matchers from TICKET-006 across the registry/listing/enrichment payloads, and
produce:

1. A single best-guess **candidate** (name, role, email, phone) with full
   `source_urls` provenance per field.
2. A `signals` dict — the feature set both classifiers (TICKET-008,
   TICKET-009) consume.
3. A list of `conflicts` (e.g. registry and listing naming different people)
   for `conflict_resolver` to flag.

This is the integration point: everything downstream depends on the shape of
`FusedContact` and `signals` defined here, so lock these down with tests
across **all 18 companies that have mock data**, not just a couple.

## Files

- Create: `contact-finder/data_comparison/conflict_resolver.py`
- Create: `contact-finder/data_comparison/signal_fusion.py`
- Create: `contact-finder/tests/test_signal_fusion.py` (fusion +
  conflict-resolver tests, kept separate from `test_data_comparison.py`
  since it tests the two new modules created here, mirroring the
  production module layout)

## Interface contract

```python
# data_comparison/conflict_resolver.py
class ConflictResolver:
    def resolve(self, registry: dict | None, listing: dict | None,
                 name_matcher: FuzzyNameMatcher) -> tuple[dict, list[dict]]:
        """
        Picks the candidate (name, role, source) to use as the primary
        identity when registry and/or listing both supply a `name`.

        Returns (chosen, conflicts) where chosen = {
            "name": str | None, "role": str | None,
            "name_source": "registry"|"listing"|None,
        }
        and conflicts is a list of
        {"field": "name", "registry": ..., "listing": ..., "reason": ...}
        when registry.name and listing.name are both present and DO NOT
        fuzzy-match (e.g. Coastal Breeze Pool Service: "Tina Alvarez" vs
        "Marcus Webb").

        Authority order when no conflict: registry > listing (registry is
        the legal-ownership record per PLAN.md "Sources & strategy").
        """
```

```python
# data_comparison/signal_fusion.py
@dataclass
class FusedContact:
    company_name: str
    mailing_address: str
    candidate_name: str | None
    candidate_role: str | None
    candidate_email: str | None
    candidate_phone: str | None
    sources: list[str]                  # providers that returned ANY data
    source_urls: dict[str, list[str]]   # field -> [source_url, ...]
    signals: dict
    conflicts: list[dict]

class SignalFusionEngine:
    def __init__(self, mock_client: MockProviderClient,
                 name_matcher: FuzzyNameMatcher,
                 email_matcher: EmailMatcher,
                 phone_matcher: PhoneMatcher,
                 conflict_resolver: ConflictResolver): ...

    def fuse(self, company_name: str, mailing_address: str) -> FusedContact: ...
```

`signals` dict (consumed by both classifiers — keep these exact key names):

```python
{
    "has_registry_name": bool,
    "has_listing_name": bool,
    "has_enrichment_email": bool,
    "has_listing_phone": bool,
    "has_enrichment_phone": bool,
    "sources_count": int,            # 0-3, providers with ANY non-null data
    "name_sources_agree": bool,      # registry & listing names fuzzy-match
    "email_matches_name": bool,      # enrichment email local part matches candidate_name
    "phone_sources_agree": bool,     # listing & enrichment phones match
    "generic_email": bool,           # enrichment email is role-based (info@, etc.)
    "role_is_decision_maker": bool,  # role NOT in NON_DECISION_MAKER_ROLES and not None
    "enrichment_provider_confidence": int,  # 0 if enrichment missing
    "has_conflict": bool,            # len(conflicts) > 0
}
```

Candidate selection rules:
- `candidate_name`/`candidate_role` come from `ConflictResolver.resolve()`.
- `candidate_email` = enrichment email if present, else `None`.
- `candidate_phone` = listing phone if present, else enrichment phone, else `None`.
- If `candidate_name` is still `None` but enrichment has a non-generic email,
  derive a display name from `EmailMatcher.name_tokens()` (e.g.
  `"jeff@lakesideglass.net"` -> `"Jeff"`) and mark its `source_urls["name"]`
  as the enrichment URL — this is what lets Lakeside Auto Glass surface
  `"Jeff"` as a low-confidence candidate instead of nothing.

## TDD cases (full 18-company mock set + 1 not-found)

Run `fuse()` for every company with mock data plus one absent company
(`Redwood Cabinetry`) and assert on `signals` + `candidate_*` for at least
these representative rows:

| Company | Expect |
|---|---|
| Cedar Ridge Plumbing LLC | `sources_count=3`, `name_sources_agree=True`, `email_matches_name=True`, candidate = Daniel Ortega / Owner |
| Pioneer Landscaping Inc | `sources_count=3`, `phone_sources_agree=True`, `email_matches_name=True` |
| Harbor Light Electric | `name_sources_agree=True` ("Sean Murphy" vs "S. Murphy"), `sources_count=2`, no enrichment |
| Coastal Breeze Pool Service | `has_conflict=True`, conflicts contains the Tina Alvarez / Marcus Webb mismatch |
| Sunbelt Roofing Co | `phone_sources_agree=True`, `has_listing_name=False` |
| Lakeside Auto Glass | `candidate_name="Jeff"` (from listing's `"Jeff (manager)"`, normalized), `email_matches_name=True` (corroborated by `jeff@lakesideglass.net`), `generic_email=False` |
| Riverside Print & Sign | `sources_count=1`, `generic_email=True`, `enrichment_provider_confidence=41` |
| Northgate HVAC Services | `has_registry_name=True`, `role_is_decision_maker=False` ("Registered Agent") |
| Redwood Cabinetry (absent) | `sources_count=0`, all `has_*` False, `candidate_name=None` |

## Acceptance criteria

- [x] `pytest contact-finder/tests/test_signal_fusion.py -v` passes (15
      tests: 4 `ConflictResolver` tests, 9 representative-company `fuse()`
      tests from the TDD table above, 1 nickname-conflict cascade test for
      Ironclad Welding Shop, 1 full 30-row sweep, plus the
      Brookside honorific-agreement test and the email-derived-name
      fallback test using a stub client)
- [x] Full suite (`pytest contact-finder/tests/ -v`) passes: 36/36
- [x] `fuse()` runs without error for all 30 companies in
      `companies.csv` (18 with mock data + 12 with none)
- [x] `signals` dict has exactly the 13 keys specified above for every
      company, including the 12 with `sources_count=0`

## Decisions to record

- [x] ADR-0003: source-authority order (registry > listing for identity),
  conflict definition (only `name` mismatches are tracked as conflicts —
  role/phone/email differences are merged, not flagged), the
  email-derived-name fallback for contacts with no registry/listing name
  (and the Lakeside Auto Glass TDD-table correction above), and the
  Robert/Bob Kowalski nickname-conflict cascade. See
  [`contact-finder/docs/decisions/0003-source-authority-and-conflict-resolution.md`](../contact-finder/docs/decisions/0003-source-authority-and-conflict-resolution.md).
