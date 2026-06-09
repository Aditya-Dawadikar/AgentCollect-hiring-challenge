# TICKET-008: v1 rule-based confidence classifier

**Status:** done
**Branch:** `feat/TICKET-008-rule-based-classifier`
**Depends on:** TICKET-007

## Goal

Implement the explainable, hand-tuned classifier (`v1_rule_based.py`) and the
shared `features.py` / `base_classifier.py` interfaces that `v2` (TICKET-009)
will also implement, so both classifiers are drop-in interchangeable.

## Files

- Create: `contact-finder/classification/__init__.py` (if not already present)
- Create: `contact-finder/classification/base_classifier.py`
- Create: `contact-finder/classification/features.py`
- Create: `contact-finder/classification/v1_rule_based.py`
- Create: `contact-finder/tests/test_classifiers.py` (v1 tests; v2 tests added
  in TICKET-009)

## Interface contract

```python
# classification/base_classifier.py
class BaseClassifier(ABC):
    def score(self, signals: dict) -> dict:
        """Returns {"confidence_score": int (0-100),
                     "classification": "high"|"medium"|"low"|"cannot_verify",
                     "needs_human_review": bool}"""
```

```python
# classification/features.py
FEATURE_NAMES: list[str]   # ordered names of numeric features, see below

def signals_to_vector(signals: dict) -> list[float]:
    """Project the signals dict (TICKET-007) onto FEATURE_NAMES, in order,
    booleans -> 0.0/1.0, enrichment_provider_confidence -> /100.0.
    Used by v1 (for readability/testing) and v2 (model input)."""
```

`FEATURE_NAMES` (13 features, all derived from the TICKET-007 `signals`
dict):
```
has_registry_name, has_listing_name, has_enrichment_email,
has_listing_phone, has_enrichment_phone, sources_count (0-3, raw int),
name_sources_agree, email_matches_name, phone_sources_agree,
generic_email, role_is_decision_maker, enrichment_provider_confidence (0-1),
has_conflict
```
(13 total — list them all explicitly in the implementation; this ticket spec
is the source of truth, not a placeholder.)

```python
# classification/v1_rule_based.py
class RuleBasedClassifier(BaseClassifier):
    def __init__(self, threshold: int = settings.CONFIDENCE_THRESHOLD): ...
    def score(self, signals: dict) -> dict: ...
```

## Scoring design (document the exact weights — this IS the ADR content)

Starting point adapted from `INSTRUCTIONS.md`'s example, extended with the
TICKET-007 signals:

| Signal | Points |
|---|---|
| `has_registry_name` | +35 |
| `has_enrichment_email` and not `generic_email` | +20 |
| `has_listing_phone` or `has_enrichment_phone` | +10 |
| `name_sources_agree` | +15 |
| `email_matches_name` | +10 |
| `phone_sources_agree` | +5 |
| `role_is_decision_maker` | +5 |
| `has_conflict` | -25 |
| `generic_email` and `sources_count == 1` | -10 |

Clamp to `[0, 100]`. `sources_count == 0` short-circuits to
`confidence_score = 0`, `classification = "cannot_verify"` regardless of the
above (no signals to sum). `enrichment_provider_confidence` deliberately does
**not** directly add to the score (CLARIFICATIONS.md: it's the provider's
self-reported number, not ours) — but `has_enrichment_email`/
`has_enrichment_phone` being true already requires it to exist.

Bucket thresholds (from `PLAN.md` "Quality"):
```python
def _classify(score):
    if score >= 80: return "high"
    if score >= 60: return "medium"
    if score >= 30: return "low"
    return "cannot_verify"

needs_human_review = score < threshold  # threshold = 70
```

## TDD cases

Hand-compute expected scores for these (use as exact-value assertions, not
just bucket checks):

| Company | sources_count | key signals | expected score range | needs_human_review |
|---|---|---|---|---|
| Cedar Ridge Plumbing LLC | 3 | name_agree, email_matches_name, phone via listing, role_is_decision_maker | >=80 ("high") | False |
| Pioneer Landscaping Inc | 3 | all agree | >=80 | False |
| Riverside Print & Sign | 1 | generic_email, no name | <30 ("cannot_verify"/"low") | True |
| Lakeside Auto Glass | 2 | email_matches_name, no registry/listing name agreement | 30-69 | True |
| Coastal Breeze Pool Service | 2 | has_conflict=True | reduced by 25 vs. no-conflict baseline | True |
| Redwood Cabinetry (no data) | 0 | — | 0, "cannot_verify" | True |

## Acceptance criteria

- [x] `pytest contact-finder/tests/test_classifiers.py -v` passes (14
      tests: feature-vector unit tests, isolated weight/penalty/clamping
      unit tests on hand-built `signals` dicts, the 6 TDD-table companies
      via real `fuse()` -> `score()` with exact-value assertions, and a
      full 30-row sweep)
- [x] Full suite (`pytest contact-finder/tests/ -v`) passes: 50/50
- [x] All 6 TDD-table cases match their hand-computed scores exactly
      (95, 100, 0, 40, 25, 0)

## Decisions to record

- [x] ADR-0004: full weight table above with rationale for each weight/penalty,
  why `enrichment_provider_confidence` is NOT summed directly into our score,
  and why `sources_count == 0` short-circuits. See
  [`contact-finder/docs/decisions/0004-rule-based-classifier-weights.md`](../contact-finder/docs/decisions/0004-rule-based-classifier-weights.md).
