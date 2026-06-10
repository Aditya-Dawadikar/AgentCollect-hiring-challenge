# ADR-0005: v2 decision-tree classifier — synthetic training data, depth, and confidence derivation

**Status:** Accepted
**Ticket:** TICKET-009

## Context

`DecisionTreeConfidenceClassifier` (v2) must implement the same
`BaseClassifier.score(signals) -> dict` interface as v1 (ADR-0004), consuming
the 13-feature vector from `features.signals_to_vector`/`FEATURE_NAMES`
(TICKET-007/008) and returning `confidence_score` (0-100), `classification`
(`high`/`medium`/`low`/`cannot_verify`), and `needs_human_review`.

We have 30 companies total, only 18 with any mock-provider data, and 15-20 of
those will become `ground_truth.csv` for TICKET-010's evaluation. Training a
model directly on the real company set and then evaluating on (a subset of)
the same set would leak the test set into training. The only way to get a
real `sklearn.tree.DecisionTreeClassifier` into this pipeline without that
leakage is to train it on **synthetic** `(signals, bucket)` examples.

## Decision

### 1. Synthetic training data (`training_data.generate_training_set`)

`generate_training_set(n=400, seed=42)` draws `n` synthetic signal dicts and
labels each with `_label_signals`, returning `(X, y)` where `X` is
`signals_to_vector(signals)` for each example and `y` is the bucket label.

**Sampling** (`_sample_signals`): `sources_count` is drawn uniformly from
`{0,1,2,3}`. If `0`, every other signal is `False`/`0` (mirrors the real
"company absent from `enrichment_responses.json`" case — TICKET-007's
`test_redwood_cabinetry_absent`). Otherwise each of the 11 boolean signals is
sampled independently with `p=0.5`, and `enrichment_provider_confidence` is
drawn uniform `[0,100]` if `has_enrichment_email or has_enrichment_phone`,
else `0` — matching the real provider-confidence scale that
`signals_to_vector` divides by 100.

**Labeling** (`_label_signals`) encodes the *same domain principles* as v1's
weight table (ADR-0004) — more agreeing sources raises confidence, conflicts
and lone generic emails lower it, zero sources is always `cannot_verify` —
but via an **independently-derived** formula (base 40, `+5 *
sources_count`, `+18` registry name, `+12` name agreement, `+12` email
matches name, `+6` phone agreement, `+6` decision-maker role, `-18` lone
generic email, `-28` conflict, plus `gauss(0, 6)` label noise, clamped to
`[0,100]`, then bucketed at the same 80/60/30 thresholds as v1).

This is deliberately *not* a copy of v1's exact weights, for two reasons:

1. **It would otherwise just be v1-as-a-tree.** If the synthetic labels were
   produced by v1's own scoring function, the "decision tree" would just
   learn to reproduce v1's arithmetic — TICKET-010's v1-vs-v2 comparison
   would then be comparing a function to a noisy approximation of itself,
   not two genuinely different approaches.
2. **The injected Gaussian noise (`σ=6`) gives the tree something to
   generalize over** rather than memorize, which is also why `max_depth` is
   bounded (see below).

`n=400` and `seed=42` are arbitrary-but-fixed: 400 synthetic examples is
small enough to fit instantly at construction time and large enough to cover
all `2^11 * 4` (boolean-signal x sources_count) combinations many times over
in expectation; `seed=42` makes `generate_training_set` — and therefore the
whole classifier — fully deterministic across runs and test invocations
(`test_generate_training_set_is_deterministic`).

### 2. `max_depth=4`

Two reasons, both explicit ticket requirements:

- **Interpretability.** A depth-4 tree (<=15 internal nodes) can be printed
  or visualized and read by a human reviewer alongside v1's weight table —
  keeping the "explainable" property from ADR-0004 roughly intact for v2,
  even though v2's splits aren't hand-authored.
- **Avoiding overfitting to label noise.** The `gauss(0,6)` noise in
  `_label_signals` means the *true* relationship between signals and bucket
  is not perfectly separable. An unbounded tree would carve out leaves for
  individual noisy examples; capping depth at 4 forces the tree to find the
  signals that matter on average (registry name, source count, conflict,
  etc.) rather than memorizing noise. `test_tree_respects_max_depth` enforces
  `model.get_depth() <= 4`.

