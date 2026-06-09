# TICKET-009: v2 decision-tree confidence classifier

**Status:** todo
**Branch:** `feat/TICKET-009-decision-tree-classifier`
**Depends on:** TICKET-008

## Goal

Implement `training_data.py` (synthetic labeled examples over the
`features.FEATURE_NAMES` space) and `v2_decision_tree.py` (a
`sklearn.tree.DecisionTreeClassifier` wrapped behind the same
`BaseClassifier.score(signals) -> dict` interface as v1).

## Why synthetic training data

We have 30 companies, only 18 with any mock data, and 15-20 will be held out
as `ground_truth.csv` for evaluation (TICKET-010) — far too few to both train
and evaluate an ML model without leaking the test set into training. Instead,
`training_data.py` programmatically generates labeled `(signals, bucket)`
examples that encode the **same domain principles** as v1
(multi-source agreement raises confidence, conflicts and generic-only emails
lower it, zero sources -> cannot_verify) but via a different weighting
formula plus injected noise — see ADR-0005. This (a) lets the tree learn a
non-linear decision boundary instead of copying v1's exact weights verbatim,
and (b) keeps the real 30-company set entirely for evaluation.

## Files

- Create: `contact-finder/classification/training_data.py`
- Create: `contact-finder/classification/v2_decision_tree.py`
- Modify: `contact-finder/tests/test_classifiers.py` (add v2 tests)
- Modify: `contact-finder/requirements.txt` if scikit-learn version changes

## Interface contract

```python
# classification/training_data.py
def generate_training_set(n: int = 400, seed: int = 42) -> tuple[list[list[float]], list[str]]:
    """Returns (X, y) where X are feature vectors (features.FEATURE_NAMES
    order) and y are bucket labels in {"high","medium","low","cannot_verify"}.
    Deterministic given `seed`."""
```

```python
# classification/v2_decision_tree.py
BUCKET_MIDPOINT = {"high": 90, "medium": 70, "low": 45, "cannot_verify": 10}

class DecisionTreeConfidenceClassifier(BaseClassifier):
    def __init__(self, threshold: int = settings.CONFIDENCE_THRESHOLD,
                 max_depth: int = 4, seed: int = 42):
        """Trains immediately on training_data.generate_training_set()."""

    def score(self, signals: dict) -> dict:
        """
        vector = features.signals_to_vector(signals)
        proba  = self.model.predict_proba([vector])[0]
        confidence_score = round(sum(p * BUCKET_MIDPOINT[c]
                                      for c, p in zip(self.model.classes_, proba)))
        classification = self.model.classes_[argmax(proba)]
        needs_human_review = confidence_score < self.threshold
        Special case: signals["sources_count"] == 0 -> force
        ("cannot_verify", 0, True) regardless of model output (same
        short-circuit as v1, for output schema consistency).
        """
```

## Synthetic labeling function (document exactly — this is ADR-0005 content)

```python
def _label_signals(signals: dict, rng) -> str:
    if signals["sources_count"] == 0:
        return "cannot_verify"
    score = 40
    score += 5 * signals["sources_count"]
    if signals["has_registry_name"]: score += 18
    if signals["name_sources_agree"]: score += 12
    if signals["email_matches_name"]: score += 12
    if signals["phone_sources_agree"]: score += 6
    if signals["role_is_decision_maker"]: score += 6
    if signals["generic_email"] and signals["sources_count"] == 1: score -= 18
    if signals["has_conflict"]: score -= 28
    score += rng.gauss(0, 6)   # label noise
    score = max(0, min(100, score))
    if score >= 80: return "high"
    if score >= 60: return "medium"
    if score >= 30: return "low"
    return "cannot_verify"
```

Feature sampling distribution for `generate_training_set`: sample
`sources_count` uniformly from `{0,1,2,3}`; for `sources_count == 0`, set all
other booleans False/0; otherwise sample each boolean independently (`p=0.5`)
and `enrichment_provider_confidence` uniform `[0,1]` if
`has_enrichment_email or has_enrichment_phone` else `0`.

## TDD cases

- `generate_training_set(n=400, seed=42)` is deterministic (same call twice
  -> identical `X`, `y`); `len(X) == len(y) == 400`; `y` contains all 4
  bucket labels.
- `DecisionTreeConfidenceClassifier().score(signals)` for
  `sources_count=0` -> exactly `{"confidence_score": 0,
  "classification": "cannot_verify", "needs_human_review": True}`.
- For the Cedar Ridge Plumbing LLC signals (from TICKET-007, all-agree
  3-source case), `score()["needs_human_review"] is False` and
  `classification in {"high","medium"}`.
- For Riverside Print & Sign (1 source, generic email), `needs_human_review
  is True`.
- `model.get_depth() <= 4` (respects `max_depth`).

## Decisions to record

- ADR-0005: synthetic training data design (labeling function above, sampling
  distribution, `n=400`, `seed=42` for reproducibility), `max_depth=4` choice
  (interpretability + avoiding overfitting on synthetic noise), the
  `predict_proba`-weighted `confidence_score` derivation, and "train on init,
  no persistence" (acceptable at this scale; call out as a production
  follow-up).
