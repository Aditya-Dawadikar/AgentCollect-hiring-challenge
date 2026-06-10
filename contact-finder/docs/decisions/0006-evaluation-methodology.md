# ADR-0006: Evaluation methodology — binary verified/review label, ground truth composition

**Status:** Accepted
**Ticket:** TICKET-010

## Context

TICKET-010 needs to compare v1 (rule-based) and v2 (decision-tree) on the
real 30-company set using precision/recall/F1. Both classifiers also emit a
4-class `classification` bucket (`high`/`medium`/`low`/`cannot_verify`).
Two questions need an answer: what is the *positive class* precision/recall
are computed over, and what does the hand-labeled ground truth set actually
contain?

## Decision

### Binary `verified` label, not 4-bucket accuracy

`precision_recall_f1` operates on a single binary label per company:
**`verified` = `NOT needs_human_review`**, positive class = `True`
("verified"). 4-bucket exact-match accuracy (`classification_accuracy`) is
still computed and reported, but as a **secondary** metric.

This follows directly from `CLARIFICATIONS.md` and `PLAN.md`:

1. **The actual business decision is binary.** Every downstream action
   (auto-contact vs. route to a human reviewer) is gated on
   `needs_human_review`, not on which of `high`/`medium`/`low`/
   `cannot_verify` a row landed in. A classifier that gets the bucket
   "wrong" (says `medium` instead of `high`) but lands on the same side of
   `CONFIDENCE_THRESHOLD = 70` made the *same* business decision — the
   4-bucket label is strictly more granular than what matters operationally.
2. **Precision is the named success metric, and "precision" only makes
   sense for a binary positive class.** `CLARIFICATIONS.md`'s "Precision,
   not recall" mandate and PLAN.md's "one confident, verified contact beats
   three guesses" are statements about the `verified` decision specifically:
   of the contacts we hand over as ready-to-use, what fraction are actually
   correct? A 4-class precision/recall (one-vs-rest per bucket, or
   macro-averaged) would dilute this into four numbers, none of which
   directly answers "can we trust the rows we didn't flag?"
3. **A high review rate is explicitly *not* a failure** (per
   `CLARIFICATIONS.md`) — it's the `cannot_verify`/`low` buckets doing their
   job. Binary recall (of companies that *should* be verified, how many did
   we verify?) measures excess caution directly; 4-bucket accuracy would
   penalize a classifier for saying `low` when ground truth says
   `cannot_verify`, even though *both* trigger review and neither is the
   costly error.

`classification_accuracy` is kept as a secondary metric because it's still
informative for comparing v1 vs v2 (e.g. "v2 gets the *bucket* right less
often even when it agrees on `needs_human_review`"), and because TICKET-009
explicitly designed v2's `confidence_score`/bucket derivation to be
comparable to v1's on the same scale (ADR-0005) — throwing that comparability
away would waste it.

### Ground truth composition: 18 rows

`evaluation/ground_truth.GROUND_TRUTH` has 18 rows:

**12 rows — companies absent from `enrichment_responses.json`** (`registry`,
`listing`, and `enrichment` all return nothing, so `sources_count == 0`):
Redwood Cabinetry, Desert Sky Solar, Cornerstone Masonry, Velvet Thread
Tailoring, Frontier Towing & Recovery, Blue Heron Landscaping, Ace Mobile
Locksmith, Granite Peak Surveying, Sierra Vista Auto Body, Evergreen Tree
Care, Liberty Sign & Awning, Crescent Moon Cafe.

Each is labeled `expected_needs_human_review = True`,
`expected_classification = "cannot_verify"`. This is **trivial by
construction** — both v1 and v2 short-circuit `sources_count == 0` to exactly
this outcome (ADR-0004, ADR-0005) — but it's still 12/18 (two-thirds) of the
ground truth set, which is intentional: it anchors both classifiers' review
rate to a floor that matches reality (12/30 = 40% of all companies have zero
provider data and *must* be reviewed), so a classifier that somehow marked
one of these "verified" would be caught immediately.

**6 rows — mock-backed companies, hand-judged by inspecting
`enrichment_responses.json` directly:**

| Company | `expected_needs_human_review` | `expected_classification` | Rationale |
|---|---|---|---|
| Cedar Ridge Plumbing LLC | False | high | All 3 sources agree on Daniel Ortega / Owner, email matches name. |
| Pioneer Landscaping Inc | False | high | All 3 sources agree on Maria Gomez / President, phone+email corroborate. |
| Harbor Light Electric | False | medium | Registry+listing agree (Sean Murphy / S. Murphy), Owner role, listing phone. |
| Greenfield Catering Group | False | medium | Registry (Angela Brooks/Owner) + enrichment email "a.brooks@..." corroborate. |
| Riverside Print & Sign | True | cannot_verify | Single weak enrichment source (confidence 41), generic "info@" email. |
| Coastal Breeze Pool Service | True | low | Registry ("Tina Alvarez") and listing ("Marcus Webb") name a different person each — conflict. |

These 6 were chosen to cover **both sides of the `needs_human_review`
boundary** (4 verified, 2 review) and **both reasons a row needs review**
(weak single source vs. an outright identity conflict) — the two failure
modes the conflict-resolution and confidence-scoring logic (ADR-0003,
ADR-0004) were specifically built to catch. The remaining 12 mock-backed
companies (of 18 total) are left unlabeled: they're available as additional
eyeball spot-checks when reading `comparison.txt`'s per-company predictions,
but are not part of the 18-row precision/recall/F1 set, keeping the ground
truth small enough to hand-verify every row against `enrichment_responses.json`.

### `evaluate_predictions` join semantics

`evaluate_predictions` iterates `GROUND_TRUTH` (not the predictions CSV) and
looks up each company by name in the predictions CSV — i.e. the 18-row
ground truth set defines `n`, and predictions for the other 12 companies are
ignored for metrics purposes (they still appear in
`v{1,2}_predictions.csv` for the full 30-company output).

## Consequences

- `comparison.txt` (TICKET-011) reports precision/recall/F1 on `n=18`, plus
  `classification_accuracy` on the same 18, for both v1 and v2.
- Because 12/18 ground truth rows are the trivial zero-source case that both
  classifiers handle identically by construction, the precision/recall
  numbers are most sensitive to the 6 hand-judged rows — by design, since
  those are the rows where v1 and v2's actual scoring logic (as opposed to
  the short-circuit) is exercised.
- If `enrichment_responses.json` or the matching/fusion logic changes such
  that any of the 6 hand-judged companies' signals change, the corresponding
  `GROUND_TRUTH` row's rationale must be re-checked — these labels are hand
  judgments tied to the *current* mock data, not derived programmatically.
