# ADR-0007: Output schema extensions beyond the minimal CLARIFICATIONS.md fields

**Status:** Accepted
**Ticket:** TICKET-011

## Context

`CLARIFICATIONS.md` and `PLAN.md` together specify a *partial* output
contract, not a full schema:

- `CLARIFICATIONS.md`: "Use **70** as the cutoff: confidence `< 70` ->
  return `contact_email_or_phone = ""` and `needs_human_review = true`."
  This names `confidence_score`, `contact_email_or_phone`, and
  `needs_human_review`, and specifies blanking for exactly one field.
- `PLAN.md` ("Provenance"): "Output includes `source_urls` mapping field ->
  provider -> URL. Zero contacts without attribution."
- `PLAN.md` ("Cannot Verify"): "Return empty contact + `needs_human_review =
  true` + reason when confidence < threshold or no corroborating data."

Neither document says what "empty contact" covers beyond
`contact_email_or_phone`, what shape `source_urls` should serialize to in a
flat CSV, or what "reason" should look like beyond "a reason". TICKET-011
has to settle on one concrete 10-column row (`output/formatter.OUTPUT_COLUMNS`)
that every row in `v1_predictions.csv` / `v2_predictions.csv` conforms to.
This ADR records the three additions and the blanking policy.

## Decision

### Three fields beyond the minimal spec

1. **`classification`** (`high` / `medium` / `low` / `cannot_verify`) — the
   4-bucket label both classifiers already produce (ADR-0004, ADR-0005).
   Carrying it through to the final CSV means `evaluation.metrics
   .evaluate_predictions` can compute ADR-0006's
   `classification_accuracy` directly from `v{1,2}_predictions.csv` without
   re-running either classifier, and a human reviewer scanning the CSV gets
   the bucket alongside the raw `confidence_score` for free.

2. **`source`** — a comma-joined list of providers that returned *any* data
   for the company (`",".join(fused.sources)`, e.g.
   `"registry,listing,enrichment"`, or `""` for the 12 zero-source
   companies). This is a coarse, human-scannable "how much did we have to
   work with" summary, independent of `source_urls`'s
   per-field detail — useful for a quick eyeball pass over the CSV without
   parsing the delimited `source_urls` string.

3. **`source_urls`** — `PLAN.md` requires this field but not its
   serialization. `FusedContact.source_urls` is already a
   `dict[str, list[str]]` (field name -> list of URLs); rather than embed
   JSON or a nested structure in a CSV cell, it's flattened to
   `field:provider:url|field:provider:url` (e.g.
   `"name:registry:mock://registry/ne/cedar-ridge-plumbing|email:enrichment:mock://enrichment/cedar-ridge-plumbing"`).
   `provider` is parsed from the URL itself (`mock://<provider>/...` ->
   `<provider>`, see `output.formatter._provider_from_url`) rather than
   stored separately, so adding a fourth mock provider later needs no schema
   change. `|`-delimited rather than JSON keeps every cell grep/sort-able in
   a plain CSV viewer.

4. **`reason`** — `PLAN.md` requires "a reason" for cannot-verify rows;
   `build_reason()` generalizes this to a fixed 5-branch taxonomy that
   applies to *every* row (not just review rows), checked in this priority
   order:
   - `sources_count == 0` -> `"No data available from any source."`
   - `has_conflict` -> `"Registry and listing disagree on contact identity."`
   - `generic_email and sources_count == 1` ->
     `"Single weak source with a generic contact email."`
   - `confidence_score < threshold` ->
     `f"Confidence {confidence_score} below threshold {threshold}."`
   - otherwise -> `f"Verified via {sources_count} agreeing source(s)."`

   A small fixed taxonomy (rather than one generic "needs review" string)
   lets a review queue be triaged by `reason` text alone — "no data" rows
   need outreach to find a source at all, "conflict" rows need a human to
   pick between two named people, "generic email" rows need a name lookup,
   and "below threshold" rows are borderline and may just need a second
   opinion.

### Blanking policy on `needs_human_review = True` rows

`CLARIFICATIONS.md` only specifies blanking `contact_email_or_phone`.
`format_output_row` blanks **all three** contact fields —
`contact_name`, `contact_role`, and `contact_email_or_phone` — whenever
`needs_human_review` is `True`, while leaving `company_name`,
`confidence_score`, `classification`, `source`, `source_urls`, and `reason`
populated.

This follows `PLAN.md`'s broader framing — "Return **empty contact** +
`needs_human_review = true` + reason" — over `CLARIFICATIONS.md`'s narrower
literal wording. Rationale: a person's name and title without a
confidently-verified way to reach them is not independently actionable, and
surfacing it anyway risks a downstream consumer treating the row as "found"
when it failed verification. Blanking the whole contact makes
`needs_human_review = True` rows unambiguous: nothing in the contact-identity
columns should be used until a human has reviewed the row.

`source_urls` and `reason` stay populated on review rows specifically
*because* of `PLAN.md`'s "Zero contacts without attribution" — even a row
that gets routed to a human needs an audit trail of what was seen and why it
wasn't enough, so the reviewer can jump straight to the source URLs instead
of re-running the pipeline. `confidence_score` and `classification` also stay
populated so a reviewer can distinguish a `cannot_verify`/`0` row (nothing to
go on) from a `low`/`45` row (some corroborating data, just below the bar) at
a glance.

Note this is consistent, not contradictory, with "zero contacts without
attribution": for the 12 companies with `sources_count == 0`, `source` and
`source_urls` are both `""` — there is genuinely nothing to attribute, so
there is nothing to blank or retain beyond the zero-data state itself.

## Consequences

- The full row schema (`output.formatter.OUTPUT_COLUMNS`) is:
  `company_name, contact_name, contact_role, contact_email_or_phone,
  confidence_score, classification, source, needs_human_review,
  source_urls, reason`.
- `tests/test_integration.py`'s two `format_output_row` cases codify this
  directly: the Cedar Ridge (verified) row has all three contact fields
  populated and `source_urls` containing `name:`/`role:`/`email:` entries;
  the Riverside Print & Sign (review) row has all three contact fields `==
  ""` while `source_urls` still contains the enrichment URL and `reason`
  mentions "generic contact email".
- If a future ticket adds a field to `FusedContact` (e.g. a fourth
  provider's contact method), it only needs an entry in
  `SignalFusionEngine.fuse`'s `source_urls` dict — `_format_source_urls`
  and the blanking logic require no changes.
- Any future change to `build_reason`'s branch order must preserve "no
  data" and "conflict" as higher priority than "below threshold", since a
  row can be simultaneously low-confidence *and* conflicted, and the more
  specific diagnosis is more useful to a reviewer.
