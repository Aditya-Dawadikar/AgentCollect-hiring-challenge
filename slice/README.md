# Contact Finder — Stage B slice

A minimal pipeline that turns `challenge/data/companies.csv` + the mocked
providers in `challenge/mocks/enrichment_responses.json` into per-company
contact rows, following the design in [`../PLAN.md`](../PLAN.md) and the
answers in [`../challenge/CLARIFICATIONS.md`](../challenge/CLARIFICATIONS.md).

## Run it

Requires Python 3.10+.

```bash
cd slice
pip install -r requirements.txt   # only dependency: pytest (for the test suite)
python contact_finder.py          # writes output.json and output.csv, prints a summary
```

The pipeline itself (`contact_finder.py`) is stdlib-only; `requirements.txt`
is needed only to run the tests.

## Testing

```bash
cd slice
python -m pytest -v
```

24 tests covering: name-matching/normalization helpers, identity resolution
(registry/listing, conflicts, Registered Agent), contact resolution
(enrichment vs. listing-phone fallback, conflict isolation), agreement-bonus
scoring, end-to-end scoring against real mock fixtures (high-confidence
agreement, weak single-source, identity conflict, Registered-Agent-only,
company absent from mocks), and threshold-gate invariants (every row below
70 is blanked + flagged, every emitted contact has provenance) across the
full 30-row dataset.

## What it does

For each of the 30 companies:

1. **Resolve identity** (`contact_name` / `contact_role`) from `registry`
   (authoritative) or `listing` (fallback). If both are present but name
   *different* people, that's an **identity conflict** — the registry
   identity is reported (higher authority) but flagged.
2. **Resolve contact method** (`contact_email_or_phone`) from `enrichment`
   (preferred — direct email/phone), falling back to a `listing` phone if
   no enrichment exists. A conflicting identity's listing phone is never
   borrowed as the output contact.
3. **Score** 0-100, additively:
   - Identity base: registry name+role `+40` (`+15` if role is
     `Registered Agent` — usually a third-party filer, not staff),
     listing-only name `+20`, nothing `+0`.
   - Contact base: enrichment `+30 × provider_confidence/100`, listing
     phone fallback `+10`, nothing `+0`.
   - Agreement bonus: `+15` for one independent corroboration (registry/listing
     name match, enrichment/listing phone match, or enrichment email
     containing an identity name token), `+20` for two or more.
   - Conflict penalty: `-20` if identity is in conflict.
4. **Threshold gate** (70, per `CLARIFICATIONS.md`): below threshold →
   `contact_email_or_phone = ""`, `needs_human_review = true`. A row with
   no contact method at all is also flagged regardless of score.
5. **Output**: `output.json` (full detail incl. `provenance` source URLs
   per field, `review_reason`, `notes`) and `output.csv` (flat columns).

Result on the full dataset: **7 confident, 23 `needs_human_review`** (12 of
those have zero provider data — genuinely "cannot verify").

## Adaptations from PLAN.md (now that real mock shapes are known)

- **`enrichment` has no `name` field.** PLAN.md assumed name-based
  cross-referencing everywhere; in practice `enrichment` only ever returns
  `email`/`phone`. Corroboration between enrichment and an identity is
  instead detected by checking whether the email's local part contains a
  name token (`d.ortega@...` ↔ "Daniel Ortega").
- **`Registered Agent` role** (Northgate HVAC) wasn't anticipated in the
  plan — it's a real pattern in business registries (a third-party filing
  service, not company staff), so it gets a reduced identity base score
  rather than the full registry weight.
- **Identity conflicts** (Coastal Breeze: registry says "Tina Alvarez /
  Manager", listing says "Marcus Webb") are resolved per clarifying
  question 1's default: registry (higher authority) is reported, the
  listing's contact is not borrowed, `review_reason = identity_conflict`,
  and the conflicting name/source is recorded in `notes`.
- **`review_reason`** was added as an additive field per clarifying
  question 3's default (`no_sources`, `identity_conflict`,
  `no_contact_method`, `single_weak_source`, `low_confidence`) — it costs
  nothing extra and turns the `needs_human_review` pile into a sortable
  triage queue.
- **Scoring weights are inline module constants**, not a per-source config
  table, per clarifying question 2's default — three sources didn't justify
  the extra abstraction.
- **State/jurisdiction parsing from `mailing_address`** (mentioned in
  PLAN.md's loader) was dropped — the mocks key purely on `company_name`,
  so there was nothing for it to feed. `mailing_address` is still passed
  through to the output as a courtesy for human reviewers.
- **CLARIFICATIONS' role-priority order** (AP/accounts-payable → owner/founder
  → CFO → office manager) doesn't change source selection for *this*
  dataset — every found identity is "Owner"/"President" (≈ owner/founder,
  priority #2) or "Registered Agent" (not on the list, downweighted as
  above), and the one conflict is resolved by source authority since
  neither candidate role maps to the priority list. `contact_role` is
  passed through unmapped so a downstream step could apply the full
  ordering if AP/CFO-specific roles ever appear.

## Output schema

| Field | Notes |
|---|---|
| `contact_name`, `contact_role` | "" if nothing found; populated even on low-confidence rows so a reviewer has a lead |
| `contact_email_or_phone` | blanked whenever `needs_human_review` is true |
| `confidence_score` | 0-100 |
| `source` | provider names that returned data for this company |
| `needs_human_review` | `confidence_score < 70` or no contact method |
| `review_reason` | additive — see above |
| `notes` | additive — human-readable explanation for conflicts / Registered Agent caveat |
| `provenance` | additive — `source_url`(s) backing each field |
