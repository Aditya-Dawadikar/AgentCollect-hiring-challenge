# ADR-0004: v1 rule-based classifier weight table

**Status:** Accepted
**Ticket:** TICKET-008

## Context

`RuleBasedClassifier` (v1) must turn the 13-key `signals` dict (TICKET-007)
into a `confidence_score` (0-100), a `classification` bucket
(`high`/`medium`/`low`/`cannot_verify`), and a `needs_human_review` flag
using `CONFIDENCE_THRESHOLD = 70` (`CLARIFICATIONS.md`). The scoring logic
must be **explainable** — every point added or subtracted should map to a
plain-English reason a human reviewer can read in `formatter.build_reason`
(TICKET-011).

## Decision

### Short-circuit: zero sources

If `sources_count == 0` (12 of the 30 companies — the ones absent from
`enrichment_responses.json`), `confidence_score = 0`,
`classification = "cannot_verify"`, `needs_human_review = True`,
unconditionally. There is nothing to sum: every other signal in `signals`
is `False`/`0` by construction (see TICKET-007's
`test_redwood_cabinetry_absent`), so summing them would also yield 0 — the
short-circuit just makes the "no data at all" case explicit and
un-skippable rather than relying on every weight coincidentally summing to
zero.

### Weight table

| Signal | Points | Rationale |
|---|---:|---|
| `has_registry_name` | **+35** | The single strongest signal: a named individual on the legal-ownership record. Largest weight in the table because everything else (role, email/phone matching) is *about* this name. |
| `has_enrichment_email and not generic_email` | **+20** | A named-person email address (`d.ortega@...`, not `info@...`) is a direct, dialable/emailable channel to a specific human — high value for an AP/collections workflow. |
| `has_listing_phone or has_enrichment_phone` | **+10** | Any phone number is useful, but a phone alone (no name) only gets you "call this business," not a decision-maker. |
| `name_sources_agree` | **+15** | Two independent sources (registry + listing) naming the *same* person is strong corroboration of identity — bigger than any single-source signal below it. |
| `email_matches_name` | **+10** | The enrichment email's local part matches the candidate name — corroborates that the email belongs to *this* person, not a generic mailbox someone else monitors. |
| `phone_sources_agree` | **+5** | Listing and enrichment phones matching corroborates the phone number, but phone corroboration matters less than name corroboration for reaching a *specific* decision-maker. |
| `role_is_decision_maker` | **+5** | A small bonus when the registry role isn't explicitly excluded (e.g. not "Registered Agent" — a legal-filing proxy, not someone who can authorize payment). Small because for 17/18 mock companies the only role we ever see is a genuine decision-maker title (Owner/President/Manager); this mostly only ever *subtracts* value via its absence (role unknown -> no bonus) or the Northgate HVAC "Registered Agent" case. |
| `has_conflict` | **-25** | Registry and listing naming two different people is the single biggest red flag for "we might be about to contact the wrong person." Sized to be larger than `has_registry_name + role_is_decision_maker` combined (40), so a conflicted registry-only company (Coastal Breeze Pool Service: 35+10+5-25=25) lands in `cannot_verify`, not just a notch down. |
| `generic_email and sources_count == 1` | **-10** | A lone `info@`/`office@`/etc. email with nothing else is barely better than nothing — this penalty pushes that case to 0 (`cannot_verify`) rather than leaving it at a misleadingly non-zero baseline of 0 anyway (there's no positive weight a generic single-source email earns in the first place; this penalty exists for symmetry/explainability — see "Why this penalty looks redundant" below). |

Score is clamped to `[0, 100]`.

### Bucket thresholds (from `PLAN.md` "Quality")

```python
def _classify(score):
    if score >= 80: return "high"
    if score >= 60: return "medium"
    if score >= 30: return "low"
    return "cannot_verify"

needs_human_review = score < 70  # CONFIDENCE_THRESHOLD
```

`needs_human_review` is derived purely from `confidence_score < 70`, not
from the bucket — `medium` (60-79) straddles the threshold, so e.g. a score
of 65 is `medium` *and* `needs_human_review=True`, while 75 is `medium` and
`needs_human_review=False`. This is intentional: the bucket is a coarse
human-readable label, the threshold is the actual business decision.

### Why `enrichment_provider_confidence` is NOT summed directly

`enrichment_provider_confidence` is the *enrichment provider's own*
self-reported confidence (e.g. 84, 41, 58) — it is in `signals` and in
`features.FEATURE_NAMES` (for v2 to learn from), but v1 deliberately does
not add `+ enrichment_provider_confidence * k` to its score. Two reasons:

1. **It's not our number.** `CLARIFICATIONS.md` asks for an *explainable*,
   *our-own-logic* score. Blending in an opaque third-party score would
   make `confidence_score` partly a re-export of someone else's number we
   can't justify.
2. **It's already gated.** `has_enrichment_email` and `has_enrichment_phone`
   being `True` already requires an enrichment record (and therefore a
   `provider_confidence`) to exist — so its *presence* is already counted
   via those two signals. Its *value* doesn't need to also move our score.

### Why this penalty looks redundant (and isn't)

For `generic_email and sources_count == 1` (e.g. Riverside Print & Sign,
Summit Pest Control, Hometown Hardware Co, Anchor Marine Supply): without
the `-10`, these companies would score `0` anyway (no other weight applies
to a single generic-email-only record), landing in `cannot_verify` either
way. The `-10` is kept for two reasons:

1. **Explainability**: `formatter.build_reason` (TICKET-011) can say "single
   generic mailbox, no name" as an explicit negative reason rather than
   "score is 0 because nothing matched" (a non-explanation).
2. **Future-proofing against new positive signals**: if a future signal adds
   e.g. `+5` for "enrichment record exists at all" (independent of
   genericness), the `-10` keeps a generic-only single source from
   crossing into `low` on the strength of that alone. Since this is a
   from-scratch design where weights may be revisited, an explicit penalty
   is more robust than relying on "no positive weights apply" by omission.

## Hand-computed TDD cases

| Company | Breakdown | Score | Bucket | `needs_human_review` |
|---|---|---:|---|---|
| Cedar Ridge Plumbing LLC | 35 (registry) + 20 (email, non-generic) + 10 (phone) + 15 (name agree) + 10 (email matches name) + 5 (decision maker) | 95 | high | False |
| Pioneer Landscaping Inc | 35 + 20 + 10 + 15 + 10 + 5 (phone agree) + 5 (decision maker) | 100 | high | False |
| Riverside Print & Sign | 0, then -10 (generic email, single source) -> clamped | 0 | cannot_verify | True |
| Lakeside Auto Glass | 20 (email, non-generic) + 10 (phone) + 10 (email matches name) | 40 | low | True |
| Coastal Breeze Pool Service | 35 (registry) + 10 (phone) + 5 (decision maker) - 25 (conflict) | 25 | cannot_verify | True |
| Redwood Cabinetry | short-circuit (`sources_count == 0`) | 0 | cannot_verify | True |

Full per-company breakdown for all 18 mock companies + 12 zero-data rows is
exercised by `tests/test_classifiers.py::test_score_runs_for_every_company_without_error`.

## Consequences

- Ironclad Welding Shop (the Robert/Bob Kowalski nickname-conflict company,
  ADR-0002/ADR-0003) scores `35 + 20 + 10 + 5 (phone agree) + 5 (decision
  maker) - 25 (conflict) = 50` -> `low`, `needs_human_review=True`. This is
  the desired outcome: strong evidence (3/3 sources, phone corroboration,
  a clear Owner role) pulled down by the unresolved identity question.
- Every weight and penalty is a single `if` on a named `signals` key, so
  `formatter.build_reason` (TICKET-011) can re-derive "why this score" by
  re-checking the same conditions — no hidden state.
- v2 (TICKET-009) reuses `features.FEATURE_NAMES`/`signals_to_vector` as its
  input vector, so the two classifiers are comparable apples-to-apples in
  TICKET-010's evaluation even though v2 doesn't use these exact weights.
