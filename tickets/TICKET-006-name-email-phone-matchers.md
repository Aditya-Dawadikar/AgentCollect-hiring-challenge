# TICKET-006: Name / email / phone matching strategies

**Status:** done
**Branch:** `feat/TICKET-006-matchers`
**Depends on:** TICKET-005

## Goal

Build the three independent matching strategies that `signal_fusion` will use
to decide whether two providers are "talking about the same person/contact
detail":

- `fuzzy_matcher.py` — name matching (handles "Daniel Ortega" vs "D. Ortega",
  title prefixes like "Dr.", parenthetical role suffixes like "Jeff
  (manager)")
- `email_matcher.py` — email normalization, generic-mailbox detection
  (`info@`, `office@`, ...), and matching an email's local part against a
  candidate name
- `phone_matcher.py` — phone normalization (E.164-ish) and matching

## Why this is its own ticket

These three matchers are independently testable against the real mock data
(`challenge/mocks/enrichment_responses.json`) and have **zero** dependency on
each other or on `signal_fusion`. Get them right and tested in isolation
before they're composed.

## Files

- Create: `contact-finder/data_comparison/__init__.py` (if not already from TICKET-005)
- Create: `contact-finder/data_comparison/base_strategy.py`
- Create: `contact-finder/data_comparison/fuzzy_matcher.py`
- Create: `contact-finder/data_comparison/email_matcher.py`
- Create: `contact-finder/data_comparison/phone_matcher.py`
- Create: `contact-finder/tests/test_data_comparison.py` (matcher tests; fusion
  tests added in TICKET-007)

## Interface contract

```python
# data_comparison/base_strategy.py
class BaseMatcher(ABC):
    def match(self, a, b) -> bool: ...
```

```python
# data_comparison/fuzzy_matcher.py
class FuzzyNameMatcher(BaseMatcher):
    def __init__(self, threshold: int = 85): ...
    def normalize(self, name: str) -> str:
        """Strip honorifics (Dr., Mr., Mrs.), parenthetical suffixes
        ('Jeff (manager)' -> 'Jeff'), collapse whitespace, title-case."""
    def score(self, name1: str, name2: str) -> int:
        """fuzzywuzzy.fuzz.token_set_ratio on normalized names."""
    def match(self, name1: str, name2: str) -> bool:
        """score(...) >= self.threshold"""
```

```python
# data_comparison/email_matcher.py
class EmailMatcher(BaseMatcher):
    def normalize(self, email: str) -> str:
        """lowercase + strip"""
    def is_generic(self, email: str) -> bool:
        """local part (before '@', split on '.', '_', '-') intersects
        config.settings.GENERIC_EMAIL_LOCAL_PARTS"""
    def name_tokens(self, email: str) -> list[str]:
        """local part split on '.', '_', '-', digits stripped"""
    def matches_name(self, email: str, name: str, name_matcher: FuzzyNameMatcher) -> bool:
        """join name_tokens(email) and fuzzy-match against `name`"""
    def match(self, email1: str, email2: str) -> bool:
        """normalize both, exact compare"""
```

```python
# data_comparison/phone_matcher.py
class PhoneMatcher(BaseMatcher):
    def normalize(self, phone: str) -> str:
        """digits only, drop leading country code '1' if 11 digits ->
        10-digit national number for comparison"""
    def match(self, phone1: str, phone2: str) -> bool:
        """normalize both, exact compare; None/'' never match"""
```

## TDD cases (drawn from real mock data — use these as test fixtures)

| Matcher | Inputs | Expected |
|---|---|---|
| `FuzzyNameMatcher` | `"Sean Murphy"`, `"S. Murphy"` | `match -> True` (Harbor Light Electric) |
| `FuzzyNameMatcher` | `"Dr. Emily Hart"`, `"Emily Hart"` | `match -> True` (Brookside Vet, after honorific strip) |
| `FuzzyNameMatcher` | `"Tina Alvarez"`, `"Marcus Webb"` | `match -> False` (Coastal Breeze — genuine conflict) |
| `EmailMatcher.is_generic` | `"info@riversideprint.biz"` | `True` |
| `EmailMatcher.matches_name` | `"d.ortega@cedarridgeplumbing.com"`, `"Daniel Ortega"` | `True` |
| `EmailMatcher.matches_name` | `"karen@bayviewauto.com"`, `"Karen Liu"` | `True` |
| `PhoneMatcher.match` | `"+1-480-555-0133"`, `"+1-480-555-0133"` | `True` (Sunbelt Roofing, listing == enrichment) |
| `PhoneMatcher.match` | `None`, `"+1-480-555-0133"` | `False` |

## Acceptance criteria

- [x] `pytest contact-finder/tests/test_data_comparison.py -v` passes (14
      tests covering all TDD cases above plus normalization edge cases)
- [x] `FuzzyNameMatcher.normalize("Jeff (manager)") == "Jeff"`
- [x] `FuzzyNameMatcher.match("Robert Kowalski", "Bob Kowalski")` is `False`
      (documented known limitation, not a bug)
- [x] `PhoneMatcher.normalize("+1-480-555-0133") == "4805550133"` (country
      code stripped, 10-digit national number)
- [x] Full suite (`pytest contact-finder/tests/ -v`) passes: 19/19

## Decisions to record

- [x] ADR-0002: name normalization rules + why `token_set_ratio` and threshold
  85, including the known limitation that pure nickname pairs (e.g. "Robert"
  vs "Bob" in Ironclad Welding Shop) are **not** caught by string similarity
  alone, and why we accept that gap for this slice (cross-checked instead via
  the email-to-name signal in TICKET-007). See
  [`contact-finder/docs/decisions/0002-name-normalization-and-fuzzy-threshold.md`](../contact-finder/docs/decisions/0002-name-normalization-and-fuzzy-threshold.md).