### 3. `predict_proba`-weighted `confidence_score`

```python
BUCKET_MIDPOINT = {"high": 90, "medium": 70, "low": 45, "cannot_verify": 10}
confidence_score = round(sum(p * BUCKET_MIDPOINT[c]
                              for c, p in zip(model.classes_, proba)))
classification = model.classes_[argmax(proba)]
```

`DecisionTreeClassifier.predict` alone only gives a hard bucket label —
useful for `classification`, but it would make `confidence_score` a
4-valued step function (always exactly one of 4 numbers), which is a poor
match for a "0-100 confidence" field that v1 produces as a smooth-ish sum of
weights. With `max_depth=4`, most leaves contain a *mix* of bucket labels
(because of the injected noise), so `predict_proba` returns a real
distribution over `{high, medium, low, cannot_verify}` per leaf. Weighting
each bucket's representative midpoint by its leaf probability turns that
distribution into a single 0-100 number that reflects how "mixed" a leaf is
(e.g. a leaf that's 60% `high`/40% `medium` scores 0.6*90 + 0.4*70 = 82,
between the two buckets it's torn between, rather than snapping to 90 or 70).

The midpoints (90/70/45/10) are the centers of v1's bucket ranges
(80-100, 60-79, 30-59, 0-29 -> 90, ~70, ~45, ~10), chosen so v1's and v2's
`confidence_score` outputs live on the *same* 0-100 scale with the *same*
bucket semantics — required for TICKET-010 to compare them apples-to-apples.

### 4. Zero-sources short-circuit (same as v1)

`score()` checks `signals["sources_count"] == 0` first and returns exactly
`{"confidence_score": 0, "classification": "cannot_verify",
"needs_human_review": True}` without consulting the model — identical to
v1's short-circuit (ADR-0004) and for the same reason: every zero-source
signal dict is also labeled `cannot_verify` in training data
(`test_generate_training_set_zero_sources_always_cannot_verify`), so the
model would very likely predict the same thing anyway, but the short-circuit
makes the "no data at all" case explicit, exact, and immune to any future
retraining changing the tree's behavior on that one all-zeros input.

### 5. Train on construction, no persistence

`DecisionTreeConfidenceClassifier.__init__` calls
`generate_training_set(seed=seed)` and `model.fit(X, y)` every time an
instance is constructed (test fixture uses `scope="module"` so this happens
once per test session). Training 400 13-feature examples to depth 4 is a
sub-millisecond operation, and `run.py` only constructs one classifier
instance to score 30 companies — persistence (pickling the fitted model to
disk) would add complexity with no measurable benefit at this scale.

**Production follow-up**: if this were scored against thousands of companies
across many process invocations (e.g. a scheduled batch job), the model
should be trained once offline, persisted (`joblib.dump`), loaded at
startup, and retrained on a schedule or when `training_data`'s generation
logic changes — not refit on every run.

## Consequences

- v1 and v2 are comparable apples-to-apples in TICKET-010: same input
  (`signals` / `FEATURE_NAMES` vector), same output shape, same 0-100 scale,
  same bucket thresholds — but v2's score comes from a fitted model with a
  different (independently-derived, noisy) notion of how signals combine, so
  disagreements between v1 and v2 on the real 30 companies are meaningful
  rather than two paths to an identical formula.
- Because labels are synthetic, v2's `confidence_score` for a *specific* real
  company is not hand-verifiable the way v1's is (ADR-0004's per-company
  table). TDD cases for v2 therefore assert *ranges and properties*
  (`needs_human_review` direction, `classification in {"high","medium"}`,
  `0 <= confidence_score <= 100`) rather than exact scores — except the
  zero-sources case, which is exact by the short-circuit.
- `requirements.txt` is unchanged: `scikit-learn==1.9.0` was already pinned
  for Python 3.13 by ADR-0001, and `DecisionTreeClassifier`/`predict_proba`
  are stable APIs across that range.
