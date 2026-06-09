# TICKET-011: Full pipeline, output formatter, README

**Status:** todo
**Branch:** `feat/TICKET-011-pipeline-readme`
**Depends on:** TICKET-007, TICKET-008, TICKET-009, TICKET-010

## Goal

Wire everything together: `output/formatter.py` builds the final per-row
schema (with provenance), `run.py` runs the full 30-company pipeline through
both classifiers, `run_evaluation.py` produces `ground_truth.csv` +
`comparison.txt`, and `contact-finder/README.md` documents the system,
how to run it, and the results.

## Files

- Create: `contact-finder/output/__init__.py` (if not present)
- Create: `contact-finder/output/formatter.py`
- Modify: `contact-finder/run.py` (replace stub with real pipeline)
- Modify: `contact-finder/run_evaluation.py` (replace stub)
- Create: `contact-finder/tests/test_integration.py`
- Create: `contact-finder/README.md`
- Generated (not hand-written, produced by running the pipeline):
  `contact-finder/output/results/v1_predictions.csv`,
  `v2_predictions.csv`, `ground_truth.csv`, `comparison.txt`

## Output row schema

Per CLARIFICATIONS.md's required fields, extended with provenance per
PLAN.md ("Zero contacts without attribution") — see ADR-0007 for the
extension rationale:

```python
{
  "company_name": str,
  "contact_name": str,             # "" when needs_human_review
  "contact_role": str,             # "" when needs_human_review
  "contact_email_or_phone": str,   # "" when needs_human_review; email
                                    # preferred over phone when both exist
  "confidence_score": int,         # 0-100
  "classification": str,           # high|medium|low|cannot_verify
  "source": str,                   # comma-joined providers with ANY data,
                                    # "" if none
  "needs_human_review": bool,
  "source_urls": str,              # "field:provider:url|field:provider:url"
                                    # — ALWAYS populated when data exists,
                                    # even on review rows (audit trail)
  "reason": str,                   # short human-readable explanation
}
```

## Interface contract

```python
# output/formatter.py
def build_reason(signals: dict, confidence_score: int, threshold: int) -> str:
    """
    sources_count == 0          -> "No data available from any source."
    has_conflict                -> "Registry and listing disagree on contact identity."
    generic_email and sources_count == 1
                                 -> "Single weak source with a generic contact email."
    confidence_score < threshold (none of the above)
                                 -> f"Confidence {confidence_score} below threshold {threshold}."
    else                         -> f"Verified via {sources_count} agreeing source(s)."
    """

def format_output_row(fused: FusedContact, result: dict,
                       threshold: int = settings.CONFIDENCE_THRESHOLD) -> dict:
    """Builds the schema above. contact_email_or_phone = fused.candidate_email
    or fused.candidate_phone (email preferred). Blanks contact_name/
    contact_role/contact_email_or_phone when result['needs_human_review']."""

def write_predictions_csv(rows: list[dict], path: str | Path) -> None:
    """csv.DictWriter with the schema's keys as header, in order."""
```

```python
# run.py
def main() -> None:
    """
    1. companies = load_companies()
    2. build SignalFusionEngine, RuleBasedClassifier, DecisionTreeConfidenceClassifier
    3. for each company: fuse -> signals -> v1.score(signals), v2.score(signals)
       -> format_output_row(fused, result) for each
    4. write_predictions_csv(v1_rows, "output/results/v1_predictions.csv")
       write_predictions_csv(v2_rows, "output/results/v2_predictions.csv")
    5. print a short per-company one-line summary to stdout
    """
```

```python
# run_evaluation.py
def main() -> None:
    """
    1. write_ground_truth_csv("output/results/ground_truth.csv")
    2. v1_metrics = evaluate_predictions(v1_predictions.csv, ground_truth.csv)
       v2_metrics = evaluate_predictions(v2_predictions.csv, ground_truth.csv)
    3. write_comparison_report(v1_metrics, v2_metrics, "output/results/comparison.txt")
    4. print comparison.txt to stdout
    Exits with an error message (not a stack trace) if predictions CSVs are
    missing, telling the user to run run.py first.
    """
```

## TDD cases

- `format_output_row` for Cedar Ridge Plumbing LLC + a `score()` result with
  `needs_human_review=False` -> `contact_name="Daniel Ortega"`,
  `contact_email_or_phone="d.ortega@cedarridgeplumbing.com"` (email over
  phone), `source` contains all three providers, `source_urls` non-empty for
  name/role/email.
- `format_output_row` for Riverside Print & Sign +
  `needs_human_review=True` -> `contact_name == "" and
  contact_email_or_phone == ""`, but `source_urls` still contains the
  enrichment URL and `reason` mentions "generic contact email".
- `build_reason` covers all 4 branches above with exact-string assertions.
- `tests/test_integration.py`: run the full `run.py` pipeline (importing
  `main`, writing to a tmp output dir via monkeypatched `OUTPUT_DIR`) over
  all 30 companies — assert 30 rows in each predictions CSV, every row has a
  non-empty `classification`, and every `needs_human_review=False` row has a
  non-empty `source_urls`.
- After implementation, run for real: `python run.py && python
  run_evaluation.py` and commit the generated
  `contact-finder/output/results/*.csv` and `comparison.txt`.

## `contact-finder/README.md` outline

1. **What this is** — one paragraph, link back to `PLAN.md` and
   `challenge/CLARIFICATIONS.md`.
2. **Architecture** — ASCII pipeline diagram: CSV -> MockProviderClient ->
   matchers -> SignalFusionEngine -> {v1, v2} classifiers -> formatter -> CSVs.
3. **How to run** — venv setup, `pip install -r requirements.txt`,
   `python run.py`, `python run_evaluation.py`.
4. **Output schema** — the table above.
5. **Design decisions** — one paragraph per ADR with a link into
   `docs/decisions/000X-*.md`.
6. **Results** — paste the final `comparison.txt` numbers + 1-2 sentences on
   what they mean (which classifier wins on precision, and why a high review
   rate is expected/good here).
7. **Known limitations / next steps** — nickname matching gap (ADR-0002), no
   model persistence (ADR-0005), synthetic training data (ADR-0005), small
   ground truth set (ADR-0006).

## Decisions to record

- ADR-0007: output schema extensions beyond the minimal CLARIFICATIONS.md
  fields (`classification`, `source_urls`, `reason`) and the "blank out
  contact fields but keep source_urls + reason on review rows" policy —
  ties to PLAN.md's "empty contact + needs_human_review + reason" and "Zero
  contacts without attribution".

## Final TODO.md update

After this ticket merges, update the repo-root `TODO.md`: tick all 7 ticket
checkboxes, tick all 7 ADR checkboxes, and add the final precision/recall/F1
numbers from `comparison.txt` to the "Decision records" section as a closing
summary line.
