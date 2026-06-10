# Contact Finder

## 1. What this is

A small pipeline that takes a CSV of company names + mailing addresses and,
for each company, tries to find **one verified decision-maker contact**
(name, role, email or phone) — pulling from three independently-fallible
mock data sources, fusing their signals, scoring confidence with two
interchangeable classifiers, and producing a CSV with full provenance and a
plain-language reason for every decision.

This is Stage B of the take-home challenge: a working implementation of the
design in [`PLAN.md`](../PLAN.md), within the constraints answered in
[`challenge/CLARIFICATIONS.md`](../challenge/CLARIFICATIONS.md) — most
importantly, **precision over recall** ("a confident, correct, traceable
contact is worth more than three guesses") and a fixed
`confidence_score < 70 -> needs_human_review = true` cutoff.

## 2. Architecture

```
challenge/data/companies.csv (30 companies: name + mailing_address)
            |
            v
   data_sources.loader.load_companies()
            |
            v
   data_sources.mocks.MockProviderClient
     - registry   (business-registry lookup; authoritative for owner/role)
     - listing    (web/maps listing; phone, generic name)
     - enrichment (email/phone enrichment; weak, self-reported confidence)
            |
            v
   data_comparison matchers
     - FuzzyNameMatcher   (ADR-0002: normalize + token_set_ratio >= 85)
     - EmailMatcher       (does email local-part match candidate name?)
     - PhoneMatcher       (do listing/enrichment phones agree?)
     - ConflictResolver   (ADR-0003: registry > listing authority,
                            same-person-different-data -> conflict flag)
            |
            v
   data_comparison.signal_fusion.SignalFusionEngine.fuse()
     -> FusedContact { candidate_name/role/email/phone, sources,
                       source_urls (field -> [urls]), signals (13 features),
                       conflicts }
            |
            v
   classification.{v1_rule_based, v2_decision_tree}.score(signals)
     -> { confidence_score (0-100), classification (high/medium/low/
          cannot_verify), needs_human_review }
     v1: ADR-0004 weighted-sum rules
     v2: ADR-0005 decision tree trained on synthetic data
            |
            v
   output.formatter.format_output_row(fused, result)
     -> 10-column row (ADR-0007): company_name, contact_name, contact_role,
        contact_email_or_phone, confidence_score, classification, source,
        needs_human_review, source_urls, reason
            |
            v
   output/results/v1_predictions.csv, v2_predictions.csv
            |
            v
   evaluation.{ground_truth, metrics, reporter} (run_evaluation.py)
     -> output/results/ground_truth.csv, comparison.txt
        (precision/recall/F1 for v1 vs v2, ADR-0006)
```

## 3. How to run

From `contact-finder/`:

```bash
python -m venv venv
venv\Scripts\activate        # Windows; use `source venv/bin/activate` on macOS/Linux
pip install -r requirements.txt

python run.py              # writes output/results/v1_predictions.csv, v2_predictions.csv
python run_evaluation.py   # writes ground_truth.csv, comparison.txt; prints comparison.txt
```

Run the tests with:

```bash
pytest -q
```

`run_evaluation.py` exits with an error message (not a stack trace) if
`v1_predictions.csv` / `v2_predictions.csv` don't exist yet — run `run.py`
first.

## 4. Output schema

Each row of `v1_predictions.csv` / `v2_predictions.csv`
(`output.formatter.OUTPUT_COLUMNS`):

| Column | Type | Notes |
|---|---|---|
| `company_name` | str | From `companies.csv`. |
| `contact_name` | str | `""` when `needs_human_review`. |
| `contact_role` | str | `""` when `needs_human_review`. |
| `contact_email_or_phone` | str | `""` when `needs_human_review`; email preferred over phone when both exist. |
| `confidence_score` | int | 0-100. |
| `classification` | str | `high` \| `medium` \| `low` \| `cannot_verify`. |
| `source` | str | Comma-joined providers with *any* data, e.g. `registry,listing,enrichment`, or `""`. |
| `needs_human_review` | bool | `confidence_score < 70` (`CLARIFICATIONS.md`). |
| `source_urls` | str | `field:provider:url\|field:provider:url`, populated whenever data exists — including on review rows. |
| `reason` | str | Short human-readable explanation; one of 5 fixed messages (see ADR-0007). |

See [ADR-0007](docs/decisions/0007-output-schema-extensions.md) for why
`classification`, `source`, and `reason` exist beyond the minimal
`CLARIFICATIONS.md` spec, and for the exact blanking policy on review rows.

## 5. Design decisions

- **[ADR-0001](docs/decisions/0001-dependency-versions-for-python-3.13.md)**
  — Dependency versions. The original build plan's pinned `requirements.txt`
  predates Python 3.13 wheel availability for some packages; this ADR records
  the closest-compatible versions actually verified to install and pass the
  test suite (`pandas==3.0.3`, `numpy==2.4.6`, `scikit-learn==1.9.0`,
  `fuzzywuzzy==0.18.0`, `python-Levenshtein==0.27.3`, `pytest==9.0.3`).
- **[ADR-0002](docs/decisions/0002-name-normalization-and-fuzzy-threshold.md)**
  — Name normalization & fuzzy-matching. Names are normalized (strip
  parentheticals, expand `.` into spaces, drop honorifics, title-case) before
  comparison with `fuzzywuzzy.fuzz.token_set_ratio` at a threshold of 85,
  chosen so that `"S. Murphy"` / `"Sean Murphy"`-style abbreviations match
  while genuinely different names don't.
- **[ADR-0003](docs/decisions/0003-source-authority-and-conflict-resolution.md)**
  — Source authority & conflict resolution. `registry` is treated as the
  legal-ownership record and wins ties for `candidate_name`/`candidate_role`;
  when `registry` and `listing` name different people, `candidate_name` still
  comes from `registry` but `signals["has_conflict"]` is set, which lowers
  confidence in both classifiers.
- **[ADR-0004](docs/decisions/0004-rule-based-classifier-weights.md)** — v1
  rule-based weights. A weighted sum over the 13 boolean/count signals (base
  score + per-source bonuses + agreement bonuses - conflict/generic-email
  penalties), with a `sources_count == 0` short-circuit to
  `confidence_score = 0` / `cannot_verify`.
- **[ADR-0005](docs/decisions/0005-decision-tree-classifier-design.md)** — v2
  decision-tree design. A `DecisionTreeClassifier(max_depth=4)` trained at
  construction time on 400 synthetic signal vectors generated by an
  *independently-derived* labeling formula (not copied from v1's weights, so
  the v1-vs-v2 comparison in ADR-0006 is meaningful), with
  `confidence_score` derived from `predict_proba` against bucket midpoints
  (`high=90, medium=70, low=45, cannot_verify=10`).
- **[ADR-0006](docs/decisions/0006-evaluation-methodology.md)** — Evaluation
  methodology. Precision/recall/F1 are computed on the binary `verified`
  label (`= NOT needs_human_review`), not 4-bucket accuracy, because the
  business decision (`auto-use` vs `route to a human`) is binary. The 18-row
  ground truth is 12 trivial zero-source companies (`cannot_verify` by
  construction) plus 6 hand-judged mock-backed companies covering both sides
  of the review boundary and both failure modes (weak single source vs.
  identity conflict).
- **[ADR-0007](docs/decisions/0007-output-schema-extensions.md)** — Output
  schema extensions. Adds `classification`, `source`, and `reason` beyond
  `CLARIFICATIONS.md`'s minimal fields, flattens `source_urls` to a
  `field:provider:url` delimited string, and blanks *all three* contact
  fields (not just `contact_email_or_phone`) on `needs_human_review = true`
  rows while keeping `source_urls`/`reason`/`confidence_score`/
  `classification` populated for audit and triage.

## 6. Results

From [`output/results/comparison.txt`](output/results/comparison.txt):

```
Contact Finder: v1 (rule-based) vs v2 (decision tree) classifier comparison
============================================================================

v1 (rule-based)
---------------
  Precision: 1.000
  Recall: 0.750
  F1: 0.857
  Classification accuracy (4-bucket): 0.889
  Confusion (verified=positive): tp=3 fp=0 fn=1 tn=14 n=18
  Review rate: 0.833

v2 (decision tree)
------------------
  Precision: 1.000
  Recall: 1.000
  F1: 1.000
  Classification accuracy (4-bucket): 0.778
  Confusion (verified=positive): tp=4 fp=0 fn=0 tn=14 n=18
  Review rate: 0.778

Verdict: v1 and v2 are tied on precision (both 1.000); review rate v1=0.833, v2=0.778, ground truth=0.778.
```

**What this means**: both classifiers achieve **perfect precision** on the
18-row ground truth — neither ever marks a contact "verified" that the
ground truth says shouldn't be. They differ on recall: v2 (decision tree)
also verifies "Harbor Light Electric" (registry+listing agree on the same
person via an abbreviated name, listing phone corroborates), where v1's
weighted sum lands just under the threshold (65 < 70) and routes it to
review. Both outcomes are *defensible* — v1 is marginally more
conservative — but v2's recall advantage costs nothing in precision here.

A 0.778-0.833 review rate is **expected and good**, not a failure: 12 of 30
companies (40%) have zero data from any mock source and *must* be reviewed
by construction (ADR-0006), and the remaining review rows are genuinely weak
single-source or conflicting cases — exactly the rows `CLARIFICATIONS.md`
says are fine to flag rather than guess on.

## 7. Known limitations / next steps

- **Nickname matching gap** ([ADR-0002](docs/decisions/0002-name-normalization-and-fuzzy-threshold.md)).
  `token_set_ratio` catches abbreviations and reordering ("S. Murphy" /
  "Sean Murphy") but not true nicknames ("Bob" / "Robert") — these would
  fuzzy-match below 85 and surface as a conflict rather than an agreement.
- **No model persistence** ([ADR-0005](docs/decisions/0005-decision-tree-classifier-design.md)).
  v2 retrains its decision tree from the synthetic generator on every
  `DecisionTreeConfidenceClassifier()` construction. Fine for a fixed
  `seed=42` and a 30-company batch run; a production version would persist
  the fitted model (e.g. `joblib`) and retrain on a schedule, not per-request.
- **Synthetic training data** ([ADR-0005](docs/decisions/0005-decision-tree-classifier-design.md)).
  v2 has never seen the real `enrichment_responses.json` signals during
  training — its agreement with v1 and the ground truth on real data is
  evidence the synthetic labeling formula is reasonable, but a larger
  hand-labeled real-data set would be a stronger basis for tuning `max_depth`
  and the bucket-midpoint mapping.
- **Small ground truth set** ([ADR-0006](docs/decisions/0006-evaluation-methodology.md)).
  18 rows (12 trivial + 6 hand-judged) is enough to catch a classifier that's
  badly broken, but precision/recall on `n=18` (and `n=6` non-trivial) swing
  by large increments per row — a real evaluation harness would need a
  larger, ideally independently-labeled, set.
