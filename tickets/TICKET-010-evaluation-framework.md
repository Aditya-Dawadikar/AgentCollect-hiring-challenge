# TICKET-010: Evaluation framework (precision / recall / F1)

**Status:** todo
**Branch:** `feat/TICKET-010-evaluation`
**Depends on:** TICKET-007, TICKET-008, TICKET-009

## Goal

Build a hand-labeled `ground_truth.csv` (15-20 rows) covering the easy
no-data cases and a representative spread of the 18 mock-backed companies,
plus `metrics.py` (precision/recall/F1) and `reporter.py` (writes
`comparison.txt`).

## What "correct" means here

CLARIFICATIONS.md draws the line at `needs_human_review`. Ground truth labels
each company as **verified** (a confident, correct, traceable contact exists
-> `needs_human_review` should be `False`) or **review** (`needs_human_review`
should be `True`). Precision/recall/F1 are computed on this binary label,
positive class = "verified":

- **Precision** = of the companies a classifier marks "verified", what
  fraction *should* be verified per ground truth. Low precision = the
  classifier is overconfident (the costly error per PLAN.md).
- **Recall** = of the companies that *should* be verified, what fraction the
  classifier actually marks verified. Low recall = excess caution.
- A high review rate that matches ground truth's review rate is a **good**
  result, not a failure (per CLARIFICATIONS.md).

## Files

- Create: `contact-finder/evaluation/__init__.py` (if not present)
- Create: `contact-finder/evaluation/ground_truth.py`
- Create: `contact-finder/evaluation/metrics.py`
- Create: `contact-finder/evaluation/reporter.py`
- Create: `contact-finder/output/results/.gitkeep` -> will be replaced by
  real `ground_truth.csv` output in this ticket
- Create: `contact-finder/tests/test_evaluation.py`

## Interface contract

```python
# evaluation/ground_truth.py
GROUND_TRUTH: list[dict]   # see schema + rows below

def write_ground_truth_csv(path: str | Path) -> None:
    """Writes GROUND_TRUTH to CSV with columns:
    company_name, expected_needs_human_review, expected_classification, rationale"""
```

```python
# evaluation/metrics.py
def precision_recall_f1(y_true: list[bool], y_pred: list[bool]) -> dict:
    """Both lists are 'verified' booleans (= NOT needs_human_review),
    positive class = True. Returns
    {"precision": float, "recall": float, "f1": float,
     "tp": int, "fp": int, "fn": int, "tn": int, "n": int}.
    Edge cases: tp+fp==0 -> precision=0.0; tp+fn==0 -> recall=0.0;
    precision+recall==0 -> f1=0.0 (no division by zero)."""

def evaluate_predictions(predictions_csv: str | Path,
                          ground_truth_csv: str | Path) -> dict:
    """Joins on company_name, returns precision_recall_f1(...) plus
    'classification_accuracy': float (4-bucket exact-match accuracy,
    secondary metric)."""
```

```python
# evaluation/reporter.py
def write_comparison_report(v1_metrics: dict, v2_metrics: dict,
                             path: str | Path) -> None:
    """Writes a plain-text comparison.txt: both metrics tables side by side
    + a one-line verdict (which classifier has higher precision, and the
    review-rate of each vs. ground truth's review rate)."""
```

## Ground truth set (18 rows — write these into `GROUND_TRUTH`)

**All 12 companies absent from `enrichment_responses.json`** (sources_count
== 0 -> trivially `cannot_verify` / review = True):
Redwood Cabinetry, Desert Sky Solar, Cornerstone Masonry, Velvet Thread
Tailoring, Frontier Towing & Recovery, Blue Heron Landscaping, Ace Mobile
Locksmith, Granite Peak Surveying, Sierra Vista Auto Body, Evergreen Tree
Care, Liberty Sign & Awning, Crescent Moon Cafe.

**6 mock-backed companies**, hand-judged by inspecting
`enrichment_responses.json` directly:

| Company | expected_needs_human_review | expected_classification | rationale |
|---|---|---|---|
| Cedar Ridge Plumbing LLC | False | high | all 3 sources agree on Daniel Ortega / Owner, email matches name |
| Pioneer Landscaping Inc | False | high | all 3 sources agree on Maria Gomez / President, phone+email corroborate |
| Harbor Light Electric | False | medium | registry+listing agree (Sean Murphy / S. Murphy), Owner role, listing phone |
| Greenfield Catering Group | False | medium | registry (Angela Brooks/Owner) + enrichment email "a.brooks@..." corroborate |
| Riverside Print & Sign | True | cannot_verify | single weak enrichment source (confidence 41), generic "info@" email |
| Coastal Breeze Pool Service | True | low | registry ("Tina Alvarez") and listing ("Marcus Webb") name a different person each — conflict |

## TDD cases

- `write_ground_truth_csv(tmp_path/"gt.csv")` produces 18 rows with the
  expected columns.
- `precision_recall_f1([True,True,False], [True,False,False])` ->
  `tp=1, fp=0, fn=1, tn=1`, `precision=1.0`, `recall=0.5`,
  `f1==pytest.approx(0.667, abs=1e-3)`.
- `precision_recall_f1([], [])` -> all zeros, no exception.
- `evaluate_predictions(...)` on a small fixture CSV pair returns the right
  joined metrics (test with a 4-row fixture, not the full 30).

## Decisions to record

- ADR-0006: why precision/recall/F1 are computed on the binary
  `verified`/`needs_human_review` label rather than 4-class bucket accuracy
  (ties directly to the CLARIFICATIONS.md decision rule and the
  precision-over-recall mandate), the 18-row ground truth composition
  (12 trivial cannot-verify + 6 hand-judged), and the explicit rationale per
  hand-judged row (table above — copy verbatim into the ADR for traceability).
